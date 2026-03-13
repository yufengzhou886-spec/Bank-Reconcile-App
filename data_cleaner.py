import pandas as pd

def clean_bank_data(df):
    if df is None or df.empty:
        return pd.DataFrame()

    if "金额" in df.columns and "银行金额" not in df.columns:
        df = df.rename(columns={"金额": "银行金额"})

    if "交易日期" not in df.columns or "银行金额" not in df.columns:
        return pd.DataFrame()

    df["交易日期"] = pd.to_datetime(df["交易日期"], errors="coerce")
    df["银行金额"] = df["银行金额"].astype(str).str.replace(",", "", regex=False).astype(float)
    df = df.dropna(subset=["交易日期", "银行金额"])
    return df