import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz

# ⭐ 避免被擋
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

# ===== 找最近交易日 =====
def get_valid_date(offset_start=1):
    tz = pytz.timezone("Asia/Taipei")
    now = datetime.now(tz)

    for i in range(offset_start, offset_start + 30):  # ⭐ 你之前已改30天
        d = (now - timedelta(days=i)).strftime("%Y%m%d")
        try:
            url = f"https://www.twse.com.tw/exchangeReport/TWT93U?response=json&date={d}"
            data = requests.get(url, headers=HEADERS, timeout=10).json()
            if data.get("stat") == "OK" and data.get("data"):
                return d
        except:
            continue
    return None


# ===== 借券資料（⭐ 加 retry + 原本邏輯不動）=====
def get_borrow(date):
    url = f"https://www.twse.com.tw/exchangeReport/TWT93U?response=json&date={date}"

    data = None
    for _ in range(3):  # ⭐ retry 3 次
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            data = res.json()
            if data.get("stat") == "OK" and data.get("data"):
                break
        except:
            pass
    else:
        print(f"❌ API失敗: {date}")
        return pd.DataFrame(columns=["證券代號","證券名稱","餘額"])

    if not data.get("data") or not data.get("fields"):
        return pd.DataFrame(columns=["證券代號","證券名稱","餘額"])

    df = pd.DataFrame(data["data"], columns=data["fields"])

    # ⭐ 自動抓欄位
    code_col = None
    name_col = None

    for col in df.columns:
        if "代號" in col:
            code_col = col
        if "名稱" in col:
            name_col = col

    if code_col is None or name_col is None:
        print("❌ 找不到代號/名稱欄:", df.columns)
        return pd.DataFrame(columns=["證券代號","證券名稱","餘額"])

    df["證券代號"] = df[code_col].astype(str).str.zfill(4)
    df["證券名稱"] = df[name_col]

    # ⭐ 保留你之前修好的：過濾 * 股票
    df = df[~df["證券名稱"].str.contains(r"[\*\＊]", na=False)]

    # ⭐ 抓「借券賣出當日餘額」
    target_col = None
    for col in df.columns:
        if "借券賣出" in col and "當日餘額" in col:
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

    # ⭐⭐⭐ 關鍵：API壞掉 → 保留舊資料（不覆蓋）
    if t.empty or y.empty:
        print("⚠️ 保留舊資料")
        return None, "⚠️ 使用前次資料"

    if cap.empty:
        return None, "❌ cap資料異常"

    # ⭐ 若只有股本 → 轉發行股數
    if "發行股數" not in cap.columns and "股本" in cap.columns:
        cap["發行股數"] = cap["股本"] * 100000000 / 10

    df = pd.merge(t, y, on="證券代號", suffixes=("_t", "_y"))
    df = pd.merge(df, cap, on="證券代號", how="left")

    # ⭐ 避免異常
    df = df[df["發行股數"] > 0]

    # ===== 計算 =====
    df["使用率"] = df["餘額_t"] / df["發行股數"] * 100
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

    # 格式化
    df["使用率(%)"] = df["使用率"].map("{:.2f}".format)
    df["增加量"] = df["增加量"].map("{:+,.0f}".format)
    df["餘額"] = df["餘額_t"].map("{:,.0f}".format)

    display_date = f"{today[:4]}-{today[4:6]}-{today[6:]}"
    return df[["排名","證券代號","證券名稱_t","餘額","增加量","使用率(%)","動作"]], f"📅 {display_date}"


# ===== HTML =====
def generate_html(df, msg):
    now = datetime.now(pytz.timezone("Asia/Taipei")).strftime("%Y-%m-%d %H:%M")

    # ⭐⭐⭐ 不覆蓋舊資料（關鍵）
    if df is None:
        print("⚠️ 跳過寫入 index.html（保留舊資料）")
        return

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
