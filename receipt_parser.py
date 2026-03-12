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

            # 贴个标签：记录这一页是否用“主力方案”成功抓到了数据
            page_success = False

            # ================= 🥇 主力方案：你原本最完美的提取逻辑 =================
            if text and len(text.strip()) >= 10:
                blocks = re.split(r"出\s*账\s*回\s*单", text)
                for block in blocks:
                    # 日期
                    date_match = re.search(r"(交易日期|日期)[:：]\s*(\d{4}[年/]\d{2}[月/]\d{2})", block)
                    if not date_match: continue
                    raw_date = date_match.group(2)
                    trade_date = raw_date.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")

                    # 金额
                    amount_match = re.search(r"(金额（小写）|交易金额\(小写\)|小写\(合计\)金额)[:：]?\s*[￥CNY]*([\d,]+\.\d{2})", block)
                    if not amount_match: continue
                    amount = -float(amount_match.group(2).replace(",", ""))

                    # 摘要
                    summary_match = re.search(r"(交易摘要|摘要)[:：]\s*(.+)", block)
                    summary = summary_match.group(2).strip() if summary_match else ""

                    records.append({
                        "交易日期": trade_date,
                        "金额": amount,
                        "摘要": summary,
                    })
                    page_success = True  # 只要成功抓到一笔，就算主力方案赢了！

            # ================= 🥈 备选方案：主力吃瘪了，才呼叫 OCR =================
            if not page_success:
                print(f"⚠️ 第 {page_num} 页常规提取无数据，正在启动 OCR 备胎方案...")
                try:
                    images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=300)
                    if images:
                        ocr_text = pytesseract.image_to_string(images[0], lang='chi_sim')

                        if ocr_text.strip():
                            # 针对 OCR 乱码专用的“散光级”正则，被隔离在这里面
                            blocks_ocr = re.split(r"出\s*账\s*回\s*单|付\s*款\s*凭\s*证", ocr_text)
                            if len(blocks_ocr) == 1: blocks_ocr = [ocr_text]

                            for block in blocks_ocr:
                                date_match = re.search(
                                    r"(交易日期|日期|打印日期|缴款日期)[^\d]*(\d{4}\s*[年/-]\s*\d{1,2}\s*[月/-]\s*\d{1,2})", block)
                                if not date_match: continue
                                raw_date = date_match.group(2).replace(" ", "")
                                trade_date = raw_date.replace("年", "-").replace("月", "-").replace("日", "").replace("/",
                                                                                                                   "-")

                                amount_match = re.search(r"(小写|金额|合计)[^\d]*?([\d,\s]+\.\s*\d{2})", block)
                                if not amount_match: continue
                                raw_amount = amount_match.group(2).replace(",", "").replace(" ", "")
                                try:
                                    amount = -float(raw_amount)
                                except ValueError:
                                    continue

                                summary = "OCR扫描回单"
                                if "缴税" in block or "税务" in block:
                                    summary = "电子缴税凭证(OCR)"
                                else:
                                    summary_match = re.search(r"(交易摘要|摘要|用途)[:：\s]*(.+)", block)
                                    if summary_match: summary = summary_match.group(2).strip()

                                records.append({
                                    "交易日期": trade_date,
                                    "金额": amount,
                                    "摘要": summary,
                                })
                except Exception as e:
                    print(f"❌ OCR 备胎方案也失败了: {e}")
            # =========================================================================

    df = pd.DataFrame(records)
    if not df.empty:
        df["交易日期"] = pd.to_datetime(df["交易日期"], errors='coerce')
        # 如果连日期或金额都是空的废数据，直接抛弃
        df.dropna(subset=['交易日期', '金额'], inplace=True)

    return df