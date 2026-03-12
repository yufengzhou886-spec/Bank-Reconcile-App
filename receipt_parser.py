import pdfplumber
import re
import pandas as pd
from pdf2image import convert_from_path
import pytesseract


def parse_receipt_pdf(pdf_path):
    records = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = page.extract_text()

            # ================= ⭐ 核心升级：OCR 视觉拦截网 =================
            # 如果这页读不出字，或者字数极其少（比如扫描成图片的 PDF）
            if not text or len(text.strip()) < 10:
                print(f"⚠️ 第 {page_num} 页未检测到足够文本，疑似扫描件，正在启动 OCR 视觉引擎...")
                try:
                    # 将这一页精确切出来，转成 300dpi 的高清图片
                    images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=300)
                    if images:
                        # 呼叫 Tesseract 引擎进行中文提取
                        text = pytesseract.image_to_string(images[0], lang='chi_sim')
                        print(f"✅ 第 {page_num} 页 OCR 识别完成！")
                except Exception as e:
                    print(f"❌ 第 {page_num} 页 OCR 识别失败: {e}")
                    text = ""  # 失败了就给个空字符串，防止后面报错
            # ===============================================================

            # 如果 OCR 扫完还是没字，说明真的是张白纸，直接跳过这页
            if not text:
                continue

            # ================= ⬇️ 你原本极其优秀的解析逻辑（完全没动） ⬇️ =================
            # 用“出账回单”作为分隔符 (这里的 \s* 刚好能完美兼容 OCR 产生的多余空格)
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
            # =========================================================================

    df = pd.DataFrame(records)
    if not df.empty:
        df["交易日期"] = pd.to_datetime(df["交易日期"])

    return df