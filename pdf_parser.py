import pdfplumber
import pandas as pd
import re


# ==========================================
# 🏦 1号流水线：招商银行解析器
# ==========================================
def _parse_cmb_pdf(pdf_path):
    """专门处理招商银行 PDF 的逻辑"""
    records = []

    # 严格匹配金额格式：支持负号、千分位逗号，且必须有两位小数 (例如 100.00, -1,234.56)
    amount_pattern = re.compile(r"^-?\d{1,3}(?:,\d{3})*(?:\.\d{2})$")

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # 退回文本提取模式，这个对无边框账单最有效
            text = page.extract_text()
            if not text:
                continue

            lines = text.splitlines()

            for line in lines:
                line = line.strip()

                # 1. 过滤：必须以 8 位或 10 位日期开头 (如 20220401 或 2022-04-01)
                if not re.match(r"^(\d{8}|\d{4}[-/]\d{2}[-/]\d{2})\b", line):
                    continue

                parts = re.split(r"\s+", line)
                if len(parts) < 3:
                    continue

                trade_date = parts[0]

                # 2. ⭐ 核心升级：从右向左“倒推”寻找金额和余额
                # 无论摘要里有多少空格或者数字，账单的最右边两列必定是金额和余额
                amount_indices = []
                for i in range(len(parts) - 1, 0, -1):
                    if amount_pattern.match(parts[i]):
                        amount_indices.append(i)

                    if len(amount_indices) == 2:
                        break  # 找到最后两个符合金额格式的就停止

                if len(amount_indices) < 2:
                    print(f"⚠️ 跳过无法识别金额的行: {line}")
                    continue

                # 记录索引（注意 amount_indices 是倒序获取的，[0] 是最右边的余额，[1] 是金额）
                bal_idx = amount_indices[0]
                amt_idx = amount_indices[1]

                amount = parts[amt_idx]
                balance = parts[bal_idx]

                # 3. 提取业务类型和摘要
                # 第1个是日期，第2个通常是业务类型
                biz_type = parts[1] if amt_idx > 1 else ""

                # ⭐ 夹在业务类型和金额之间的所有碎片，全部用空格无缝拼接成摘要！
                summary = " ".join(parts[2:amt_idx]) if amt_idx > 2 else ""

                records.append({
                    "交易日期": trade_date,
                    "业务类型": biz_type,
                    "摘要": summary,
                    "金额": amount,
                    "余额": balance
                })

    return pd.DataFrame(records)


# ==========================================
# 🏦 2号流水线：工商银行解析器 (预留位置)
# ==========================================
def _parse_icbc_pdf(pdf_path):
    """专门处理工商银行 PDF 的逻辑（示例）"""
    print("⚠️ 工商银行解析引擎正在开发中...")
    # 未来如果要加别的银行，参考上面招行的写法，最后 return 一个 DataFrame 即可
    return pd.DataFrame()


# ==========================================
# 🚦 中央调度室 (Router)
# ==========================================
def parse_bank_pdf(pdf_path, bank_type="招商银行"):
    """
    根据用户选择的银行，自动将文件分发给对应的解析器
    """
    if bank_type == "招商银行":
        return _parse_cmb_pdf(pdf_path)

    elif bank_type == "工商银行 (开发中)":
        return _parse_icbc_pdf(pdf_path)

    else:
        raise ValueError(f"系统暂不支持该银行类型的解析: {bank_type}")