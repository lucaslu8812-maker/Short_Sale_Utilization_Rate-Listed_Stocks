def build():
    # ⭐ 改這裡：抓「最近3天有資料的日期」
    dates = get_last_n_valid_dates(3)

    if len(dates) < 2:
        return None, "❌ 無資料"

    # ⭐ 自動過濾「API有資料的日子」
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

    # ===== 原本邏輯完全不動 =====
    t = get_borrow(today)
    y = get_borrow(yesterday)
    cap = get_cap()

    if t.empty or y.empty:
        return None, "❌ API資料異常"

    df = pd.merge(t, y, on="證券代號", suffixes=("_t", "_y"))

    # 合併股本
    if not cap.empty:
        df = pd.merge(df, cap, on="證券代號", how="left")

        df["發行股數"] = pd.to_numeric(df["發行股數"], errors="coerce")
        df["發行股數"] = df["發行股數"].replace(0, pd.NA)

        # 使用率（百分比）
        df["使用率"] = df["餘額_t"] / df["發行股數"] * 100
        df["使用率"] = df["使用率"].fillna(0)
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

    df = df.sort_values(by="使用率", ascending=False).head(30)
    df.insert(0, "排名", range(1, len(df)+1))

    # 格式化
    df["使用率(%)"] = df["使用率"].map("{:.2f}".format)
    df["增加量"] = df["增加量"].map("{:+,.0f}".format)
    df["餘額"] = df["餘額_t"].map("{:,.0f}".format)

    display_date = f"{today[:4]}-{today[4:6]}-{today[6:]}"
    return df[["排名","證券代號","證券名稱_t","餘額","增加量","使用率(%)","動作"]], f"📅 {display_date}"
