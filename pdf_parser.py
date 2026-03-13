import pdfplumber
import pandas as pd
import re

# ==========================================
# 🏦 1号流水线：招商银行解析器
# ==========================================
def _parse_cmb_pdf(pdf_path):
    records = []
    # 🌟 修复点1：放宽正则，兼容 -1.270.96 或 - 25.00 这种识别瑕疵
    amount_pattern = re.compile(r"^-?\s*\d[\d,.]*\.\d{2}$")

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.splitlines()

            for line in lines:
                line = line.strip()

                if not re.match(r"^(\d{8}|\d{4}[-/]\d{2}[-/]\d{2})\b", line):
                    continue

                parts = re.split(r"\s+", line)
                if len(parts) < 3:
                    continue

                trade_date = parts[0]

                # 从右向左“倒推”寻找金额和余额
                amount_indices = []
                for i in range(len(parts) - 1, 0, -1):
                    if amount_pattern.match(parts[i]):
                        amount_indices.append(i)
                    if len(amount_indices) == 2:
                        break

                if len(amount_indices) < 2:
                    continue

                bal_idx = amount_indices[0]
                amt_idx = amount_indices[1]

                raw_amount = parts[amt_idx]
                raw_balance = parts[bal_idx]

                # 🌟 修复点2：清理错乱的标点符号，将 -1.270.96 恢复为 -1270.96
                def clean_number(s):
                    s = s.replace(" ", "")
                    if s.count('.') > 1:
                        parts = s.split('.')
                        return "".join(parts[:-1]) + "." + parts[-1]
                    return s.replace(",", "")

                amount = clean_number(raw_amount)
                balance = clean_number(raw_balance)

                biz_type = parts[1] if amt_idx > 1 else ""
                summary = " ".join(parts[2:amt_idx]) if amt_idx > 2 else ""

                records.append({
                    "交易日期": trade_date,
                    "业务类型": biz_type,
                    "摘要": summary,
                    "银行金额": amount, # 🌟 修复点3：直接命名为下游所需的“银行金额”
                    "余额": balance
                })

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