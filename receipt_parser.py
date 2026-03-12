import pandas as pd
from pdf2image import convert_from_path
import pytesseract


def parse_receipt_pdf(pdf_path):
    # ==== 🧨 暴力测试模式：不管三七二十一，直接启动 OCR ====
    try:
        print("正在强制转换第一页为图片...")
        images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=300)

        if images:
            print("正在呼叫 Tesseract 引擎...")
            text = pytesseract.image_to_string(images[0], lang='chi_sim')

            # 拿到结果后，直接引爆，把文字甩到网页上！
            raise ValueError(f"【强制OCR提取原文如下，请发给我】\n\n{text}")

    except Exception as e:
        # 如果是底层没装好，把报错直接扔到网页上
        raise ValueError(f"【OCR底层引擎运行失败，请发给我】: {str(e)}")

    return pd.DataFrame()