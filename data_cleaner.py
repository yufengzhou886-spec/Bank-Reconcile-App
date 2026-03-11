import pandas as pd

def clean_bank_data(df):
    if df is None or df.empty:
        return pd.DataFrame()

    if "交易日期" not in df.columns or "金额" not in df.columns:
        print("⚠️ 银行对账单列异常：", df.columns.tolist())
        return pd.DataFrame()

    # 日期统一
    df["交易日期"] = pd.to_datetime(df["交易日期"], errors="coerce")

    # ⭐ 关键：金额去逗号、转 float
    df["金额"] = (
        df["金额"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .astype(float)
    )

    df = df.dropna(subset=["交易日期", "金额"])

    return df
