#!/usr/bin/env python3
"""
MacroAlpha ETL Import Script
=============================
Converts Bloomberg Excel exports to SQLite database.

Data Sources:
- company_master.csv          → companies table
- index_membership_snapshot.csv → index_membership table
- price_weekly.xlsx.xlsx      → prices_weekly table
- financials_annual.xlsx      → financials table (period_type='ANNUAL')
- financials_quarterly.xlsx   → financials table (period_type='QUARTERLY')
- usa/uk/de/jp/cn_macros_*.xlsx → macro_indicators table
- 5 countries 10y yield...xlsx → interest_rates table

Usage:
    python etl_import.py
"""

import pandas as pd
import sqlite3
import warnings
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import re

warnings.filterwarnings('ignore')

# Configuration
DB_PATH = "macroalpha.db"
DATA_DIR = Path(".")

# ============================================================================
# Helper Functions
# ============================================================================

def clean_value(val):
    """Convert Bloomberg N/A values to None."""
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    if val_str in ['#N/A', '--', '#N/A Requesting Data...', 'N/A', '']:
        return None
    try:
        return float(val_str.replace(',', ''))
    except ValueError:
        return val_str


def parse_bloomberg_date(date_val) -> Optional[str]:
    """Parse various date formats to YYYY-MM-DD string."""
    if pd.isna(date_val):
        return None
    
    if isinstance(date_val, datetime):
        return date_val.strftime('%Y-%m-%d')
    
    date_str = str(date_val).strip()
    
    # Try common formats
    formats = [
        '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y',
        '%Y/%m/%d', '%d-%m-%Y', '%m-%d-%Y'
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    return None


def create_database(conn):
    """Create database schema."""
    print("📦 Creating database schema...")
    
    with open("schema.sql", "r") as f:
        schema_sql = f.read()
    
    # Execute schema (SQLite version)
    conn.executescript(schema_sql)
    conn.commit()
    print("   ✓ Schema created")


# ============================================================================
# Import: Company Master
# ============================================================================

def import_companies(conn):
    """Import company_master.csv → companies table."""
    print("\n🏢 Importing companies...")
    
    df = pd.read_csv(DATA_DIR / "company_master.csv", skiprows=[0])
    
    records = []
    for _, row in df.iterrows():
        ticker = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else None
        if not ticker or ticker == '#N/A':
            continue
            
        records.append({
            'ticker': ticker,
            'company_name': row.get('NAME'),
            'country_id': row.get('COUNTRY', '')[:2] if pd.notna(row.get('COUNTRY')) else None,
            'currency': row.get('CRNCY'),
            'gics_sector_name': clean_value(row.get('GICS_SECTOR_NAME')),
            'gics_industry_group_name': clean_value(row.get('GICS_INDUSTRY_GROUP_NAME')),
            'gics_industry_name': clean_value(row.get('GICS_INDUSTRY_NAME')),
            'gics_sub_industry_name': clean_value(row.get('GICS_SUB_INDUSTRY_NAME')),
            'current_market_cap': clean_value(row.get('CUR_MKT_CAP')),
            'is_active': True
        })
    
    cursor = conn.cursor()
    for r in records:
        cursor.execute("""
            INSERT OR IGNORE INTO companies 
            (ticker, company_name, country_id, currency, 
             gics_sector_name, gics_industry_group_name, 
             gics_industry_name, gics_sub_industry_name,
             current_market_cap, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (r['ticker'], r['company_name'], r['country_id'], r['currency'],
              r['gics_sector_name'], r['gics_industry_group_name'],
              r['gics_industry_name'], r['gics_sub_industry_name'],
              r['current_market_cap'], r['is_active']))
    
    conn.commit()
    print(f"   ✓ Imported {len(records)} companies")
    
    return {r['ticker']: i+1 for i, r in enumerate(records)}  # ticker -> company_id mapping


# ============================================================================
# Import: Index Membership
# ============================================================================

def import_index_membership(conn, ticker_to_id):
    """Import index_membership_snapshot.csv → index_membership table."""
    print("\n📊 Importing index membership...")
    
    df = pd.read_csv(DATA_DIR / "index_membership_snapshot.csv")
    
    cursor = conn.cursor()
    count = 0
    
    for _, row in df.iterrows():
        ticker = str(row['Ticker']).strip()
        index_id = row['index_id']
        
        # Get company_id
        company_id = ticker_to_id.get(ticker)
        if not company_id:
            # Try to find by inserting
            cursor.execute("SELECT company_id FROM companies WHERE ticker = ?", (ticker,))
            result = cursor.fetchone()
            if result:
                company_id = result[0]
            else:
                continue  # Skip if company not found
        
        # Parse date
        as_of_date = parse_bloomberg_date(row['as_of_date'])
        if not as_of_date:
            continue
        
        # Parse weight and shares
        weight = clean_value(row['Weight'])
        shares = clean_value(row['Shares'])
        price = clean_value(row['Price'])
        
        cursor.execute("""
            INSERT OR IGNORE INTO index_membership 
            (index_id, company_id, as_of_date, weight, shares_outstanding, price)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (index_id, company_id, as_of_date, weight, shares, price))
        count += 1
    
    conn.commit()
    print(f"   ✓ Imported {count} membership records")


# ============================================================================
# Import: Weekly Prices (Bloomberg Wide Table)
# ============================================================================

def import_prices_weekly(conn, ticker_to_id):
    """Import price_weekly.xlsx.xlsx → prices_weekly table."""
    print("\n📈 Importing weekly prices...")
    
    df = pd.read_excel(DATA_DIR / "price_weekly.xlsx.xlsx", header=None)
    
    # Structure:
    # Row 3: Tickers (every other column: 1, 3, 5, ...)
    # Row 4: Field names ("Last Price", "Day to Day Total Return...")
    # Row 6+: Data (col 0 = date, col 1+ = values)
    # 
    # Pattern: col 1 = ticker1 price, col 2 = ticker1 return
    #          col 3 = ticker2 price, col 4 = ticker2 return, etc.
    
    ticker_row = df.iloc[3]
    field_row = df.iloc[4]
    
    # Build ticker -> column mapping
    # Tickers appear at odd columns (1, 3, 5, ...) with 2 fields each
    ticker_cols = {}  # ticker -> {'price_col': int, 'return_col': int}
    
    col = 1
    while col < len(ticker_row):
        ticker = str(ticker_row.iloc[col]).strip() if pd.notna(ticker_row.iloc[col]) else None
        
        if ticker and ticker not in ['nan', '#N/A Requesting Data...']:
            field1 = str(field_row.iloc[col]).strip() if col < len(field_row) and pd.notna(field_row.iloc[col]) else ''
            field2 = str(field_row.iloc[col+1]).strip() if col+1 < len(field_row) and pd.notna(field_row.iloc[col+1]) else ''
            
            ticker_cols[ticker] = {
                'price_col': col if 'Price' in field1 else (col+1 if 'Price' in field2 else col),
                'return_col': col+1 if 'Return' in field2 else (col if 'Return' in field1 else col+1)
            }
        
        col += 2  # Move to next ticker (2 columns per ticker)
    
    print(f"   Found {len(ticker_cols)} tickers in price file")
    
    cursor = conn.cursor()
    count = 0
    matched = 0
    
    # Process data rows
    for row_idx in range(6, len(df)):
        date_val = df.iloc[row_idx, 0]
        price_date = parse_bloomberg_date(date_val)
        if not price_date:
            continue
        
        for ticker, cols in ticker_cols.items():
            company_id = ticker_to_id.get(ticker)
            if not company_id:
                cursor.execute("SELECT company_id FROM companies WHERE ticker = ?", (ticker,))
                result = cursor.fetchone()
                if result:
                    company_id = result[0]
                    ticker_to_id[ticker] = company_id
                else:
                    continue
            
            if matched == 0:
                matched = 1
            
            price_col = cols.get('price_col')
            return_col = cols.get('return_col')
            
            close_price = clean_value(df.iloc[row_idx, price_col]) if price_col and price_col < df.shape[1] else None
            total_return = clean_value(df.iloc[row_idx, return_col]) if return_col and return_col < df.shape[1] else None
            
            if close_price is not None:
                cursor.execute("""
                    INSERT OR IGNORE INTO prices_weekly 
                    (company_id, price_date, close_price, total_return)
                    VALUES (?, ?, ?, ?)
                """, (company_id, price_date, close_price, total_return))
                count += 1
        
        if row_idx % 200 == 0:
            conn.commit()
            print(f"   ... processed {row_idx - 5} weeks, {count} records")
    
    conn.commit()
    print(f"   ✓ Imported {count} price records ({matched} tickers matched)")


# ============================================================================
# Import: Financials (Bloomberg Wide Table)
# ============================================================================

def import_financials(conn, ticker_to_id, filename, period_type):
    """Import financials Excel → financials table.
    
    Note: Excel files should have complete dates in column A (run fix_dates.py first).
    """
    print(f"\n💰 Importing financials ({period_type})...")
    
    df = pd.read_excel(DATA_DIR / filename, header=None)
    
    # Structure:
    # Row 3: Tickers (every 7 columns)
    # Row 5: Field names (7 fields per ticker)
    # Row 6: Header "Dates"
    # Row 7+: Data (col 0 = date, col 1+ = values)
    
    ticker_row = df.iloc[3]
    field_row = df.iloc[5]
    
    # Field mapping
    field_map = {
        'SALES_REV_TURN': 'revenue',
        'EBITDA': 'ebitda',
        'IS_INT_EXPENSE': 'interest_expense',
        'CF_FREE_CASH_FLOW': 'free_cash_flow',
        'GROSS_PROFIT': 'gross_profit',
        'SHORT_AND_LONG_TERM_DEBT': 'total_debt',
        'ARD_COST_OF_GOODS_SOLD': 'cost_of_goods_sold'
    }
    
    # Build ticker -> field -> column mapping
    fields_per_ticker = 7
    num_tickers = (len(ticker_row) - 1) // fields_per_ticker
    
    ticker_fields = {}
    
    for t_idx in range(num_tickers):
        base_col = 1 + t_idx * fields_per_ticker
        ticker = str(ticker_row.iloc[base_col]).strip() if pd.notna(ticker_row.iloc[base_col]) else None
        
        if ticker and ticker != '#N/A Requesting Data...':
            ticker_fields[ticker] = {}
            for f_idx in range(fields_per_ticker):
                col = base_col + f_idx
                if col < len(field_row):
                    field = str(field_row.iloc[col]).strip() if pd.notna(field_row.iloc[col]) else None
                    if field and field in field_map:
                        ticker_fields[ticker][field_map[field]] = col
    
    print(f"   Found {len(ticker_fields)} tickers")
    
    cursor = conn.cursor()
    count = 0
    
    # Process data rows (Excel row 7 = df.iloc[6], first data row is 2005)
    # Excel row 6 is "Dates" header = df.iloc[5]
    for row_idx in range(6, len(df)):
        # Get date from column 0 (dates are now complete after fix_dates.py)
        date_val = df.iloc[row_idx, 0]
        period_end_date = parse_bloomberg_date(date_val)
        
        if not period_end_date:
            continue  # Skip rows without valid dates
        
        for ticker, field_cols in ticker_fields.items():
            company_id = ticker_to_id.get(ticker)
            if not company_id:
                cursor.execute("SELECT company_id FROM companies WHERE ticker = ?", (ticker,))
                result = cursor.fetchone()
                if result:
                    company_id = result[0]
                    ticker_to_id[ticker] = company_id
                else:
                    continue
            
            # Extract field values
            values = {field: clean_value(df.iloc[row_idx, col]) for field, col in field_cols.items()}
            
            # Skip if all values are None
            if all(v is None for v in values.values()):
                continue
            
            cursor.execute("""
                INSERT OR REPLACE INTO financials 
                (company_id, period_end_date, period_type,
                 revenue, ebitda, interest_expense, free_cash_flow,
                 gross_profit, total_debt, cost_of_goods_sold, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                company_id, period_end_date, period_type,
                values.get('revenue'), values.get('ebitda'),
                values.get('interest_expense'), values.get('free_cash_flow'),
                values.get('gross_profit'), values.get('total_debt'),
                values.get('cost_of_goods_sold'), None
            ))
            count += 1
    
    conn.commit()
    print(f"   ✓ Imported {count} financial records")


# ============================================================================
# Import: Macro Indicators (Bloomberg ECST Format)
# ============================================================================

def import_macro(conn, filename, country_id):
    """Import macro Excel → macro_indicators table."""
    print(f"\n🌍 Importing macro ({country_id})...")
    
    df = pd.read_excel(DATA_DIR / filename, header=None)
    
    # Structure:
    # Row 0: Empty
    # Row 1: Header (Text, Ticker, Dec, Nov, Oct, ...)
    # Row 2+: Data (indicator_name, bloomberg_ticker, values...)
    
    # Build date mapping: column index -> date
    # Dates go from newest (2024-12) to oldest (2005-01)
    num_months = df.shape[1] - 2  # Exclude first 2 columns
    date_map = {}
    
    # Start from 2024-12 and go backwards
    start_date = datetime(2024, 12, 1)
    for col_offset in range(num_months):
        col = 2 + col_offset
        month_offset = col_offset
        target_date = start_date - timedelta(days=month_offset * 30)  # Approximate
        # More precise: calculate year and month
        year = 2024 - (col_offset // 12)
        month = 12 - (col_offset % 12)
        if month <= 0:
            month += 12
            year -= 1
        date_map[col] = f"{year}-{month:02d}-01"
    
    cursor = conn.cursor()
    count = 0
    
    # Process indicator rows
    for row_idx in range(2, len(df)):
        indicator_name = str(df.iloc[row_idx, 0]).strip() if pd.notna(df.iloc[row_idx, 0]) else None
        bloomberg_ticker = str(df.iloc[row_idx, 1]).strip() if pd.notna(df.iloc[row_idx, 1]) else None
        
        if not indicator_name or indicator_name == 'nan':
            continue
        
        # Determine category from indicator name
        category = None
        name_lower = indicator_name.lower()
        if 'gdp' in name_lower:
            category = 'GDP'
        elif 'cpi' in name_lower or 'price' in name_lower or 'inflation' in name_lower:
            category = 'CPI'
        elif 'unemploy' in name_lower or 'employ' in name_lower:
            category = 'Employment'
        elif 'housing' in name_lower or 'construction' in name_lower:
            category = 'Housing'
        elif 'rate' in name_lower or 'yield' in name_lower:
            category = 'Rates'
        elif 'trade' in name_lower or 'export' in name_lower or 'import' in name_lower:
            category = 'Trade'
        else:
            category = 'Other'
        
        # Process each month
        for col in range(2, df.shape[1]):
            if col not in date_map:
                continue
            
            value = clean_value(df.iloc[row_idx, col])
            if value is None:
                continue
            
            cursor.execute("""
                INSERT OR IGNORE INTO macro_indicators 
                (country_id, indicator_date, indicator_name, bloomberg_ticker,
                 indicator_value, indicator_category)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                country_id, date_map[col], indicator_name,
                bloomberg_ticker, value, category
            ))
            count += 1
    
    conn.commit()
    print(f"   ✓ Imported {count} macro records")


