-- ============================================================================
-- MacroAlpha: SQL Queries for 5 Use Cases (15 Queries Total)
-- ============================================================================
-- Database: macroalpha.db (SQLite)
-- Data Range: 2005-2024 (20 years)
-- ============================================================================

-- ############################################################################
-- USE CASE 1: Market Concentration & Point-in-Time Index Dynamics
-- Focus: FTSE 100 (UKX) - Complete Weight/Shares data available
-- ############################################################################

-- ----------------------------------------------------------------------------
-- UC1-Q1: Top-Heavy Concentration Trend (2005-2024)
-- Calculate cumulative weight of Top 10 companies in FTSE 100 per year
-- Correlate with UK GDP growth
-- ----------------------------------------------------------------------------

WITH yearly_top10 AS (
    SELECT 
        strftime('%Y', im.as_of_date) AS year,
        im.company_id,
        c.company_name,
        im.weight,
        ROW_NUMBER() OVER (
            PARTITION BY strftime('%Y', im.as_of_date) 
            ORDER BY im.weight DESC
        ) AS rank
    FROM index_membership im
    JOIN companies c ON im.company_id = c.company_id
    WHERE im.index_id = 'UKX' 
      AND im.weight IS NOT NULL
),
concentration AS (
    SELECT 
        year,
        SUM(weight) AS top10_weight,
        GROUP_CONCAT(company_name, ', ') AS top10_companies
    FROM yearly_top10
    WHERE rank <= 10
    GROUP BY year
),
uk_gdp AS (
    SELECT 
        strftime('%Y', indicator_date) AS year,
        AVG(indicator_value) AS gdp_growth
    FROM macro_indicators
    WHERE country_id = 'GB' 
      AND indicator_name LIKE '%Real GDP%yoy%'
    GROUP BY strftime('%Y', indicator_date)
)
SELECT 
    c.year,
    ROUND(c.top10_weight, 2) AS top10_weight_pct,
    ROUND(g.gdp_growth, 2) AS uk_gdp_growth_pct,
    c.top10_companies
FROM concentration c
LEFT JOIN uk_gdp g ON c.year = g.year
ORDER BY c.year;


-- ----------------------------------------------------------------------------
-- UC1-Q2: Herfindahl-Hirschman Index (HHI) by Year
-- Compute market concentration index HHI = SUM(weight²) per year
-- Lower HHI = more competitive, Higher HHI = more concentrated
-- ----------------------------------------------------------------------------

WITH hhi_calc AS (
    SELECT 
        strftime('%Y', im.as_of_date) AS year,
        SUM(im.weight * im.weight) AS hhi,
        COUNT(*) AS num_members,
        AVG(im.weight) AS avg_weight,
        MAX(im.weight) AS max_weight
    FROM index_membership im
    WHERE im.index_id = 'UKX' 
      AND im.weight IS NOT NULL
    GROUP BY strftime('%Y', im.as_of_date)
),
uk_returns AS (
    -- Calculate average annual return for UKX constituents
    SELECT 
        strftime('%Y', p.price_date) AS year,
        AVG(p.total_return) AS avg_weekly_return
    FROM prices_weekly p
    JOIN index_membership im ON p.company_id = im.company_id
    WHERE im.index_id = 'UKX'
      AND strftime('%Y', p.price_date) = strftime('%Y', im.as_of_date)
    GROUP BY strftime('%Y', p.price_date)
)
SELECT 
    h.year,
    ROUND(h.hhi, 2) AS hhi_index,
    h.num_members,
    ROUND(h.avg_weight, 2) AS avg_weight_pct,
    ROUND(h.max_weight, 2) AS largest_weight_pct,
    ROUND(10000.0 / h.hhi, 1) AS effective_positions,
    ROUND(r.avg_weekly_return * 52, 2) AS approx_annual_return_pct,
    CASE 
        WHEN h.hhi < 1500 THEN 'Unconcentrated'
        WHEN h.hhi < 2500 THEN 'Moderately Concentrated'
        ELSE 'Highly Concentrated'
    END AS concentration_level
FROM hhi_calc h
LEFT JOIN uk_returns r ON h.year = r.year
ORDER BY h.year;


