import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. Page Configuration
st.set_page_config(page_title="CryptoLakehouse", layout="wide", page_icon="📊")

# Modern dark theme styling
st.markdown("""
    <style>
    div[data-testid="stMetricValue"] { color: #E2E8F0 !important; }
    div[data-testid="stMetricLabel"] { color: #94A3B8 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Enterprise Crypto Data Lakehouse")
st.markdown("Live Multi-Asset Metrics via **Supabase Postgres**")

# 2. Database Connection
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# 3. Data Ingestion
@st.cache_data(ttl=1800)
def load_data():
    response = supabase.table("crypto_metrics").select(
        "coin_id, datetime_utc, price, market_cap, total_volume"
    ).order("datetime_utc", desc=False).execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        df['datetime_utc'] = pd.to_datetime(df['datetime_utc'])
        return df
    return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("No records found. Please ensure your pipeline is ingesting data.")
else:
    # 4. Sidebar Controls
    st.sidebar.header("Dashboard Controls")
    
    available_coins = sorted(df['coin_id'].unique().tolist())
    selected_coin = st.sidebar.selectbox("Select Primary Asset", available_coins, index=0)
    view_mode = st.sidebar.radio("Analysis Mode", ["Single Asset Analysis", "Market Comparison"])
    
    st.sidebar.divider()
    
    # Date Filtering Controls (Always visible with toggle)
    st.sidebar.subheader("Date Range Settings")
    min_date = df['datetime_utc'].min().date()
    max_date = df['datetime_utc'].max().date()
    
    # Toggle between All Data and Custom Range
    enable_custom_range = st.sidebar.toggle("Enable Custom Date Range", value=False)
    
    # Date input remains permanently rendered on screen
    date_range = st.sidebar.date_input(
        "Select Date Window",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        disabled=not enable_custom_range
    )
    
    # Determine active start and end dates
    if enable_custom_range and isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    # Master Filter applied to both single and multi-asset modes
    mask = (df['datetime_utc'].dt.date >= start_date) & (df['datetime_utc'].dt.date <= end_date)
    filtered_df = df.loc[mask].copy()

    display_df = pd.DataFrame()

    # 5. Visualizations
    if view_mode == "Single Asset Analysis":
        display_df = filtered_df[filtered_df['coin_id'] == selected_coin].sort_values("datetime_utc")
        
        if not display_df.empty:
            latest = display_df.iloc[-1]
            
            # KPI Cards
            col1, col2, col3 = st.columns(3)
            col1.metric("Current Price", f"${latest['price']:,.2f}")
            col2.metric("Market Cap", f"${latest['market_cap']:,.0f}" if pd.notnull(latest['market_cap']) else "N/A")
            col3.metric("24h Volume", f"${latest['total_volume']:,.0f}" if pd.notnull(latest['total_volume']) else "N/A")

            st.divider()

            # Dual-Axis Price & Volume Profile
            st.subheader(f"{selected_coin.capitalize()} Price & Volume Profile")
            fig_combined = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig_combined.add_trace(
                go.Scatter(
                    x=display_df['datetime_utc'], y=display_df['price'],
                    name="Price (USD)", line=dict(color="#3B82F6", width=2)
                ),
                secondary_y=False,
            )
            fig_combined.add_trace(
                go.Bar(
                    x=display_df['datetime_utc'], y=display_df['total_volume'],
                    name="Volume", marker_color="#10B981", opacity=0.3
                ),
                secondary_y=True,
            )
            fig_combined.update_layout(
                template="plotly_dark",
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            fig_combined.update_yaxes(title_text="Price (USD)", secondary_y=False)
            fig_combined.update_yaxes(title_text="Volume (USD)", showgrid=False, secondary_y=True)
            st.plotly_chart(fig_combined, width='stretch')

            # Market Cap Area Chart
            st.subheader("Market Capitalization Trend")
            fig_mcap = go.Figure()
            fig_mcap.add_trace(go.Scatter(
                x=display_df['datetime_utc'], y=display_df['market_cap'],
                fill='tozeroy', mode='lines', line=dict(color="#8B5CF6"),
                name="Market Cap"
            ))
            fig_mcap.update_layout(template="plotly_dark", yaxis_title="Market Cap (USD)")
            st.plotly_chart(fig_mcap, width='stretch')
        else:
            st.info("No records found for this coin within the selected date range.")

    else:
        # ==================== MARKET COMPARISON MODE ====================
        display_df = filtered_df
        st.subheader("🌐 Comprehensive Market Comparison Suite")

        if not display_df.empty:
            # Row 1: Normalized Returns & Raw Price
            col_m1, col_m2 = st.columns(2)

            with col_m1:
                # Normalized % Performance
                filtered_df_sorted = filtered_df.sort_values('datetime_utc')
                norm_df = filtered_df_sorted.copy()
                norm_df['normalized_return'] = norm_df.groupby('coin_id')['price'].transform(
                    lambda x: ((x - x.iloc[0]) / x.iloc[0]) * 100 if len(x) > 0 and x.iloc[0] > 0 else 0
                )

                fig_norm = px.line(
                    norm_df, x="datetime_utc", y="normalized_return", color="coin_id",
                    template="plotly_dark", title="Normalized Performance (% Return from Period Start)"
                )
                fig_norm.update_layout(xaxis_title="", yaxis_title="Return (%)", hovermode="x unified")
                st.plotly_chart(fig_norm, width='stretch')

            with col_m2:
                # Raw Comparative Price with Log Scale
                use_log = st.checkbox("Logarithmic Scale", value=True, help="Balances BTC vs ETH vs USDT visual gaps")
                fig_compare_price = px.line(
                    display_df, x="datetime_utc", y="price", color="coin_id",
                    template="plotly_dark", title="Raw Comparative Price History", log_y=use_log
                )
                fig_compare_price.update_layout(xaxis_title="", yaxis_title="Price (USD)", hovermode="x unified")
                st.plotly_chart(fig_compare_price, width='stretch')

            st.divider()

            # Row 2: Market Cap Dominance & Velocity
            col_m3, col_m4 = st.columns(2)

            with col_m3:
                fig_share = px.area(
                    display_df, x="datetime_utc", y="market_cap", color="coin_id",
                    groupnorm="percent", template="plotly_dark",
                    title="Market Cap Dominance Share (%)"
                )
                fig_share.update_layout(xaxis_title="", yaxis_title="Dominance (%)", hovermode="x unified")
                st.plotly_chart(fig_share, width='stretch')

            with col_m4:
                temp_turnover_df = display_df.copy()
                temp_turnover_df['turnover_ratio'] = (temp_turnover_df['total_volume'] / temp_turnover_df['market_cap']) * 100
                
                fig_turnover = px.line(
                    temp_turnover_df, x="datetime_utc", y="turnover_ratio", color="coin_id",
                    template="plotly_dark", title="Trading Velocity (Volume / Market Cap %)"
                )
                fig_turnover.update_layout(xaxis_title="", yaxis_title="Turnover Ratio (%)", hovermode="x unified")
                st.plotly_chart(fig_turnover, width='stretch')

            st.divider()

            # Row 3: Absolute Market Cap & Volume
            col_m5, col_m6 = st.columns(2)

            with col_m5:
                fig_compare_mcap = px.line(
                    display_df, x="datetime_utc", y="market_cap", color="coin_id",
                    template="plotly_dark", title="Comparative Absolute Market Cap"
                )
                fig_compare_mcap.update_layout(xaxis_title="", yaxis_title="Market Cap (USD)", hovermode="x unified")
                st.plotly_chart(fig_compare_mcap, width='stretch')

            with col_m6:
                fig_compare_vol = px.bar(
                    display_df, x="datetime_utc", y="total_volume", color="coin_id",
                    template="plotly_dark", title="Comparative 24h Trading Volume", barmode='group'
                )
                fig_compare_vol.update_layout(xaxis_title="", yaxis_title="Volume (USD)", hovermode="x unified")
                st.plotly_chart(fig_compare_vol, width='stretch')
        else:
            st.info("No records found across assets within the selected date range.")

    # Raw Data Table Contextually Filtered
    with st.expander("View Filtered Datastore"):
        st.dataframe(
            display_df.sort_values(by="datetime_utc", ascending=False),
            width='stretch'
        )