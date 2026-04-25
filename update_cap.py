import pandas as pd
import requests

# ===== 政府資料（上市公司基本資料，含股本）=====
url = "https://quality.data.gov.tw/dq_download_csv.php?nid=18419"

# 下載
df = pd.read_csv(url)

# ===== 找欄位（避免改名）=====
code_col = None
cap_col = None

for col in df.columns:
    if "代號" in col:
        code_col = col
    if "股本" in col:
        cap_col = col

if code_col is None or cap_col is None:
    raise Exception(f"❌ 找不到欄位: {df.columns}")

# ===== 整理 =====
df = df[[code_col, cap_col]].copy()
df.columns = ["證券代號", "股本"]

# ===== 清洗 =====
df["證券代號"] = df["證券代號"].astype(str).str.strip()

df["股本"] = (
    df["股本"]
    .astype(str)
    .str.replace(",", "")
    .replace("", "0")
    .astype(float)
)

# 過濾掉非股票（例如空白 / ETF / 無代號）
df = df[df["證券代號"].str.match(r"^\d{4}$")]

# ===== 存檔（給 borrow.py 用）=====
df.to_csv("cap.csv", index=False, encoding="utf-8-sig")

print(f"✅ cap.csv 更新完成，共 {len(df)} 筆")
