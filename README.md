# Project Proposal: MacroAlpha — Global Macroeconomic Sensitivity & Corporate Performance Analysis System (Point-in-Time)

## Topic (Database Application)

**MacroAlpha: Global Macroeconomic Sensitivity & Corporate Performance Analysis System**

MacroAlpha is an institutional-style “Top-Down” research database. Instead of analyzing firms in isolation, it models the dynamic mapping between **Macroeconomic Indicators** (GDP, CPI, yields, FX indexes) and **Corporate Fundamentals/Market Performance** (financial statements, solvency, margins, returns), while ensuring **point-in-time correctness** for index universes (e.g., S&P 500, FTSE 100) across long horizons.

**Project Goal**

* Quantify **macro sensitivity** (by sector, industry, and company) across cycles.
* Identify **defensive vs cyclical** exposures, inflation resilience, and rate-shock solvency risk.
* Support “what-if” scenario analysis with reproducible SQL queries on real datasets.

**Technical Complexity**

* Multi-granularity time series (weekly prices, quarterly macro, annual/quarterly financials) with alignment logic.
* Advanced SQL: **window functions** (LAG/LEAD/rolling windows), **complex joins** (country/industry/FX mappings), **recursive queries** (GICS hierarchy rollups), and **derived metrics** (growth, ratios, stress scenarios).

---

## Data Sources & Acquisition Strategy (Bloomberg Terminal)

### 1) Macro & Market Data (Bloomberg)

* **Macro indicators:** `<ECST>` for GDP, CPI, policy rates, sovereign yields across major economies (US, UK, DE, JP, CN).
* **FX & indexes:** DXY (and/or relevant home-currency indexes), government bond benchmarks (e.g., 10Y).
* **Equity market data:** **Weekly** price levels and returns for constituent equities plus index levels.
  - **Rationale for Weekly Frequency:** Weekly data provides optimal balance between:
    1. **Frequency matching:** Aligns better with quarterly macro indicators and annual/quarterly financial statements
    2. **Noise reduction:** Filters out intraday volatility and market microstructure noise
    3. **Sufficiency for analysis:** All proposed use cases (correlations, beta calculations, rolling windows) are fully supported by weekly granularity
    4. **Data manageability:** Reduces dimensionality while preserving analytical integrity (especially critical for 1000+ tickers over 20 years)

### 2) Corporate Fundamentals (Bloomberg) — *Point-in-Time & Cross-Sectional Standardization*

* **Financial statements & derived fields:** `<FA>` for standardized income statement / balance sheet / cash flow items (Revenue, EBITDA, Interest Expense, Debt, FCF, margins, ROE, etc.), across companies that appear in the index history.
* **Industry classification:** GICS sector/industry/sub-industry labels for hierarchical grouping.

### 3) Critical Addition: **Historical Index Membership (Point-in-Time Universe)**

To avoid survivorship bias, MacroAlpha will not use “today’s members”. Instead, we will ingest **historical index membership** for:

* **S&P 500** and **FTSE 100**
* with **effective date ranges** per security (entry date / exit date), optionally weights.

This dataset will be the backbone for all “index-based” analyses: for any date (t), the valid universe is:
`start_date <= t AND (end_date IS NULL OR end_date > t)`.

### Static ETL & Bloomberg Extraction Strategy

We will export Bloomberg results to cleaned CSV files and ingest into the relational database. The final submission runs fully locally using those files, reproducing all queries.

**Bloomberg Terminal Extraction Process:**

1. **Tool:** Spreadsheet Builder → Time Series Table
2. **Frequency:** Weekly (preferably Friday close / end-of-week)
3. **Fields:** Start with `PX_LAST` (closing price); additional fields as needed
4. **Batch Strategy:** To manage data volume (1000+ tickers × 20 years):
   - Extract in batches of 100-200 tickers per request
   - Concatenate locally to avoid Excel/Bloomberg limits
5. **Derived Calculations:** Compute returns, rolling correlations, and volatility measures in the database using SQL window functions rather than pre-computing in Bloomberg

---

## Core Schema Ideas (high level)

* `Company(company_id, ticker, name, country_id, currency, gics_sub_industry_id, ...)`
* `Index(index_id, name, currency, ...)`
* `Index_Membership(index_id, company_id, start_date, end_date, weight)`
* `Macro(country_id, date, indicator_id, value, frequency)`
* `Financials(company_id, fiscal_period_end, period_type, item_id, value, currency, ...)`
* `Prices(company_id, date, close, return)` — **Weekly frequency** (e.g., Friday close)
* `GICS_Hierarchy(node_id, parent_id, level, name)` (for recursive rollups)

