import streamlit as st
import pandas as pd
import os
import plotly.express as px
from supabase import create_client, Client

# 导入核心逻辑
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
    for d in [TEMP_DIR, OUTPUT_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)


init_env()


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


st.title("📊 智能财务对账系统")
st.markdown("支持批量上传并合并对账，对账结果将自动同步至云端看板。")
st.divider()

# ================= ⭐ 核心优化：双标签页结构 =================
tab_reconcile, tab_history = st.tabs(["🔍 进行对账 (工作台)", "📈 历史报表 (大屏)"])

# ----------------- 标签页 1：对账工作台 -----------------
with tab_reconcile:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏦 1. 银行对账单 (支持多选)")
        bank_files = st.file_uploader("请拖拽或选择多个银行流水 PDF", type=["pdf"], key="bank", accept_multiple_files=True)

    with col2:
        st.subheader("🧾 2. 电子回单 (支持多选)")
        receipt_files = st.file_uploader("请拖拽或选择多个回单 PDF", type=["pdf"], key="receipt", accept_multiple_files=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
    with col_btn2:
        run_button = st.button("🚀 开始批量对账", use_container_width=True, type="primary")

    if "is_processed" not in st.session_state:
        st.session_state.is_processed = False

    if run_button:
        if not bank_files or not receipt_files:
            st.warning("⚠️ 请先至少上传一份【银行对账单】和一份【电子回单】！")
            st.session_state.is_processed = False
        else:
            st.session_state.is_processed = True

    if st.session_state.is_processed and bank_files and receipt_files:
        with st.spinner("系统正在努力解析和合并多个文件，请稍候..."):
            try:
                # 处理逻辑
                df_bank_list = [process_single_bank(bf.getvalue(), bf.name) for bf in bank_files]
                df_bank_list = [df for df in df_bank_list if not df.empty]
                df_bank_all = pd.concat(df_bank_list, ignore_index=True) if df_bank_list else pd.DataFrame()

                df_receipt_list = [process_single_receipt(rf.getvalue(), rf.name) for rf in receipt_files]
                df_receipt_list = [df for df in df_receipt_list if not df.empty]
                df_receipt_all = pd.concat(df_receipt_list, ignore_index=True) if df_receipt_list else pd.DataFrame()

                if df_bank_all.empty or df_receipt_all.empty:
                    st.error("❌ 解析失败或数据为空，请检查文件格式。")
                else:
                    df_result = get_reconcile_result(df_bank_all, df_receipt_all)
                    display_df = df_result.copy()

                    st.success(f"🎉 批量加载成功！共合并了 {len(bank_files)} 份银行流水和 {len(receipt_files)} 份回单。")

                    st.subheader("📈 对账概览")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("合并后流水笔数", len(df_bank_all))
                    m2.metric("合并后回单笔数", len(df_receipt_all))
                    matched_count = len(df_result[df_result["状态"] == "✔ 已对账"])
                    m3.metric("成功匹配笔数", matched_count)

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("☁️ 备份本次对账概览到云端", type="secondary"):
                        try:
                            url: str = st.secrets["SUPABASE_URL"]
                            key: str = st.secrets["SUPABASE_KEY"]
                            supabase: Client = create_client(url, key)

                            log_data = {
                                "bank_count": len(df_bank_all),
                                "receipt_count": len(df_receipt_all),
                                "matched_count": matched_count
                            }
                            supabase.table("history_logs").insert(log_data).execute()
                            st.success("✅ 云端备份成功！快去旁边的【📈 历史报表】看看吧！")
                            st.balloons()
                        except Exception as e:
                            st.error(f"❌ 备份失败: {e}")

                    st.divider()
                    st.subheader("🎨 财务可视化分析")
                    chart_col1, chart_col2 = st.columns(2)
                    with chart_col1:
                        status_counts = df_result["状态"].value_counts().reset_index()
                        status_counts.columns = ["状态", "数量"]
                        color_map = {"✔ 已对账": "#28a745", "❌ 未找到回单": "#dc3545", "➕ 收入-不校验": "#6c757d",
                                     "⚠️ 人工确认已核对": "#ffc107"}
                        fig_pie = px.pie(status_counts, names="状态", values="数量", title="状态分布", color="状态",
                                         color_discrete_map=color_map, hole=0.4)
                        st.plotly_chart(fig_pie, use_container_width=True)

                    with chart_col2:
                        df_expense = df_result[df_result["银行金额"] < 0].copy()
                        if not df_expense.empty:
                            df_expense["支出金额"] = df_expense["银行金额"].abs().round(2)
                            df_expense["纯日期"] = pd.to_datetime(df_expense["交易日期"]).dt.strftime('%Y-%m-%d')
                            daily_expense = df_expense.groupby("纯日期")["支出金额"].sum().reset_index()
                            fig_bar = px.bar(daily_expense, x="纯日期", y="支出金额", title="每日支出汇总", text_auto='.2f',
                                             color_discrete_sequence=["#FF7F0E"])
                            st.plotly_chart(fig_bar, use_container_width=True)
                        else:
                            st.info("没有支出记录。")

                    st.divider()
                    st.subheader("📋 详细结果 (支持双击修改)")
                    status_options = ["✔ 已对账", "❌ 未找到回单", "➕ 收入-不校验", "⚠️ 人工确认已核对"]
                    edited_df = st.data_editor(
                        display_df,
                        column_config={
                            "状态": st.column_config.SelectboxColumn("状态 (双击修改)", options=status_options, required=True)},
                        disabled=["交易日期", "银行金额", "匹配回单数", "月份"],
                        use_container_width=True, hide_index=True, height=400
                    )

                    st.divider()
                    st.subheader("💾 导出结果")
                    final_excel_path = os.path.join(OUTPUT_DIR, "最终对账单.xlsx")
                    edited_df.to_excel(final_excel_path, index=False)
                    with open(final_excel_path, "rb") as f:
                        st.download_button("📥 下载最新对账 Excel", data=f, file_name="自动化批量对账结果.xlsx",
                                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                           type="primary")

            except Exception as e:
                st.error(f"💔 发生错误: {str(e)}")

# ----------------- 标签页 2：历史报表大屏 -----------------
with tab_history:
    st.subheader("🌍 云端对账历史数据")
    st.info("💡 这里的每次记录都来自于工作台点击【☁️ 备份本次对账概览到云端】按钮产生的数据。")

    # 获取数据的按钮，不加缓存，保证每次点击都能看到最新数据
    if st.button("🔄 刷新最新报表数据"):
        with st.spinner("正在从云端拉取数据..."):
            try:
                url: str = st.secrets["SUPABASE_URL"]
                key: str = st.secrets["SUPABASE_KEY"]
                supabase: Client = create_client(url, key)

                # 从数据库拉取所有记录，按时间倒序排
                response = supabase.table("history_logs").select("*").order("created_at", desc=False).execute()
                history_data = response.data

                if not history_data:
                    st.warning("📭 云端数据库目前还是空的，请先在工作台跑一次对账并备份。")
                else:
                    # 转换成 DataFrame 方便处理
                    df_hist = pd.DataFrame(history_data)

                    # 清洗时间格式 (把 UTC 时间转成好看的本地日期)
                    df_hist["created_at"] = pd.to_datetime(df_hist["created_at"]).dt.tz_convert(
                        'Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M')
                    df_hist.rename(columns={
                        "created_at": "备份时间",
                        "bank_count": "总流水数",
                        "receipt_count": "提供回单数",
                        "matched_count": "成功匹配数"
                    }, inplace=True)

                    # 计算一个额外的指标：匹配成功率
                    df_hist["成功率(%)"] = (df_hist["成功匹配数"] / df_hist["总流水数"] * 100).round(1)

                    # --- 画折线大图 ---
                    fig_line = px.line(
                        df_hist,
                        x="备份时间",
                        y="成功匹配数",
                        markers=True,
                        title="历次对账成功匹配数量走势图",
                        color_discrete_sequence=["#1f77b4"]
                    )
                    fig_line.update_traces(line=dict(width=3), marker=dict(size=8))
                    st.plotly_chart(fig_line, use_container_width=True)

                    # --- 展示数据明细表 ---
                    st.markdown("#### 📝 历史备份明细")
                    st.dataframe(
                        df_hist.sort_values(by="备份时间", ascending=False),  # 明细表倒序，最新的在最上面
                        use_container_width=True,
                        hide_index=True
                    )

            except Exception as e:
                st.error(f"❌ 无法连接到云端数据库，请检查 Secrets 配置或网络: {e}")