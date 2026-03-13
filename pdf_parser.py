import pdfplumber
import pandas as pd
import re


# ==========================================
# 🏦 1号流水线：招商银行解析器
# ==========================================
def _parse_cmb_pdf(pdf_path):
    """专门处理招商银行 PDF 的逻辑"""
    records = []
    amount_pattern = re.compile(r"^-?\d{1,3}(?:,\d{3})*(?:\.\d{2})$")

    # 尝试抓取整篇文档的“期初余额”（用于给第一行数据做推算参考）
    starting_balance = None
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "".join([page.extract_text() or "" for page in pdf.pages])
        sb_match = re.search(r"(?:期初余额|上期余额|承前页)[:：\s]*([-\d,]+\.\d{2})", full_text)
        if sb_match:
            starting_balance = float(sb_match.group(1).replace(',', ''))

    # 开始逐页提取
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue

            for line in text.splitlines():
                line = line.strip()
                if not re.match(r"^(\d{8}|\d{4}[-/]\d{2}[-/]\d{2})\b", line):
                    continue

                parts = re.split(r"\s+", line)
                if len(parts) < 3: continue

                trade_date = parts[0]

                # 从右向左倒推寻找金额和余额
                amount_indices = []
                for i in range(len(parts) - 1, 0, -1):
                    if amount_pattern.match(parts[i]):
                        amount_indices.append(i)
                    if len(amount_indices) == 2: break

                if len(amount_indices) < 2: continue

                bal_idx = amount_indices[0]
                amt_idx = amount_indices[1]

                amount = parts[amt_idx]
                balance = parts[bal_idx]
                biz_type = parts[1] if amt_idx > 1 else ""
                summary = " ".join(parts[2:amt_idx]) if amt_idx > 2 else ""

                records.append({
                    "交易日期": trade_date,
                    "业务类型": biz_type,
                    "摘要": summary,
                    "银行金额": amount,  # ⭐ 注意：这里直接一步到位，改名叫“银行金额”
                    "余额": balance
                })

    # ================= ⭐ 核心升级：余额数学推算引擎 ⭐ =================
    # 利用上下文的余额差值，精准反推这笔钱到底是支出还是收入！
    for i in range(len(records)):
        curr_amt = float(records[i]['银行金额'].replace(',', ''))
        curr_bal = float(records[i]['余额'].replace(',', ''))

        prev_bal = None
        if i > 0:
            prev_bal = float(records[i - 1]['余额'].replace(',', ''))
        elif starting_balance is not None:
            prev_bal = starting_balance

        if prev_bal is not None:
            # 数学反推：当前余额 - 上期余额 = 资金变动
            diff = round(curr_bal - prev_bal, 2)
            if abs(diff - curr_amt) <= 0.01:
                records[i]['银行金额'] = curr_amt  # 余额增加 -> 收入
            elif abs(diff - (-curr_amt)) <= 0.01:
                records[i]['银行金额'] = -curr_amt  # 余额减少 -> 支出
            else:
                records[i]['银行金额'] = -curr_amt  # 推算失败的兜底策略：默认当作支出
        else:
            # 如果是首行且没有期初余额，通过关键词粗略判断
            if any(k in records[i]['摘要'] + records[i]['业务类型'] for k in ["付", "支", "扣", "费", "划", "转出"]):
                records[i]['银行金额'] = -curr_amt
            else:
                records[i]['银行金额'] = -curr_amt  # 默认转负，优先保证支出能对账

        # 格式化回字符串
        records[i]['银行金额'] = str(records[i]['银行金额'])

    return pd.DataFrame(records)


# ==========================================
# 🏦 2号流水线：工商银行解析器 (预留位置)
# ==========================================
def _parse_icbc_pdf(pdf_path):
    print("⚠️ 工商银行解析引擎正在开发中...")
    return pd.DataFrame()


# ==========================================
# 🚦 中央调度室 (Router)
# ==========================================
def parse_bank_pdf(pdf_path, bank_type="招商银行"):
    if bank_type == "招商银行":
        return _parse_cmb_pdf(pdf_path)
    elif bank_type == "工商银行 (开发中)":
        return _parse_icbc_pdf(pdf_path)
    else:
        raise ValueError(f"系统暂不支持该银行类型的解析: {bank_type}")