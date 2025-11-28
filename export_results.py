#!/usr/bin/env python3
"""
Export Query Results to CSV
============================
Executes all queries from queries.sql and saves results to results/ directory.
"""

import sqlite3
import pandas as pd
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

# Configuration
DB_PATH = "macroalpha.db"
OUTPUT_DIR = Path("results")

# Create output directory
OUTPUT_DIR.mkdir(exist_ok=True)

def get_connection():
    """Get database connection with timeout."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn

# ============================================================================
# Define all queries to export
# ============================================================================

QUERIES = {
    # USE CASE 1: Market Concentration
    "uc1_q1_top10_concentration": """
        WITH yearly_top10 AS (
            SELECT 
                strftime('%Y', im.as_of_date) AS year,
                im.company_id,
                c.company_name,
                im.weight,
                ROW_NUMBER() OVER (PARTITION BY strftime('%Y', im.as_of_date) 
                                   ORDER BY im.weight DESC) AS rank
            FROM index_membership im
            JOIN companies c ON im.company_id = c.company_id
            WHERE im.index_id = 'UKX' AND im.weight IS NOT NULL
        )
        SELECT year, SUM(weight) AS top10_weight_pct, COUNT(*) AS top10_count
        FROM yearly_top10
        WHERE rank <= 10
        GROUP BY year
        ORDER BY year
    """,
    
    "uc1_q2_hhi_concentration": """
        WITH hhi_calc AS (
            SELECT 
                strftime('%Y', im.as_of_date) AS year,
                SUM(im.weight * im.weight) AS hhi,
                COUNT(*) AS num_members,
                AVG(im.weight) AS avg_weight,
                MAX(im.weight) AS max_weight
            FROM index_membership im
            WHERE im.index_id = 'UKX' AND im.weight IS NOT NULL
            GROUP BY strftime('%Y', im.as_of_date)
        )
        SELECT 
            year,
            ROUND(hhi, 2) AS hhi_index,
            num_members,
            ROUND(avg_weight, 2) AS avg_weight_pct,
            ROUND(max_weight, 2) AS largest_weight_pct,
            ROUND(10000.0 / hhi, 1) AS effective_positions,
            CASE 
                WHEN hhi < 1500 THEN 'Unconcentrated'
                WHEN hhi < 2500 THEN 'Moderately Concentrated'
                ELSE 'Highly Concentrated'
            END AS concentration_level
        FROM hhi_calc
        ORDER BY year
    """,
    
    # USE CASE 2: Corporate Leverage
    "uc2_q1_debt_to_revenue_distribution": """
        WITH de_ratios AS (
            SELECT 
                strftime('%Y', f.period_end_date) AS year,
                f.company_id,
                c.company_name,
                c.gics_sector_name,
                CASE 
                    WHEN f.revenue > 0 THEN f.total_debt / f.revenue 
                    ELSE NULL 
                END AS debt_to_revenue_ratio
            FROM financials f
            JOIN companies c ON f.company_id = c.company_id
            WHERE f.period_type = 'ANNUAL'
              AND c.gics_sector_name != 'Financials'
              AND f.total_debt IS NOT NULL 
              AND f.revenue > 0
        )
        SELECT 
            year,
            COUNT(*) AS company_count,
            ROUND(AVG(debt_to_revenue_ratio), 3) AS mean_debt_to_revenue,
            ROUND(MIN(debt_to_revenue_ratio), 3) AS min_ratio,
            ROUND(MAX(debt_to_revenue_ratio), 3) AS max_ratio
        FROM de_ratios
        WHERE debt_to_revenue_ratio IS NOT NULL
        GROUP BY year
        ORDER BY year
    """,
    
    "uc2_q2_deleveraging_cycles": """
        WITH de_ratios AS (
            SELECT 
                f.company_id,
                c.company_name,
                c.gics_sector_name,
                strftime('%Y', f.period_end_date) AS year,
                CASE 
                    WHEN f.revenue > 0 THEN f.total_debt / f.revenue 
                    ELSE NULL 
                END AS de_ratio
            FROM financials f
            JOIN companies c ON f.company_id = c.company_id
            WHERE f.period_type = 'ANNUAL'
              AND c.gics_sector_name != 'Financials'
              AND f.total_debt IS NOT NULL
              AND f.revenue > 0
        ),
        deleveraging AS (
            SELECT 
                company_id,
                company_name,
                gics_sector_name,
                year,
                de_ratio,
                LAG(de_ratio, 1) OVER (PARTITION BY company_id ORDER BY year) AS de_prev1,
                LAG(de_ratio, 2) OVER (PARTITION BY company_id ORDER BY year) AS de_prev2
            FROM de_ratios
        )
        SELECT 
            year,
            COUNT(*) AS deleveraging_companies,
            gics_sector_name,
            COUNT(*) AS count_by_sector
        FROM deleveraging
        WHERE de_ratio < de_prev1 AND de_prev1 < de_prev2
        GROUP BY year, gics_sector_name
        ORDER BY year, count_by_sector DESC
    """,
    
    "uc2_q3_icr_rate_sensitivity": """
        WITH icr_data AS (
            SELECT 
                f.company_id,
                c.company_name,
                c.country_id,
                c.gics_sector_name,
                CAST(strftime('%Y', f.period_end_date) AS INTEGER) AS year,
                CASE 
                    WHEN f.interest_expense > 0 THEN f.ebitda / f.interest_expense
                    ELSE NULL
                END AS interest_coverage_ratio
            FROM financials f
            JOIN companies c ON f.company_id = c.company_id
            WHERE f.period_type = 'ANNUAL'
              AND c.gics_sector_name != 'Financials'
              AND f.ebitda IS NOT NULL
              AND f.interest_expense > 0
        ),
        policy_rates AS (
            SELECT 
                CAST(strftime('%Y', rate_date) AS INTEGER) AS year,
                country_id,
                AVG(rate_value) AS avg_policy_rate
            FROM interest_rates
            WHERE rate_type = 'POLICY_RATE'
            GROUP BY strftime('%Y', rate_date), country_id
        ),
        combined AS (
            SELECT 
                i.company_id,
                i.company_name,
                i.gics_sector_name,
                i.country_id,
                i.year,
                i.interest_coverage_ratio,
                p.avg_policy_rate
            FROM icr_data i
            JOIN policy_rates p ON i.year = p.year AND i.country_id = p.country_id
        ),
        rolling_correlation AS (
            SELECT 
                c1.company_id,
                c1.company_name,
                c1.gics_sector_name,
                c1.country_id,
                c1.year,
                COUNT(c2.year) AS window_size,
                AVG(c2.interest_coverage_ratio) AS avg_icr,
                AVG(c2.avg_policy_rate) AS avg_rate,
                AVG(c2.interest_coverage_ratio * c2.avg_policy_rate) AS avg_icr_rate_product,
                AVG(c2.interest_coverage_ratio * c2.interest_coverage_ratio) AS avg_icr_squared,
                AVG(c2.avg_policy_rate * c2.avg_policy_rate) AS avg_rate_squared
            FROM combined c1
            JOIN combined c2 ON c1.company_id = c2.company_id 
                             AND c2.year BETWEEN (c1.year - 4) AND c1.year
            GROUP BY c1.company_id, c1.company_name, c1.gics_sector_name, c1.country_id, c1.year
            HAVING COUNT(c2.year) = 5
        ),
        correlation_calc AS (
            SELECT 
                company_id,
                company_name,
                gics_sector_name,
                country_id,
                year,
                avg_icr,
                avg_rate,
                CASE 
                    WHEN (avg_icr_squared - avg_icr * avg_icr) > 0 
                     AND (avg_rate_squared - avg_rate * avg_rate) > 0 
                    THEN (avg_icr_rate_product - avg_icr * avg_rate) / 
                         (SQRT(avg_icr_squared - avg_icr * avg_icr) * 
                          SQRT(avg_rate_squared - avg_rate * avg_rate))
                    ELSE NULL
                END AS rolling_correlation
            FROM rolling_correlation
        ),
        latest_correlation AS (
            SELECT 
                c.company_id,
                c.company_name,
                c.gics_sector_name,
                c.country_id,
                MAX(c.year) AS latest_year,
                COUNT(DISTINCT cm.year) AS total_years_data
            FROM correlation_calc c
            JOIN combined cm ON c.company_id = cm.company_id
            GROUP BY c.company_id, c.company_name, c.gics_sector_name, c.country_id
            HAVING COUNT(DISTINCT cm.year) >= 10
        )
        SELECT 
            lc.company_name,
            lc.gics_sector_name,
            lc.country_id,
            lc.total_years_data,
            ROUND(cc.avg_icr, 2) AS avg_icr_recent_5y,
            ROUND(cc.rolling_correlation, 4) AS correlation_with_policy_rate,
            CASE 
                WHEN cc.rolling_correlation < -0.3 THEN 'Highly Rate-Sensitive'
                WHEN cc.rolling_correlation < 0 THEN 'Moderately Rate-Sensitive'
                WHEN cc.rolling_correlation < 0.3 THEN 'Rate-Insulated'
                ELSE 'Positively Correlated'
            END AS rate_sensitivity_classification
        FROM latest_correlation lc
        JOIN correlation_calc cc ON lc.company_id = cc.company_id AND lc.latest_year = cc.year
        WHERE cc.rolling_correlation IS NOT NULL
        ORDER BY cc.rolling_correlation
        LIMIT 100
    """,
    
    # USE CASE 3: Stress Test
    "uc3_q1_zombie_companies": """
        WITH icr_data AS (
            SELECT 
                f.company_id,
                c.company_name,
                c.gics_sector_name,
                c.country_id,
                strftime('%Y', f.period_end_date) AS year,
                CASE 
                    WHEN f.interest_expense > 0 THEN f.ebitda / f.interest_expense
                    ELSE NULL
                END AS icr
            FROM financials f
            JOIN companies c ON f.company_id = c.company_id
            WHERE f.period_type = 'ANNUAL'
              AND c.gics_sector_name != 'Financials'
              AND f.ebitda IS NOT NULL
              AND f.interest_expense > 0
        )
        SELECT 
            year,
            COUNT(*) AS zombie_count,
            gics_sector_name
        FROM icr_data
        WHERE icr < 1.5
        GROUP BY year, gics_sector_name
        ORDER BY year, zombie_count DESC
    """,
    
    # USE CASE 4: Macro Lead-Lag
    "uc4_q2_revenue_volatility": """
        WITH revenue_growth AS (
            SELECT 
                f.company_id,
                c.company_name,
                c.gics_sector_name,
                CAST(strftime('%Y', f.period_end_date) AS INTEGER) AS year,
                f.revenue,
                (f.revenue - LAG(f.revenue, 1) OVER (PARTITION BY f.company_id ORDER BY f.period_end_date)) 
                    / NULLIF(LAG(f.revenue, 1) OVER (PARTITION BY f.company_id ORDER BY f.period_end_date), 0) * 100 AS rev_growth
            FROM financials f
            JOIN companies c ON f.company_id = c.company_id
            WHERE f.period_type = 'ANNUAL'
              AND f.revenue IS NOT NULL
        ),
        rolling_volatility AS (
            SELECT 
                rg1.company_id,
                rg1.company_name,
                rg1.gics_sector_name,
                rg1.year,
                COUNT(rg2.year) AS window_size,
                AVG(rg2.rev_growth) AS avg_growth_10y,
                SQRT(AVG(rg2.rev_growth * rg2.rev_growth) - AVG(rg2.rev_growth) * AVG(rg2.rev_growth)) AS rolling_volatility
            FROM revenue_growth rg1
            JOIN revenue_growth rg2 ON rg1.company_id = rg2.company_id 
                                     AND rg2.year BETWEEN (rg1.year - 9) AND rg1.year
                                     AND rg2.rev_growth IS NOT NULL
            WHERE rg1.rev_growth IS NOT NULL
            GROUP BY rg1.company_id, rg1.company_name, rg1.gics_sector_name, rg1.year
            HAVING COUNT(rg2.year) = 10
        ),
        latest_volatility AS (
            SELECT 
                rv.company_id,
                rv.company_name,
                rv.gics_sector_name,
                MAX(rv.year) AS latest_year,
                COUNT(DISTINCT rg.year) AS total_years_data
            FROM rolling_volatility rv
            JOIN revenue_growth rg ON rv.company_id = rg.company_id
            GROUP BY rv.company_id, rv.company_name, rv.gics_sector_name
            HAVING COUNT(DISTINCT rg.year) >= 10
        ),
        company_volatility AS (
            SELECT 
                lv.company_id,
                lv.company_name,
                lv.gics_sector_name,
                lv.total_years_data,
                rv.rolling_volatility AS volatility,
                rv.avg_growth_10y AS avg_growth
            FROM latest_volatility lv
            JOIN rolling_volatility rv ON lv.company_id = rv.company_id AND lv.latest_year = rv.year
            WHERE rv.rolling_volatility IS NOT NULL
        ),
        quartiles AS (
            SELECT 
                *,
                NTILE(4) OVER (ORDER BY volatility) AS volatility_quartile
            FROM company_volatility
        )
        SELECT 
            volatility_quartile,
            CASE volatility_quartile
                WHEN 1 THEN 'Low Volatility (Defensive)'
                WHEN 2 THEN 'Below Average'
                WHEN 3 THEN 'Above Average'
                WHEN 4 THEN 'High Volatility (Cyclical)'
            END AS classification,
            COUNT(*) AS company_count,
            ROUND(AVG(volatility), 2) AS avg_volatility,
            ROUND(AVG(avg_growth), 2) AS avg_growth_rate
        FROM quartiles
        GROUP BY volatility_quartile
        ORDER BY volatility_quartile
    """,
    
    # USE CASE 5: Inflation & Rate Sensitivity
    "uc5_q1_sector_inflation_performance": """
        WITH monthly_cpi AS (
            SELECT 
                country_id,
                strftime('%Y-%m', indicator_date) AS year_month,
                indicator_value AS cpi_value,
                (indicator_value - LAG(indicator_value, 12) OVER (PARTITION BY country_id ORDER BY indicator_date)) 
                    / NULLIF(LAG(indicator_value, 12) OVER (PARTITION BY country_id ORDER BY indicator_date), 0) * 100 AS cpi_yoy
            FROM macro_indicators
            WHERE indicator_category = 'CPI'
              AND indicator_name LIKE '%CPI%'
        ),
        inflation_regime AS (
            SELECT 
                year_month,
                country_id,
                cpi_yoy,
                CASE 
                    WHEN cpi_yoy > 3 THEN 'High Inflation'
                    ELSE 'Low Inflation'
                END AS regime
            FROM monthly_cpi
            WHERE cpi_yoy IS NOT NULL
        )
        SELECT 
            regime,
            COUNT(*) AS months,
            ROUND(AVG(cpi_yoy), 2) AS avg_cpi_yoy
        FROM inflation_regime
        GROUP BY regime
        ORDER BY regime
    """,
}

# ============================================================================
# Export Functions
# ============================================================================

def export_query(query_name, sql_query, conn):
    """Execute query and save to CSV."""
    print(f"   Executing: {query_name}...")
    try:
        df = pd.read_sql_query(sql_query, conn)
        output_file = OUTPUT_DIR / f"{query_name}.csv"
        df.to_csv(output_file, index=False)
        print(f"   ✓ Saved: {output_file} ({len(df)} rows)")
        return True
    except Exception as e:
        print(f"   ✗ Error: {str(e)[:80]}")
        return False

def main():
    """Main export function."""
    print("=" * 70)
    print("📊 Exporting Query Results to CSV")
    print("=" * 70)
    
    conn = get_connection()
    
    success_count = 0
    total_count = len(QUERIES)
    
    print(f"\n🔍 Exporting {total_count} queries to {OUTPUT_DIR}/\n")
    
    for query_name, sql_query in QUERIES.items():
        if export_query(query_name, sql_query, conn):
            success_count += 1
        print()
    
    conn.close()
    
    # Summary
    print("=" * 70)
    print("📈 Export Summary")
    print("=" * 70)
    print(f"   Total queries: {total_count}")
    print(f"   Successful: {success_count}")
    print(f"   Failed: {total_count - success_count}")
    print(f"   Output directory: {OUTPUT_DIR.absolute()}")
    
    if success_count == total_count:
        print("\n✅ All queries exported successfully!")
    else:
        print(f"\n⚠️  {total_count - success_count} queries failed to export")
    
    print("=" * 70)

if __name__ == "__main__":
    main()
