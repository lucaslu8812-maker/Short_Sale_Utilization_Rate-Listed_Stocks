import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz


# ===== 找最近N個有資料交易日（穩定版）=====
def get_last_n_valid_dates(n=2):
    tz = pytz.timezone("Asia/Taipei")
    now = datetime.now(tz)

    dates = []

    for i in range(1, 15):  # 最多往前找兩週
        d = (now - timedelta(days=i)).strftime("%Y%m%d")

        try:
            url = f"https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={d}"
            data = requests.get(url, timeout=10).json()

            if data.get("stat") == "OK" and data.get("data"):
                dates.append(d)

            if len(dates) >= n:
                return dates

        except:
            continue

    return dates


# ===== 借券賣出餘額（穩定抓欄位）=====
def get_borrow(date):
    url = f"https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={date}"
    data = requests.get(url).json()

    if not data.get("data") or not data.get("fields"):
        return pd.DataFrame(columns=["證券代號","證券名稱","餘額"])

    df = pd.DataFrame(data["data"], columns=data["fields"])

    df["證券代號"] = df["證券代號"].astype(str).str.zfill(4)

    # ⭐ 只在借券區塊找「當日餘額」
    borrow_cols = df.columns[8:]

    target_col = None
    for col in borrow_cols:
        if "當日餘額" in col:
            target_col = col
            break

    if target_col is None:
        print("❌ 找不到借券當日餘額:", df.columns)
        return pd.DataFrame(columns=["證券代號","證券名稱","餘額"])

    df["餘額"] = (
        df[target_col]
        .astype(str)
        .str.replace(",", "")
        .replace("", "0")
        .astype(float)
    )

    return df[["證券代號", "證券名稱", "餘額"]]


# ===== 股本 =====
def get_cap():
    try:
        df = pd.read_csv("cap.csv")
        df["證券代號"] = df["證券代號"].astype(str).str.zfill(4)

        cap_col = None
        for col in df.columns:
            if "股本" in col:
                cap_col = col
                break

        if cap_col is None:
            return pd.DataFrame(columns=["證券代號","發行股數"])

        df["股本"] = (
            df[cap_col]
            .astype(str)
            .str.replace(",", "")
            .replace("", "0")
            .astype(float)
        )

        df["發行股數"] = df["股本"] * 10_000_000

        return df[["證券代號", "發行股數"]]

    except:
        return pd.DataFrame(columns=["證券代號","發行股數"])


# ===== 主邏輯 =====
def build():
    dates = get_last_n_valid_dates(2)

    if len(dates) < 2:
        return None, "❌ 無資料"

    today, yesterday = dates[0], dates[1]

    t = get_borrow(today)
    y = get_borrow(yesterday)
    cap = get_cap()

    if t.empty or y.empty:
        return None, "❌ API資料異常"

    df = pd.merge(t, y, on="證券代號", suffixes=("_t", "_y"))

    if not cap.empty:
        df = pd.merge(df, cap, on="證券代號", how="left")

        df["發行股數"] = pd.to_numeric(df["發行股數"], errors="coerce")
        df["發行股數"] = df["發行股數"].replace(0, pd.NA)

        df["使用率"] = df["餘額_t"] / df["發行股數"] * 100
        df["使用率"] = df["使用率"].fillna(0)
    else:
        df["使用率"] = 0

    df["增加量"] = df["餘額_t"] - df["餘額_y"]

    def judge(x):
        if x > 0:
            return "加空"
        elif x < 0:
            return "回補"
        return "無"

    df["動作"] = df["增加量"].apply(judge)

    df = df.sort_values(by="使用率", ascending=False).head(30)
    df.insert(0, "排名", range(1, len(df)+1))

    df["使用率(%)"] = df["使用率"].map("{:.2f}".format)
    df["增加量"] = df["增加量"].map("{:+,.0f}".format)
    df["餘額"] = df["餘額_t"].map("{:,.0f}".format)

    display_date = f"{today[:4]}-{today[4:6]}-{today[6:]}"
    return df[["排名","證券代號","證券名稱_t","餘額","增加量","使用率(%)","動作"]], f"📅 {display_date}"
