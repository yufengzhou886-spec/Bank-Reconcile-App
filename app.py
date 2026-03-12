import streamlit as st
import pandas as pd
import os
import shutil
import plotly.express as px
from supabase import create_client, Client  # ⭐ 引入 Supabase 库

# 导入你原有的核心逻辑（完全无需修改）
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
        if not os.path.exists(d):
            os.makedirs(d)


init_env()


# ================= ⭐ 核心优化：单文件解析缓存 =================
@st.cache_data(show_spinner=False)
def process_single_bank(file_bytes, file_name):
    temp_path = os.path.join(TEMP_DIR, f"bank_{file_name}")
    with open(temp_path, "wb") as f:
        f.write(file_bytes)
    raw_df = parse_bank_pdf(temp_path)
    return clean_bank_data(raw_df)


@st.cache_data(show_spinner=False)
def process_single_receipt(file_bytes, file_name):
    temp_path = os.path.join(TEMP_DIR, f"receipt_{file_name}")
    with open(temp_path, "wb") as f:
        f.write(file_bytes)
    return parse_receipt_pdf(temp_path)


@st.cache_data(show_spinner=False)
def get_reconcile_result(df_bank, df_receipt):
    return reconcile_and_export(df_bank, df_receipt, output_dir=OUTPUT_DIR)


# ===============================================================

# ----------------- UI 界面构建 -----------------
st.title("📊 智能财务对账系统")
st.markdown("支持**批量上传**多个银行对账单和出账回单，系统将自动合并、清洗并进行全局匹配对账。")
st.divider()

# 使用两列布局放置上传组件
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏦 1. 银行对账单 (支持多选)")
    bank_files = st.file_uploader("请拖拽或选择多个银行流水 PDF", type=["pdf"], key="bank", accept_multiple_files=True)

with col2:
    st.subheader("🧾 2. 电子回单 (支持多选)")
    receipt_files = st.file_uploader("请拖拽或选择多个回单 PDF", type=["pdf"], key="receipt", accept_multiple_files=True)

# 居中放置运行按钮
st.markdown("<br>", unsafe_allow_html=True)
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
with col_btn2:
    run_button = st.button("🚀 开始批量对账", use_container_width=True, type="primary")

# 记忆按钮的点击状态，防止页面刷新丢失结果
if "is_processed" not in st.session_state:
    st.session_state.is_processed = False

if run_button:
    if not bank_files or not receipt_files:
        st.warning("⚠️ 请先至少上传一份【银行对账单】和一份【电子回单】！")
        st.session_state.is_processed = False
    else:
        st.session_state.is_processed = True

# 只有当处理状态为 True，且文件没有被清空时，才展示结果
if st.session_state.is_processed and bank_files and receipt_files:
    with st.spinner("系统正在努力解析和合并多个文件，请稍候..."):
        try:
            # === 1. 批量处理银行账单并缝合 ===
            df_bank_list = []
            for bf in bank_files:
                df = process_single_bank(bf.getvalue(), bf.name)
                if not df.empty:
                    df_bank_list.append(df)

            df_bank_all = pd.concat(df_bank_list, ignore_index=True) if df_bank_list else pd.DataFrame()

            # === 2. 批量处理电子回单并缝合 ===
            df_receipt_list = []
            for rf in receipt_files:
                df = process_single_receipt(rf.getvalue(), rf.name)
                if not df.empty:
                    df_receipt_list.append(df)

            df_receipt_all = pd.concat(df_receipt_list, ignore_index=True) if df_receipt_list else pd.DataFrame()

            # === 3. 拦截空表 ===
            if df_bank_all.empty:
                st.error("❌ 银行对账单全部解析失败或数据为空，请检查文件格式。")
            elif df_receipt_all.empty:
                st.error("❌ 电子回单全部解析失败或数据为空，请检查文件格式。")
            else:
                # === 4. 调用对账逻辑 ===
                df_result = get_reconcile_result(df_bank_all, df_receipt_all)
                display_df = df_result.copy()

                st.success(f"🎉 批量加载成功！共合并了 {len(bank_files)} 份银行流水和 {len(receipt_files)} 份回单文件。")

                # === 5. 统计数据卡片 ===
                st.subheader("📈 对账概览")
                m1, m2, m3 = st.columns(3)
                m1.metric("合并后银行流水笔数", len(df_bank_all))
                m2.metric("合并后识别回单笔数", len(df_receipt_all))
                matched_count = len(df_result[df_result["状态"] == "✔ 已对账"])
                m3.metric("成功匹配笔数", matched_count)

                # ================= ⭐ 新增：云端备份按钮 =================
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("☁️ 备份本次对账概览到云端数据库", type="secondary"):
                    try:
                        # 从 Streamlit Secrets 里获取 Supabase 密钥
                        url: str = st.secrets["SUPABASE_URL"]
                        key: str = st.secrets["SUPABASE_KEY"]
                        supabase: Client = create_client(url, key)

                        # 组装要保存的数据
                        log_data = {
                            "bank_count": len(df_bank_all),
                            "receipt_count": len(df_receipt_all),
                            "matched_count": matched_count
                        }

                        # 写入 Supabase 的 history_logs 表
                        data, count = supabase.table("history_logs").insert(log_data).execute()
                        st.success("✅ 云端备份成功！老板以后随时可以拉历史报表啦！")
                        st.balloons()  # 庆祝动画
                    except Exception as e:
                        st.error(f"❌ 备份失败，请检查网络或 Secrets 配置: {e}")
                # ===============================================================

                # === 6. 可视化图表区 ===
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
                        status_counts, names="状态", values="数量", title="对账状态分布 (笔数)",
                        color="状态", color_discrete_map=color_map, hole=0.4
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
                            daily_expense, x="纯日期", y="支出金额", title="每日支出金额汇总 (元)",
                            text_auto='.2f', color_discrete_sequence=["#FF7F0E"]
                        )
                        fig_bar.update_layout(
                            xaxis_title="交易日期", yaxis_title="总支出金额 (元)", xaxis={'type': 'category'}
                        )
                        st.plotly_chart(fig_bar, use_container_width=True)
                    else:
                        st.info("没有支出记录，无法生成支出图表。")

                # === 7. 交互式数据表格 ===
                st.divider()
                st.subheader("📋 详细对账结果 (支持手动修改)")
                st.info("💡 提示：您可以双击表格手动更改状态。由于开启了智能缓存，修改操作将瞬间响应。")

                status_options = ["✔ 已对账", "❌ 未找到回单", "➕ 收入-不校验", "⚠️ 人工确认已核对"]

                edited_df = st.data_editor(
                    display_df,
                    column_config={
                        "状态": st.column_config.SelectboxColumn("状态 (双击修改)", width="medium", options=status_options,
                                                               required=True),
                        "未对账原因": st.column_config.TextColumn("未对账原因/备注 (双击修改)")
                    },
                    disabled=["交易日期", "银行金额", "匹配回单数", "月份"],
                    use_container_width=True, hide_index=True, height=400
                )

                # === 8. 提供 Excel 下载 ===
                st.divider()
                st.subheader("💾 导出结果")
                final_excel_path = os.path.join(OUTPUT_DIR, "最终汇总对账单.xlsx")
                edited_df.to_excel(final_excel_path, index=False)

                with open(final_excel_path, "rb") as f:
                    st.download_button(
                        label="📥 下载最新对账 Excel", data=f, file_name="自动化批量对账结果.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary"
                    )

        except Exception as e:
            st.error(f"💔 处理过程中出现错误: {str(e)}")