-- ----------------------------------------------------------------------------
-- UC1-Q3: Index Churn Analysis (Entry/Exit Dynamics)
-- Identify companies added to or removed from FTSE 100 each year
-- Compare valuation metrics of exited vs continuing members
-- ----------------------------------------------------------------------------

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
      AND m2.year < '2024'  -- Can't detect exits in the last year
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
ORDER BY ac.year, ac.status;


-- ############################################################################
-- USE CASE 2: Corporate Leverage Cycles & Financial Health Evolution
-- Scope: Non-financial companies only (WHERE gics_sector_name != 'Financials')
-- ############################################################################

-- ----------------------------------------------------------------------------
-- UC2-Q1: Debt-to-Revenue Ratio Distribution Evolution (2005-2024)
-- Calculate cross-sectional percentiles of Debt/Revenue ratio each year
-- ----------------------------------------------------------------------------

WITH de_ratios AS (
    SELECT 
        strftime('%Y', f.period_end_date) AS year,
        f.company_id,
        c.company_name,
        c.gics_sector_name,
        f.total_debt,
        f.revenue,
        CASE 
            WHEN f.revenue > 0 THEN f.total_debt / f.revenue 
            ELSE NULL 
        END AS debt_to_revenue_ratio
    FROM financials f
    JOIN companies c ON f.company_id = c.company_id
    WHERE f.period_type = 'ANNUAL'
      AND c.gics_sector_name != 'Financials'
      AND f.total_debt IS NOT NULL 
      AND f.revenue IS NOT NULL
      AND f.revenue > 0
),
percentiles AS (
    SELECT 
        year,
        COUNT(*) AS company_count,
        AVG(debt_to_revenue_ratio) AS mean_ratio,
        -- Approximate percentiles using NTILE
        MIN(debt_to_revenue_ratio) AS min_ratio,
        MAX(debt_to_revenue_ratio) AS max_ratio
    FROM de_ratios
    GROUP BY year
)
SELECT 
    p.year,
    p.company_count,
    ROUND(p.mean_ratio, 3) AS mean_debt_to_revenue,
    ROUND(p.min_ratio, 3) AS min_ratio,
    ROUND(p.max_ratio, 3) AS max_ratio,
    CASE 
        WHEN p.year IN ('2008', '2009', '2020') THEN 'Crisis Year'
        WHEN p.year IN ('2006', '2007', '2021') THEN 'Boom Year'
        ELSE 'Normal'
    END AS economic_period
FROM percentiles p
ORDER BY p.year;


-- ----------------------------------------------------------------------------
-- UC2-Q2: Deleveraging Cycles Detection (Firm-Level)
-- Identify companies that reduced debt for 3+ consecutive years
-- Test if deleveraging is pro-cyclical or counter-cyclical
-- ----------------------------------------------------------------------------

WITH yearly_debt AS (
    SELECT 
        f.company_id,
        c.company_name,
        c.country_id,
        strftime('%Y', f.period_end_date) AS year,
        f.total_debt,
        LAG(f.total_debt, 1) OVER (PARTITION BY f.company_id ORDER BY f.period_end_date) AS prev_debt_1,
        LAG(f.total_debt, 2) OVER (PARTITION BY f.company_id ORDER BY f.period_end_date) AS prev_debt_2
    FROM financials f
    JOIN companies c ON f.company_id = c.company_id
    WHERE f.period_type = 'ANNUAL'
      AND c.gics_sector_name != 'Financials'
      AND f.total_debt IS NOT NULL
),
deleveraging AS (
    SELECT 
        company_id,
        company_name,
        country_id,
        year,
        total_debt,
        prev_debt_1,
        prev_debt_2,
        CASE 
            WHEN total_debt < prev_debt_1 
             AND prev_debt_1 < prev_debt_2 
            THEN 1 
            ELSE 0 
        END AS is_3yr_deleveraging
    FROM yearly_debt
    WHERE prev_debt_2 IS NOT NULL
),
gdp_status AS (
    SELECT 
        strftime('%Y', indicator_date) AS year,
        country_id,
        AVG(indicator_value) AS gdp_growth,
        CASE WHEN AVG(indicator_value) < 0 THEN 'Contraction' ELSE 'Expansion' END AS gdp_phase
    FROM macro_indicators
    WHERE indicator_name LIKE '%Real GDP%yoy%'
    GROUP BY strftime('%Y', indicator_date), country_id
)
SELECT 
    d.year,
    g.gdp_phase,
    COUNT(*) AS total_companies,
    SUM(d.is_3yr_deleveraging) AS deleveraging_companies,
    ROUND(SUM(d.is_3yr_deleveraging) * 100.0 / COUNT(*), 1) AS deleveraging_pct
