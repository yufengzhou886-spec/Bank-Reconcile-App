# reconciler.py
import pandas as pd
import os


def reconcile_and_export(bank_df, receipt_df, output_dir="output"):
    """
    对账并按月份输出 Excel (已修复回单重复消耗 Bug)
    - bank_df: 银行账单 DataFrame，包含列 ["交易日期", "金额", ...]
    - receipt_df: 回单 DataFrame，包含列 ["交易日期", "金额", ...]
    - output_dir: 输出目录
    """
    os.makedirs(output_dir, exist_ok=True)

    bank_df = bank_df.copy()
    receipt_df = receipt_df.copy()

    # 按月份分组
    bank_df["月份"] = bank_df["交易日期"].dt.to_period("M")
    receipt_df["月份"] = receipt_df["交易日期"].dt.to_period("M")

    all_results = []

    for month, bank_month_df in bank_df.groupby("月份"):
        receipt_month_df = receipt_df[receipt_df["月份"] == month]
        used_receipts = set()  # 已匹配回单索引的集合

        results = []

        for _, row in bank_month_df.iterrows():
            bank_date = row["交易日期"]
            amount = row["金额"]

            # 收入不校验
            if amount > 0:
                results.append({
                    "交易日期": bank_date,
                    "银行金额": amount,
                    "状态": "➕ 收入-不校验",
                    "匹配回单数": "-",
                    "月份": str(month),
                    "未对账原因": ""
                })
                continue

            # 提前过滤出当前“未被使用”的回单池
            available_receipts = receipt_month_df[~receipt_month_df.index.isin(used_receipts)]

            # 1️⃣ 同日 + 同金额
            exact = available_receipts[
                (available_receipts["金额"] == amount) &
                (available_receipts["交易日期"] == bank_date)
                ]

            # 2️⃣ ±1天
            near = exact
            if exact.empty:
                near = available_receipts[
                    (available_receipts["金额"] == amount) &
                    (abs((available_receipts["交易日期"] - bank_date).dt.days) <= 1)
                    ]

            # 3️⃣ 同月兜底
            fallback = near
            if near.empty:
                fallback = available_receipts[
                    (available_receipts["金额"] == amount)
                ]

            if not fallback.empty:
                # ⭐ 核心修复：只取第一张匹配的回单，精准消耗 1 张
                matched_idx = fallback.index[0]
                used_receipts.add(matched_idx)

                status = "✔ 已对账"
                reason = ""
                match_count = 1
            else:
                status = "❌ 未找到回单"
                reason = "回单缺失或已被其他流水占用"
                match_count = 0

            results.append({
                "交易日期": bank_date,
                "银行金额": amount,
                "状态": status,
                "匹配回单数": match_count,
                "月份": str(month),
                "未对账原因": reason
            })

        # 保存每个月 Excel
        df_month = pd.DataFrame(results)
        all_results.append(df_month)
        output_file = os.path.join(output_dir, f"对账结果_{month}.xlsx")
        df_month.to_excel(output_file, index=False)
        # 注意：在使用 Streamlit 前端时，这里的 print 会输出在后端的黑框框里
        print(f"✅ 已生成 {output_file}")

    if not all_results:
        return pd.DataFrame()

    return pd.concat(all_results, ignore_index=True)