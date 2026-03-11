# main.py
import os
import pandas as pd
from pdf_parser import parse_bank_pdf
from receipt_parser import parse_receipt_pdf
from data_cleaner import clean_bank_data
from reconciler import reconcile_and_export

BASE_DIR = "input"
OUTPUT_DIR = "output"

all_results = []

# 遍历每个月文件夹
for month_dir in os.listdir(BASE_DIR):
    month_path = os.path.join(BASE_DIR, month_dir)
    if not os.path.isdir(month_path):
        continue

    print(f"\n===== 正在处理月份：{month_dir} =====")

    bank_pdf = os.path.join(month_path, "bank.pdf")
    receipt_pdf = os.path.join(month_path, "receipt.pdf")

    if not (os.path.exists(bank_pdf) and os.path.exists(receipt_pdf)):
        print("⚠️ 缺少 bank.pdf 或 receipt.pdf，跳过")
        continue

    # 解析并清洗数据
    df_bank = clean_bank_data(parse_bank_pdf(bank_pdf))
    if df_bank.empty:
        print(f"⚠️ {month_dir} 银行对账单无法解析，跳过")
        continue

    df_receipt = parse_receipt_pdf(receipt_pdf)

    # 调用新版对账函数，会生成单月 Excel 并返回结果
    df_result = reconcile_and_export(df_bank, df_receipt, output_dir=OUTPUT_DIR)

    all_results.append(df_result)

# 汇总所有月份
if all_results:
    final_result = pd.concat(all_results, ignore_index=True)
    print("\n===== 全部月份对账结果 =====")
    print(final_result)
else:
    print("⚠️ 没有可用的对账数据")