---

# Use Cases & Queries (Updated)

## Use Case 1: Market Concentration & Point-in-Time Index Dynamics

**Goal:** Analyze market structure evolution and concentration trends using FTSE 100, demonstrating survivorship-bias-free analysis with complete Weight/Shares data.

**Rationale for UK Focus:** UKX provides complete historical Weight and Shares Outstanding data (unlike SPX where 83% of Weight/Shares are missing), enabling precise point-in-time calculations without data imputation. This showcases the methodology applicable to any market with complete data.

1. **Top-Heavy Concentration Trend (2005–2024):**
   Calculate the cumulative weight of Top 10 companies in FTSE 100 for each year-end; test whether UK market has become more concentrated over time. Uses `ROW_NUMBER() OVER (PARTITION BY year ORDER BY weight DESC)` to identify top holdings, then aggregate their weights. Correlate concentration ratio with UK GDP growth to test if concentration increases during economic stress.

2. **Herfindahl-Hirschman Index (HHI) by Year:**
   Compute market concentration index HHI = SUM(weight²) for each year-end membership snapshot; identify years of maximum/minimum concentration. Join with macro indicators (UK GDP growth, FTSE 100 returns) to analyze: does higher concentration predict lower/higher market returns? Uses point-in-time membership to avoid survivorship bias.

3. **Index Churn Analysis (Entry/Exit Dynamics):**
   Identify companies added to or removed from FTSE 100 each year using `LAG(membership_flag) OVER (PARTITION BY company ORDER BY year)`; compare the average valuation metrics (Price-to-Book, Market Cap) of "exited" vs "continuing" members. Test hypothesis: are index removals driven by fundamental deterioration or just relative size changes? Demonstrates complex temporal joins and point-in-time correctness.

## Use Case 2: Corporate Leverage Cycles & Financial Health Evolution

**Goal:** Analyze how corporate capital structure (leverage ratios) evolves across economic cycles, and identify companies whose debt burden creates vulnerability to rate shocks. This analysis does not require GICS sector classification, using data-driven groupings instead.

1. **Debt-to-Equity Ratio Distribution Evolution (2005–2024):**
   For each year, calculate the cross-sectional distribution of Debt-to-Equity ratios across all companies with available data. Compute key percentiles (P25, Median, P75, P90) using `PERCENTILE_CONT()`. Visualize how the distribution shifts during: (a) pre-2008 credit boom, (b) 2008–2009 deleveraging, (c) post-2010 recovery. Join with macro GDP growth to test: does leverage increase during expansions?

2. **Deleveraging Cycles Detection (Firm-Level):**
   Identify companies that reduced D/E ratio for 3+ consecutive years. Use `LAG(de_ratio, 1) OVER (PARTITION BY company ORDER BY year)` and `LAG(de_ratio, 2)` to detect persistent deleveraging. Count how many firms deleveraged during: (a) GDP contraction years vs (b) expansion years. Test hypothesis: is deleveraging pro-cyclical (occurs during stress) or counter-cyclical (occurs during recovery)?

3. **Interest Coverage Sensitivity to Policy Rates:**
   For each company with 10+ years of data, calculate the rolling 5-year correlation between Interest Coverage Ratio (EBITDA / Interest Expense) and the domestic policy rate. Identify "rate-sensitive" companies (high negative correlation) vs "rate-insulated" companies (near-zero correlation). Rank companies by sensitivity score; this provides a data-driven alternative to sector-based classification of "cyclical" firms. Uses window functions for rolling correlations.

## Use Case 3: Rate-Shock Solvency Stress Test (Point-in-Time + Scenario)

**Goal:** Measure rate sensitivity and identify "zombie companies" credibly through time. This analysis uses annual/quarterly financial statements + policy rate data; demonstrates scenario analysis and early warning signals.

1. **Zombie Companies (3-Year Persistence) with Macro Constraint:**
   Identify companies with Interest Coverage Ratio (EBITDA / Interest Expense) < 1.5 for 3 consecutive years **and** located in countries with declining GDP growth trend (negative slope over 3-year window). Uses `LAG()` and `LEAD()` window functions to detect 3-year persistence. Join with macro GDP table to filter by country-level growth trend. Point-in-time membership ensures only "actively traded" companies at each date are analyzed.

