import pandas as pd

def clean_bank_data(df):
    if df is None or df.empty:
        return pd.DataFrame()

    # ⭐ 修复 1：架构适配。把上游解析出来的 "金额" 统一强制改名为下游需要的 "银行金额"
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

    # ⭐ 修复 2：防坑预警。确保对账系统的支出是“负数”！
    # 如果你发现系统跑完，所有状态都是灰色的“➕ 收入-不校验”，
    # 说明你的 PDF 提取出来的支出全是正数！
    # 这时候你就需要取消下面这行代码的注释，强行把它们变成负数（假设这份账单里全是支出）：
    # df["银行金额"] = -df["银行金额"].abs()

    df = df.dropna(subset=["交易日期", "银行金额"])

    return df