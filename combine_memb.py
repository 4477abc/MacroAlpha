import re
from pathlib import Path
import pandas as pd

# === 配置：当前目录就是 MacroAlpha（你在里面运行脚本）===
folder = Path(".")

# 抓取文件：SPX + UKX
files = sorted(list(folder.glob("SPX as of*.xlsx")) + list(folder.glob("UKX as of*.xlsx")))

# 过滤掉 Excel 的临时文件（~$ 开头）
files = [f for f in files if f.is_file() and not f.name.startswith("~$")]

rows = []

for f in files:
    # 从文件名前 3 个字符得到指数：SPX / UKX
    index_id = f.name[:3]

    # 从文件名提取年份：2005~2024（兼容末尾多了个 1 的情况）
    m = re.search(r"(20\d{2})", f.name)
    if not m:
        raise ValueError(f"Cannot find year in filename: {f.name}")
    year = int(m.group(1))

    # 你现在导出的都是年末 as-of；先固定成 12/31（后续也可以改成真实最后交易日）
    as_of_date = f"{year}-12-31"

    # === 方案1核心：强制使用 openpyxl 引擎 ===
    df = pd.read_excel(f, engine="openpyxl")

    # 清理列名空格
    df.columns = [str(c).strip() for c in df.columns]

    # 只保留你截图里常见的列（有就保留，没有就跳过）
    keep = [c for c in ["Ticker", "Name", "Weight", "Shares", "Price"] if c in df.columns]
    if "Ticker" not in keep:
        raise ValueError(f"{f.name}: missing 'Ticker' column, got columns={df.columns.tolist()}")

    df = df[keep].copy()

    # 去掉空行
    df = df[df["Ticker"].notna()]
    df["Ticker"] = df["Ticker"].astype(str).str.strip()

    if "Name" in df.columns:
        df["Name"] = df["Name"].astype(str).str.strip()

    # 加上两列：index_id + as_of_date
    df.insert(0, "index_id", index_id)
    df.insert(1, "as_of_date", as_of_date)

    rows.append(df)

# 合并全部文件
out = pd.concat(rows, ignore_index=True)

# 去重：同一指数同一日期同一 ticker 不应重复
out = out.drop_duplicates(subset=["index_id", "as_of_date", "Ticker"])

# 保存
out.to_csv("index_membership_snapshot.csv", index=False)
print("Saved: index_membership_snapshot.csv")
print("Total rows:", len(out))
print("Total files processed:", len(files))