FROM deleveraging d
LEFT JOIN gdp_status g ON d.year = g.year AND d.country_id = g.country_id
GROUP BY d.year, g.gdp_phase
ORDER BY d.year;


-- ----------------------------------------------------------------------------
-- UC2-Q3: Interest Coverage Sensitivity to Policy Rates
-- Calculate rolling 5-year correlation between ICR and policy rate
-- Identify rate-sensitive vs rate-insulated companies
-- ----------------------------------------------------------------------------

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
      AND f.interest_expense IS NOT NULL
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
-- Calculate rolling 5-year correlation for each company-year
rolling_correlation AS (
    SELECT 
        c1.company_id,
        c1.company_name,
        c1.gics_sector_name,
        c1.country_id,
        c1.year,
        COUNT(c2.year) AS window_size,
        -- Calculate correlation over 5-year window
        AVG(c2.interest_coverage_ratio) AS avg_icr,
        AVG(c2.avg_policy_rate) AS avg_rate,
        AVG(c2.interest_coverage_ratio * c2.avg_policy_rate) AS avg_icr_rate_product,
        AVG(c2.interest_coverage_ratio * c2.interest_coverage_ratio) AS avg_icr_squared,
        AVG(c2.avg_policy_rate * c2.avg_policy_rate) AS avg_rate_squared
    FROM combined c1
    JOIN combined c2 ON c1.company_id = c2.company_id 
                     AND c2.year BETWEEN (c1.year - 4) AND c1.year
    GROUP BY c1.company_id, c1.company_name, c1.gics_sector_name, c1.country_id, c1.year
    HAVING COUNT(c2.year) = 5  -- Full 5-year window
),
-- Calculate actual correlation from components
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
-- Get most recent correlation for each company (with at least 10 years total)
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
    HAVING COUNT(DISTINCT cm.year) >= 10  -- At least 10 years of data
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
ORDER BY cc.rolling_correlation ASC
LIMIT 50;


-- ############################################################################
-- USE CASE 3: Rate-Shock Solvency Stress Test
-- Scope: Non-financial companies only
-- ############################################################################

-- ----------------------------------------------------------------------------
-- UC3-Q1: Zombie Companies (3-Year Persistence)
-- Interest Coverage Ratio < 1.5 for 3 consecutive years
-- AND in countries with declining GDP trend
-- ----------------------------------------------------------------------------

WITH icr_calc AS (
    SELECT 
        f.company_id,
        c.company_name,
        c.country_id,
        c.gics_sector_name,
        strftime('%Y', f.period_end_date) AS year,
        f.ebitda,
        f.interest_expense,
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
),
zombie_persistence AS (
    SELECT 
        company_id,
        company_name,
        country_id,
        gics_sector_name,
        year,
        icr,
        is_zombie,
        is_zombie + 
        COALESCE(LAG(is_zombie, 1) OVER (PARTITION BY company_id ORDER BY year), 0) +
        COALESCE(LAG(is_zombie, 2) OVER (PARTITION BY company_id ORDER BY year), 0) AS zombie_streak
    FROM icr_calc
),
gdp_trend AS (
    SELECT 
        country_id,
        strftime('%Y', indicator_date) AS year,
        AVG(indicator_value) AS gdp_growth,
        AVG(indicator_value) - LAG(AVG(indicator_value), 1) OVER (
            PARTITION BY country_id ORDER BY strftime('%Y', indicator_date)
        ) AS gdp_change
    FROM macro_indicators
    WHERE indicator_name LIKE '%Real GDP%yoy%'
    GROUP BY country_id, strftime('%Y', indicator_date)
)
SELECT 
    z.year,
    z.country_id,
    COUNT(*) AS total_companies_analyzed,
    SUM(CASE WHEN z.zombie_streak >= 3 THEN 1 ELSE 0 END) AS persistent_zombies,
    ROUND(AVG(g.gdp_growth), 2) AS avg_gdp_growth,
    ROUND(AVG(g.gdp_change), 2) AS gdp_trend
