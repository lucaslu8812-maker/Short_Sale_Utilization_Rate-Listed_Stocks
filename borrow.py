import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz


# ===== 找最近N個有資料交易日 =====
def get_last_n_valid_dates(n=3):
    tz = pytz.timezone("Asia/Taipei")
    now = datetime.now(tz)

    dates = []

    for i in range(1, 15):
        d = (now - timedelta(days=i)).strftime("%Y%m%d")
        try:
            url = f"https://www.twse.com.tw/exchangeReport/TWT93U?response=json&date={d}"
            data = requests.get(url, timeout=10).json()

            if data.get("stat") == "OK" and data.get("data"):
                dates.append(d)

            if len(dates) >= n:
                return dates

        except:
            continue

    return dates


# ===== 借券賣出餘額 =====
def get_borrow(date):
    url = f"https://www.twse.com.tw/exchangeReport/TWT93U?response=json&date={date}"
    data = requests.get(url).json()

    if not data.get("data") or not data.get("fields"):
        return pd.DataFrame(columns=["證券代號","證券名稱","餘額"])

    df = pd.DataFrame(data["data"], columns=data["fields"])

    # ⭐ 自動找欄位
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

    # ⭐ 抓「當日餘額」
    target_col = None
    for col in df.columns:
        if "當日餘額" in col:
            target_col = col
            break

    if target_col is None:
        print("❌ 找不到當日餘額:", df.columns)
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
    dates = get_last_n_valid_dates(3)

    if len(dates) < 2:
        return None, "❌ 無資料"

    valid_dates = []
    for d in dates:
        test = get_borrow(d)
        if not test.empty:
            valid_dates.append(d)

        if len(valid_dates) == 2:
            break

    if len(valid_dates) < 2:
        return None, "❌ 無有效資料"

    today, yesterday = valid_dates[0], valid_dates[1]

    t = get_borrow(today)
    y = get_borrow(yesterday)
    cap = get_cap()

    if t.empty or y.empty:
        return None, "❌ API資料異常"

    df = pd.merge(t, y, on="證券代號", suffixes=("_t", "_y"))

    # ⭐ ⭐ ⭐ 補回你原本的過濾（很重要）
    df = df[~df["證券名稱_t"].str.contains(r"\*", na=False)]

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
