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

st.set_page_config(
    page_title="智能财务对账系统",
    page_icon="📊",
    layout="wide"
)

TEMP_DIR = "temp_workspace"
OUTPUT_DIR = "output_workspace"


def init_env():
    """初始化文件夹"""
    for d in [TEMP_DIR, OUTPUT_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)


init_env()


# ================= ⭐ 核心优化：智能缓存装饰器 =================
# 加上 @st.cache_data 后，只要上传的 PDF 文件内容（file_bytes）不变，
# 这些函数就不会重复执行，而是直接“瞬间”返回上一次解析好的 DataFrame！

@st.cache_data(show_spinner=False)
def load_and_clean_bank(file_bytes):
    bank_path = os.path.join(TEMP_DIR, "bank.pdf")
    with open(bank_path, "wb") as f:
        f.write(file_bytes)
    raw_df = parse_bank_pdf(bank_path)
    return clean_bank_data(raw_df)


@st.cache_data(show_spinner=False)
def load_receipts(file_bytes):
    receipt_path = os.path.join(TEMP_DIR, "receipt.pdf")
    with open(receipt_path, "wb") as f:
        f.write(file_bytes)
    return parse_receipt_pdf(receipt_path)


@st.cache_data(show_spinner=False)
def get_reconcile_result(df_bank, df_receipt):
    return reconcile_and_export(df_bank, df_receipt, output_dir=OUTPUT_DIR)


# ===============================================================

# ----------------- UI 界面构建 -----------------
st.title("📊 智能财务对账系统")
st.markdown("上传您的银行对账单和出账回单，系统将自动进行解析、清洗与匹配对账。")
st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("🏦 1. 银行对账单 (Bank PDF)")
    bank_file = st.file_uploader("请上传银行流水的 PDF 文件", type=["pdf"], key="bank")

with col2:
    st.subheader("🧾 2. 电子回单 (Receipt PDF)")
    receipt_file = st.file_uploader("请上传包含多张回单的 PDF 文件", type=["pdf"], key="receipt")

st.markdown("<br>", unsafe_allow_html=True)
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
with col_btn2:
    run_button = st.button("🚀 开始智能对账", use_container_width=True, type="primary")

# ================= ⭐ 核心优化：页面状态保持 =================
# 记忆按钮的点击状态，防止用户点击表格导致页面刷新后，结果直接消失
if "is_processed" not in st.session_state:
    st.session_state.is_processed = False

if run_button:
    if not bank_file or not receipt_file:
        st.warning("⚠️ 请先上传【银行对账单】和【电子回单】两个 PDF 文件！")
        st.session_state.is_processed = False
    else:
        st.session_state.is_processed = True

# 只有当处理状态为 True，且文件没有被用户清空时，才展示结果
if st.session_state.is_processed and bank_file and receipt_file:
    # ===============================================================

    with st.spinner("系统正在努力解析数据，请稍候..."):
        try:
            # 1. 获取文件的二进制数据，这是触发缓存的关键钥匙
            bank_bytes = bank_file.getvalue()
            receipt_bytes = receipt_file.getvalue()

            # 2. 调用带有缓存的函数（第二次执行时瞬间完成）
            df_bank = load_and_clean_bank(bank_bytes)
            df_receipt = load_receipts(receipt_bytes)

            if df_bank.empty:
                st.error("❌ 银行对账单解析失败或数据为空，请检查文件格式。")
            elif df_receipt.empty:
                st.error("❌ 电子回单解析失败或数据为空，请检查文件格式。")
            else:
                # 3. 对账逻辑同样被缓存
                df_result = get_reconcile_result(df_bank, df_receipt)

                # 为了防止用户修改表格导致原数据被污染，我们用 copy() 传给表格
                display_df = df_result.copy()

                st.success("🎉 数据加载成功！(已启用智能缓存，修改表格不会重复解析PDF)")

                # === 统计数据卡片 ===
                st.subheader("📈 对账概览")
                m1, m2, m3 = st.columns(3)
                m1.metric("银行流水总笔数", len(df_bank))
                m2.metric("识别到回单总笔数", len(df_receipt))
                matched_count = len(df_result[df_result["状态"] == "✔ 已对账"])
                m3.metric("成功匹配笔数", matched_count)

                # === 可视化图表区 ===
                st.divider()
                st.subheader("🎨 财务可视化分析")
                chart_col1, chart_col2 = st.columns(2)

                with chart_col1:
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

                # === 交互式数据表格 ===
                st.divider()
                st.subheader("📋 详细对账结果 (支持手动修改)")
                st.info("💡 提示：您可以双击表格手动更改状态。由于开启了智能缓存，修改操作将瞬间响应。")

                status_options = ["✔ 已对账", "❌ 未找到回单", "➕ 收入-不校验", "⚠️ 人工确认已核对"]

                edited_df = st.data_editor(
                    display_df,
                    column_config={
                        "状态": st.column_config.SelectboxColumn(
                            "状态 (双击修改)",
                            width="medium",
                            options=status_options,
                            required=True,
                        ),
                        "未对账原因": st.column_config.TextColumn(
                            "未对账原因/备注 (双击修改)",
                        )
                    },
                    disabled=["交易日期", "银行金额", "匹配回单数", "月份"],
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )

                # === 提供 Excel 下载 ===
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