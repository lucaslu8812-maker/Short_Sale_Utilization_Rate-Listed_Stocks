import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz


# ===== 找最近交易日 =====
def get_valid_date(offset_start=1):
    tz = pytz.timezone("Asia/Taipei")
    now = datetime.now(tz)

    for i in range(offset_start, offset_start + 7):
        d = (now - timedelta(days=i)).strftime("%Y%m%d")
        try:
            url = f"https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={d}"
            data = requests.get(url, timeout=10).json()
            if data.get("stat") == "OK" and data.get("data"):
                return d
        except:
            continue
    return None


# ===== 借券賣出餘額 =====
def get_borrow(date):
    url = f"https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={date}"
    data = requests.get(url).json()

    if not data.get("data") or not data.get("fields"):
        return pd.DataFrame(columns=["證券代號","證券名稱","餘額"])

    df = pd.DataFrame(data["data"], columns=data["fields"])

    # 過濾合計列
    df = df[~df["證券代號"].astype(str).str.contains("合計")]

    # ⭐ 統一代號格式
    df["證券代號"] = df["證券代號"].astype(str).str.zfill(4)

    # 找餘額欄
    target_col = None
    for col in df.columns:
        if "餘額" in col:
            target_col = col
            break

    if target_col is None:
        return pd.DataFrame(columns=["證券代號","證券名稱","餘額"])

    df["餘額"] = (
        df[target_col]
        .astype(str)
        .str.replace(",", "")
        .replace("", "0")
        .astype(float)
    )

    return df[["證券代號", "證券名稱", "餘額"]]


# ===== 讀 cap.csv =====
def get_cap():
    try:
        df = pd.read_csv("cap.csv")

        # ⭐ 統一代號格式（關鍵）
        df["證券代號"] = df["證券代號"].astype(str).str.zfill(4)

        return df
    except:
        return pd.DataFrame(columns=["證券代號","發行股數"])


# ===== 主邏輯 =====
def build():
    today = get_valid_date(1)
    yesterday = get_valid_date(2)

    if not today or not yesterday:
        return None, "❌ 無資料"

    t = get_borrow(today)
    y = get_borrow(yesterday)
    cap = get_cap()

    if t.empty or y.empty:
        return None, "❌ API資料異常"

    # ⭐ 保險（再統一一次）
    t["證券代號"] = t["證券代號"].astype(str)
    y["證券代號"] = y["證券代號"].astype(str)

    df = pd.merge(t, y, on="證券代號", suffixes=("_t", "_y"))

    # 合併股本
    if not cap.empty:
        df = pd.merge(df, cap, on="證券代號", how="left")
        df["使用率"] = df["餘額_t"] / df["發行股數"] * 100
    else:
        df["使用率"] = 0

    df["增加量"] = df["餘額_t"] - df["餘額_y"]

    # 主力判斷
    def judge(x):
        if x > 0:
            return "加空"
        elif x < 0:
            return "回補"
        return "無"

    df["動作"] = df["增加量"].apply(judge)

    # 排序
    if "發行股數" in df.columns:
        df = df.sort_values(by="使用率", ascending=False)
    else:
        df = df.sort_values(by="增加量", ascending=False)

    df = df.head(30)
    df.insert(0, "排名", range(1, len(df)+1))

    # 格式化
    df["使用率(%)"] = df["使用率"].fillna(0).map("{:.2f}".format)
    df["增加量"] = df["增加量"].map("{:+,.0f}".format)
    df["餘額"] = df["餘額_t"].map("{:,.0f}".format)

    display_date = f"{today[:4]}-{today[4:6]}-{today[6:]}"
    return df[["排名","證券代號","證券名稱_t","餘額","增加量","使用率(%)","動作"]], f"📅 {display_date}"


# ===== HTML =====
def generate_html(df, msg):
    now = datetime.now(pytz.timezone("Asia/Taipei")).strftime("%Y-%m-%d %H:%M")

    if df is None:
        df = pd.DataFrame([{"排名":"-","證券代號":"-","證券名稱_t":"無資料"}])

    rows = ""
    for _, r in df.iterrows():
        rate = float(r["使用率(%)"]) if "使用率(%)" in r else 0

        style = ""
        if rate > 10:
            style = "background:#ffcccc;"
        elif rate > 8:
            style = "background:#fff3cd;"

        rows += f"""
        <tr style="{style}">
            <td>{r.get('排名','')}</td>
            <td>{r.get('證券代號','')}</td>
            <td>{r.get('證券名稱_t','')}</td>
            <td>{r.get('餘額','')}</td>
            <td>{r.get('增加量','')}</td>
            <td>{r.get('使用率(%)','')}</td>
            <td>{r.get('動作','')}</td>
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
    <p>{msg}</p>
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
