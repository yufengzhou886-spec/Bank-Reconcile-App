import streamlit as st
import pandas as pd
import os
import shutil
import plotly.express as px

# 导入你原有的核心逻辑
from pdf_parser import parse_bank_pdf
from receipt_parser import parse_receipt_pdf
from data_cleaner import clean_bank_data
from reconciler import reconcile_and_export

# 页面配置设置（必须在第一行 Streamlit 命令）
st.set_page_config(
    page_title="智能财务对账系统",
    page_icon="📊",
    layout="wide"
)

# 临时目录配置
TEMP_DIR = "temp_workspace"
OUTPUT_DIR = "output_workspace"


def init_env():
    """初始化清理临时文件夹"""
    for d in [TEMP_DIR, OUTPUT_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)


# ----------------- UI 界面构建 -----------------
st.title("📊 智能财务对账系统")
st.markdown("上传您的银行对账单和出账回单，系统将自动进行解析、清洗与匹配对账。")
st.divider()

# 使用两列布局放置上传组件
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏦 1. 银行对账单 (Bank PDF)")
    bank_file = st.file_uploader("请上传银行流水的 PDF 文件", type=["pdf"], key="bank")

with col2:
    st.subheader("🧾 2. 电子回单 (Receipt PDF)")
    receipt_file = st.file_uploader("请上传包含多张回单的 PDF 文件", type=["pdf"], key="receipt")

# 居中放置运行按钮
st.markdown("<br>", unsafe_allow_html=True)
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
with col_btn2:
    run_button = st.button("🚀 开始智能对账", use_container_width=True, type="primary")

# ----------------- 核心交互逻辑 -----------------
if run_button:
    if not bank_file or not receipt_file:
        st.warning("⚠️ 请先上传【银行对账单】和【电子回单】两个 PDF 文件！")
    else:
        init_env()

        # 将上传的内存文件保存到临时目录
        bank_path = os.path.join(TEMP_DIR, "bank.pdf")
        receipt_path = os.path.join(TEMP_DIR, "receipt.pdf")

        with open(bank_path, "wb") as f:
            f.write(bank_file.getbuffer())
        with open(receipt_path, "wb") as f:
            f.write(receipt_file.getbuffer())

        with st.spinner("系统正在努力解析 PDF 并进行对账，请稍候..."):
            try:
                # 1. 解析与清洗
                raw_bank_df = parse_bank_pdf(bank_path)
                df_bank = clean_bank_data(raw_bank_df)

                df_receipt = parse_receipt_pdf(receipt_path)

                if df_bank.empty:
                    st.error("❌ 银行对账单解析失败或数据为空，请检查文件格式。")
                elif df_receipt.empty:
                    st.error("❌ 电子回单解析失败或数据为空，请检查文件格式。")
                else:
                    # 2. 调用对账逻辑
                    df_result = reconcile_and_export(df_bank, df_receipt, output_dir=OUTPUT_DIR)
                    st.success("🎉 对账完成！")

                    # === 3. 统计数据卡片 ===
                    st.subheader("📈 对账概览")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("银行流水总笔数", len(df_bank))
                    m2.metric("识别到回单总笔数", len(df_receipt))
                    matched_count = len(df_result[df_result["状态"] == "✔ 已对账"])
                    m3.metric("成功匹配笔数", matched_count)

                    # === 4. 可视化图表区 ===
                    st.divider()
                    st.subheader("🎨 财务可视化分析")
                    chart_col1, chart_col2 = st.columns(2)

                    with chart_col1:
                        # (1) 对账状态环形图
                        status_counts = df_result["状态"].value_counts().reset_index()
                        status_counts.columns = ["状态", "数量"]

                        color_map = {
                            "✔ 已对账": "#28a745",
                            "❌ 未找到回单": "#dc3545",
                            "➕ 收入-不校验": "#6c757d",
                            "⚠️ 人工确认已核对": "#ffc107"
                        }

                        fig_pie = px.pie(
                            status_counts,
                            names="状态",
                            values="数量",
                            title="对账状态分布 (笔数)",
                            color="状态",
                            color_discrete_map=color_map,
                            hole=0.4
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)

                    with chart_col2:
                        # (2) 每日支出柱状图（已修复日期与精度问题）
                        df_expense = df_result[df_result["银行金额"] < 0].copy()
                        if not df_expense.empty:
                            df_expense["支出金额"] = df_expense["银行金额"].abs().round(2)
                            df_expense["纯日期"] = pd.to_datetime(df_expense["交易日期"]).dt.strftime('%Y-%m-%d')

                            daily_expense = df_expense.groupby("纯日期")["支出金额"].sum().reset_index()
                            daily_expense["支出金额"] = daily_expense["支出金额"].round(2)

                            fig_bar = px.bar(
                                daily_expense,
                                x="纯日期",
                                y="支出金额",
                                title="每日支出金额汇总 (元)",
                                text_auto='.2f',
                                color_discrete_sequence=["#FF7F0E"]
                            )
                            fig_bar.update_layout(
                                xaxis_title="交易日期",
                                yaxis_title="总支出金额 (元)",
                                xaxis={'type': 'category'}
                            )
                            st.plotly_chart(fig_bar, use_container_width=True)
                        else:
                            st.info("没有支出记录，无法生成支出图表。")

                    # === 5. 交互式数据表格（支持手动微调） ===
                    st.divider()
                    st.subheader("📋 详细对账结果 (支持手动修改)")
                    st.info("💡 提示：您可以双击表格中的【状态】和【未对账原因】列进行手动修改。修改后，下方导出的 Excel 将自动包含您的最新更改。")

                    status_options = ["✔ 已对账", "❌ 未找到回单", "➕ 收入-不校验", "⚠️ 人工确认已核对"]

                    edited_df = st.data_editor(
                        df_result,
                        column_config={
                            "状态": st.column_config.SelectboxColumn(
                                "状态 (双击修改)",
                                help="双击此处可手动更改对账状态",
                                width="medium",
                                options=status_options,
                                required=True,
                            ),
                            "未对账原因": st.column_config.TextColumn(
                                "未对账原因/备注 (双击修改)",
                                help="如果是人工核对的，可以在这里写上备注",
                            )
                        },
                        disabled=["交易日期", "银行金额", "匹配回单数", "月份"],
                        use_container_width=True,
                        hide_index=True,
                        height=400
                    )

                    # === 6. 提供 Excel 下载 ===
                    st.divider()
                    st.subheader("💾 导出结果")

                    final_excel_path = os.path.join(OUTPUT_DIR, "最终汇总对账单.xlsx")
                    edited_df.to_excel(final_excel_path, index=False)

                    with open(final_excel_path, "rb") as f:
                        st.download_button(
                            label="📥 下载最新对账 Excel",
                            data=f,
                            file_name="自动化对账结果(含人工微调).xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary"
                        )

            except Exception as e:
                st.error(f"💔 处理过程中出现错误: {str(e)}")