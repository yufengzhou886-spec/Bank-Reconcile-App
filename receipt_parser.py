# receipt_parser.py
import pdfplumber
import re
import pandas as pd


def parse_receipt_pdf(pdf_path):
    records = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            # 用“出账回单”作为分隔符
            blocks = re.split(r"出\s*账\s*回\s*单", text)

            for block in blocks:
                # 日期
                date_match = re.search(
                    r"(交易日期|日期)[:：]\s*(\d{4}[年/]\d{2}[月/]\d{2})",
                    block,
                )
                if not date_match:
                    continue

                raw_date = date_match.group(2)
                trade_date = (
                    raw_date.replace("年", "-")
                    .replace("月", "-")
                    .replace("日", "")
                    .replace("/", "-")
                )

                # 金额
                amount_match = re.search(
                    r"(金额（小写）|交易金额\(小写\)|小写\(合计\)金额)[:：]?\s*[￥CNY]*([\d,]+\.\d{2})",
                    block,
                )
                if not amount_match:
                    continue

                amount = -float(amount_match.group(2).replace(",", ""))

                # 摘要
                summary_match = re.search(r"(交易摘要|摘要)[:：]\s*(.+)", block)
                summary = summary_match.group(2).strip() if summary_match else ""

                records.append({
                    "交易日期": trade_date,
                    "金额": amount,
                    "摘要": summary,
                })

    df = pd.DataFrame(records)
    if not df.empty:
        df["交易日期"] = pd.to_datetime(df["交易日期"])

    return df
