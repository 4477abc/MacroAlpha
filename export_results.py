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

    "uc1_q3_index_churn": """
        WITH membership_by_year AS (
            SELECT
                company_id,
                strftime('%Y', as_of_date) AS year,
                1 AS is_member
            FROM index_membership
            WHERE index_id = 'UKX'
        ),
        membership_changes AS (
            SELECT
                m1.company_id,
                m1.year,
                m1.is_member AS current_member,
                COALESCE(m2.is_member, 0) AS prev_year_member,
                CASE
                    WHEN m2.is_member IS NULL AND m1.is_member = 1 THEN 'ENTRY'
                    WHEN m1.is_member = 1 AND m2.is_member = 1 THEN 'CONTINUING'
                    ELSE 'OTHER'
                END AS status
            FROM membership_by_year m1
            LEFT JOIN membership_by_year m2
                ON m1.company_id = m2.company_id
                AND CAST(m1.year AS INTEGER) = CAST(m2.year AS INTEGER) + 1
        ),
        exits AS (
            SELECT
                m2.company_id,
                m2.year AS exit_year,
                'EXIT' AS status
            FROM membership_by_year m2
            LEFT JOIN membership_by_year m1
                ON m2.company_id = m1.company_id
                AND CAST(m2.year AS INTEGER) = CAST(m1.year AS INTEGER) - 1
            WHERE m1.company_id IS NULL
              AND m2.year < '2024'
        ),
        all_changes AS (
            SELECT company_id, year, status FROM membership_changes WHERE status = 'ENTRY'
            UNION ALL
            SELECT company_id, exit_year AS year, status FROM exits
        )
        SELECT
            ac.year,
            ac.status,
            COUNT(*) AS company_count,
            GROUP_CONCAT(c.company_name, ', ') AS companies
        FROM all_changes ac
        JOIN companies c ON ac.company_id = c.company_id
        GROUP BY ac.year, ac.status
        ORDER BY ac.year, ac.status
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

    "uc3_q2_rate_shock": """
        WITH current_financials AS (
            SELECT
                f.company_id,
                c.company_name,
                c.country_id,
                c.gics_sector_name,
                strftime('%Y', f.period_end_date) AS year,
                f.ebitda,
                f.interest_expense,
                f.total_debt,
                CASE
                    WHEN f.interest_expense > 0 THEN f.ebitda / f.interest_expense
                    ELSE NULL
                END AS current_icr
            FROM financials f
            JOIN companies c ON f.company_id = c.company_id
            WHERE f.period_type = 'ANNUAL'
              AND c.gics_sector_name != 'Financials'
              AND f.ebitda IS NOT NULL
              AND f.interest_expense IS NOT NULL
              AND f.interest_expense > 0
              AND f.total_debt IS NOT NULL
              AND strftime('%Y', f.period_end_date) = '2024'
        ),
        stress_test AS (
            SELECT
                company_id,
                company_name,
                country_id,
                gics_sector_name,
                ebitda,
                interest_expense AS current_interest,
                total_debt,
                current_icr,
                interest_expense + (total_debt * 0.5 * 0.02) AS shocked_interest,
                ebitda / (interest_expense + (total_debt * 0.5 * 0.02)) AS shocked_icr
            FROM current_financials
            WHERE current_icr IS NOT NULL
        )
        SELECT
            country_id,
            COUNT(*) AS total_companies,
            SUM(CASE WHEN current_icr >= 2.0 AND shocked_icr < 1.5 THEN 1 ELSE 0 END) AS healthy_to_atrisk,
            SUM(CASE WHEN current_icr >= 1.5 AND shocked_icr < 1.5 THEN 1 ELSE 0 END) AS newly_distressed,
            ROUND(AVG(current_icr), 2) AS avg_current_icr,
            ROUND(AVG(shocked_icr), 2) AS avg_shocked_icr,
            ROUND(AVG(current_icr - shocked_icr), 2) AS avg_icr_decline
        FROM stress_test
        GROUP BY country_id
        ORDER BY newly_distressed DESC
    """,

    "uc3_q3_geographic_risk": """
        WITH company_risk AS (
            SELECT
                f.company_id,
                c.company_name,
                c.country_id,
                strftime('%Y', f.period_end_date) AS year,
                f.ebitda,
                f.interest_expense,
                f.total_debt,
                CASE
                    WHEN f.interest_expense > 0 THEN f.ebitda / f.interest_expense
                    ELSE NULL
                END AS icr,
                CASE
                    WHEN f.interest_expense > 0 AND f.ebitda / f.interest_expense < 1.5 THEN 1
                    ELSE 0
                END AS is_zombie
            FROM financials f
            JOIN companies c ON f.company_id = c.company_id
            WHERE f.period_type = 'ANNUAL'
              AND c.gics_sector_name != 'Financials'
              AND f.ebitda IS NOT NULL
              AND f.interest_expense IS NOT NULL
              AND f.interest_expense > 0
              AND strftime('%Y', f.period_end_date) = '2024'
        ),
        country_gdp AS (
            SELECT
                country_id,
                AVG(indicator_value) AS nominal_gdp_bn
            FROM macro_indicators
            WHERE indicator_name LIKE '%Nominal GDP%bn%'
              AND strftime('%Y', indicator_date) = '2024'
            GROUP BY country_id
        )
        SELECT
            cr.country_id,
            COUNT(*) AS total_companies,
            SUM(cr.is_zombie) AS zombie_count,
            ROUND(SUM(cr.is_zombie) * 100.0 / COUNT(*), 1) AS zombie_pct,
            ROUND(SUM(CASE WHEN cr.is_zombie = 1 THEN cr.total_debt ELSE 0 END) / 1000000, 2) AS zombie_debt_bn,
            ROUND(g.nominal_gdp_bn, 0) AS country_gdp_bn,
            ROUND(SUM(CASE WHEN cr.is_zombie = 1 THEN cr.total_debt ELSE 0 END) / 1000000 /
                  NULLIF(g.nominal_gdp_bn, 0) * 100, 2) AS zombie_debt_pct_gdp
        FROM company_risk cr
        LEFT JOIN country_gdp g ON cr.country_id = g.country_id
        GROUP BY cr.country_id, g.nominal_gdp_bn
        ORDER BY zombie_pct DESC
    """,

    # USE CASE 4: Macro Lead-Lag
    "uc4_q1_housing_starts": """
        WITH housing_quarterly AS (
            SELECT
                country_id,
                strftime('%Y', indicator_date) AS year,
                CASE
                    WHEN CAST(strftime('%m', indicator_date) AS INTEGER) BETWEEN 1 AND 3 THEN 'Q1'
                    WHEN CAST(strftime('%m', indicator_date) AS INTEGER) BETWEEN 4 AND 6 THEN 'Q2'
                    WHEN CAST(strftime('%m', indicator_date) AS INTEGER) BETWEEN 7 AND 9 THEN 'Q3'
                    ELSE 'Q4'
                END AS quarter,
                AVG(indicator_value) AS housing_starts
            FROM macro_indicators
            WHERE indicator_name LIKE '%Housing Start%'
            GROUP BY country_id, year, quarter
        ),
        housing_lagged AS (
            SELECT
                country_id,
                year || '-' || quarter AS year_quarter,
                housing_starts,
                LAG(housing_starts, 2) OVER (PARTITION BY country_id ORDER BY year, quarter) AS housing_lag_2q
            FROM housing_quarterly
        ),
        company_revenue AS (
            SELECT
                f.company_id,
                c.company_name,
                c.country_id,
                c.gics_sector_name,
                strftime('%Y', f.period_end_date) AS year,
                CASE
                    WHEN CAST(strftime('%m', f.period_end_date) AS INTEGER) BETWEEN 1 AND 3 THEN 'Q1'
                    WHEN CAST(strftime('%m', f.period_end_date) AS INTEGER) BETWEEN 4 AND 6 THEN 'Q2'
                    WHEN CAST(strftime('%m', f.period_end_date) AS INTEGER) BETWEEN 7 AND 9 THEN 'Q3'
                    ELSE 'Q4'
                END AS quarter,
                f.revenue,
                (f.revenue - LAG(f.revenue, 1) OVER (PARTITION BY f.company_id ORDER BY f.period_end_date))
                    / NULLIF(LAG(f.revenue, 1) OVER (PARTITION BY f.company_id ORDER BY f.period_end_date), 0) * 100 AS revenue_growth
            FROM financials f
            JOIN companies c ON f.company_id = c.company_id
            WHERE f.period_type = 'QUARTERLY'
              AND f.revenue IS NOT NULL
              AND c.gics_sector_name IN ('Consumer Discretionary', 'Materials', 'Industrials')
        )
        SELECT
            cr.gics_sector_name,
            cr.country_id,
            COUNT(*) AS observations,
            ROUND(AVG(cr.revenue_growth), 2) AS avg_revenue_growth_pct,
            ROUND(AVG(h.housing_lag_2q), 2) AS avg_housing_lag_2q
        FROM company_revenue cr
        LEFT JOIN housing_lagged h ON cr.country_id = h.country_id AND cr.year || '-' || cr.quarter = h.year_quarter
        WHERE cr.revenue_growth IS NOT NULL
          AND h.housing_lag_2q IS NOT NULL
        GROUP BY cr.gics_sector_name, cr.country_id
        ORDER BY cr.gics_sector_name, cr.country_id
    """,

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

    "uc4_q3_downturn_resilience": """
        WITH gdp_contraction AS (
            SELECT
                country_id,
                strftime('%Y', indicator_date) AS year,
                CASE
                    WHEN CAST(strftime('%m', indicator_date) AS INTEGER) BETWEEN 1 AND 3 THEN 'Q1'
                    WHEN CAST(strftime('%m', indicator_date) AS INTEGER) BETWEEN 4 AND 6 THEN 'Q2'
                    WHEN CAST(strftime('%m', indicator_date) AS INTEGER) BETWEEN 7 AND 9 THEN 'Q3'
                    ELSE 'Q4'
                END AS quarter,
                AVG(indicator_value) AS gdp_growth
            FROM macro_indicators
            WHERE indicator_name LIKE '%Real GDP%yoy%'
            GROUP BY country_id, year, quarter
            HAVING AVG(indicator_value) < 0
        ),
        company_performance AS (
            SELECT
                f.company_id,
                c.company_name,
                c.country_id,
                c.gics_sector_name,
                strftime('%Y', f.period_end_date) AS year,
                CASE
                    WHEN CAST(strftime('%m', f.period_end_date) AS INTEGER) BETWEEN 1 AND 3 THEN 'Q1'
                    WHEN CAST(strftime('%m', f.period_end_date) AS INTEGER) BETWEEN 4 AND 6 THEN 'Q2'
                    WHEN CAST(strftime('%m', f.period_end_date) AS INTEGER) BETWEEN 7 AND 9 THEN 'Q3'
                    ELSE 'Q4'
                END AS quarter,
                f.revenue,
                f.free_cash_flow,
                (f.revenue - LAG(f.revenue, 1) OVER (PARTITION BY f.company_id ORDER BY f.period_end_date))
                    / NULLIF(LAG(f.revenue, 1) OVER (PARTITION BY f.company_id ORDER BY f.period_end_date), 0) * 100 AS rev_growth
            FROM financials f
            JOIN companies c ON f.company_id = c.company_id
            WHERE f.period_type = 'QUARTERLY'
              AND c.gics_sector_name != 'Financials'
              AND f.revenue IS NOT NULL
              AND f.free_cash_flow IS NOT NULL
        ),
        resilient_companies AS (
            SELECT
                cp.country_id,
                cp.year,
                cp.quarter,
                cp.gics_sector_name,
                cp.company_name,
                cp.rev_growth,
                cp.free_cash_flow,
                gc.gdp_growth,
                CASE
                    WHEN cp.rev_growth < 0 AND cp.free_cash_flow > 0 THEN 1
                    ELSE 0
                END AS is_resilient
            FROM company_performance cp
            JOIN gdp_contraction gc ON cp.country_id = gc.country_id AND cp.year = gc.year AND cp.quarter = gc.quarter
            WHERE cp.rev_growth IS NOT NULL
        )
        SELECT
            country_id,
            year || '-' || quarter AS year_quarter,
            ROUND(gdp_growth, 2) AS gdp_growth_pct,
            COUNT(*) AS total_companies,
            SUM(is_resilient) AS resilient_companies,
            ROUND(SUM(is_resilient) * 100.0 / COUNT(*), 1) AS resilience_rate_pct
        FROM resilient_companies
        GROUP BY country_id, year, quarter, gdp_growth
        ORDER BY year, quarter, country_id
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

    "uc5_q2_sector_cpi_lag": """
        WITH monthly_data AS (
            SELECT
                strftime('%Y-%m', p.price_date) AS year_month,
                c.gics_sector_name,
                AVG(p.total_return) * 4.33 AS monthly_return
            FROM prices_weekly p
            JOIN companies c ON p.company_id = c.company_id
            WHERE c.gics_sector_name IS NOT NULL
              AND c.country_id = 'US'
            GROUP BY strftime('%Y-%m', p.price_date), c.gics_sector_name
        ),
        cpi_changes AS (
            SELECT
                strftime('%Y-%m', indicator_date) AS year_month,
                AVG(indicator_value) AS cpi_yoy,
                AVG(indicator_value) - LAG(AVG(indicator_value), 1) OVER (ORDER BY indicator_date) AS cpi_change
            FROM macro_indicators
            WHERE indicator_name LIKE '%CPI%yoy%'
              AND country_id = 'US'
            GROUP BY strftime('%Y-%m', indicator_date)
        ),
        sector_cpi_combined AS (
            SELECT
                md.year_month,
                md.gics_sector_name,
                md.monthly_return,
                cc.cpi_change,
                LAG(cc.cpi_change, 1) OVER (PARTITION BY md.gics_sector_name ORDER BY md.year_month) AS cpi_lag1,
                LAG(cc.cpi_change, 2) OVER (PARTITION BY md.gics_sector_name ORDER BY md.year_month) AS cpi_lag2,
                LAG(cc.cpi_change, 3) OVER (PARTITION BY md.gics_sector_name ORDER BY md.year_month) AS cpi_lag3
            FROM monthly_data md
            JOIN cpi_changes cc ON md.year_month = cc.year_month
        )
        SELECT
            gics_sector_name,
            COUNT(*) AS months,
            ROUND(AVG(monthly_return), 4) AS avg_return,
            ROUND(AVG(cpi_change), 4) AS avg_cpi_change,
            ROUND(AVG(monthly_return * cpi_change) - AVG(monthly_return) * AVG(cpi_change), 6) AS return_cpi_covariance,
            CASE
                WHEN AVG(monthly_return * cpi_change) - AVG(monthly_return) * AVG(cpi_change) > 0.001 THEN 'Positive (Inflation Beneficiary)'
                WHEN AVG(monthly_return * cpi_change) - AVG(monthly_return) * AVG(cpi_change) < -0.001 THEN 'Negative (Inflation Sensitive)'
                ELSE 'Neutral'
            END AS cpi_sensitivity
        FROM sector_cpi_combined
        WHERE cpi_change IS NOT NULL
        GROUP BY gics_sector_name
        ORDER BY return_cpi_covariance DESC
    """,

    "uc5_q3_sector_rate_sensitivity": """
        WITH weekly_yield AS (
            SELECT
                rate_date,
                rate_value AS yield_10y,
                rate_value - LAG(rate_value, 1) OVER (ORDER BY rate_date) AS yield_change
            FROM interest_rates
            WHERE country_id = 'US'
              AND rate_type = '10Y_YIELD'
        ),
        sector_returns AS (
            SELECT
                p.price_date,
                c.gics_sector_name,
                AVG(p.total_return) AS sector_return
            FROM prices_weekly p
            JOIN companies c ON p.company_id = c.company_id
            WHERE c.gics_sector_name IS NOT NULL
              AND c.country_id = 'US'
            GROUP BY p.price_date, c.gics_sector_name
        ),
        combined AS (
            SELECT
                sr.price_date,
                sr.gics_sector_name,
                sr.sector_return,
                wy.yield_change
            FROM sector_returns sr
            JOIN weekly_yield wy ON sr.price_date = wy.rate_date
            WHERE wy.yield_change IS NOT NULL
        )
        SELECT
            gics_sector_name,
            COUNT(*) AS weeks,
            ROUND(AVG(sector_return), 4) AS avg_weekly_return,
            ROUND(AVG(yield_change), 4) AS avg_yield_change_bp,
            ROUND(AVG(sector_return * yield_change) - AVG(sector_return) * AVG(yield_change), 6) AS rate_sensitivity,
            CASE
                WHEN AVG(sector_return * yield_change) - AVG(sector_return) * AVG(yield_change) < -0.001 THEN 'Rate Sensitive (Duration Risk)'
                WHEN AVG(sector_return * yield_change) - AVG(sector_return) * AVG(yield_change) > 0.001 THEN 'Rate Beneficiary'
                ELSE 'Rate Neutral'
            END AS rate_profile
        FROM combined
        GROUP BY gics_sector_name
        ORDER BY rate_sensitivity ASC
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
