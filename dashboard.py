import streamlit as st
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
import json
import os
import re
import glob
import time
from collections import Counter
import streamlit.components.v1 as components

try:
    from strategy_patterns import STRATEGY_PATTERNS
except Exception:
    STRATEGY_PATTERNS = {}

BKK = timezone(timedelta(hours=7))

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

# ── Sidebar controls ─────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")
    if st.button("🔄 Refresh now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    auto_refresh = st.checkbox("Auto-refresh", value=False)
    refresh_sec = st.select_slider("Interval (s)", options=[15, 30, 60], value=30)
    history_days = st.slider("History window (days)", 1, 90, 30)

if auto_refresh:
    # JS reload — เลี่ยง dependency streamlit_autorefresh
    try:
        from streamlit.components.v1 import html as _st_html
        _st_html(
            f"<script>setTimeout(function(){{window.parent.location.reload();}}, {refresh_sec * 1000});</script>",
            height=0,
        )
    except Exception:
        pass


# ── Data loaders ─────────────────────────────────────────────
@st.cache_data(ttl=15)
def load_bot_state():
    state_file = "bot_state.json"
    # bot เขียนไฟล์นี้ทุก 15s — retry กัน partial read กลาง write
    for _ in range(3):
        try:
            if os.path.exists(state_file):
                with open(state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except (json.JSONDecodeError, OSError):
            time.sleep(0.15)
    return {}


def load_heartbeat():
    """อ่าน bot_heartbeat.txt (เขียนทุก 15s) — ไม่ cache เพื่อให้ freshness แม่น"""
    f = "bot_heartbeat.txt"
    if not os.path.exists(f):
        return {}
    try:
        d = {}
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    d[k] = v
        return d
    except Exception:
        return {}


@st.cache_data(ttl=60)
def load_news_status():
    import news_filter
    try:
        is_active, reason = news_filter.is_news_embargo_active()
        upcoming = news_filter.get_upcoming_news()
        return is_active, reason, upcoming
    except Exception:
        return False, "", []


@st.cache_data(ttl=300)
def load_mt5_history(days=30):
    if not mt5.initialize():
        return pd.DataFrame()

    end_time = datetime.now(BKK)
    start_time = end_time - timedelta(days=days)

    history_deals = mt5.history_deals_get(start_time, end_time)
    if history_deals is None or len(history_deals) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
    # deal time เป็น UTC epoch → แปลงเป็น BKK (UTC+7) ตามกฎ timezone ของ repo
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert(BKK).dt.tz_localize(None)

    # Net P/L รวม swap + commission + fee (ไม่ใช่แค่ profit)
    for col in ('profit', 'swap', 'commission', 'fee'):
        if col not in df.columns:
            df[col] = 0.0
    df['net'] = df['profit'] + df['swap'] + df['commission'] + df['fee']

    # เฉพาะดีลปิด (ที่กระทบ balance)
    df = df[df['entry'] == mt5.DEAL_ENTRY_OUT]
    return df


def _find_bot_log():
    candidates = ["logs/bot.log", f"logs/bot-{datetime.now(BKK).strftime('%Y-%m')}.log"]
    for c in candidates:
        if os.path.exists(c):
            return c
    files = glob.glob("logs/**/bot*.log", recursive=True)
    files = [f for f in files if not f.endswith(".bak")]
    if files:
        return max(files, key=os.path.getmtime)
    return None


# event ที่ถือว่าเป็น "block/skip" (ทำไมไม่เข้าไม้) และ "error"
BLOCK_EVENTS = [
    "SL_GUARD_GROUP_BLOCK", "SL_GUARD_BLOCK", "TREND_FILTER_BLOCK",
    "SYMBOL_GUARD_BLOCK", "CONFIRM_LOOKBACK_BLOCK", "STRONG_TREND_BLOCK",
    "PENDING_LIMIT_BLOCK", "SCAN_SKIP", "ORDER_SKIPPED",
]
FEED_EVENTS = [
    "ORDER_CREATED", "ENTRY_FILL", "POSITION_CLOSED", "ORDER_CANCELED",
    "ORDER_FAILED", "TG_DROP", "SL_CHANGED",
]
_TS = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\S+)')


@st.cache_data(ttl=60)
def load_log_events():
    path = _find_bot_log()
    if not path:
        return {}
    blocks = Counter()
    errors = Counter()
    feed = []  # ring buffer ของ event น่าสนใจล่าสุด
    first_ts = last_ts = None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = _TS.match(line)
                if not m:
                    continue
                ts, ev = m.group(1), m.group(2)
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
                if ev in BLOCK_EVENTS:
                    blocks[ev] += 1
                if ev in ("ORDER_FAILED", "TG_DROP") or ev.endswith("_ERROR") or ev.endswith("_FAIL"):
                    errors[ev] += 1
                if ev in FEED_EVENTS or ev.endswith("_ERROR"):
                    summary = line.split("] ", 1)[-1].strip()
                    feed.append((ts, ev, summary[:130]))
    except Exception:
        return {}
    return {
        "path": path,
        "span": (first_ts, last_ts),
        "blocks": dict(blocks),
        "errors": dict(errors),
        "feed": feed[-20:][::-1],
    }


# ── Load all ─────────────────────────────────────────────────
state = load_bot_state()
df_history = load_mt5_history(history_days)
news_active, news_reason, upcoming_news = load_news_status()
hb = load_heartbeat()
logs = load_log_events()

tab_overview, tab_strat, tab_health, tab_docs = st.tabs(
    ["📊 Overview", "🏆 Strategies", "🩺 Health & Logs", "📚 Strategy Docs"]
)

# ============================================================
#  TAB 1 — OVERVIEW
# ============================================================
with tab_overview:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("Auto Trade", "✅ ON" if state.get("auto_active", False) else "❌ OFF")
    with c2:
        st.metric("Daily P/L", f"${state.get('daily_stats', {}).get('realized', 0.0):.2f}")
    with c3:
        st.metric("Trades Today", str(state.get('daily_stats', {}).get('count', 0)))
    with c4:
        st.metric("Net Profit", f"${df_history['net'].sum():.2f}" if not df_history.empty else "—")
    with c5:
        if not df_history.empty:
            eq = df_history.sort_values('time')['net'].cumsum()
            max_dd = (eq - eq.cummax()).min()
            st.metric("Max Drawdown", f"${max_dd:.2f}")
        else:
            st.metric("Max Drawdown", "—")
    with c6:
        st.metric("News Filter", "⛔ PAUSED" if news_active else "✅ CLEAR")

    if news_active:
        st.error(f"**News Embargo is Active:** {news_reason}")
    elif len(upcoming_news) > 0:
        nx = upcoming_news[0]
        nxt = nx['time'].astimezone(BKK).strftime('%H:%M BKK')
        st.info(f"**Next High-Impact News:** {nx['title']} at {nxt}")

    if not df_history.empty:
        st.divider()
        m1, m2, m3 = st.columns(3)
        wins = df_history[df_history['net'] > 0]
        losses = df_history[df_history['net'] <= 0]
        win_rate = len(wins) / len(df_history) * 100 if len(df_history) > 0 else 0
        avg_win = wins['net'].mean() if len(wins) > 0 else 0
        avg_loss = abs(losses['net'].mean()) if len(losses) > 0 else 1
        rr = avg_win / avg_loss if avg_loss > 0 else 0
        with m1:
            st.metric(f"Win Rate ({history_days}D)", f"{win_rate:.1f}%")
        with m2:
            st.metric("Avg R:R", f"1 : {rr:.2f}")
        with m3:
            st.metric("Total Trades", str(len(df_history)))

        st.divider()
        st.subheader("📈 Equity Curve (Net)")
        dfh = df_history.sort_values(by='time').copy()
        dfh['cumulative_net'] = dfh['net'].cumsum()
        st.line_chart(dfh.set_index('time')['cumulative_net'])

        cc1, cc2 = st.columns(2)
        with cc1:
            st.subheader("💡 Profit by Symbol")
            st.bar_chart(dfh.groupby('symbol')['net'].sum())
        with cc2:
            st.subheader("🕒 Win Rate by Hour (BKK %)")
            dfh['hour'] = dfh['time'].dt.hour
            dfh['win'] = (dfh['net'] > 0).astype(int)
            st.bar_chart(dfh.groupby('hour')['win'].mean() * 100)
    else:
        st.warning("No MT5 History found or MT5 not connected.")

# ============================================================
#  TAB 2 — STRATEGIES
# ============================================================
with tab_strat:
    if df_history.empty:
        st.warning("No MT5 History found or MT5 not connected.")
    else:
        d = df_history.copy()
        d['strategy'] = d['comment'].str.extract(r'_(S\d+)').fillna('Other')
        d['asset'] = d['symbol'].apply(lambda s: 'BTC' if 'BTC' in str(s) else 'XAU')

        st.subheader("🏆 Strategy Leaderboard (Net P/L by SID)")
        st.bar_chart(d.groupby('strategy')['net'].sum().sort_values(ascending=False))

        st.subheader("📋 Per-Strategy Breakdown")
        rows = []
        for sid, g in d.groupby('strategy'):
            w = g[g['net'] > 0]['net']
            l = g[g['net'] <= 0]['net']
            pf = w.sum() / abs(l.sum()) if l.sum() != 0 else float('inf')
            rows.append({
                "Strategy": sid,
                "Trades": len(g),
                "Win%": round((g['net'] > 0).mean() * 100, 1),
                "Net P/L": round(g['net'].sum(), 2),
                "Avg Win": round(w.mean(), 2) if len(w) else 0.0,
                "Avg Loss": round(l.mean(), 2) if len(l) else 0.0,
                "Profit Factor": ("∞" if pf == float('inf') else round(pf, 2)),
            })
        st.dataframe(
            pd.DataFrame(rows).sort_values("Net P/L", ascending=False),
            use_container_width=True, hide_index=True,
        )

        st.subheader("⚖️ XAU vs BTC (Net P/L by Strategy)")
        pivot = d.pivot_table(index='strategy', columns='asset', values='net',
                              aggfunc='sum', fill_value=0).round(2)
        st.dataframe(pivot, use_container_width=True)

# ============================================================
#  TAB 3 — HEALTH & LOGS
# ============================================================
with tab_health:
    st.subheader("🩺 Bot Health (from heartbeat)")
    if hb and hb.get("ts", "").isdigit():
        age = int(time.time()) - int(hb["ts"])
        if age < 30:
            status, color = "🟢 LIVE", "normal"
        elif age < 90:
            status, color = "🟡 LAGGING", "off"
        else:
            status, color = "🔴 STALE / DOWN", "inverse"
        last_scan = int(hb.get("last_scan", "0") or 0)
        scan_age = int(time.time()) - last_scan if last_scan else None

        h1, h2, h3, h4, h5 = st.columns(5)
        with h1:
            st.metric("Process", status, f"{age}s ago", delta_color=color)
        with h2:
            st.metric("MT5", "✅ OK" if hb.get("mt5_ok") == "1" else "❌ DOWN")
        with h3:
            st.metric("Auto", "ON" if hb.get("auto") == "1" else "OFF")
        with h4:
            st.metric("Last Scan", f"{scan_age}s ago" if scan_age is not None else "—")
        with h5:
            st.metric("PID", hb.get("pid", "—"))
        if age >= 90:
            st.error("Heartbeat stale — bot process may be hung or stopped. "
                     "Supervisor (run_supervised.bat) should auto-restart it.")
    else:
        st.warning("No heartbeat file (bot_heartbeat.txt). Bot not running, "
                   "or started without heartbeat_job.")

    st.divider()
    if logs:
        sp = logs.get("span", (None, None))
        st.caption(f"Log source: `{logs.get('path','?')}` | window: {sp[0]} → {sp[1]}")
        lc1, lc2 = st.columns(2)
        with lc1:
            st.subheader("🚫 Why Not Entering (block / skip)")
            blocks = logs.get("blocks", {})
            if blocks:
                bs = pd.Series(blocks).sort_values(ascending=False)
                st.bar_chart(bs)
            else:
                st.info("No block/skip events in current log.")
        with lc2:
            st.subheader("⚠️ Error Monitor")
            errs = logs.get("errors", {})
            if errs:
                st.dataframe(pd.Series(errs, name="count").to_frame(),
                             use_container_width=True)
            else:
                st.success("No ORDER_FAILED / TG_DROP / *_ERROR in current log. ✅")

        st.subheader("📰 Recent Events")
        feed = logs.get("feed", [])
        if feed:
            st.dataframe(
                pd.DataFrame(feed, columns=["time", "event", "detail"]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("No recent lifecycle events.")
    else:
        st.warning("No bot log found under logs/.")

    st.divider()
    st.subheader("📌 Current Tracked Positions")
    tracked = state.get("tracked_positions", {})
    if tracked:
        st.dataframe(pd.DataFrame.from_dict(tracked, orient='index'),
                     use_container_width=True)
    else:
        st.info("No active positions tracked.")

# ============================================================
#  TAB 4 — STRATEGY DOCS (candlestick pattern explorer)
# ============================================================
_DOCS_HTML = """
<div style="font-family:'Outfit',sans-serif;background:linear-gradient(135deg,#0b1120 0%,#171430 60%,#1e1b4b 100%);color:#f8fafc;border-radius:14px;padding:16px 18px 22px;">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
<div style="font-size:18px;font-weight:800;background:linear-gradient(45deg,#fde68a,#f59e0b);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px;">Strategy Docs &mdash; Pattern Explorer</div>
<div id="chips" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px;"></div>
<div id="dTitle" style="font-size:1.2rem;font-weight:800;color:#fde68a;"></div>
<div id="dTag" style="font-size:12px;color:#94a3b8;margin:2px 0 8px;"></div>
<div id="dDoc" style="font-size:13px;color:#cbd5e1;line-height:1.6;"></div>
<div id="dCfg" style="font-size:12px;color:#94a3b8;margin:8px 0 4px;"></div>
<div id="dPats" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin-top:10px;"></div>
<div style="display:flex;gap:14px;margin-top:10px;font-size:11.5px;">
  <span style="color:#fbbf24;">Entry</span><span style="color:#fb7185;">SL</span><span style="color:#34d399;">TP</span><span style="color:#a78bfa;">zone</span>
</div>
<style>
.chip{font-family:'Outfit',sans-serif;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.12);color:#cbd5e1;border-radius:9px;padding:5px 10px;font-size:12px;font-weight:600;cursor:pointer;}
.chip-on{background:rgba(251,191,36,.18);border-color:rgba(251,191,36,.5);color:#fde68a;}
.pcard{background:rgba(0,0,0,.25);border:1px solid rgba(255,255,255,.06);border-radius:12px;padding:11px 12px;}
.ptitle{font-size:12.5px;font-weight:600;color:#fde68a;margin-bottom:2px;}
.pdesc{font-size:11.5px;color:#94a3b8;line-height:1.45;margin-bottom:4px;}
.pnote{font-size:11px;color:#94a3b8;margin-top:5px;line-height:1.4;}
</style>
<script>
var DATA=__DATA__;
var G="#34d399",R="#fb7185";
function svgFor(dg){
 var PW=320,PH=180,pT=12,pB=22,pL=8,pR=66;
 var plotW=PW-pL-pR,plotH=PH-pT-pB,n=dg.candles.length,slot=plotW/n;
 var vals=[];dg.candles.forEach(function(c){vals.push(c.h,c.l);});(dg.refs||[]).forEach(function(r){vals.push(r.p);});
 if(dg.band){vals.push(dg.band.from,dg.band.to);}
 var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals),pad=(mx-mn)*0.08||1;mn-=pad;mx+=pad;
 function y(p){return pT+(mx-p)/(mx-mn)*plotH;}
 var s='<svg viewBox="0 0 '+PW+' '+PH+'" width="100%" role="img" aria-label="candlestick pattern">';
 if(dg.band){var yb=y(dg.band.to),hb=y(dg.band.from)-y(dg.band.to);s+='<rect x="'+pL+'" y="'+yb+'" width="'+plotW+'" height="'+hb+'" fill="'+dg.band.c+'"/>';}
 (dg.refs||[]).forEach(function(r){var yy=y(r.p);s+='<line x1="'+pL+'" y1="'+yy+'" x2="'+(pL+plotW)+'" y2="'+yy+'" stroke="'+r.c+'" stroke-width="1.2" stroke-dasharray="4 3"/>';s+='<text x="'+(pL+plotW+4)+'" y="'+(yy+3.5)+'" fill="'+r.c+'" font-size="9.5" font-family="Outfit">'+r.t+'</text>';});
 dg.candles.forEach(function(c,i){var cx=pL+slot*(i+0.5),up=c.c>=c.o,col=up?G:R,bw=Math.min(slot*0.5,22);
  s+='<line x1="'+cx+'" y1="'+y(c.h)+'" x2="'+cx+'" y2="'+y(c.l)+'" stroke="'+col+'" stroke-width="1.6"/>';
  var yt=y(Math.max(c.o,c.c)),hh=Math.max(2,Math.abs(y(c.o)-y(c.c)));
  s+='<rect x="'+(cx-bw/2)+'" y="'+yt+'" width="'+bw+'" height="'+hh+'" rx="1.5" fill="'+col+'"/>';
  s+='<text x="'+cx+'" y="'+(PH-7)+'" fill="#94a3b8" font-size="9.5" font-family="Outfit" text-anchor="middle">'+c.lab+'</text>';});
 return s+'</svg>';
}
function show(sid){
 document.querySelectorAll('.chip').forEach(function(c){c.classList.toggle('chip-on',c.dataset.k===sid);});
 var d=DATA[sid];
 document.getElementById('dTitle').textContent=d.name;
 document.getElementById('dTag').textContent=d.tag||'';
 document.getElementById('dDoc').innerHTML=d.doc||'';
 document.getElementById('dCfg').innerHTML=d.cfg?('&#9881; '+d.cfg):'';
 var box=document.getElementById('dPats');box.innerHTML='';
 var pats=d.patterns||[];
 if(!pats.length){box.innerHTML='<div class="pcard" style="grid-column:1/-1;color:#64748b;font-size:12px;">candlestick diagram &mdash; ดูคำอธิบายเต็มใน <b>docs/strategies/s'+sid+'.md</b></div>';return;}
 pats.forEach(function(p){var el=document.createElement('div');el.className='pcard';
  el.innerHTML='<div class="ptitle">'+p.title+'</div><div class="pdesc">'+(p.desc||'')+'</div>'+svgFor(p)+'<div class="pnote">'+(p.note||'')+'</div>';
  box.appendChild(el);});
}
var keys=Object.keys(DATA).sort(function(a,b){return (+a)-(+b);});
var ch=document.getElementById('chips');
keys.forEach(function(k){var b=document.createElement('button');b.className='chip';b.dataset.k=k;b.textContent='S'+k;b.onclick=function(){show(k);};ch.appendChild(b);});
if(keys.length){show(keys[0]);}
</script>
</div>
"""

with tab_docs:
    if not STRATEGY_PATTERNS:
        st.warning("strategy_patterns.py not found — Strategy Docs tab disabled.")
    else:
        _docs_html = _DOCS_HTML.replace(
            "__DATA__", json.dumps(STRATEGY_PATTERNS, ensure_ascii=False)
        )
        components.html(_docs_html, height=1000, scrolling=True)