# ============================================================================
# Import: Interest Rates
# ============================================================================

def import_interest_rates(conn):
    """Import 5 countries 10y yield and policy rate.xlsx → interest_rates table."""
    print("\n💹 Importing interest rates...")
    
    df = pd.read_excel(DATA_DIR / "5 countries 10y yield and policy rate.xlsx", header=None)
    
    # Structure:
    # Row 3: Tickers (USGG10YR Index, GTGBP10Y Govt, ..., FDTR Index, ...)
    # Row 4: Field names (Last Price)
    # Row 6+: Data (col 0 = date, col 1+ = values)
    
    # Column mapping (from earlier analysis)
    col_map = {
        1: ('US', '10Y_YIELD', 'USGG10YR Index'),
        2: ('GB', '10Y_YIELD', 'GTGBP10Y Govt'),
        3: ('DE', '10Y_YIELD', 'GTDEM10Y Govt'),
        4: ('JP', '10Y_YIELD', 'GTJPY10Y Govt'),
        5: ('CN', '10Y_YIELD', 'GTCNY10Y Govt'),
        6: ('US', 'POLICY_RATE', 'FDTR Index'),
        7: ('GB', 'POLICY_RATE', 'UKBRBASE Index'),
        8: ('DE', 'POLICY_RATE', 'EURR002W Index'),
        9: ('JP', 'POLICY_RATE', 'BOJDTR Index'),
        10: ('CN', 'POLICY_RATE', 'PBOC7P Index'),
    }
    
    cursor = conn.cursor()
    count = 0
    
    for row_idx in range(6, len(df)):
        date_val = df.iloc[row_idx, 0]
        rate_date = parse_bloomberg_date(date_val)
        if not rate_date:
            continue
        
        for col, (country_id, rate_type, ticker) in col_map.items():
            if col >= df.shape[1]:
                continue
            
            value = clean_value(df.iloc[row_idx, col])
            if value is None:
                continue
            
            cursor.execute("""
                INSERT OR IGNORE INTO interest_rates 
                (country_id, rate_date, rate_type, bloomberg_ticker, rate_value)
                VALUES (?, ?, ?, ?, ?)
            """, (country_id, rate_date, rate_type, ticker, value))
            count += 1
    
    conn.commit()
    print(f"   ✓ Imported {count} rate records")


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 70)
    print("🚀 MacroAlpha ETL Import")
    print("=" * 70)
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Create schema
        create_database(conn)
        
        # Import in order
        ticker_to_id = import_companies(conn)
        import_index_membership(conn, ticker_to_id)
        import_prices_weekly(conn, ticker_to_id)
        
        # Import financials
        import_financials(conn, ticker_to_id, "financials_annual.xlsx", "ANNUAL")
        if Path(DATA_DIR / "financials_quarterly.xlsx").exists():
            import_financials(conn, ticker_to_id, "financials_quarterly.xlsx", "QUARTERLY")
        
        # Import macro
        macro_files = [
            ("usa_macros_2024~2005.xlsx", "US"),
            ("uk_macros_2024~2005.xlsx", "GB"),
            ("de_macros_2024~2005.xlsx", "DE"),
            ("jp_macros_2024~2005.xlsx", "JP"),
            ("cn_macros_2024~2005.xlsx", "CN"),
        ]
        for filename, country_id in macro_files:
            if Path(DATA_DIR / filename).exists():
                import_macro(conn, filename, country_id)
        
        # Import interest rates
        import_interest_rates(conn)
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 Import Summary")
        print("=" * 70)
        
        cursor = conn.cursor()
        tables = ['companies', 'index_membership', 'prices_weekly', 
                  'financials', 'macro_indicators', 'interest_rates']
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"   {table}: {count:,} records")
        
        print("\n✅ ETL Complete! Database saved to:", DB_PATH)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    main()

