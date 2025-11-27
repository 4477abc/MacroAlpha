# Project Proposal: MacroAlpha — Global Macroeconomic Sensitivity & Corporate Performance Analysis System (Point-in-Time)

## Group Name

**MacroAlpha Team**

## Topic (Database Application)

**MacroAlpha: Global Macroeconomic Sensitivity & Corporate Performance Analysis System**

MacroAlpha is a "Top-Down" research database that connects macroeconomic indicators (GDP, CPI, yields, FX) with corporate fundamentals and market performance. Unlike firm-level analyses, it models these relationships across economic cycles while maintaining point-in-time correctness for index universes (S&P 500, FTSE 100) over 20-year horizons.

The system quantifies macro sensitivity by sector, industry, and company; identifies defensive versus cyclical exposures, inflation resilience, and rate-shock solvency risk; and supports scenario analysis through reproducible SQL queries on real datasets.

Technical implementation handles multi-granularity time series (weekly prices, quarterly macro, annual/quarterly financials) with alignment logic. SQL techniques include window functions (LAG/LEAD, rolling windows), complex joins (country/industry/FX mappings), recursive queries (GICS hierarchy rollups), and derived metrics (growth, ratios, stress scenarios).

---

## Data Sources & Acquisition Strategy (Bloomberg Terminal)

Data was extracted from Bloomberg Terminal and exported to cleaned CSV/Excel files. The following files populate the database:

### Data Source Files (with GitHub Links)

