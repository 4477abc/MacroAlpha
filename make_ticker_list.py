import pandas as pd

df = pd.read_csv("index_membership_snapshot.csv")

# 兼容你的列名：Ticker / ticker
ticker_col = "Ticker" if "Ticker" in df.columns else "ticker"

tickers = (
    df[ticker_col]
    .dropna()
    .astype(str)
    .str.strip()
    .drop_duplicates()
    .sort_values()
)

tickers.to_csv("tickers_unique.csv", index=False, header=["ticker"])
print("Saved tickers_unique.csv, unique tickers =", len(tickers))