FROM zombie_persistence z
LEFT JOIN gdp_trend g ON z.country_id = g.country_id AND z.year = g.year
WHERE z.zombie_streak >= 3  -- 3-year zombie
  AND g.gdp_change < 0      -- Declining GDP trend
GROUP BY z.year, z.country_id
ORDER BY z.year, persistent_zombies DESC;


-- ----------------------------------------------------------------------------
-- UC3-Q2: 200bp Rate Shock Scenario (Stress Testing)
-- Simulate +200bp rate increase
-- Assume 50% floating-rate debt reprices immediately
-- ----------------------------------------------------------------------------

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
      AND strftime('%Y', f.period_end_date) = '2024'  -- Latest year
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
        -- Shocked interest = current + (50% of debt * 2% rate increase)
        interest_expense + (total_debt * 0.5 * 0.02) AS shocked_interest,
        -- Shocked ICR
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
ORDER BY newly_distressed DESC;


-- ----------------------------------------------------------------------------
-- UC3-Q3: Geographic Risk Concentration (Systemic Solvency Risk)
-- Rank countries by: (a) % companies below threshold, (b) aggregate zombie debt
-- ----------------------------------------------------------------------------

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
ORDER BY zombie_pct DESC;


-- ############################################################################
-- USE CASE 4: Macro Lead-Lag & Business Cycle Sensitivity
-- ############################################################################

-- ----------------------------------------------------------------------------
-- UC4-Q1: Housing Starts Lead Revenue (2-Quarter Lag Test)
-- Test if housing activity predicts company revenue with lag
-- Focus on consumer/housing-related sectors
-- ----------------------------------------------------------------------------

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
ORDER BY cr.gics_sector_name, cr.country_id;


-- ----------------------------------------------------------------------------
-- UC4-Q2: Revenue Volatility as Cyclicality Proxy (Data-Driven Classification)
-- Compute 10-year rolling STDDEV of revenue growth
-- Classify companies into quartiles: High Volatility = Cyclical
-- ----------------------------------------------------------------------------

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
-- Calculate 10-year rolling volatility for each company-year
rolling_volatility AS (
    SELECT 
        rg1.company_id,
        rg1.company_name,
        rg1.gics_sector_name,
        rg1.year,
        COUNT(rg2.year) AS window_size,
        AVG(rg2.rev_growth) AS avg_growth_10y,
        -- Standard deviation over 10-year window
        SQRT(AVG(rg2.rev_growth * rg2.rev_growth) - AVG(rg2.rev_growth) * AVG(rg2.rev_growth)) AS rolling_volatility
    FROM revenue_growth rg1
    JOIN revenue_growth rg2 ON rg1.company_id = rg2.company_id 
                             AND rg2.year BETWEEN (rg1.year - 9) AND rg1.year
                             AND rg2.rev_growth IS NOT NULL
    WHERE rg1.rev_growth IS NOT NULL
    GROUP BY rg1.company_id, rg1.company_name, rg1.gics_sector_name, rg1.year
    HAVING COUNT(rg2.year) = 10  -- Full 10-year window
),
-- Get most recent rolling volatility for each company
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
    HAVING COUNT(DISTINCT rg.year) >= 10  -- At least 10 years total
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
    GROUP_CONCAT(DISTINCT gics_sector_name) AS sectors_represented,
    ROUND(AVG(volatility), 2) AS avg_volatility,
    ROUND(AVG(avg_growth), 2) AS avg_growth_rate
FROM quartiles
GROUP BY volatility_quartile
ORDER BY volatility_quartile;


-- ----------------------------------------------------------------------------
-- UC4-Q3: Downturn Resilience (Cash Flow Focus)
-- Identify GDP contraction quarters, find companies with positive FCF
-- despite negative revenue growth
-- ----------------------------------------------------------------------------

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
    HAVING AVG(indicator_value) < 0  -- Contraction quarters
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
ORDER BY year, quarter, country_id;


