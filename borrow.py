import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import os
import re


# ===== 找最近交易日（最多往前找30天）=====
def get_valid_date(offset_start=1):
    tz = pytz.timezone("Asia/Taipei")
    now = datetime.now(tz)

    for i in range(offset_start, offset_start + 30):
        d = (now - timedelta(days=i)).strftime("%Y%m%d")
        try:
            url = f"https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={d}"
            res = requests.get(url, timeout=10)
            data = res.json()

            if data.get("stat") == "OK" and data.get("data"):
                return d
        except:
            continue
    return None


# ===== 借券資料（含 retry + 正確欄位）=====
def get_borrow(date):
    url = f"https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={date}"

    for _ in range(3):
        try:
            res = requests.get(url, timeout=10)
            data = res.json()

            if not data.get("data") or not data.get("fields"):
                continue

            df = pd.DataFrame(data["data"], columns=data["fields"])

            if "證券代號" not in df.columns:
                return pd.DataFrame(columns=["證券代號","證券名稱","餘額"])

            df["證券代號"] = df["證券代號"].astype(str).str.zfill(4)

            # ⭐ 固定抓「借券 當日餘額」（第12欄）
            try:
                target_col = df.columns[12]
            except:
                return pd.DataFrame(columns=["證券代號","證券名稱","餘額"])

            df["餘額"] = (
                df[target_col]
                .astype(str)
                .str.replace(",", "")
                .replace("", "0")
                .astype(float)
            )

            return df[["證券代號", "證券名稱", "餘額"]]

        except:
            continue

    return pd.DataFrame(columns=["證券代號","證券名稱","餘額"])


# ===== 讀 cap.csv =====
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
    today = get_valid_date(1)
    yesterday = get_valid_date(2)

    if not today or not yesterday:
        return None, "⚠️ 無有效交易日資料"

    t = get_borrow(today)
    y = get_borrow(yesterday)
    cap = get_cap()

    # ⭐ API壞掉 → 不更新
    if t.empty or y.empty:
        print("⚠️ API失敗，本次不更新")
        return None, "⚠️ 今日資料尚未更新"

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

    # ⭐ 移除 * 股票
    df = df[~df["證券名稱_t"].str.contains(r"\*", na=False)]

    df = df.sort_values(by="使用率", ascending=False).head(30)
    df.insert(0, "排名", range(1, len(df)+1))

    df["使用率(%)"] = df["使用率"].map("{:.2f}".format)
    df["增加量"] = df["增加量"].map("{:+,.0f}".format)
    df["餘額"] = df["餘額_t"].map("{:,.0f}".format)

    display_date = f"{today[:4]}-{today[4:6]}-{today[6:]}"
    return df[["排名","證券代號","證券名稱_t","餘額","增加量","使用率(%)","動作"]], f"📅 {display_date}"


# ===== HTML =====
def generate_html(df, msg):
    now = datetime.now(pytz.timezone("Asia/Taipei")).strftime("%Y-%m-%d %H:%M")

    # ⭐ API壞掉 → 不覆蓋
    if df is None or df.empty:
        print("⚠️ 無有效資料，不覆蓋 index.html")

        # 有舊資料 → 保留
        if os.path.exists("index.html"):
            with open("index.html", "r", encoding="utf-8") as f:
                old_html = f.read()

            m = re.search(r"📅 (\d{4}-\d{2}-\d{2})", old_html)
            if m:
                print(f"📅 保留舊資料日期: {m.group(1)}")
            return

        # 沒舊資料 → 建最小頁面
        html = f"""
        <html>
        <head><meta charset="UTF-8"></head>
        <body>
        <h2>📊 上市券賣監控</h2>
        <p>{msg if msg else "⚠️ 尚無資料（等待API恢復）"}</p>
        <p>更新時間：{now}</p>
        </body>
        </html>
        """
        with open("index.html","w",encoding="utf-8") as f:
            f.write(html)
        return

    rows = ""
    for _, r in df.iterrows():
        rate = float(r["使用率(%)"])

        style = ""
        if rate > 10:
            style = "background:#ffcccc;"
        elif rate > 8:
            style = "background:#fff3cd;"

        rows += f"""
        <tr style="{style}">
            <td>{r['排名']}</td>
            <td>{r['證券代號']}</td>
            <td>{r['證券名稱_t']}</td>
            <td>{r['餘額']}</td>
            <td>{r['增加量']}</td>
            <td>{r['使用率(%)']}</td>
            <td>{r['動作']}</td>
        </tr>
        """

    html = f"""
    <html>
    <head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="300">
    <style>
    body {{ font-family:sans-serif;background:#f5f5f5; }}
    .box {{ max-width:1000px;margin:auto;background:white;padding:20px }}
    table {{ width:100%;border-collapse:collapse }}
    th {{ background:#007aff;color:white;padding:10px }}
    td {{ text-align:center;padding:10px;border-bottom:1px solid #eee }}
    </style>
    </head>
    <body>
    <div class="box">
    <h2>📊 借券監控</h2>
    <p>{msg if msg else "⚠️ 尚無資料（等待API恢復）"}</p>
    <p>更新時間：{now}</p>
    <table>
    <tr>
    <th>排名</th><th>代號</th><th>名稱</th>
    <th>餘額</th><th>增加量</th><th>使用率</th><th>動作</th>
    </tr>
    {rows}
    </table>
    </div>
    </body>
    </html>
    """

    with open("index.html","w",encoding="utf-8") as f:
        f.write(html)


# ===== 執行 =====
if __name__ == "__main__":
    df, msg = build()
    generate_html(df, msg)
