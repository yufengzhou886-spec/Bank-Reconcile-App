import pandas as pd
import numpy as np
import itertools
import os


def reconcile_and_export(df_bank, df_receipt, output_dir="output_workspace", tolerance=10.0):
    # 1. 复制数据，防止污染原始数据
    bank = df_bank.copy()
    receipt = df_receipt.copy()

    # 统一格式
    bank["银行金额"] = bank["银行金额"].astype(float)
    receipt["金额"] = receipt["金额"].astype(float)
    bank["交易日期"] = pd.to_datetime(bank["交易日期"])
    receipt["交易日期"] = pd.to_datetime(receipt["交易日期"])

    # 2. 初始化全新状态标签
    bank["状态"] = "❌ 未找到回单"
    bank["匹配回单数"] = 0
    bank["智能备注"] = ""
    receipt["已匹配"] = False

    # 3. 三级思考匹配算法
    for i, b_row in bank.iterrows():
        b_amt = b_row["银行金额"]
        b_date = b_row["交易日期"]

        # 收入跳过
        if b_amt > 0:
            bank.at[i, "状态"] = "➕ 收入-不校验"
            continue

        # 锁定日期相差在 3 天以内的未匹配回单作为“备选池”
        unmatched = receipt[~receipt["已匹配"]]
        date_mask = (unmatched["交易日期"] >= b_date - pd.Timedelta(days=3)) & \
                    (unmatched["交易日期"] <= b_date + pd.Timedelta(days=3))
        candidates = unmatched[date_mask]

        if candidates.empty:
            continue

        # ================= 🥇 第一级：精确匹配 (一对一) =================
        exact_match = candidates[np.isclose(candidates["金额"], b_amt, atol=0.01)]
        if not exact_match.empty:
            r_idx = exact_match.index[0]
            receipt.at[r_idx, "已匹配"] = True
            bank.at[i, "状态"] = "✔ 精确匹配"
            bank.at[i, "匹配回单数"] = 1
            bank.at[i, "智能备注"] = f"回单日期:{receipt.at[r_idx, '交易日期'].strftime('%Y-%m-%d')}"
            continue

        # ================= 🥈 第二级：容差匹配 (含手续费) =================
        # 寻找：银行扣款比回单金额大，且差额在 tolerance (默认10元) 以内的
        tol_match = candidates[(abs(b_amt) - abs(candidates["金额"]) > 0) &
                               (abs(b_amt) - abs(candidates["金额"]) <= tolerance)]
        if not tol_match.empty:
            r_idx = tol_match.index[0]
            fee = abs(b_amt) - abs(receipt.at[r_idx, "金额"])
            receipt.at[r_idx, "已匹配"] = True
            bank.at[i, "状态"] = "⚠️ 容差匹配(含手续费)"
            bank.at[i, "匹配回单数"] = 1
            bank.at[i, "智能备注"] = f"推测包含手续费: {fee:.2f}元"
            continue

        # ================= 🥉 第三级：多对一组合匹配 (排列组合穷举) =================
        # 尝试将 2 到 4 张回单组合起来，看看总和是否等于银行流水
        found_combo = False
        c_indices = candidates.index.tolist()

        # 为了防止算力爆炸，如果同一天没对上的票超过15张，只取前15张做组合计算
        if len(c_indices) > 15: c_indices = c_indices[:15]

        for r_count in range(2, min(5, len(c_indices) + 1)):
            for combo in itertools.combinations(c_indices, r_count):
                combo_sum = receipt.loc[list(combo), "金额"].sum()
                if np.isclose(combo_sum, b_amt, atol=0.01):
                    # 组合成功！锁定这批回单
                    for idx in combo:
                        receipt.at[idx, "已匹配"] = True
                    bank.at[i, "状态"] = "🔄 组合匹配(多张回单)"
                    bank.at[i, "匹配回单数"] = r_count
                    bank.at[i, "智能备注"] = f"由 {r_count} 张回单合并构成"
                    found_combo = True
                    break
            if found_combo: break

    # 4. 整理输出
    bank["月份"] = bank["交易日期"].dt.strftime("%Y-%m")
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    return bank