-- ############################################################################
-- USE CASE 5: Sector Rotation & Inflation Regime Analysis
-- ############################################################################

-- ----------------------------------------------------------------------------
-- UC5-Q1: Sector Performance by Inflation Regime (High vs Low CPI)
-- Classify months into High Inflation (CPI > 3%) vs Low Inflation
-- Calculate average returns by sector for each regime
-- ----------------------------------------------------------------------------

WITH monthly_cpi AS (
    SELECT 
        strftime('%Y-%m', indicator_date) AS year_month,
        country_id,
        AVG(indicator_value) AS cpi_yoy,
        CASE WHEN AVG(indicator_value) > 3 THEN 'High Inflation' ELSE 'Low Inflation' END AS inflation_regime
    FROM macro_indicators
    WHERE indicator_name LIKE '%CPI%yoy%'
      AND country_id = 'US'
    GROUP BY strftime('%Y-%m', indicator_date), country_id
),
monthly_sector_returns AS (
    SELECT 
        strftime('%Y-%m', p.price_date) AS year_month,
        c.gics_sector_name,
        AVG(p.total_return) AS avg_weekly_return,
        COUNT(*) AS weeks
    FROM prices_weekly p
    JOIN companies c ON p.company_id = c.company_id
    WHERE c.gics_sector_name IS NOT NULL
      AND c.country_id = 'US'
    GROUP BY strftime('%Y-%m', p.price_date), c.gics_sector_name
)
SELECT 
    cpi.inflation_regime,
    sr.gics_sector_name,
    COUNT(*) AS months,
    ROUND(AVG(cpi.cpi_yoy), 2) AS avg_cpi,
    ROUND(AVG(sr.avg_weekly_return) * 4.33, 4) AS avg_monthly_return_pct,
    ROUND(AVG(sr.avg_weekly_return) * 52, 2) AS annualized_return_pct
FROM monthly_cpi cpi
JOIN monthly_sector_returns sr ON cpi.year_month = sr.year_month
GROUP BY cpi.inflation_regime, sr.gics_sector_name
ORDER BY cpi.inflation_regime, annualized_return_pct DESC;


-- ----------------------------------------------------------------------------
-- UC5-Q2: Sector-CPI Lead-Lag Relationship
-- Compute correlation between sector returns and lagged CPI
-- Identify leading vs lagging sectors
-- ----------------------------------------------------------------------------

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
    -- Simplified correlation approximation
    ROUND(AVG(monthly_return * cpi_change) - AVG(monthly_return) * AVG(cpi_change), 6) AS return_cpi_covariance,
    CASE 
        WHEN AVG(monthly_return * cpi_change) - AVG(monthly_return) * AVG(cpi_change) > 0.001 THEN 'Positive (Inflation Beneficiary)'
        WHEN AVG(monthly_return * cpi_change) - AVG(monthly_return) * AVG(cpi_change) < -0.001 THEN 'Negative (Inflation Sensitive)'
        ELSE 'Neutral'
    END AS cpi_sensitivity
FROM sector_cpi_combined
WHERE cpi_change IS NOT NULL
GROUP BY gics_sector_name
ORDER BY return_cpi_covariance DESC;


-- ----------------------------------------------------------------------------
-- UC5-Q3: Rate Sensitivity by Sector (Duration Proxy)
-- Calculate correlation between sector returns and 10Y yield changes
-- Identify rate-sensitive sectors
-- ----------------------------------------------------------------------------

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
    -- Covariance as sensitivity measure
    ROUND(AVG(sector_return * yield_change) - AVG(sector_return) * AVG(yield_change), 6) AS rate_sensitivity,
    CASE 
        WHEN AVG(sector_return * yield_change) - AVG(sector_return) * AVG(yield_change) < -0.001 THEN 'Rate Sensitive (Duration Risk)'
        WHEN AVG(sector_return * yield_change) - AVG(sector_return) * AVG(yield_change) > 0.001 THEN 'Rate Beneficiary'
        ELSE 'Rate Neutral'
    END AS rate_profile
FROM combined
GROUP BY gics_sector_name
ORDER BY rate_sensitivity ASC;


-- ############################################################################
-- END OF QUERIES
-- ############################################################################

