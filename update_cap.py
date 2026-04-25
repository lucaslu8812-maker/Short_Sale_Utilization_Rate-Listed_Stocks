import pandas as pd
import requests

# ===== 用證交所資料（穩定）=====
url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

res = requests.get(url, timeout=10)

if res.status_code != 200:
    raise Exception("❌ API 失敗")

data = res.json()

df = pd.DataFrame(data)

# ===== 找欄位 =====
code_col = None
cap_col = None

for col in df.columns:
    if "公司代號" in col:
        code_col = col
    if "實收資本額" in col:
        cap_col = col

if code_col is None or cap_col is None:
    raise Exception(f"❌ 找不到欄位: {df.columns}")

# ===== 整理 =====
df = df[[code_col, cap_col]].copy()
df.columns = ["證券代號", "股本"]

# ===== 清洗 =====
df["證券代號"] = df["證券代號"].astype(str).str.zfill(4)

df["股本"] = (
    df["股本"]
    .astype(str)
    .str.replace(",", "")
    .replace("", "0")
    .astype(float)
)

# 👉 單位是「元」，轉成「億元」
df["股本"] = df["股本"] / 100000000

# ===== 過濾股票 =====
df = df[df["證券代號"].str.match(r"^\d{4}$")]

# ===== 存檔 =====
df.to_csv("cap.csv", index=False, encoding="utf-8-sig")

print(f"✅ cap.csv 更新完成，共 {len(df)} 筆")
