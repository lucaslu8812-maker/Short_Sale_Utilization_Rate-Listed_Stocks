import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz

LINE_TOKEN = "你的LINE_NOTIFY_TOKEN"


def send_line(msg):
    try:
        requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {LINE_TOKEN}"},
            data={"message": msg}
        )
    except:
        pass


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


def get_borrow(date):
    url = f"https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={date}"
    data = requests.get(url).json()

    df = pd.DataFrame(data["data"], columns=data["fields"])
    df["餘額"] = df["當日餘額"].str.replace(",", "").astype(float)

    return df[["證券代號", "證券名稱", "餘額"]]


def get_cap(date):
    url = f"https://www.twse.com.tw/exchangeReport/BWIBBU_d?response=json&date={date}"
    data = requests.get(url).json()

    df = pd.DataFrame(data["data"], columns=data["fields"])
    df["股本"] = pd.to_numeric(df["股本"], errors="coerce")
    df["發行股數"] = df["股本"] * 10_000_000

    return df[["證券代號", "發行股數"]]


def build():
    today = get_valid_date(1)
    yesterday = get_valid_date(2)

    if not today or not yesterday:
        return None, "❌ 無資料"

    t = get_borrow(today)
    y = get_borrow(yesterday)
    cap = get_cap(today)

    df = pd.merge(t, y, on="證券代號", suffixes=("_t", "_y"))
    df = pd.merge(df, cap, on="證券代號")

    # 計算
    df["使用率"] = df["餘額_t"] / df["發行股數"] * 100
    df["增加量"] = df["餘額_t"] - df["餘額_y"]

    df = df.sort_values(by="使用率", ascending=False).head(30)

    df.insert(0, "排名", range(1, len(df)+1))

    # LINE 推播
    alerts = df[df["使用率"] > 8]

    if not alerts.empty:
        msg = "🚨 借券使用率警報\n"
        for _, r in alerts.iterrows():
            msg += f"{r['證券代號']} {r['證券名稱_t']} {r['使用率']:.2f}% (+{int(r['增加量'])})\n"
        send_line(msg)

    # 格式化
    df["使用率(%)"] = df["使用率"].map("{:.2f}".format)
    df["增加量"] = df["增加量"].map("{:+,.0f}".format)
    df["餘額"] = df["餘額_t"].map("{:,.0f}".format)

    display_date = f"{today[:4]}-{today[4:6]}-{today[6:]}"
    return df[["排名","證券代號","證券名稱_t","餘額","增加量","使用率(%)"]], f"📅 {display_date}"


def generate_html(df, msg):
    now = datetime.now(pytz.timezone("Asia/Taipei")).strftime("%Y-%m-%d %H:%M")

    if df is None:
        df = pd.DataFrame([{"排名":"-","證券代號":"-","證券名稱_t":"無資料"}])

    rows = ""
    for _, r in df.iterrows():
        rate = float(r["使用率(%)"])

        style = ""
        if rate > 10:
            style = "background:#ffcccc;"   # 紅色警報
        elif rate > 8:
            style = "background:#fff3cd;"   # 黃色警戒

        rows += f"""
        <tr style="{style}">
            <td>{r['排名']}</td>
            <td>{r['證券代號']}</td>
            <td>{r['證券名稱_t']}</td>
            <td>{r['餘額']}</td>
            <td>{r['增加量']}</td>
            <td>{r['使用率(%)']}</td>
        </tr>
        """

    html = f"""
    <html>
    <head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="300">
    <style>
    body {{ font-family:sans-serif;background:#f5f5f5; }}
    .box {{ max-width:900px;margin:auto;background:white;padding:20px }}
    table {{ width:100%;border-collapse:collapse }}
    th {{ background:#007aff;color:white;padding:10px }}
    td {{ text-align:center;padding:10px;border-bottom:1px solid #eee }}
    </style>
    </head>
    <body>
    <div class="box">
    <h2>📊 借券監控（接近10%）</h2>
    <p>{msg}</p>
    <p>更新時間：{now}</p>
    <table>
    <tr>
    <th>排名</th><th>代號</th><th>名稱</th>
    <th>餘額</th><th>增加量</th><th>使用率</th>
    </tr>
    {rows}
    </table>
    </div>
    </body>
    </html>
    """

    with open("index.html","w",encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    df, msg = build()
    generate_html(df, msg)
