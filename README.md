# Project Proposal: MacroAlpha - Global Macroeconomic Sensitivity & Corporate Performance Analysis System

## Topic (Database Application)
**MacroAlpha: Global Macroeconomic Sensitivity & Corporate Performance Analysis System**

The **MacroAlpha** database application is designed to simulate an institutional-grade "Top-Down" investment research platform. Unlike standard financial databases that look at companies in isolation, MacroAlpha models the dynamic relationships between **Macroeconomic Indicators** (e.g., GDP, Inflation, Interest Rates) and **Microeconomic Corporate Fundamentals** (e.g., Revenue, Debt, Margins).

**Project Goal:**
The system aims to quantify the sensitivity of different industries and companies to economic cycles. It will allow analysts to identify "Recession-Proof" assets, simulate the impact of interest rate hikes on corporate solvency, and optimize sector allocation based on real-world data.

**Technical Complexity:**
The application will require a robust schema to handle data with different granularities (Quarterly Macro Data vs. Annual Financial Reports vs. Daily Market Data). It will necessitate advanced SQL techniques including **Window Functions** (for time-series analysis), **Complex Joins** (mapping macro trends to micro entities), and **Recursive Queries** (for supply chain or industry hierarchies).

---

## Data Sources & Acquisition Strategy

To ensure our database application simulates a real-world, institutional-grade environment, we have secured access to the **Bloomberg Terminal**, the gold standard for financial data integrity.

* **Description:** We will extract structured datasets using the Bloomberg Professional Service.
    * **Macro Data:** Function `<ECST>` (World Economic Statistics) for GDP, CPI, and Sovereign Yields across major economies (US, China, UK, DE, JP).
    * **Corporate Data:** Function `<EQS>` (Equity Screening) and `<FA>` (Financial Analysis) for standardized financial statements of S&P 500 and FTSE 100 constituents.
* **Why this source is chosen (Data Excellence):**
    * **High-Fidelity Normalization:** Unlike public web sources (e.g., Yahoo Finance) which often contain inconsistent formatting and missing values, Bloomberg provides **pre-normalized** data (e.g., standardizing fiscal years across different reporting jurisdictions). This allows for a rigorous Relational Schema design.
    * **Point-in-Time Accuracy:** The data accounts for historical restatements and corporate actions, ensuring mathematical accuracy for our time-series queries.
* **Accessibility & Reproducibility Strategy:**
    * To ensure the project is assessable without a Bloomberg license, we will perform a **static ETL (Extract-Transform-Load) process**.
    * We will export the query results from the terminal into cleaned **CSV flat files**. [cite_start]The final database submission will ingest these static files (consistent with the guideline allowing "data insertion from real datasets" [cite: 8]), allowing the grading team to reproduce all queries locally.

## Use Cases & Queries

### Use Case 1: The "Buffett Indicator" & Global Valuation Analysis
**Goal:** To analyze the relative valuation of national equity markets by comparing Total Market Capitalization to Nominal GDP, extending this analysis to specific industries.
* **Query 1 (Aggregation & Join):** Calculate the "Market Cap to GDP" ratio for each country for the years 2015-2024. This requires joining the `Macro_Economics` table with the `Companies` table and aggregating the total market cap by `Country_ID`.
* **Query 2 (Ranking):** Identify the "Top 3 Undervalued Countries" (lowest Market Cap/GDP ratio) and list the top 5 companies by ROE (Return on Equity) within those specific countries.
* **Query 3 (Sector Contribution):** Analyze which GICS Sector (e.g., Technology vs. Energy) contributed the most to the total market capitalization growth in years where National GDP growth exceeded 3%.

### Use Case 2: Inflation Resilience & Pricing Power Screening
**Goal:** To identify companies that can maintain or grow their profit margins during periods of high inflation (High CPI).
* **Query 1 (Statistical Correlation):** Calculate the correlation coefficient between the `National_CPI` (Consumer Price Index) and `Company_Gross_Margin` over a 10-year period for all companies in the "Consumer Staples" sector.
* **Query 2 (Window Function filtering):** Filter for "Inflation Survivors": Companies that achieved Revenue Growth higher than the National Inflation Rate (CPI) for 3 consecutive years during high-inflation periods (CPI > 4%).
* **Query 3 (Comparative Analysis):** Compare the average "Cost of Goods Sold (COGS)" growth rate between the "Luxury Goods" sector and the "Industrial Manufacturing" sector during inflationary years.

### Use Case 3: Debt Crisis Stress Testing (Solvency Analysis)
**Goal:** To simulate the impact of rising interest rates on corporate balance sheets and identify "Zombie Companies" at risk of bankruptcy.
* **Query 1 (Conditional Logic):** Identify "Zombie Companies": Select companies where the "Interest Coverage Ratio" (EBITDA / Interest Expense) has been less than 1.5 for 3 consecutive years, specifically in countries with declining GDP growth.
* **Query 2 (Simulation/Projection):** **Scenario Analysis:** Calculate the hypothetical `Net_Income` for all companies if the `Reference_Interest_Rate` (10-Year Treasury Yield) increases by 200 basis points (2%), assuming floating-rate debt costs rise proportionally.

### Use Case 4: Cyclical vs. Defensive Sector Rotation
**Goal:** To analyze the time-lag relationship between macroeconomic cycles and specific industry performance to guide investment rotation.
* **Query 1 (Time-Lag Analysis):** Use the `LAG()` window function to analyze if a decline in "Housing Starts" (Macro Indicator) predicts a decline in "Home Improvement Retailer Revenue" (Company Metric) with a 2-quarter delay.
* **Query 2 (Volatility Analysis):** Calculate the Standard Deviation of `Revenue_Growth` for each industry sector over the past 20 years to classify sectors as "Cyclical" (High Volatility) or "Defensive" (Low Volatility).
* **Query 3 (Growth Decomposition):** Analyze the composition of growth during GDP contractions: Identify companies where `Free_Cash_Flow` remained positive despite negative `Revenue_Growth`.

### Use Case 5: FX Sensitivity & International Exposure
**Goal:** To assess the impact of currency fluctuations on multinational corporations.
* **Query 1 (Correlation):** Identify companies with >50% "Foreign Revenue Exposure" and calculate the correlation between their Stock Price and the "Dollar Index (DXY)" (or their home currency index).
* **Query 2 (Impact Analysis):** Find all companies where "Foreign Exchange Losses" reduced Net Income by more than 10% in years where the domestic currency appreciated by >5%.
* **Query 3 (Data Transformation):** Adjust "Revenue per Capita" for multinational consumer companies using "PPP Conversion Factors" (Purchasing Power Parity) from the World Bank dataset to compare real market penetration across countries.