#### 1) Company Master Data
Company master file with ticker, name, country, currency, GICS classification, and market capitalization.
* Source: [`company_master.csv`](https://github.com/4477abc/MacroAlpha/blob/main/company_master.csv) → `companies` table

#### 2) Index Membership (Point-in-Time)
Historical membership data for S&P 500 and FTSE 100 with effective dates and weights. This file consolidates year-end snapshots (SPX/UKX as of Dec 31 YYYY.xlsx) to enable point-in-time analysis and avoid survivorship bias.
* Source: [`index_membership_snapshot.csv`](https://github.com/4477abc/MacroAlpha/blob/main/index_membership_snapshot.csv) → `index_membership` table

#### 3) Equity Price Data
Weekly closing prices and total returns for constituent equities. Weekly frequency balances frequency matching (aligns with quarterly macro and annual/quarterly financials), noise reduction (filters intraday volatility), analytical sufficiency (supports correlations, beta, rolling windows), and data manageability (critical for 1000+ tickers over 20 years).
* Source: [`price_weekly.xlsx.xlsx`](https://github.com/4477abc/MacroAlpha/blob/main/price_weekly.xlsx.xlsx) → `prices_weekly` table

#### 4) Corporate Financials
Standardized income statement, balance sheet, and cash flow items (Revenue, EBITDA, Interest Expense, Debt, FCF, etc.) extracted via Bloomberg `<FA>` function.
* Annual: [`financials_annual.xlsx`](https://github.com/4477abc/MacroAlpha/blob/main/financials_annual.xlsx) → `financials` table (period_type='ANNUAL')
* Quarterly: [`financials_quarterly.xlsx`](https://github.com/4477abc/MacroAlpha/blob/main/financials_quarterly.xlsx) → `financials` table (period_type='QUARTERLY')

#### 5) Macroeconomic Indicators
GDP, CPI, employment, housing starts, and other economic indicators extracted via Bloomberg `<ECST>` function for five countries:
* US: [`usa_macros_2024~2005.xlsx`](https://github.com/4477abc/MacroAlpha/blob/main/usa_macros_2024~2005.xlsx) → `macro_indicators` (country_id='US')
* UK: [`uk_macros_2024~2005.xlsx`](https://github.com/4477abc/MacroAlpha/blob/main/uk_macros_2024~2005.xlsx) → `macro_indicators` (country_id='GB')
* Germany: [`de_macros_2024~2005.xlsx`](https://github.com/4477abc/MacroAlpha/blob/main/de_macros_2024~2005.xlsx) → `macro_indicators` (country_id='DE')
* Japan: [`jp_macros_2024~2005.xlsx`](https://github.com/4477abc/MacroAlpha/blob/main/jp_macros_2024~2005.xlsx) → `macro_indicators` (country_id='JP')
* China: [`cn_macros_2024~2005.xlsx`](https://github.com/4477abc/MacroAlpha/blob/main/cn_macros_2024~2005.xlsx) → `macro_indicators` (country_id='CN')

#### 6) Interest Rates
Government bond yields and central bank policy rates for five countries (US, UK, DE, JP, CN).
* Source: [`5 countries 10y yield and policy rate.xlsx`](https://github.com/4477abc/MacroAlpha/blob/main/5%20countries%2010y%20yield%20and%20policy%20rate.xlsx) → `interest_rates` table

### Bloomberg Terminal Extraction Process

#### Overview
Data extraction used Bloomberg's Spreadsheet Builder with Time Series Table format. To manage volume (1000+ tickers × 20 years), extractions were batched (100-200 tickers per request) and concatenated locally. Returns, rolling correlations, and volatility measures are computed in the database using SQL window functions rather than pre-computed in Bloomberg.

#### Step-by-Step Export Instructions

**1. Access Spreadsheet Builder**
- In Bloomberg Terminal, type `W <GO>` to open Excel Add-In
- Or use menu: `Excel` → `Bloomberg` → `Spreadsheet Builder`

**2. Equity Price Data (Weekly)**
- **Tool:** Spreadsheet Builder → `Time Series Table`
- **Tickers:** Enter ticker list (batch 100-200 tickers per request)
- **Fields:** 
  - `PX_LAST` (Last Price)
  - `DAY_TO_DAY_TOT_RETURN_GROSS_DVDS` (Total Return)
- **Frequency:** Weekly (Friday close)
- **Date Range:** 2005-01-01 to 2024-12-31
- **Export:** Save as Excel file (`price_weekly.xlsx.xlsx`)
- **Note:** Bloomberg exports in wide-table format (tickers as columns, dates as rows)

**3. Financial Statements (Annual/Quarterly)**
- **Tool:** Spreadsheet Builder → `Time Series Table`
- **Tickers:** Enter ticker list
- **Fields:** Use `<FA>` function for standardized fields:
  - `SALES_REV_TURN` (Revenue)
  - `EBITDA` (EBITDA)
  - `IS_INT_EXPENSE` (Interest Expense)
  - `SHORT_AND_LONG_TERM_DEBT` (Total Debt)
  - `CF_FREE_CASH_FLOW` (Free Cash Flow)
  - `GROSS_PROFIT` (Gross Profit)
  - `ARD_COST_OF_GOODS_SOLD` (COGS)
- **Frequency:** 
  - Annual: Fiscal Annual
  - Quarterly: Fiscal Quarterly
- **Date Range:** 2005-01-01 to 2024-12-31
- **Export:** Save as separate Excel files (`financials_annual.xlsx`, `financials_quarterly.xlsx`)
- **Note:** Financial companies (banks) may show N/A for EBITDA and Interest Coverage fields—this is expected and correct.

**4. Macroeconomic Indicators**
- **Tool:** Spreadsheet Builder → `Time Series Table`
- **Country Tickers:** Use `<ECST>` function for economic statistics:
  - US: `USGDP Index`, `USCPI Index`, `USUNEMPL Index`, etc.
  - UK: `UKGDP Index`, `UKCPI Index`, `UKUNEMPL Index`, etc.
  - Germany: `BDGDP Index`, `BDCPI Index`, `BDUNEMPL Index`, etc.
  - Japan: `JPGDP Index`, `JPCPI Index`, `JPUNEMPL Index`, etc.
  - China: `CNGDP Index`, `CNCPI Index`, `CNUNEMPL Index`, etc.
- **Fields:** Select relevant indicators (GDP, CPI, Employment, Housing Starts, etc.)
- **Frequency:** Monthly or Quarterly (depending on indicator)
- **Date Range:** 2005-01-01 to 2024-12-31
- **Export:** Save as separate Excel files per country (`usa_macros_2024~2005.xlsx`, etc.)
- **Note:** Column headers show month names (Dec, Nov, Oct...) without years; dates are reconstructed from column position

**5. Interest Rates**
- **Tool:** Spreadsheet Builder → `Time Series Table`
- **Tickers:**
  - 10Y Yields: `USGG10YR Index`, `GTGBP10Y Govt`, `GTDEM10Y Govt`, `GTJPY10Y Govt`, `GTCNY10Y Govt`
  - Policy Rates: `FDTR Index` (US), `UKBRBASE Index` (UK), `EURR002W Index` (EU/Germany), `BOJDTR Index` (Japan), `PBOC7P Index` (China)
- **Fields:** `PX_LAST` (Last Price)
- **Frequency:** Weekly or Daily
- **Date Range:** 2005-01-01 to 2024-12-31
- **Export:** Save as Excel file (`5 countries 10y yield and policy rate.xlsx`)

**6. Index Membership (Historical Snapshots)**
- **Tool:** Terminal → `SPX Index MEMB <GO>` or `UKX Index MEMB <GO>`
- **Method:**
  1. Type `SPX Index MEMB <GO>` (or `UKX Index MEMB <GO>` for FTSE 100)
  2. Change **As of Date** to the last trading day of each year (Dec 31, 2005 through Dec 31, 2024)
  3. Click **Export/Output** → CSV or Excel
  4. Repeat for each year-end date (20 dates × 2 indices = 40 files)
- **Export:** Save as separate Excel files per year (`SPX as of Dec 31 2005.xlsx`, `UKX as of Dec 31 2005.xlsx`, etc.)
- **Post-Processing:** Use `combine_memb.py` to consolidate all 40 files into a single long table `index_membership_snapshot.csv` with columns: `index_id`, `as_of_date`, `ticker`, `weight`, etc.

**7. Company Master Data**
- **Tool:** Spreadsheet Builder → `Company Information`
- **Tickers:** Enter full ticker list
- **Fields:**
  - `NAME` (Company Name)
  - `COUNTRY` (Country)
  - `CRNCY` (Currency)
  - `GICS_SECTOR_NAME` (GICS Sector)
  - `GICS_INDUSTRY_GROUP_NAME` (GICS Industry Group)
  - `GICS_INDUSTRY_NAME` (GICS Industry)
  - `GICS_SUB_INDUSTRY_NAME` (GICS Sub-Industry)
  - `CUR_MKT_CAP` (Current Market Cap)
- **Export:** Save as CSV file (`company_master.csv`)

#### Data Quality Notes
- Bloomberg may return `#N/A` or `--` for missing data points; these are handled as NULL in the database
- Some date columns may be incomplete (especially in financials files); use `fix_dates.py` to populate missing dates
- Wide-table format requires parsing logic to extract ticker-field pairs (see `etl_import.py`)

All source data files are available in the project repository: [https://github.com/4477abc/MacroAlpha](https://github.com/4477abc/MacroAlpha)

---

## Analytical Methodology: Sector-Specific Financial Metrics

### Exclusion of Financial Sector from EBITDA-Based Analyses

Several use cases (UC2, UC3, UC4) exclude Financials sector companies from EBITDA-based and Interest Coverage analyses. This reflects fundamental differences in financial statement structures, not a data quality issue.

For non-financial companies, EBITDA is applicable and interest expense represents debt servicing costs. Interest Coverage Ratio measures debt serviceability, Debt-to-Equity ratios around 1.0 indicate high leverage, and Free Cash Flow (Operating CF minus CapEx) is a meaningful metric.

For financial companies (banks), EBITDA is not applicable because interest is core business revenue, not a financing cost. Interest expense represents payments to depositors (a normal operating cost), making Interest Coverage Ratio meaningless—ratios below 1.0 are normal for banks. Debt-to-Equity ratios of 10+ are normal because deposits (liabilities) fund lending operations. Free Cash Flow is conceptually inapplicable—is lending considered capital expenditure?

Banks earn spread income (Net Interest Income = Interest Received − Interest Paid), so interest expense is their cost of goods sold, not a financing burden. High leverage is structural: banks operate with D/E ratios of 10–15x because deposits (liabilities) fund lending. Bloomberg correctly reports N/A for EBITDA and Interest Coverage at banks like JP Morgan—these metrics are undefined for financial institutions.

SQL implementation: `WHERE gics_sector_name != 'Financials'`. This filter appears in queries involving EBITDA, Interest Coverage, and Free Cash Flow, following the industry-standard approach used by rating agencies (Moody's, S&P), equity research, and academic studies.

Banks require sector-specific metrics (NIM, NPL, Tier 1 Capital Ratio, Loan-to-Deposit Ratio), which are out of scope for this project but could be added as a future extension.

---

## Core Schema Ideas

* `Company(company_id, ticker, name, country_id, currency, gics_sub_industry_id, ...)`
* `Index(index_id, name, currency, ...)`
* `Index_Membership(index_id, company_id, start_date, end_date, weight)`
* `Macro(country_id, date, indicator_id, value, frequency)`
* `Financials(company_id, fiscal_period_end, period_type, item_id, value, currency, ...)`
* `Prices(company_id, date, close, return)` — **Weekly frequency** (e.g., Friday close)
* `GICS_Hierarchy(node_id, parent_id, level, name)` (for recursive rollups)

---

# Use Cases & Queries

## Use Case 1: Market Concentration & Point-in-Time Index Dynamics

Analyzes market structure evolution and concentration trends using FTSE 100, demonstrating survivorship-bias-free analysis. UKX provides complete historical Weight and Shares Outstanding data (unlike SPX where 83% are missing), enabling precise point-in-time calculations without imputation.

1. **Top-Heavy Concentration Trend (2005–2024):** Calculates cumulative weight of Top 10 companies in FTSE 100 for each year-end. Uses `ROW_NUMBER() OVER (PARTITION BY year ORDER BY weight DESC)` to identify top holdings, then aggregates weights. Correlates concentration ratio with UK GDP growth to test whether concentration increases during economic stress.

2. **Herfindahl-Hirschman Index (HHI) by Year:** Computes HHI = SUM(weight²) for each year-end snapshot. Joins with macro indicators (UK GDP growth, FTSE 100 returns) to analyze whether higher concentration predicts market returns. Uses point-in-time membership to avoid survivorship bias.

3. **Index Churn Analysis (Entry/Exit Dynamics):** Identifies companies added to or removed from FTSE 100 each year using `LAG(membership_flag) OVER (PARTITION BY company ORDER BY year)`. Compares average valuation metrics (Price-to-Book, Market Cap) of exited versus continuing members to test whether removals are driven by fundamental deterioration or relative size changes.

## Use Case 2: Corporate Leverage Cycles & Financial Health Evolution

Analyzes how corporate capital structure evolves across economic cycles and identifies companies vulnerable to rate shocks. Uses data-driven groupings rather than GICS sector classification. Scope: non-financial companies only (`WHERE gics_sector_name != 'Financials'`).

1. **Debt-to-Equity Ratio Distribution Evolution (2005–2024):** Calculates cross-sectional distribution of Debt-to-Equity ratios for each year using `PERCENTILE_CONT()` (P25, Median, P75, P90). Tracks distribution shifts during pre-2008 credit boom, 2008–2009 deleveraging, and post-2010 recovery. Joins with macro GDP growth to test whether leverage increases during expansions.

2. **Deleveraging Cycles Detection (Firm-Level):** Identifies companies that reduced D/E ratio for 3+ consecutive years using `LAG(de_ratio, 1)` and `LAG(de_ratio, 2)`. Counts firms deleveraging during GDP contraction years versus expansion years to test whether deleveraging is pro-cyclical (occurs during stress) or counter-cyclical (occurs during recovery).

3. **Interest Coverage Sensitivity to Policy Rates:** For companies with 10+ years of data, calculates rolling 5-year correlation between Interest Coverage Ratio (EBITDA / Interest Expense) and domestic policy rate. Ranks companies by sensitivity score to identify rate-sensitive (high negative correlation) versus rate-insulated (near-zero correlation) firms, providing a data-driven alternative to sector-based classification.

## Use Case 3: Rate-Shock Solvency Stress Test (Point-in-Time + Scenario)

Measures rate sensitivity and identifies "zombie companies" through time using annual/quarterly financial statements and policy rate data. Demonstrates scenario analysis and early warning signals. Scope: non-financial companies only (`WHERE gics_sector_name != 'Financials'`).

1. **Zombie Companies (3-Year Persistence) with Macro Constraint:** Identifies companies with Interest Coverage Ratio < 1.5 for 3 consecutive years located in countries with declining GDP growth (negative slope over 3-year window). Uses `LAG()` and `LEAD()` to detect persistence. Joins with macro GDP table to filter by country-level growth trend. Point-in-time membership ensures only actively traded companies at each date are analyzed.

2. **200bp Rate Shock Scenario (Stress Testing):** Simulates a +200 basis point increase in policy rates. Recalculates interest expense assuming 50% floating-rate (reprices immediately) and 50% fixed. Recomputes Interest Coverage Ratio and Net Income under shocked rates. Flags companies transitioning from healthy (ratio > 2.0) to at-risk (ratio < 1.5). Compares shock impact across countries.

3. **Geographic Risk Concentration (Systemic Solvency Risk):** Ranks countries by percentage of companies below coverage threshold (< 1.5) and aggregate debt of zombie companies as % of country GDP. Identifies geographies with highest systemic solvency risk concentration, complementing Use Case 2's firm-level analysis.

## Use Case 4: Macro Lead-Lag & Business Cycle Sensitivity

Tests whether macro indicators lead corporate fundamentals with time lags and classifies companies by business cycle sensitivity using data-driven methods. Query 3 excludes financial companies due to FCF metric inapplicability; Queries 1–2 include all sectors.

1. **Housing Starts Lead Revenue (2-Quarter Lag Test):** Uses `LAG(housing_starts, 2) OVER (PARTITION BY country ORDER BY quarter)` to align lagged housing data with company revenue growth. Filters for companies with high consumer durables or home improvement exposure. Tests whether housing activity predicts revenue with a 6-month lag. Requires cross-frequency join: quarterly macro → quarterly/annual financials.

2. **Revenue Volatility as Cyclicality Proxy (Data-Driven Classification):** Computes 10-year rolling standard deviation of revenue growth using `STDDEV() OVER (PARTITION BY company ORDER BY year ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)`. Classifies companies into quartiles using `NTILE(4)`: High Volatility (Q4) represents cyclical firms, Low Volatility (Q1) represents defensive firms. Validates whether high-volatility firms underperform during GDP contraction years, providing an objective alternative to GICS-based labels.

3. **Downturn Resilience (Cash Flow Focus):** Identifies GDP contraction quarters (YoY GDP growth < 0). Lists companies that maintained positive Free Cash Flow despite negative revenue growth. Computes resilience rate by country: (# of resilient firms) / (# of total firms with negative revenue). Compares resilience patterns across US, UK, and other markets.

## Use Case 5: Sector Rotation & Inflation Regime Analysis

Analyzes how GICS sectors perform across macroeconomic regimes (inflation environments, rate cycles) and identifies sector rotation patterns that lead or lag macro indicators. Uses weekly price data, GICS classification, and macro indicators (CPI, policy rates). All sectors included. Complements firm-level analyses (UC2–UC4) by providing sector-level insights for portfolio allocation.

1. **Sector Performance by Inflation Regime (High vs Low CPI):** Classifies each month into High Inflation (CPI YoY > 3%) versus Low Inflation (CPI YoY ≤ 3%) using `CASE WHEN cpi_yoy > 3 THEN 'High' ELSE 'Low' END`. Calculates average monthly returns by GICS sector for each regime using `AVG(sector_return) OVER (PARTITION BY sector, inflation_regime)`. Identifies inflation winners (Energy, Materials) versus inflation losers (Utilities, Real Estate). Tests whether defensive sectors outperform during high-inflation periods.

2. **Sector-CPI Lead-Lag Relationship:** Computes rolling 12-month correlation between each sector's monthly return and CPI changes (contemporaneous and lagged) using `LAG(cpi_change, n) OVER (ORDER BY month)` for n = 0, 1, 2, 3 months. Identifies leading sectors (returns predict future CPI) and lagging sectors (returns respond to past CPI). Ranks sectors by lead-lag coefficient to provide timing signals for sector rotation strategies.

3. **Rate Sensitivity by Sector (Duration Proxy):** Calculates rolling 2-year beta of sector returns against 10-year Treasury yield changes. Uses weekly sector returns aggregated from constituent stocks (market-cap weighted where available, equal-weighted otherwise) and `CORR(sector_return, yield_change) OVER (PARTITION BY sector ORDER BY week ROWS BETWEEN 103 PRECEDING AND CURRENT ROW)`. Identifies rate-sensitive sectors (negative beta: Utilities, Real Estate, REITs) versus rate-insensitive sectors (Financials benefit from higher rates). Compares whether sector sensitivities change across different rate regimes.
