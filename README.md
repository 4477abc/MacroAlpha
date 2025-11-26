# Project Proposal: MacroAlpha — Global Macroeconomic Sensitivity & Corporate Performance Analysis System (Point-in-Time)

## Topic (Database Application)

**MacroAlpha: Global Macroeconomic Sensitivity & Corporate Performance Analysis System**

MacroAlpha is an institutional-style “Top-Down” research database. Instead of analyzing firms in isolation, it models the dynamic mapping between **Macroeconomic Indicators** (GDP, CPI, yields, FX indexes) and **Corporate Fundamentals/Market Performance** (financial statements, solvency, margins, returns), while ensuring **point-in-time correctness** for index universes (e.g., S&P 500, FTSE 100) across long horizons.

**Project Goal**

* Quantify **macro sensitivity** (by sector, industry, and company) across cycles.
* Identify **defensive vs cyclical** exposures, inflation resilience, and rate-shock solvency risk.
* Support “what-if” scenario analysis with reproducible SQL queries on real datasets.

**Technical Complexity**

* Multi-granularity time series (daily prices, quarterly macro, annual/quarterly financials) with alignment logic.
* Advanced SQL: **window functions** (LAG/LEAD/rolling windows), **complex joins** (country/industry/FX mappings), **recursive queries** (GICS hierarchy rollups), and **derived metrics** (growth, ratios, stress scenarios).

---

## Data Sources & Acquisition Strategy (Bloomberg Terminal)

### 1) Macro & Market Data (Bloomberg)

* **Macro indicators:** `<ECST>` for GDP, CPI, policy rates, sovereign yields across major economies (US, UK, DE, JP, CN).
* **FX & indexes:** DXY (and/or relevant home-currency indexes), government bond benchmarks (e.g., 10Y).
* **Equity market data:** daily/weekly price levels and returns for constituent equities plus index levels.

### 2) Corporate Fundamentals (Bloomberg) — *Point-in-Time & Cross-Sectional Standardization*

* **Financial statements & derived fields:** `<FA>` for standardized income statement / balance sheet / cash flow items (Revenue, EBITDA, Interest Expense, Debt, FCF, margins, ROE, etc.), across companies that appear in the index history.
* **Industry classification:** GICS sector/industry/sub-industry labels for hierarchical grouping.

### 3) Critical Addition: **Historical Index Membership (Point-in-Time Universe)**

To avoid survivorship bias, MacroAlpha will not use “today’s members”. Instead, we will ingest **historical index membership** for:

* **S&P 500** and **FTSE 100**
* with **effective date ranges** per security (entry date / exit date), optionally weights.

This dataset will be the backbone for all “index-based” analyses: for any date (t), the valid universe is:
`start_date <= t AND (end_date IS NULL OR end_date > t)`.

### Static ETL

We will export Bloomberg results to cleaned CSV files and ingest into the relational database. The final submission runs fully locally using those files, reproducing all queries.

---

## Core Schema Ideas (high level)

* `Company(company_id, ticker, name, country_id, currency, gics_sub_industry_id, ...)`
* `Index(index_id, name, currency, ...)`
* `Index_Membership(index_id, company_id, start_date, end_date, weight)`
* `Macro(country_id, date, indicator_id, value, frequency)`
* `Financials(company_id, fiscal_period_end, period_type, item_id, value, currency, ...)`
* `Prices(company_id, date, close, return)`
* `GICS_Hierarchy(node_id, parent_id, level, name)` (for recursive rollups)

---

# Use Cases & Queries (Updated)

## Use Case 1: Point-in-Time “Buffett Indicator” (Index-Based Market Cap / GDP)

**Goal:** Compare national equity valuation vs GDP without survivorship bias.

1. **Market Cap/GDP by country (2015–2024, point-in-time):**
   For each year-end date, aggregate total market cap of **that date’s** index members by country, join with nominal GDP for that country/year; output ratio.
2. **Undervalued countries + quality screen (ranking):**
   Find bottom 3 countries by MarketCap/GDP in each year; within those country universes, list top 5 companies by ROE (point-in-time membership at that year-end).
3. **Sector contribution during high GDP growth:**
   For years where GDP growth > 3%, compute which GICS sector contributed most to market cap growth, using recursion to roll up sub-industries → sectors.

## Use Case 2: Inflation Regimes & Margin Resilience (Regime Classification + Rolling Windows)

**Goal:** Identify “pricing power” using macro regime definitions.

1. **Define inflation regimes (window-based):**
   Mark periods as “High Inflation” when CPI YoY > 4% for at least 2 consecutive quarters (use window functions).
2. **Inflation survivors (3-year persistence):**
   Within high-inflation regimes, find companies whose **real revenue growth** (revenue growth − CPI) > 0 for 3 consecutive fiscal years.
3. **Margin protection by sector (comparative):**
   Compare gross margin change distributions between Consumer Staples vs Industrials during high inflation years; rank sectors by median margin stability.

## Use Case 3: Rate-Shock Solvency Stress Test (Point-in-Time + Scenario)

**Goal:** Measure rate sensitivity and identify “zombies” credibly through time.

1. **Zombie companies (3-year) with macro constraint:**
   Identify companies with interest coverage ratio < 1.5 for 3 consecutive years **and** in countries with declining GDP growth trend (e.g., negative slope over 3 years).
2. **200bp shock scenario (profit & coverage impact):**
   Recalculate interest expense assuming floating-rate debt reprices with +200bp; recompute coverage ratio and net income; flag newly-at-risk firms.
3. **Transition analysis (early warning):**
   Using `LAG()`, detect firms whose coverage ratio has deteriorated for 4 successive periods before becoming zombie; rank “most rapidly worsening” per sector.

## Use Case 4: Macro Lead-Lag & Sector Rotation Signals (Cross-Frequency Alignment)

**Goal:** Find whether macro indicators lead company fundamentals/returns with lags.

1. **Housing starts lead revenue (2-quarter lag, by industry):**
   Use `LAG()` on quarterly housing starts; test association with subsequent revenue growth of home improvement retailers, aligned by country and quarter.
2. **Cyclical vs defensive classification (volatility):**
   Compute 10Y rolling standard deviation of revenue growth per GICS sector; classify as cyclical/defensive; show how classification changes across regimes.
3. **Downturn resilience (cash flow focus):**
   During GDP contraction quarters, list companies with positive FCF despite negative revenue growth; compare prevalence across sectors.

## Use Case 5: FX Sensitivity & International Exposure (Hedging Need Identification)

**Goal:** Quantify FX risk and identify firms where FX materially hits earnings.

1. **FX-return sensitivity (point-in-time members):**
   For multinational firms with foreign revenue exposure > 50%, compute correlation between stock returns and DXY (or home FX index), in rolling 3Y windows.
2. **Earnings hit detection:**
   Find firms where FX losses reduce net income >10% in years where domestic currency appreciates >5%; break down by sector/country.
3. **FX stress scenario:**
   Apply a hypothetical +10% currency appreciation shock; estimate translated revenue impact (using disclosed foreign revenue share) and re-rank firms by sensitivity.
