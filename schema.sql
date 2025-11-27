-- ============================================================================
-- MacroAlpha Database Schema
-- Global Macroeconomic Sensitivity & Corporate Performance Analysis System
-- ============================================================================

-- 删除已存在的表（按依赖顺序）
DROP TABLE IF EXISTS prices_weekly;
DROP TABLE IF EXISTS financials;
DROP TABLE IF EXISTS macro_indicators;
DROP TABLE IF EXISTS interest_rates;
DROP TABLE IF EXISTS index_membership;
DROP TABLE IF EXISTS companies;
DROP TABLE IF EXISTS indices;
DROP TABLE IF EXISTS countries;
DROP TABLE IF EXISTS gics_sectors;

-- ============================================================================
-- 1. 基础维度表
-- ============================================================================

-- 国家表
CREATE TABLE countries (
    country_id VARCHAR(2) PRIMARY KEY,      -- US, GB, DE, JP, CN
    country_name VARCHAR(100) NOT NULL,
    currency VARCHAR(3) NOT NULL             -- USD, GBP, EUR, JPY, CNY
);

INSERT INTO countries (country_id, country_name, currency) VALUES
    ('US', 'United States', 'USD'),
    ('GB', 'United Kingdom', 'GBP'),
    ('DE', 'Germany', 'EUR'),
    ('JP', 'Japan', 'JPY'),
    ('CN', 'China', 'CNY');

-- GICS 行业分类表
CREATE TABLE gics_sectors (
    sector_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sector_name VARCHAR(100) NOT NULL,
    industry_group_name VARCHAR(100),
    industry_name VARCHAR(100),
    sub_industry_name VARCHAR(100)
);

