Query Results Export
====================
Generated: 2024-11-28
Database: macroalpha.db

This directory contains CSV exports of key SQL query results from queries.sql.

Files:
------
1. uc1_q1_top10_concentration.csv (20 rows)
   - Top 10 companies' cumulative weight in FTSE 100 by year (2005-2024)
   - Shows market concentration trend

2. uc1_q2_hhi_concentration.csv (20 rows)
   - Herfindahl-Hirschman Index (HHI) calculation by year
   - Scale: 0-10,000 (actual range: 234-367)
   - Effective positions = 10,000 / HHI

3. uc2_q1_debt_to_revenue_distribution.csv (20 rows)
   - Debt-to-Revenue ratio distribution by year

4. uc2_q2_deleveraging_cycles.csv (172 rows)
   - Companies that reduced leverage for 3+ consecutive years
   - Grouped by year and sector

5. uc2_q3_icr_rate_sensitivity.csv (100 rows)
   - Rolling 5-year correlation between ICR and policy rates
   - Top 100 most rate-sensitive companies (sorted by correlation)
   - Classification: Highly/Moderately Sensitive, Rate-Insulated, Positively Correlated

6. uc3_q1_zombie_companies.csv (187 rows)
   - Companies with ICR < 1.5 by year and sector
   - "Zombie" companies struggling to cover interest expense

7. uc4_q2_revenue_volatility.csv (4 rows)
   - 10-year rolling STDDEV of revenue growth
   - Quartile classification: Defensive → Cyclical

8. uc5_q1_sector_inflation_performance.csv (2 rows)
   - High vs Low inflation regime classification
   - CPI YoY > 3% = High Inflation

Usage:
------
These CSV files can be:
- Imported into Excel/Google Sheets for further analysis
- Used for validation of visualizations
- Referenced in academic submissions
- Processed by other analysis tools

To regenerate:
--------------
Run: python export_results.py
(Uses conda base environment)

Data Source:
------------
All data extracted from macroalpha.db SQLite database
Original data from Bloomberg Excel exports (see main directory)
