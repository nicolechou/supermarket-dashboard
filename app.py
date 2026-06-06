import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yaml
import streamlit_authenticator as stauth
from pathlib import Path

st.set_page_config(
    page_title="超市銷售儀表板",
    page_icon="🛒",
    layout="wide",
)

# ── 載入帳號設定 ──────────────────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "config.yaml"

def load_config():
    # 支援 Streamlit Cloud Secrets（部署用）或本地 config.yaml（開發用）
    if "credentials" in st.secrets:
        return {
            "credentials": st.secrets["credentials"].to_dict(),
            "cookie": st.secrets["cookie"].to_dict(),
        }
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
)

# ── 登入畫面 ──────────────────────────────────────────────────────────────────
authenticator.login(location="main")

if st.session_state.get("authentication_status") is False:
    st.error("帳號或密碼錯誤，請重新輸入")
    st.stop()

if st.session_state.get("authentication_status") is None:
    st.info("請輸入帳號和密碼以登入")
    st.stop()

# ── 已登入：顯示儀表板 ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state.get('name', '')}")
    authenticator.logout("登出", location="sidebar")
    st.divider()

# ── 載入資料 ──────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    data_path = Path(__file__).parent / "supermarket_sales.csv"
    df = pd.read_csv(data_path)
    df["Date"] = pd.to_datetime(df["Date"])
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    df["DayOfWeek"] = df["Date"].dt.day_name()
    df["Hour"] = pd.to_datetime(df["Time"], format="%H:%M").dt.hour
    return df

df_all = load_data()

# ── 側邊欄篩選器 ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("🔍 篩選條件")

    branches = st.multiselect(
        "分店",
        options=sorted(df_all["Branch"].unique()),
        default=sorted(df_all["Branch"].unique()),
    )

    product_lines = st.multiselect(
        "產品線",
        options=sorted(df_all["Product line"].unique()),
        default=sorted(df_all["Product line"].unique()),
    )

    payment_methods = st.multiselect(
        "付款方式",
        options=sorted(df_all["Payment"].unique()),
        default=sorted(df_all["Payment"].unique()),
    )

    date_min = df_all["Date"].min().date()
    date_max = df_all["Date"].max().date()
    date_range = st.date_input("日期範圍", value=(date_min, date_max), min_value=date_min, max_value=date_max)

# 套用篩選
df = df_all[
    df_all["Branch"].isin(branches)
    & df_all["Product line"].isin(product_lines)
    & df_all["Payment"].isin(payment_methods)
]
if len(date_range) == 2:
    df = df[(df["Date"].dt.date >= date_range[0]) & (df["Date"].dt.date <= date_range[1])]

# ── 頁面標題 ──────────────────────────────────────────────────────────────────
st.title("🛒 超市銷售儀表板")
st.caption(f"資料期間：{df_all['Date'].min().strftime('%Y-%m-%d')} ～ {df_all['Date'].max().strftime('%Y-%m-%d')}　｜　篩選後筆數：{len(df):,}")

# ── KPI 卡片 ──────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)

total_revenue = df["Total"].sum()
total_profit = df["gross income"].sum()
avg_transaction = df["Total"].mean()
avg_rating = df["Rating"].mean()

k1.metric("💰 總營收", f"${total_revenue:,.0f}")
k2.metric("📈 總毛利", f"${total_profit:,.0f}")
k3.metric("🧾 平均客單價", f"${avg_transaction:,.1f}")
k4.metric("⭐ 平均評分", f"{avg_rating:.2f} / 10")

st.divider()

# ── 第一排：趨勢 + 產品線 ─────────────────────────────────────────────────────
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("各分店月營收趨勢")
    trend = df.groupby(["Month", "Branch"])["Total"].sum().reset_index()
    fig_trend = px.line(
        trend, x="Month", y="Total", color="Branch",
        markers=True,
        labels={"Total": "營收 ($)", "Month": "月份", "Branch": "分店"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_trend.update_layout(legend_title_text="分店", height=320)
    st.plotly_chart(fig_trend, use_container_width=True)

with col2:
    st.subheader("產品線銷售佔比")
    pl_sales = df.groupby("Product line")["Total"].sum().reset_index()
    fig_pie = px.pie(
        pl_sales, values="Total", names="Product line",
        hole=0.35,
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    fig_pie.update_layout(showlegend=False, height=320)
    st.plotly_chart(fig_pie, use_container_width=True)

# ── 第二排：熱力圖 + 付款方式 ─────────────────────────────────────────────────
col3, col4 = st.columns([3, 2])

with col3:
    st.subheader("銷售熱力圖（星期 × 時段）")
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    heat = df.groupby(["DayOfWeek", "Hour"])["Total"].sum().reset_index()
    heat_pivot = heat.pivot(index="DayOfWeek", columns="Hour", values="Total").reindex(day_order)
    fig_heat = px.imshow(
        heat_pivot,
        labels={"x": "小時", "y": "星期", "color": "營收"},
        color_continuous_scale="Blues",
        aspect="auto",
    )
    fig_heat.update_layout(height=320)
    st.plotly_chart(fig_heat, use_container_width=True)

with col4:
    st.subheader("付款方式分佈")
    pay = df.groupby("Payment")["Total"].sum().reset_index().sort_values("Total", ascending=True)
    fig_pay = px.bar(
        pay, x="Total", y="Payment", orientation="h",
        labels={"Total": "營收 ($)", "Payment": "付款方式"},
        color="Payment",
        color_discrete_sequence=px.colors.qualitative.Set3,
    )
    fig_pay.update_layout(showlegend=False, height=320)
    st.plotly_chart(fig_pay, use_container_width=True)

# ── 第三排：客戶類型 + 評分分佈 ───────────────────────────────────────────────
col5, col6 = st.columns(2)

with col5:
    st.subheader("客戶類型 × 產品線平均消費")
    cust = df.groupby(["Customer type", "Product line"])["Total"].mean().reset_index()
    fig_cust = px.bar(
        cust, x="Product line", y="Total", color="Customer type",
        barmode="group",
        labels={"Total": "平均消費 ($)", "Product line": "產品線", "Customer type": "客戶類型"},
        color_discrete_sequence=["#636EFA", "#EF553B"],
    )
    fig_cust.update_layout(legend_title_text="客戶類型", height=320, xaxis_tickangle=-20)
    st.plotly_chart(fig_cust, use_container_width=True)

with col6:
    st.subheader("客戶評分分佈")
    fig_hist = px.histogram(
        df, x="Rating", nbins=20,
        labels={"Rating": "評分", "count": "筆數"},
        color_discrete_sequence=["#00CC96"],
    )
    fig_hist.update_layout(bargap=0.05, height=320)
    st.plotly_chart(fig_hist, use_container_width=True)

# ── 原始資料預覽 ───────────────────────────────────────────────────────────────
with st.expander("📋 原始資料預覽（前 100 筆）"):
    st.dataframe(df.head(100), use_container_width=True)