2. **200bp Rate Shock Scenario (Stress Testing):**
   Simulate a hypothetical +200 basis point increase in policy rates. Recalculate interest expense assuming: (a) 50% of debt is floating-rate and reprices immediately, (b) 50% is fixed. Recompute Interest Coverage Ratio and Net Income under shocked rates. Flag companies that transition from "healthy" (ratio > 2.0) to "at-risk" (ratio < 1.5) under the shock. Compare shock impact across countries (US vs UK vs others).

3. **Geographic Risk Concentration (Systemic Solvency Risk):**
   Rank **countries** (not sectors) by: (a) percentage of companies falling below coverage threshold (< 1.5), (b) aggregate debt of "zombie" companies as % of country GDP. Identify which geographies have the highest concentration of systemic solvency risk. This geographic lens complements Use Case 2's firm-level analysis. Optionally: use recursive CTE if analyzing parent-subsidiary structures across borders.

## Use Case 4: Macro Lead-Lag & Business Cycle Sensitivity

**Goal:** Test whether macro indicators lead corporate fundamentals with time lags, and classify companies by business cycle sensitivity using data-driven methods (without requiring GICS sector labels).

1. **Housing Starts Lead Revenue (2-Quarter Lag Test):**
   Use `LAG(housing_starts, 2) OVER (PARTITION BY country ORDER BY quarter)` to align lagged housing data with company revenue growth. Filter for companies with high "consumer durables" or "home improvement" exposure (identified via keywords in company name/description, or manually tagged subset). Test: does housing activity predict revenue with a 6-month lag? Requires cross-frequency join: quarterly macro → quarterly/annual financials.

2. **Revenue Volatility as Cyclicality Proxy (Data-Driven Classification):**
   Compute 10-year rolling standard deviation of revenue growth for each company using `STDDEV() OVER (PARTITION BY company ORDER BY year ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)`. Classify companies into quartiles using `NTILE(4)`: "High Volatility" (Q4) represents cyclical firms, "Low Volatility" (Q1) represents defensive firms. Validate classification: do high-volatility firms underperform during GDP contraction years? This provides an objective, data-driven alternative to GICS-based cyclical/defensive labels.

3. **Downturn Resilience (Cash Flow Focus):**
   Identify GDP contraction quarters (YoY GDP growth < 0). Within those quarters, list companies that maintained positive Free Cash Flow despite negative revenue growth. Compute "resilience rate" by country: (# of resilient firms) / (# of total firms with negative revenue). Compare: do US vs UK vs other markets show different resilience patterns? Demonstrates complex conditional logic and multi-table joins.

## Use Case 5: FX Sensitivity & International Exposure (Hedging Need Identification)

**Goal:** Quantify FX risk and identify firms where foreign exchange fluctuations materially impact earnings. This analysis uses weekly price data + annual financial disclosures.

1. **FX-Return Sensitivity (Point-in-Time Members, Weekly Data):**
   For multinational firms with disclosed foreign revenue exposure > 50%, compute rolling 3-year correlation between weekly stock returns and DXY Index (or home-currency index like GBP/USD for UK firms). Uses `CORR() OVER (PARTITION BY company ORDER BY week ROWS BETWEEN 155 PRECEDING AND CURRENT ROW)` for rolling correlations. Weekly frequency is sufficient for capturing FX beta while filtering noise. Identify "FX-exposed" firms (|correlation| > 0.3) vs "FX-neutral" firms.

2. **Earnings Hit Detection (Fundamental Impact):**
   Identify firms where reported FX losses (from financial footnotes or "FX impact on earnings" disclosures) reduced net income by >10% in years when domestic currency appreciated >5%. Cross-reference with currency movements from macro table. Break down by country (US vs UK vs others); optionally group by sector where GICS data is complete. Demonstrates join between financial data and FX macro data.

3. **FX Stress Scenario (Revenue Translation Risk):**
   Apply a hypothetical +10% domestic currency appreciation shock. Estimate revenue impact using disclosed "foreign revenue as % of total" from financial statements. Recalculate translated revenue assuming: Foreign Rev (USD) → Home Currency at shocked rate. Rank companies by revenue sensitivity (% revenue decline); compare "high-exposure" (>30% foreign revenue) vs "domestic-focused" (<10% foreign revenue) firms. Scenario analysis complements Use Case 3's rate-shock methodology.
