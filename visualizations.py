#!/usr/bin/env python3
"""
MacroAlpha Visualizations
=========================
Generate charts for the 5 Use Cases.
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

# Style settings
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 11

# Colors
COLORS = {
    'primary': '#2E86AB',
    'secondary': '#A23B72',
    'accent': '#F18F01',
    'success': '#C73E1D',
    'neutral': '#6C757D',
    'highlight': '#28A745'
}

def get_connection():
    return sqlite3.connect("macroalpha.db")

# ============================================================================
# UC1: Market Concentration
# ============================================================================

def plot_uc1_concentration():
    """UC1-Q1 & Q2: Top 10 Concentration and HHI over time."""
    conn = get_connection()
    
    # Query Top 10 concentration
    query1 = """
    WITH yearly_top10 AS (
        SELECT strftime('%Y', im.as_of_date) AS year, im.weight,
            ROW_NUMBER() OVER (PARTITION BY strftime('%Y', im.as_of_date) ORDER BY im.weight DESC) AS rank
        FROM index_membership im
        WHERE im.index_id = 'UKX' AND im.weight IS NOT NULL
    )
    SELECT year, SUM(weight) AS top10_weight
    FROM yearly_top10 WHERE rank <= 10 GROUP BY year ORDER BY year
    """
    df1 = pd.read_sql_query(query1, conn)
    
    # Query HHI
    query2 = """
    SELECT strftime('%Y', im.as_of_date) AS year,
        SUM(im.weight * im.weight) AS hhi
    FROM index_membership im
    WHERE im.index_id = 'UKX' AND im.weight IS NOT NULL
    GROUP BY strftime('%Y', im.as_of_date) ORDER BY year
    """
    df2 = pd.read_sql_query(query2, conn)
    conn.close()
    
    # Create figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Plot 1: Top 10 Concentration
    ax1.bar(df1['year'], df1['top10_weight'], color=COLORS['primary'], alpha=0.8)
    ax1.axhline(y=50, color=COLORS['accent'], linestyle='--', label='50% threshold')
    ax1.set_xlabel('Year')
    ax1.set_ylabel('Top 10 Weight (%)')
    ax1.set_title('UC1-Q1: FTSE 100 Top 10 Concentration (2005-2024)')
    ax1.set_ylim(0, 60)
    ax1.legend()
    ax1.tick_params(axis='x', rotation=45)
    
    # Highlight crisis years
    for year in ['2008', '2020', '2022']:
        if year in df1['year'].values:
            idx = df1[df1['year'] == year].index[0]
            ax1.bar(year, df1.loc[idx, 'top10_weight'], color=COLORS['success'], alpha=0.9)
    
    # Plot 2: HHI Index
    ax2.plot(df2['year'], df2['hhi'], marker='o', color=COLORS['secondary'], linewidth=2, markersize=6)
    ax2.fill_between(df2['year'], df2['hhi'], alpha=0.3, color=COLORS['secondary'])
    ax2.axhline(y=250, color=COLORS['accent'], linestyle='--', label='Moderate concentration')
    ax2.set_xlabel('Year')
    ax2.set_ylabel('HHI Index')
    ax2.set_title('UC1-Q2: Herfindahl-Hirschman Index (Market Concentration)')
    ax2.legend()
    ax2.tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.savefig('viz_uc1_concentration.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Saved: viz_uc1_concentration.png")


def plot_uc2_leverage():
    """UC2: Corporate Leverage Cycles."""
    conn = get_connection()
    
    # Query deleveraging cycles
    query = """
    WITH yearly_debt AS (
        SELECT f.company_id, strftime('%Y', f.period_end_date) AS year, f.total_debt,
            LAG(f.total_debt, 1) OVER (PARTITION BY f.company_id ORDER BY f.period_end_date) AS prev1,
            LAG(f.total_debt, 2) OVER (PARTITION BY f.company_id ORDER BY f.period_end_date) AS prev2
        FROM financials f
        JOIN companies c ON f.company_id = c.company_id
        WHERE f.period_type = 'ANNUAL' AND c.gics_sector_name != 'Financials' AND f.total_debt IS NOT NULL
    ),
    deleveraging AS (
        SELECT year, CASE WHEN total_debt < prev1 AND prev1 < prev2 THEN 1 ELSE 0 END AS is_delev
        FROM yearly_debt WHERE prev2 IS NOT NULL
    )
    SELECT year, COUNT(*) AS companies, SUM(is_delev) AS deleveraging,
           ROUND(SUM(is_delev) * 100.0 / COUNT(*), 1) AS pct
    FROM deleveraging GROUP BY year ORDER BY year
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Color bars based on value
    colors = [COLORS['success'] if p > 25 else COLORS['primary'] if p > 15 else COLORS['neutral'] 
              for p in df['pct']]
    
    bars = ax.bar(df['year'], df['pct'], color=colors, alpha=0.85, edgecolor='white', linewidth=0.5)
    
    # Add value labels
    for bar, pct in zip(bars, df['pct']):
        height = bar.get_height()
        ax.annotate(f'{pct:.0f}%', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
    
    ax.axhline(y=20, color=COLORS['accent'], linestyle='--', linewidth=1.5, label='20% threshold')
    ax.set_xlabel('Year')
    ax.set_ylabel('Companies Deleveraging (%)')
    ax.set_title('UC2-Q2: Deleveraging Cycles (3+ Consecutive Years of Debt Reduction)')
    ax.set_ylim(0, 35)
    ax.legend()
    ax.tick_params(axis='x', rotation=45)
    
    # Add annotations for key events
    ax.annotate('Post-GFC\nRecovery', xy=('2010', 29.2), xytext=('2008', 32),
                arrowprops=dict(arrowstyle='->', color='gray'), fontsize=9, ha='center')
    ax.annotate('COVID\nLeverage', xy=('2020', 9.9), xytext=('2018', 5),
                arrowprops=dict(arrowstyle='->', color='gray'), fontsize=9, ha='center')
    ax.annotate('Rate Hike\nResponse', xy=('2022', 29.8), xytext=('2024', 33),
                arrowprops=dict(arrowstyle='->', color='gray'), fontsize=9, ha='center')
    
    plt.tight_layout()
    plt.savefig('viz_uc2_leverage.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Saved: viz_uc2_leverage.png")


def plot_uc3_stress_test():
    """UC3: Rate Shock Stress Test."""
    conn = get_connection()
    
    query = """
    WITH current_financials AS (
        SELECT c.country_id, f.ebitda, f.interest_expense, f.total_debt,
            CASE WHEN f.interest_expense > 0 THEN f.ebitda / f.interest_expense ELSE NULL END AS current_icr
        FROM financials f
        JOIN companies c ON f.company_id = c.company_id
        WHERE f.period_type = 'ANNUAL' AND c.gics_sector_name != 'Financials'
          AND f.ebitda IS NOT NULL AND f.interest_expense > 0 AND f.total_debt IS NOT NULL
          AND strftime('%Y', f.period_end_date) = '2024'
    ),
    stress_test AS (
        SELECT country_id, current_icr,
            ebitda / (interest_expense + (total_debt * 0.5 * 0.02)) AS shocked_icr
        FROM current_financials WHERE current_icr IS NOT NULL
    )
    SELECT country_id, COUNT(*) AS companies,
        ROUND(AVG(current_icr), 2) AS current_icr,
        ROUND(AVG(shocked_icr), 2) AS shocked_icr,
        SUM(CASE WHEN current_icr >= 1.5 AND shocked_icr < 1.5 THEN 1 ELSE 0 END) AS newly_distressed
    FROM stress_test
    GROUP BY country_id
    HAVING COUNT(*) >= 10
    ORDER BY companies DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(df))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, df['current_icr'].clip(upper=80), width, 
                   label='Current ICR', color=COLORS['primary'], alpha=0.8)
    bars2 = ax.bar(x + width/2, df['shocked_icr'].clip(upper=80), width, 
                   label='Shocked ICR (+200bp)', color=COLORS['success'], alpha=0.8)
    
    ax.axhline(y=1.5, color=COLORS['accent'], linestyle='--', linewidth=2, label='Distress Threshold (1.5)')
    ax.set_xlabel('Country')
    ax.set_ylabel('Interest Coverage Ratio')
    ax.set_title('UC3-Q2: 200bp Rate Shock Stress Test (2024 Data)')
    ax.set_xticks(x)
    ax.set_xticklabels(df['country_id'])
    ax.legend()
    ax.set_ylim(0, 80)
    
    # Add company count annotations
    for i, (country, companies) in enumerate(zip(df['country_id'], df['companies'])):
        ax.annotate(f'n={companies}', xy=(i, 2), ha='center', fontsize=8, color='gray')
    
    plt.tight_layout()
    plt.savefig('viz_uc3_stress_test.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Saved: viz_uc3_stress_test.png")


def plot_uc4_volatility():
    """UC4: Revenue Volatility Classification."""
    conn = get_connection()
    
    query = """
    WITH rev_growth AS (
        SELECT f.company_id, c.gics_sector_name,
            (f.revenue - LAG(f.revenue) OVER (PARTITION BY f.company_id ORDER BY f.period_end_date)) 
            / NULLIF(LAG(f.revenue) OVER (PARTITION BY f.company_id ORDER BY f.period_end_date), 0) * 100 AS growth
        FROM financials f JOIN companies c ON f.company_id = c.company_id
        WHERE f.period_type = 'ANNUAL' AND f.revenue IS NOT NULL AND c.gics_sector_name IS NOT NULL
    ),
    volatility AS (
        SELECT company_id, gics_sector_name,
            SQRT(ABS(AVG(growth*growth) - AVG(growth)*AVG(growth))) AS vol
        FROM rev_growth WHERE growth IS NOT NULL
        GROUP BY company_id, gics_sector_name HAVING COUNT(*) >= 10
    )
    SELECT gics_sector_name, COUNT(*) AS companies, 
           AVG(vol) AS avg_vol, MIN(vol) AS min_vol, MAX(vol) AS max_vol
    FROM volatility
    WHERE gics_sector_name IS NOT NULL
    GROUP BY gics_sector_name
    ORDER BY avg_vol
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Color gradient from defensive (green) to cyclical (red)
    colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(df)))
    
    bars = ax.barh(df['gics_sector_name'], df['avg_vol'].clip(upper=100), color=colors, alpha=0.85)
    
    ax.axvline(x=20, color=COLORS['accent'], linestyle='--', linewidth=1.5, label='20% volatility threshold')
    ax.set_xlabel('Average Revenue Volatility (%)')
    ax.set_ylabel('GICS Sector')
    ax.set_title('UC4-Q2: Revenue Volatility by Sector (Cyclicality Proxy)')
    ax.legend(loc='lower right')
    
    # Add labels
    for bar, vol in zip(bars, df['avg_vol']):
        width = bar.get_width()
        label = f'{vol:.1f}%' if vol < 100 else f'{vol:.0f}%'
        ax.annotate(label, xy=(min(width, 100) + 1, bar.get_y() + bar.get_height()/2),
                    va='center', fontsize=9)
    
    # Add classification labels
    ax.text(5, -0.8, '← Defensive', fontsize=10, color=COLORS['highlight'], fontweight='bold')
    ax.text(80, -0.8, 'Cyclical →', fontsize=10, color=COLORS['success'], fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('viz_uc4_volatility.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Saved: viz_uc4_volatility.png")


def plot_uc5_inflation_regime():
    """UC5: Sector Performance by Inflation Regime."""
    conn = get_connection()
    
    query = """
    WITH monthly_cpi AS (
        SELECT strftime('%Y-%m', indicator_date) AS ym,
            CASE WHEN AVG(indicator_value) > 3 THEN 'High Inflation (CPI>3%)' ELSE 'Low Inflation (CPI≤3%)' END AS regime
        FROM macro_indicators
        WHERE indicator_name LIKE '%CPI%yoy%' AND country_id = 'US'
        GROUP BY strftime('%Y-%m', indicator_date)
    ),
    sector_returns AS (
        SELECT strftime('%Y-%m', p.price_date) AS ym, c.gics_sector_name AS sector,
            AVG(p.total_return) * 52 AS ann_return
        FROM prices_weekly p
        JOIN companies c ON p.company_id = c.company_id
        WHERE c.gics_sector_name IS NOT NULL AND c.country_id = 'US'
        GROUP BY strftime('%Y-%m', p.price_date), c.gics_sector_name
    )
    SELECT cpi.regime, sr.sector, AVG(sr.ann_return) AS ann_return
    FROM monthly_cpi cpi
    JOIN sector_returns sr ON cpi.ym = sr.ym
    GROUP BY cpi.regime, sr.sector
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Pivot for grouped bar chart
    df_pivot = df.pivot(index='sector', columns='regime', values='ann_return').fillna(0)
    
    fig, ax = plt.subplots(figsize=(14, 7))
    
    x = np.arange(len(df_pivot))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, df_pivot['High Inflation (CPI>3%)'], width, 
                   label='High Inflation (CPI>3%)', color=COLORS['success'], alpha=0.85)
    bars2 = ax.bar(x + width/2, df_pivot['Low Inflation (CPI≤3%)'], width, 
                   label='Low Inflation (CPI≤3%)', color=COLORS['primary'], alpha=0.85)
    
    ax.axhline(y=0, color='black', linewidth=0.8)
    ax.set_xlabel('GICS Sector')
    ax.set_ylabel('Annualized Return (%)')
    ax.set_title('UC5-Q1: Sector Performance by Inflation Regime (US Market)')
    ax.set_xticks(x)
    ax.set_xticklabels(df_pivot.index, rotation=45, ha='right')
    ax.legend()
    ax.set_ylim(-50, 40)
    
    plt.tight_layout()
    plt.savefig('viz_uc5_inflation.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Saved: viz_uc5_inflation.png")


def plot_uc5_rate_sensitivity():
    """UC5-Q3: Rate Sensitivity by Sector."""
    conn = get_connection()
    
    query = """
    WITH yield_chg AS (
        SELECT rate_date, rate_value - LAG(rate_value) OVER (ORDER BY rate_date) AS chg
        FROM interest_rates WHERE country_id = 'US' AND rate_type = '10Y_YIELD'
    ),
    sector_ret AS (
        SELECT p.price_date, c.gics_sector_name, AVG(p.total_return) AS ret
        FROM prices_weekly p JOIN companies c ON p.company_id = c.company_id
        WHERE c.gics_sector_name IS NOT NULL AND c.country_id = 'US'
        GROUP BY p.price_date, c.gics_sector_name
    ),
    combined AS (
        SELECT sr.gics_sector_name, sr.ret, yc.chg
        FROM sector_ret sr JOIN yield_chg yc ON sr.price_date = yc.rate_date WHERE yc.chg IS NOT NULL
    )
    SELECT gics_sector_name, AVG(ret*chg) - AVG(ret)*AVG(chg) AS sensitivity
    FROM combined GROUP BY gics_sector_name ORDER BY sensitivity
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Color: negative = rate sensitive (red), positive = rate beneficiary (green)
    colors = [COLORS['success'] if s < 0 else COLORS['highlight'] for s in df['sensitivity']]
    
    bars = ax.barh(df['gics_sector_name'], df['sensitivity'] * 1000, color=colors, alpha=0.85)
    
    ax.axvline(x=0, color='black', linewidth=1)
    ax.set_xlabel('Rate Sensitivity (×1000)')
    ax.set_ylabel('GICS Sector')
    ax.set_title('UC5-Q3: Sector Rate Sensitivity (Correlation with 10Y Yield Changes)')
    
    # Add labels
    ax.text(-10, -0.8, '← Rate Sensitive', fontsize=10, color=COLORS['success'], fontweight='bold')
    ax.text(80, -0.8, 'Rate Beneficiary →', fontsize=10, color=COLORS['highlight'], fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('viz_uc5_rate_sensitivity.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Saved: viz_uc5_rate_sensitivity.png")


def create_summary_dashboard():
    """Create a summary dashboard with key metrics."""
    conn = get_connection()
    
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle('MacroAlpha Dashboard: Key Metrics (2005-2024)', fontsize=16, fontweight='bold')
    
    # 1. Database Stats
    ax = axes[0, 0]
    stats = {
        'Companies': pd.read_sql_query("SELECT COUNT(*) FROM companies", conn).iloc[0, 0],
        'Price Records': pd.read_sql_query("SELECT COUNT(*) FROM prices_weekly", conn).iloc[0, 0],
        'Financial Records': pd.read_sql_query("SELECT COUNT(*) FROM financials", conn).iloc[0, 0],
        'Macro Indicators': pd.read_sql_query("SELECT COUNT(*) FROM macro_indicators", conn).iloc[0, 0],
    }
    ax.barh(list(stats.keys()), [v/1000 for v in stats.values()], color=COLORS['primary'])
    ax.set_xlabel('Records (thousands)')
    ax.set_title('Database Size')
    for i, (k, v) in enumerate(stats.items()):
        ax.text(v/1000 + 5, i, f'{v:,}', va='center', fontsize=9)
    
    # 2. Companies by Sector
    ax = axes[0, 1]
    query = "SELECT gics_sector_name, COUNT(*) as cnt FROM companies WHERE gics_sector_name IS NOT NULL GROUP BY gics_sector_name ORDER BY cnt DESC LIMIT 6"
    df = pd.read_sql_query(query, conn)
    ax.pie(df['cnt'], labels=df['gics_sector_name'], autopct='%1.0f%%', colors=plt.cm.Set3.colors)
    ax.set_title('Companies by Sector (Top 6)')
    
    # 3. Coverage by Year
    ax = axes[0, 2]
    query = """
    SELECT strftime('%Y', period_end_date) as year, COUNT(DISTINCT company_id) as companies
    FROM financials WHERE period_type = 'ANNUAL' GROUP BY year ORDER BY year
    """
    df = pd.read_sql_query(query, conn)
    ax.plot(df['year'], df['companies'], marker='o', color=COLORS['secondary'])
    ax.set_xlabel('Year')
    ax.set_ylabel('Companies with Data')
    ax.set_title('Financial Data Coverage')
    ax.tick_params(axis='x', rotation=45)
    
    # 4. Top 10 Concentration Trend
    ax = axes[1, 0]
    query = """
    WITH yearly_top10 AS (
        SELECT strftime('%Y', im.as_of_date) AS year, im.weight,
            ROW_NUMBER() OVER (PARTITION BY strftime('%Y', im.as_of_date) ORDER BY im.weight DESC) AS rank
        FROM index_membership im WHERE im.index_id = 'UKX' AND im.weight IS NOT NULL
    )
    SELECT year, SUM(weight) AS top10 FROM yearly_top10 WHERE rank <= 10 GROUP BY year
    """
    df = pd.read_sql_query(query, conn)
    ax.fill_between(df['year'], df['top10'], alpha=0.3, color=COLORS['primary'])
    ax.plot(df['year'], df['top10'], marker='s', color=COLORS['primary'])
    ax.set_ylabel('Top 10 Weight (%)')
    ax.set_title('FTSE 100 Concentration')
    ax.tick_params(axis='x', rotation=45)
    
    # 5. Interest Rates
    ax = axes[1, 1]
    query = """
    SELECT strftime('%Y', rate_date) as year, AVG(rate_value) as rate
    FROM interest_rates WHERE country_id = 'US' AND rate_type = '10Y_YIELD'
    GROUP BY year ORDER BY year
    """
    df = pd.read_sql_query(query, conn)
    ax.plot(df['year'], df['rate'], marker='o', color=COLORS['accent'], linewidth=2)
    ax.set_ylabel('10Y Yield (%)')
    ax.set_title('US 10-Year Treasury Yield')
    ax.tick_params(axis='x', rotation=45)
    
    # 6. Macro Coverage
    ax = axes[1, 2]
    query = "SELECT country_id, COUNT(DISTINCT indicator_name) as indicators FROM macro_indicators GROUP BY country_id"
    df = pd.read_sql_query(query, conn)
    ax.bar(df['country_id'], df['indicators'], color=COLORS['highlight'])
    ax.set_ylabel('Unique Indicators')
    ax.set_title('Macro Data by Country')
    
    conn.close()
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig('viz_dashboard.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Saved: viz_dashboard.png")


def main():
    print("=" * 60)
    print("📊 Generating MacroAlpha Visualizations")
    print("=" * 60)
    
    plot_uc1_concentration()
    plot_uc2_leverage()
    plot_uc3_stress_test()
    plot_uc4_volatility()
    plot_uc5_inflation_regime()
    plot_uc5_rate_sensitivity()
    create_summary_dashboard()
    
    print("\n" + "=" * 60)
    print("✅ All visualizations saved!")
    print("=" * 60)
    print("\nGenerated files:")
    for f in Path('.').glob('viz_*.png'):
        print(f"  📈 {f}")


if __name__ == "__main__":
    main()

