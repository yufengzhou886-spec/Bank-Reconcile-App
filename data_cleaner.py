import pandas as pd

def clean_bank_data(df):
    if df is None or df.empty:
        return pd.DataFrame()

    # ⭐ 修复 1：架构适配！把上游的 "金额" 自动改名为下游需要的 "银行金额"
    if "金额" in df.columns and "银行金额" not in df.columns:
        df = df.rename(columns={"金额": "银行金额"})

    if "交易日期" not in df.columns or "银行金额" not in df.columns:
        print("⚠️ 银行对账单列异常：", df.columns.tolist())
        return pd.DataFrame()

    # 日期统一
    df["交易日期"] = pd.to_datetime(df["交易日期"], errors="coerce")

    # 金额去逗号、转 float
    df["银行金额"] = (
        df["银行金额"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .astype(float)
    )

    df = df.dropna(subset=["交易日期", "银行金额"])

    return df