-- 指数表
CREATE TABLE indices (
    index_id VARCHAR(10) PRIMARY KEY,       -- SPX, UKX
    index_name VARCHAR(100) NOT NULL,
    country_id VARCHAR(2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    FOREIGN KEY (country_id) REFERENCES countries(country_id)
);

INSERT INTO indices (index_id, index_name, country_id, currency) VALUES
    ('SPX', 'S&P 500', 'US', 'USD'),
    ('UKX', 'FTSE 100', 'GB', 'GBP');

-- ============================================================================
-- 2. 公司主数据表
-- ============================================================================

CREATE TABLE companies (
    company_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker VARCHAR(50) NOT NULL UNIQUE,     -- Bloomberg ticker (e.g., "AAPL UQ Equity")
    company_name VARCHAR(200),
    country_id VARCHAR(2),
    currency VARCHAR(3),
    gics_sector_name VARCHAR(100),
    gics_industry_group_name VARCHAR(100),
    gics_industry_name VARCHAR(100),
    gics_sub_industry_name VARCHAR(100),
    current_market_cap DECIMAL(20, 2),      -- 当前市值（可能为NULL，退市公司）
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (country_id) REFERENCES countries(country_id)
);

-- 创建索引加速查询
CREATE INDEX idx_companies_country ON companies(country_id);
CREATE INDEX idx_companies_sector ON companies(gics_sector_name);
CREATE INDEX idx_companies_ticker ON companies(ticker);

-- ============================================================================
-- 3. 指数成分股表（Point-in-Time）
-- ============================================================================

CREATE TABLE index_membership (
    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_id VARCHAR(10) NOT NULL,
    company_id INTEGER NOT NULL,
    as_of_date DATE NOT NULL,               -- 快照日期 (每年12月31日)
    weight DECIMAL(10, 6),                  -- 权重 (UKX有，SPX为NULL)
    shares_outstanding DECIMAL(20, 6),      -- 流通股数 (UKX有，SPX为NULL)
    price DECIMAL(15, 4),                   -- 当日价格
    FOREIGN KEY (index_id) REFERENCES indices(index_id),
    FOREIGN KEY (company_id) REFERENCES companies(company_id),
    UNIQUE(index_id, company_id, as_of_date)
);

CREATE INDEX idx_membership_date ON index_membership(as_of_date);
CREATE INDEX idx_membership_index ON index_membership(index_id);
CREATE INDEX idx_membership_company ON index_membership(company_id);

-- ============================================================================
-- 4. 周度价格表
-- ============================================================================

CREATE TABLE prices_weekly (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    price_date DATE NOT NULL,               -- 周五日期
    close_price DECIMAL(15, 4),             -- 收盘价 (PX_LAST)
    total_return DECIMAL(10, 6),            -- 日回报率 (DAY_TO_DAY_TOT_RETURN_GROSS_DVDS)
    FOREIGN KEY (company_id) REFERENCES companies(company_id),
    UNIQUE(company_id, price_date)
);

CREATE INDEX idx_prices_date ON prices_weekly(price_date);
CREATE INDEX idx_prices_company ON prices_weekly(company_id);
CREATE INDEX idx_prices_company_date ON prices_weekly(company_id, price_date);

-- ============================================================================
-- 5. 财务数据表（年度/季度合并）
-- ============================================================================

CREATE TABLE financials (
    financial_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    period_end_date DATE NOT NULL,          -- 财务期末日期
    period_type VARCHAR(10) NOT NULL,       -- 'ANNUAL' 或 'QUARTERLY'
    
    -- 核心财务指标
    revenue DECIMAL(20, 2),                 -- SALES_REV_TURN (营业收入)
    ebitda DECIMAL(20, 2),                  -- EBITDA
    interest_expense DECIMAL(20, 2),        -- IS_INT_EXPENSE (利息支出)
    free_cash_flow DECIMAL(20, 2),          -- CF_FREE_CASH_FLOW (自由现金流)
    gross_profit DECIMAL(20, 2),            -- GROSS_PROFIT (毛利润)
    total_debt DECIMAL(20, 2),              -- SHORT_AND_LONG_TERM_DEBT (总债务)
    cost_of_goods_sold DECIMAL(20, 2),      -- ARD_COST_OF_GOODS_SOLD (销售成本)
    
    -- 衍生指标（可在导入时计算或用SQL计算）
    -- interest_coverage_ratio = ebitda / interest_expense
    -- debt_to_equity_ratio = total_debt / (total_assets - total_debt)
    
    currency VARCHAR(3),                    -- 报告货币
    FOREIGN KEY (company_id) REFERENCES companies(company_id),
    UNIQUE(company_id, period_end_date, period_type)
);

CREATE INDEX idx_financials_date ON financials(period_end_date);
CREATE INDEX idx_financials_company ON financials(company_id);
CREATE INDEX idx_financials_type ON financials(period_type);

-- ============================================================================
-- 6. 宏观经济指标表
-- ============================================================================

CREATE TABLE macro_indicators (
    macro_id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_id VARCHAR(2) NOT NULL,
    indicator_date DATE NOT NULL,           -- 数据日期 (月度)
    indicator_name VARCHAR(100) NOT NULL,   -- 指标名称 (e.g., "Real GDP (qoq %)")
    bloomberg_ticker VARCHAR(50),           -- Bloomberg ticker (e.g., "GDP CQOQ Index")
    indicator_value DECIMAL(20, 6),         -- 指标值
    indicator_category VARCHAR(50),         -- 分类 (GDP, CPI, Employment, etc.)
    FOREIGN KEY (country_id) REFERENCES countries(country_id),
    UNIQUE(country_id, indicator_date, bloomberg_ticker)
);

CREATE INDEX idx_macro_date ON macro_indicators(indicator_date);
CREATE INDEX idx_macro_country ON macro_indicators(country_id);
CREATE INDEX idx_macro_name ON macro_indicators(indicator_name);
CREATE INDEX idx_macro_ticker ON macro_indicators(bloomberg_ticker);

-- ============================================================================
-- 7. 利率数据表
-- ============================================================================

CREATE TABLE interest_rates (
    rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_id VARCHAR(2) NOT NULL,
    rate_date DATE NOT NULL,                -- 周度日期
    rate_type VARCHAR(20) NOT NULL,         -- '10Y_YIELD' 或 'POLICY_RATE'
    bloomberg_ticker VARCHAR(50),           -- Bloomberg ticker
    rate_value DECIMAL(10, 6),              -- 利率值 (%)
    FOREIGN KEY (country_id) REFERENCES countries(country_id),
    UNIQUE(country_id, rate_date, rate_type)
);

CREATE INDEX idx_rates_date ON interest_rates(rate_date);
CREATE INDEX idx_rates_country ON interest_rates(country_id);
CREATE INDEX idx_rates_type ON interest_rates(rate_type);

-- ============================================================================
-- 8. 辅助视图（简化查询）
-- ============================================================================

-- 视图：公司完整信息（含国家）
CREATE VIEW v_company_details AS
SELECT 
    c.company_id,
    c.ticker,
    c.company_name,
    c.country_id,
    co.country_name,
    c.currency,
    c.gics_sector_name,
    c.gics_industry_group_name,
    c.is_active
FROM companies c
LEFT JOIN countries co ON c.country_id = co.country_id;

-- 视图：年度财务数据
CREATE VIEW v_financials_annual AS
SELECT 
    f.*,
    c.ticker,
    c.company_name,
    c.country_id,
    c.gics_sector_name,
    -- 计算 Interest Coverage Ratio
    CASE 
        WHEN f.interest_expense > 0 THEN f.ebitda / f.interest_expense
        ELSE NULL 
    END AS interest_coverage_ratio,
    -- 计算 Gross Margin
    CASE 
        WHEN f.revenue > 0 THEN f.gross_profit / f.revenue
        ELSE NULL 
    END AS gross_margin
FROM financials f
JOIN companies c ON f.company_id = c.company_id
WHERE f.period_type = 'ANNUAL';

-- 视图：Point-in-Time 指数成分（带公司信息）
CREATE VIEW v_index_members AS
SELECT 
    im.*,
    c.ticker,
    c.company_name,
    c.country_id,
    c.gics_sector_name,
    i.index_name
FROM index_membership im
JOIN companies c ON im.company_id = c.company_id
JOIN indices i ON im.index_id = i.index_id;

-- 视图：宏观指标（带国家名称）
CREATE VIEW v_macro_with_country AS
SELECT 
    m.*,
    c.country_name,
    c.currency
FROM macro_indicators m
JOIN countries c ON m.country_id = c.country_id;

-- ============================================================================
-- 9. 数据统计查询（验证用）
-- ============================================================================

-- 使用以下查询验证数据导入后的完整性：
/*
-- 公司数量
SELECT COUNT(*) as total_companies FROM companies;
SELECT country_id, COUNT(*) as count FROM companies GROUP BY country_id;

-- 指数成分数量
SELECT index_id, as_of_date, COUNT(*) as member_count 
FROM index_membership 
GROUP BY index_id, as_of_date 
ORDER BY index_id, as_of_date;

-- 价格数据覆盖
SELECT MIN(price_date), MAX(price_date), COUNT(DISTINCT company_id), COUNT(*) 
FROM prices_weekly;

-- 财务数据覆盖
SELECT period_type, MIN(period_end_date), MAX(period_end_date), COUNT(DISTINCT company_id), COUNT(*) 
FROM financials 
GROUP BY period_type;

-- 宏观数据覆盖
SELECT country_id, MIN(indicator_date), MAX(indicator_date), COUNT(DISTINCT indicator_name), COUNT(*) 
FROM macro_indicators 
GROUP BY country_id;
*/

