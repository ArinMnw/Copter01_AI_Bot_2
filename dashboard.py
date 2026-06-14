import streamlit as st
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
import json
import os

# Set page config
st.set_page_config(page_title="Copter Gold Bot Dashboard", page_icon="📈", layout="wide")

# ── Premium Global UI Injection ──
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');

html, body, [class*="css"]  {
    font-family: 'Outfit', sans-serif !important;
}

/* App Background: Deep dark premium gradient */
.stApp {
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
    color: #f8fafc;
}

/* Hide default streamlit elements */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}

/* Glassmorphism Metric Cards */
div[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    animation: fadeInUp 0.8s ease-out;
}

div[data-testid="stMetric"]:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 40px rgba(99, 102, 241, 0.3);
    border: 1px solid rgba(99, 102, 241, 0.5);
}

/* Metric labels and values */
div[data-testid="stMetricLabel"] > div > div > p {
    color: #94a3b8 !important;
    font-size: 1.1rem !important;
    font-weight: 600;
}

div[data-testid="stMetricValue"] > div {
    font-size: 2.5rem !important;
    font-weight: 800;
    background: -webkit-linear-gradient(45deg, #38bdf8, #818cf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

/* Charts & Dataframes */
div[data-testid="stDataFrame"], .stVegaLiteChart {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.05);
    padding: 15px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    animation: fadeInUp 1s ease-out;
}

/* Animations */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Custom Headers */
h1 {
    font-weight: 800 !important;
    background: -webkit-linear-gradient(45deg, #ffffff, #64748b);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    padding-bottom: 20px;
}
h2, h3 {
    font-weight: 600 !important;
    color: #e2e8f0 !important;
}

/* Dividers */
hr {
    border-color: rgba(255, 255, 255, 0.1) !important;
}
</style>
""", unsafe_allow_html=True)
# ──────────────────────────────────

st.title("🤖 Copter Gold Bot - Command Center")

@st.cache_data(ttl=60)
def load_bot_state():
    state_file = "bot_state.json"
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@st.cache_data(ttl=300)
def load_mt5_history(days=30):
    if not mt5.initialize():
        return pd.DataFrame()
    
    tz = timezone(timedelta(hours=7)) # BKK
    end_time = datetime.now(tz)
    start_time = end_time - timedelta(days=days)
    
    history_deals = mt5.history_deals_get(start_time, end_time)
    if history_deals is None or len(history_deals) == 0:
        return pd.DataFrame()
        
    df = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Filter only closed trades that affected balance
    df = df[df['entry'] == mt5.DEAL_ENTRY_OUT]
    return df

state = load_bot_state()
df_history = load_mt5_history()

# Layout
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Auto Trade Active", "✅ YES" if state.get("auto_active", False) else "❌ NO")
with col2:
    st.metric("Daily P/L", f"${state.get('daily_stats', {}).get('realized', 0.0):.2f}")
with col3:
    st.metric("Total Trades Today", str(state.get('daily_stats', {}).get('count', 0)))
with col4:
    if not df_history.empty:
        total_profit = df_history['profit'].sum()
        st.metric("30-Day Profit", f"${total_profit:.2f}")

if not df_history.empty:
    st.divider()
    col_m1, col_m2, col_m3 = st.columns(3)
    wins = df_history[df_history['profit'] > 0]
    losses = df_history[df_history['profit'] <= 0]
    win_rate = len(wins) / len(df_history) * 100 if len(df_history) > 0 else 0
    avg_win = wins['profit'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['profit'].mean()) if len(losses) > 0 else 1
    rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    with col_m1:
        st.metric("Win Rate (30D)", f"{win_rate:.1f}%")
    with col_m2:
        st.metric("Average R:R Ratio", f"1 : {rr_ratio:.2f}")
    with col_m3:
        st.metric("Total Trades (30D)", str(len(df_history)))

st.divider()

if not df_history.empty:
    st.subheader("📈 30-Day Equity Curve")
    df_history = df_history.sort_values(by='time')
    df_history['cumulative_profit'] = df_history['profit'].cumsum()
    st.line_chart(df_history.set_index('time')['cumulative_profit'])
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("💡 Profit by Symbol")
        profit_by_symbol = df_history.groupby('symbol')['profit'].sum()
        st.bar_chart(profit_by_symbol)
        
    with col_chart2:
        st.subheader("🕒 Trade Count by Hour")
        df_history['hour'] = df_history['time'].dt.hour
        trades_by_hour = df_history.groupby('hour').size()
        st.bar_chart(trades_by_hour)

    st.divider()
    st.subheader("🏆 Strategy Leaderboard (Profit by SID)")
    # Extract SID from comment (e.g. M1_S14_PB -> S14)
    df_history['strategy'] = df_history['comment'].str.extract(r'_(S\d+)')
    # For trades without a recognized pattern, label as 'Manual/Other'
    df_history['strategy'] = df_history['strategy'].fillna('Other')
    profit_by_strategy = df_history.groupby('strategy')['profit'].sum().sort_values(ascending=False)
    st.bar_chart(profit_by_strategy)
else:
    st.warning("No MT5 History found or MT5 not connected.")

st.divider()
st.subheader("📋 Current Tracked Positions")
tracked = state.get("tracked_positions", {})
if tracked:
    df_tracked = pd.DataFrame.from_dict(tracked, orient='index')
    st.dataframe(df_tracked, use_container_width=True)
else:
    st.info("No active positions tracked.")
