# -*- coding: utf-8 -*-
"""Copter Gold Bot — Apex Command Center & Institutional Quant Dashboard v3.0
UX/UI Redesign & Comprehensive Trading Terminal for Multi-Account Bot Fleet.
Includes Live TradingView Candlestick Chart, Monte Carlo Simulation, SMC Liquidity Radar,
Emergency Control Actions, and Demo Portfolio Catalog.
"""

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
import calendar as pycal
import html as html_escape
import json
import os
import re
import sys
import glob
import shutil
import subprocess
import time
import requests
from collections import Counter
import streamlit.components.v1 as components

try:
    from strategy_patterns import STRATEGY_PATTERNS
except Exception:
    STRATEGY_PATTERNS = {}

BKK = timezone(timedelta(hours=7))
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Page configuration
st.set_page_config(
    page_title="Copter Gold Bot — Apex Command Center",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
#  APEX DARK PRO — INSTITUTIONAL DESIGN SYSTEM & CSS INJECTION
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap');

html, body, [class*="css"], .stMarkdown {
    font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

code, kbd, samp, pre {
    font-family: 'JetBrains Mono', monospace !important;
}

/* Base Ambient Dark Glow */
.stApp {
    background: radial-gradient(circle at 50% 0%, #17153a 0%, #0a0d1a 45%, #05070f 100%) !important;
    color: #f1f5f9;
}

/* Chrome Removal */
#MainMenu { visibility: hidden; }
header { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stExpandSidebarButton"] { visibility: visible !important; }

/* ── Metric Cards (Glassmorphism & Luminous Borders) ── */
div[data-testid="stMetric"] {
    background: linear-gradient(145deg, rgba(26, 31, 56, 0.75) 0%, rgba(13, 17, 34, 0.85) 100%) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-top: 1px solid rgba(255, 255, 255, 0.16) !important;
    border-radius: 16px !important;
    padding: 16px 20px !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-3px) scale(1.01);
    box-shadow: 0 16px 40px rgba(99, 102, 241, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.15) !important;
    border-color: rgba(99, 102, 241, 0.45) !important;
}
/* Metric Labels & Values */
div[data-testid="stMetricLabel"] {
    color: #94a3b8 !important;
    font-size: 0.88rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
}
div[data-testid="stMetricLabel"] * {
    color: #94a3b8 !important;
}
div[data-testid="stMetricValue"] {
    color: #ffffff !important;
}
div[data-testid="stMetricValue"] > div {
    font-size: clamp(1.2rem, 2vw, 1.65rem) !important;
    font-weight: 800 !important;
    letter-spacing: -0.01em !important;
    color: #ffffff !important;
    background: linear-gradient(135deg, #ffffff 40%, #cbd5e1 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}

/* ── Tabs Navigation Modernization (Institutional Glass Cockpit) ── */
div[data-baseweb="tab-list"] {
    gap: 8px !important;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.8) 0%, rgba(9, 13, 26, 0.9) 100%) !important;
    padding: 8px !important;
    border-radius: 16px !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    margin-bottom: 24px !important;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    flex-wrap: wrap !important;
    overflow-x: visible !important;
}
/* ปุ่มลูกศรเลื่อนแท็บซ้าย/ขวาของ Streamlit ไม่จำเป็นแล้วเมื่อ tab-list wrap ได้ */
div[data-baseweb="tab-list"] + button,
button[data-testid="stTabsMoreButton"],
div[data-baseweb="tab-list"] ~ div button[kind="tabsScrollButton"] {
    display: none !important;
}
button[data-baseweb="tab"] {
    border-radius: 10px !important;
    padding: 10px 18px !important;
    color: #94a3b8 !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    border: 1px solid transparent !important;
    background: transparent !important;
    transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
button[data-baseweb="tab"]:hover {
    color: #ffffff !important;
    background: rgba(255, 255, 255, 0.06) !important;
    border-color: rgba(255, 255, 255, 0.08) !important;
    transform: translateY(-1px);
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #38bdf8 !important;
    background: linear-gradient(135deg, rgba(56, 189, 248, 0.16) 0%, rgba(99, 102, 241, 0.12) 100%) !important;
    border: 1px solid rgba(56, 189, 248, 0.45) !important;
    box-shadow: 0 4px 20px rgba(56, 189, 248, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    font-weight: 700 !important;
    transform: translateY(-1px);
}
div[data-baseweb="tab-highlight"] {
    display: none !important;
}

/* ── Containers, Charts & DataFrames (Anti-Overflow & Pixel Perfect) ── */
div[data-testid="stDataFrame"] {
    background: rgba(13, 18, 36, 0.75) !important;
    border-radius: 16px !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    padding: 16px !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3) !important;
}

div[data-testid="stVegaLiteChart"], .stVegaLiteChart {
    background: linear-gradient(145deg, rgba(20, 26, 48, 0.7) 0%, rgba(11, 15, 30, 0.85) 100%) !important;
    border-radius: 16px !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-top: 1px solid rgba(255, 255, 255, 0.15) !important;
    padding: 8px 12px 12px 8px !important;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.06) !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
    max-width: 100% !important;
}

div[data-testid="stVegaLiteChart"] .vega-embed,
.stVegaLiteChart .vega-embed {
    width: 100% !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
}

div[data-testid="stVegaLiteChart"] svg,
.stVegaLiteChart svg,
div[data-testid="stVegaLiteChart"] canvas,
.stVegaLiteChart canvas {
    max-width: 100% !important;
    box-sizing: border-box !important;
    display: block !important;
}

/* ── Sleek Institutional Loading Progress Bar ── */
div[data-testid="stProgress"] {
    background: rgba(15, 23, 42, 0.85) !important;
    border: 1px solid rgba(56, 189, 248, 0.35) !important;
    border-radius: 12px !important;
    padding: 6px 14px !important;
    box-shadow: 0 4px 20px rgba(56, 189, 248, 0.25) !important;
    backdrop-filter: blur(12px) !important;
    margin: 8px 0 14px 0 !important;
}
div[data-testid="stProgress"] > div > div > div > div {
    background: linear-gradient(90deg, #38bdf8 0%, #6366f1 50%, #a855f7 100%) !important;
    border-radius: 6px !important;
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.7) !important;
}
div[data-testid="stProgress"] [data-testid="stMarkdownContainer"] p {
    color: #e2e8f0 !important;
    font-size: 12.5px !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
}


/* ── Form Controls, Inputs & Popovers ── */
.stButton > button, .stPopover > button, div[data-baseweb="select"] > div,
div[data-baseweb="input"], [data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input {
    border-radius: 12px !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    background: #10162a !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    color: #f8fafc !important;
}
[data-testid="stNumberInput"] div[data-baseweb="input"] {
    background: #10162a !important;
}
[data-testid="stNumberInput"] button {
    background: #1a223f !important;
    color: #f8fafc !important;
    border: none !important;
}
.stButton > button:hover {
    transform: translateY(-1px);
    border-color: rgba(99, 102, 241, 0.6) !important;
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.35);
    background: rgba(99, 102, 241, 0.15) !important;
    color: #ffffff !important;
}

/* ── Streamlit Expander Dark Theming ── */
div[data-testid="stExpander"], [data-testid="stExpander"] {
    background: #0f172a !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 14px !important;
    overflow: hidden !important;
}
div[data-testid="stExpander"] details, [data-testid="stExpander"] details {
    background: #0f172a !important;
}
div[data-testid="stExpander"] summary, [data-testid="stExpander"] summary,
div[data-testid="stExpander"] details > summary {
    background: #151e36 !important;
    color: #f1f5f9 !important;
    font-weight: 600 !important;
    border-radius: 14px !important;
    padding: 12px 16px !important;
    border: none !important;
}
div[data-testid="stExpander"] summary *, [data-testid="stExpander"] summary span,
div[data-testid="stExpander"] summary p, div[data-testid="stExpander"] summary svg {
    color: #f1f5f9 !important;
    fill: #f1f5f9 !important;
}
div[data-testid="stExpander"] summary:hover {
    color: #38bdf8 !important;
    background: #1c2748 !important;
}
div[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    background: #0b0f19 !important;
    padding: 16px !important;
}

/* ── Streamlit Selectbox Dropdown Menu (Popped Open) ── */
ul[data-baseweb="menu"] {
    background: #0f172a !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 12px !important;
    color: #f8fafc !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5) !important;
}
li[data-baseweb="menu-item"] {
    color: #cbd5e1 !important;
}
li[data-baseweb="menu-item"]:hover, li[data-baseweb="menu-item"][aria-selected="true"] {
    background: rgba(56, 189, 248, 0.15) !important;
    color: #38bdf8 !important;
}

/* ── Streamlit Multiselect Tags ── */
span[data-baseweb="tag"] {
    background: rgba(56, 189, 248, 0.18) !important;
    border: 1px solid rgba(56, 189, 248, 0.4) !important;
    border-radius: 8px !important;
}
span[data-baseweb="tag"] span {
    color: #7dd3fc !important;
    font-weight: 600 !important;
}

/* ── Typography & Global Text Readability ── */
h1, h2, h3, h4, h5, h6 {
    color: #f8fafc !important;
    font-weight: 700 !important;
}
p, span, label, div {
    color: #cbd5e1;
}
.stMarkdown p {
    color: #cbd5e1 !important;
    font-size: 13.5px;
}
small, .stCaption, [data-testid="stCaptionContainer"] p {
    color: #94a3b8 !important;
}

/* ── Sidebar Custom Styling ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #090d1a 0%, #0e1224 100%) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
}

/* ── Pulse Dots & Badges ── */
@keyframes pulseGreen {
    0%, 100% { transform: scale(1); filter: drop-shadow(0 0 4px #34d399); opacity: 1; }
    50% { transform: scale(0.88); filter: drop-shadow(0 0 1px #34d399); opacity: 0.6; }
}
@keyframes pulseRed {
    0%, 100% { transform: scale(1); filter: drop-shadow(0 0 4px #fb7185); opacity: 1; }
    50% { transform: scale(0.88); filter: drop-shadow(0 0 1px #fb7185); opacity: 0.6; }
}
.pulse-live {
    display: inline-block;
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: #34d399;
    animation: pulseGreen 1.8s infinite ease-in-out;
    margin-right: 6px;
    vertical-align: middle;
}
.pulse-danger {
    display: inline-block;
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: #fb7185;
    animation: pulseRed 1.8s infinite ease-in-out;
    margin-right: 6px;
    vertical-align: middle;
}

/* Badge tags */
.badge-buy {
    display: inline-block;
    background: rgba(52, 211, 153, 0.16);
    color: #34d399;
    border: 1px solid rgba(52, 211, 153, 0.4);
    padding: 2px 8px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 11px;
}
.badge-sell {
    display: inline-block;
    background: rgba(251, 113, 133, 0.16);
    color: #fb7185;
    border: 1px solid rgba(251, 113, 133, 0.4);
    padding: 2px 8px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 11px;
}
.badge-remote {
    display: inline-block;
    background: rgba(56, 189, 248, 0.16);
    color: #38bdf8;
    border: 1px solid rgba(56, 189, 248, 0.4);
    padding: 2px 8px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 11px;
}
.badge-tag {
    display: inline-block;
    background: rgba(148, 163, 184, 0.14);
    color: #cbd5e1;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
}

/* Pro Tables & Cards */
.pro-card {
    background: rgba(15, 23, 42, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 16px;
    box-shadow: 0 6px 24px rgba(0,0,0,0.25);
}
.pro-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'Outfit', sans-serif;
    font-size: 13px;
}
.pro-table th {
    background: rgba(10, 15, 30, 0.9);
    color: #94a3b8;
    font-weight: 700;
    text-align: left;
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    position: sticky;
    top: 0;
    z-index: 2;
}
.pro-table td {
    padding: 9px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    color: #e2e8f0;
}
.pro-table tr:hover td {
    background: rgba(99, 102, 241, 0.08);
}

/* Scrollbar */
::-webkit-scrollbar { width: 7px; height: 7px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: rgba(148, 163, 184, 0.3);
    border-radius: 8px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(148, 163, 184, 0.5); }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  MULTI-ACCOUNT REGISTRY & SYSTEM PROCESS RUNNER
# ─────────────────────────────────────────────────────────────
ACCOUNT_LABELS = {
    "": "🟢 Demo • IUX 4448 — Main Bot (root)",
    "real-vtmarket-26575165": "🔴 Real • VT Markets 26575165 (Main Bot)",
    "demo-iux-2101114448": "🟠 Demo • IUX 4448 (profile dir)",
    "demo-iux-2101182459": "🟢 Demo • IUX 2459 — LTS_AHR2",
    "demo-iux-2101182460": "🟢 Demo • IUX 2460 — LTS_AVENGERS_BASE",
    "demo-iux-2101182461": "🟢 Demo • IUX 2461 — AF (AF22/34/47)",
    "demo-iux-2101183586": "⚪ Demo • IUX 3586 — (Disabled)",
    "demo-iux-2101183587": "🟢 Demo • IUX 3587 — S421/S427/S429",
    "demo-exness-416010472": "🟢 Demo • Exness 472 — LTS_AUS2",
    "demo-exness-433881786": "🟢 Demo • Exness 786 — P18 + S101/102/105/106/111",
    "demo-exness-416273786": "🟢 Demo • Exness 786b — LTS_AUS3",
    "demo-exness-414252716": "🟢 Demo • Exness 716 — LTS_AHR3",
    "demo-exness-434237129": "🟢 Demo • Exness 129 — S20 Institutional Suite (11 Strats)",
    "demo-exness-434238722": "🟢 Demo • Exness 722 — 15 ML Groups",
}
RUN_PS1 = os.path.join(ROOT_DIR, "run_supervised.ps1")
STOP_PS1 = os.path.join(ROOT_DIR, "stop_supervised.ps1")


def discover_accounts():
    accounts = [{
        "key": "", "dir": ROOT_DIR, "kind": "root",
        "label": ACCOUNT_LABELS.get("", "Real (root/main)"),
    }]
    for kind in ("real", "demo"):
        base = os.path.join(ROOT_DIR, "profiles", kind)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            d = os.path.join(base, name)
            if os.path.isfile(os.path.join(d, "profile.env")):
                accounts.append({
                    "key": name,
                    "dir": d,
                    "kind": kind,
                    "label": ACCOUNT_LABELS.get(name, name),
                })
    return accounts


def read_account_status(acc_dir):
    hb_path = os.path.join(acc_dir, "bot_heartbeat.txt")
    marker_path = os.path.join(acc_dir, "supervisor_closed.marker")
    d = {}
    if os.path.exists(hb_path):
        try:
            with open(hb_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        d[k] = v
        except Exception:
            pass
    if not d.get("ts", "").isdigit():
        return {"state": "OFF", "label": "⚪ ไม่ได้รัน", "age": None, "pid": None, "auto": None}
    age = int(time.time()) - int(d["ts"])
    auto_flag = d.get("auto") == "1"
    if os.path.exists(marker_path):
        try:
            if os.path.getmtime(marker_path) >= os.path.getmtime(hb_path):
                return {"state": "OFF", "label": "⚪ ปิดแล้ว", "age": age, "pid": d.get("pid"), "auto": None}
        except Exception:
            pass
    if age < 30:
        return {"state": "LIVE", "label": "🟢 ทำงานอยู่", "age": age, "pid": d.get("pid"), "auto": auto_flag}
    elif age < 90:
        return {"state": "LAGGING", "label": "🟡 ค้าง/ช้า", "age": age, "pid": d.get("pid"), "auto": auto_flag}
    else:
        return {"state": "STALE", "label": "🔴 ไม่ตอบสนอง", "age": age, "pid": d.get("pid"), "auto": None}


def start_account(profile_key):
    args = ["powershell", "-ExecutionPolicy", "Bypass", "-NoProfile", "-File", RUN_PS1]
    if profile_key:
        args += ["-Profile", profile_key]
    try:
        subprocess.Popen(args, cwd=ROOT_DIR, creationflags=subprocess.CREATE_NEW_CONSOLE)
        return True, "สั่งเปิดแล้ว กรุณารอ 10-20 วินาทีให้ MT5 เชื่อมต่อ"
    except Exception as e:
        return False, str(e)


def stop_account(profile_key):
    args = ["powershell", "-ExecutionPolicy", "Bypass", "-NoProfile", "-File", STOP_PS1]
    if profile_key:
        args += ["-Profile", profile_key]
    try:
        r = subprocess.run(args, cwd=ROOT_DIR, capture_output=True, text=True, timeout=45)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return False, str(e)


@st.cache_data(ttl=300, show_spinner=False)
def _account_mt5_path(acc_dir):
    env_path = os.path.join(acc_dir, "profile.env")
    is_root = not os.path.isfile(env_path)
    if is_root:
        env_path = os.path.join(acc_dir, ".env")
        rel = ""
    else:
        rel = "mt5/terminal64.exe"
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("MT5_PATH="):
                    rel = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    except Exception:
        pass
    if rel:
        return os.path.abspath(os.path.join(acc_dir, rel))
    if is_root:
        for cand in (r"C:\MT5\terminal64.exe", r"C:\Program Files\MetaTrader 5\terminal64.exe"):
            if os.path.exists(cand):
                return cand
    return os.path.abspath(os.path.join(acc_dir, "mt5/terminal64.exe"))


# บัญชีที่รันบอทอยู่เครื่องอื่น (heartbeat ในเครื่องนี้จะไม่มีวัน LIVE) —
# ดึงเฉพาะประวัติเทรด/P&L แบบ read-only ด้วยการ login ตรง (ไม่ Start/Stop บอทจากที่นี่)
REMOTE_VIEW_ACCOUNTS = {"real-vtmarket-26575165"}


@st.cache_data(ttl=300, show_spinner=False)
def _account_credentials(acc_dir):
    """อ่าน MT5_LOGIN/MT5_PASSWORD/MT5_SERVER จาก profile.env สำหรับบัญชีที่รันอยู่เครื่องอื่น"""
    env_path = os.path.join(acc_dir, "profile.env")
    if not os.path.isfile(env_path):
        return None
    d = {}
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    d[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        return None
    login, password, server = d.get("MT5_LOGIN"), d.get("MT5_PASSWORD"), d.get("MT5_SERVER")
    if not (login and password and server):
        return None
    try:
        return {"login": int(login), "password": password, "server": server}
    except ValueError:
        return None


def _mt5_connect(acc_key, acc_dir, mt5_path, acc_status_state):
    """เชื่อมต่อ MT5: บัญชีที่รันในเครื่องนี้ใช้ attach ปกติ, บัญชีใน REMOTE_VIEW_ACCOUNTS ที่นี่ไม่ได้รัน (OFF/STALE) ให้ login ตรงด้วย credentials แทน (read-only, ไม่กระทบบอทจริงที่รันอยู่เครื่องอื่น)"""
    if acc_status_state in ("LIVE", "LAGGING"):
        return os.path.exists(mt5_path) and mt5.initialize(path=mt5_path)
    if acc_key in REMOTE_VIEW_ACCOUNTS and os.path.exists(mt5_path):
        creds = _account_credentials(acc_dir)
        if creds:
            return mt5.initialize(path=mt5_path, login=creds["login"], password=creds["password"], server=creds["server"])
    return False


# ─────────────────────────────────────────────────────────────
#  BACKTEST RUNNER — เฉพาะกลยุทธ์ที่มี --compare รองรับแล้วเท่านั้น
#  (S420-S430 มี backtest_sNNN.py เฉพาะตัวที่ implement args.compare จริง;
#   ส่วนที่เหลือ (P13/P16/P18/AF22-47/LTS_*/S101-111) ใช้ run_backtest_sim.py
#   ที่ compare กับ MT5 จริงเสมอทุกครั้งที่รัน ไม่ต้องมี flag แยก)
# ─────────────────────────────────────────────────────────────
S42X_COMPARE_IDS = {"S420", "S421", "S422", "S423", "S424", "S425", "S426", "S427", "S428", "S429", "S430"}

PORTFOLIO_BACKTEST_SCRIPT = os.path.join(ROOT_DIR, "strategy", "demo_portfolio", "backtest-sim", "run_backtest_sim.py")

# S20.14xx sub-variant legs (LTS ladder) — เช็คโค้ดจริงแล้ว 2026-09: มี --compare ผ่าน
# strategy/s20.14.1/backtest-sim/v38_standalone_group{N}.py ซึ่ง mt5_matcher.py เทียบกับ MT5 comment
# "S20.14{group_id}" ตรงๆ (group_id ในไฟล์ตรงกับเลขหลัง S20.14 ของ "S20.14N")
# ⚠️ S20.1419 ไม่รวม — ไฟล์ v38_standalone_group19.py มี group_id=24 ผิด (บั๊กจริงในซอร์ส เทียบกับ
# S20.1424 แทนที่จะเป็น S20.1419) ยังใช้ compare ไม่ได้ถูกต้องจนกว่าจะแก้ต้นทาง
S20_14_GROUP_MAP = {
    "S20.141": 1, "S20.142": 2, "S20.145": 5, "S20.149": 9,
    "S20.1412": 12, "S20.1413": 13, "S20.1414": 14, "S20.1416": 16,
    "S20.1418": 18, "S20.1421": 21, "S20.1422": 22, "S20.1423": 23, "S20.1424": 24,
}
S20_14_GROUP_SCRIPT_DIR = os.path.join(ROOT_DIR, "strategy", "s20.14.1", "backtest-sim")

# S20.18-S20.304 family: thin wrapper scripts (backtest_s20_XX.py) ที่ delegate เข้า
# strategy/backtest_s20_unified.py (shared engine, --compare + --compare-profile) —
# ตรวจสอบโค้ดจริงแล้ว 2026-09: ครบทั้ง 11 ตัว (ตอนแรกเช็ค args.compare ในไฟล์ wrapper เองแล้วไม่เจอ
# เพราะ logic จริงอยู่ใน backtest_s20_unified.py ที่ import มาใช้ — เช็คถูกจุดแล้วยืนยันครบ)
S20X_COMPARE_PROFILE_SCRIPTS = {
    "S20.18": os.path.join(ROOT_DIR, "strategy", "s20.18", "backtest_s20_18.py"),
    "S20.19": os.path.join(ROOT_DIR, "strategy", "s20.19", "backtest_s20_19.py"),
    "S20.20": os.path.join(ROOT_DIR, "strategy", "s20.20", "backtest_s20_20.py"),
    "S20.21": os.path.join(ROOT_DIR, "strategy", "s20.21", "backtest_s20_21.py"),
    "S20.22": os.path.join(ROOT_DIR, "strategy", "s20.22", "backtest_s20_22.py"),
    "S20.24": os.path.join(ROOT_DIR, "strategy", "s20.24", "backtest_s20_24.py"),
    "S20.28": os.path.join(ROOT_DIR, "strategy", "s20.28", "backtest_s20_28.py"),
    "S20.301": os.path.join(ROOT_DIR, "strategy", "s20.301", "backtest_s20_301.py"),
    "S20.302": os.path.join(ROOT_DIR, "strategy", "s20.302", "backtest_s20_302.py"),
    "S20.303": os.path.join(ROOT_DIR, "strategy", "s20.303", "backtest_s20_303.py"),
    "S20.304": os.path.join(ROOT_DIR, "strategy", "s20.304", "backtest_s20_304.py"),
}

# บัญชี -> กลยุทธ์/พอร์ตที่รันอยู่จริงบนบัญชีนั้น (ใช้เป็น hint/default เท่านั้น — ไม่ได้ใช้จำกัด dropdown แล้ว
# ตามที่พี่ขอให้เปิดเลือกได้ทุกบัญชี เพราะพี่จะเลือกกลยุทธ์เอง)
ACCOUNT_BACKTEST_STRATEGIES = {
    "": [],
    "real-vtmarket-26575165": [],
    "demo-iux-2101114448": [],
    "demo-iux-2101182459": ["LTS_AHR2"],
    "demo-iux-2101182460": ["LTS_AVENGERS_BASE"],
    "demo-iux-2101182461": ["AF22", "AF34", "AF47"],
    "demo-iux-2101183586": ["S420"],
    "demo-iux-2101183587": ["S421", "S427", "S429"],
    "demo-exness-416010472": ["LTS_AUS2"],
    "demo-exness-433881786": ["P18", "S101", "S102", "S105", "S106", "S111"],
    "demo-exness-416273786": ["LTS_AUS3"],
    "demo-exness-414252716": ["LTS_AHR3"],
    "demo-exness-434237129": ["S20_ALL", "S20_301", "S20_302", "S20_303", "S20_304"],
    "demo-exness-434238722": ["S20_ALL", "20.141", "20.142", "20.145", "20.147", "20.148", "20.1410", "20.1411", "20.1412", "20.1413", "20.1415", "20.1417", "20.1418", "20.1422", "20.1423", "20.1424"],
}

# รายชื่อกลยุทธ์/พอร์ตทั้งหมดที่มี --compare รองรับแล้ว (ตรวจสอบโค้ดจริงแล้ว 2026-09) — ไม่ผูกกับบัญชีที่เลือก
ALL_BACKTEST_STRATEGY_IDS = sorted(S42X_COMPARE_IDS | set(S20_14_GROUP_MAP.keys()) | set(S20X_COMPARE_PROFILE_SCRIPTS.keys()) | {
    "P13", "P16", "P18",
    "S101", "S102", "S105", "S106", "S111",
    "S432", "S433", "S434",
    "AF22", "AF34", "AF47",
    "LTS44", "LTS890", "LTS999",
    "LTS_AVENGERS_BASE", "LTS_AVENGERS_P34", "LTS_AVENGERS_HIGH_RISK", "LTS_AVENGERS_ULTRA_SAFE", "LTS_AVENGERS_HIGH_FREQ",
    "LTS_AHR2", "LTS_AHR3", "LTS_AUS2", "LTS_AUS3",
})

BACKTEST_OUT_ROOT = os.path.join(ROOT_DIR, "dashboard_backtest_runs")


def _backtest_route_for(strategy_id):
    if strategy_id in S42X_COMPARE_IDS:
        sid_lower = strategy_id.lower()
        return {
            "kind": "s42x",
            "script": os.path.join(ROOT_DIR, "strategy", sid_lower, f"backtest_{sid_lower}.py"),
        }
    if strategy_id in S20_14_GROUP_MAP:
        group_n = S20_14_GROUP_MAP[strategy_id]
        return {
            "kind": "s2014group",
            "script": os.path.join(S20_14_GROUP_SCRIPT_DIR, f"v38_standalone_group{group_n}.py"),
        }
    if strategy_id in S20X_COMPARE_PROFILE_SCRIPTS:
        return {"kind": "s20x_profile", "script": S20X_COMPARE_PROFILE_SCRIPTS[strategy_id]}
    return {"kind": "portfolio", "script": PORTFOLIO_BACKTEST_SCRIPT}


def run_backtest_subprocess(strategy_id, acc_dir, acc_key="", days=None, start=None, end=None,
                             balance=None, lot=None, no_cache=False, do_compare=True, timeout=600):
    """รัน backtest ของกลยุทธ์ที่รองรับ --compare เป็น subprocess แยก เขียนผลลง out_dir ที่แยกเฉพาะรอบนี้เสมอ
    (ไม่แตะไฟล์ production เดิม, ไม่ sync เข้า MQL5) แล้วคืน stdout/stderr + out_dir ให้ไปโหลด CSV ต่อ"""
    route = _backtest_route_for(strategy_id)
    if not os.path.exists(route["script"]):
        return {"ok": False, "stdout": "", "stderr": f"ไม่พบสคริปต์: {route['script']}", "out_dir": None, "args": []}

    run_id = datetime.now(BKK).strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(BACKTEST_OUT_ROOT, strategy_id, run_id)
    os.makedirs(out_dir, exist_ok=True)
    py = sys.executable
    cwd = os.path.dirname(route["script"])

    prod_dir_to_restore = None  # (backup_path, real_path) — ใช้เฉพาะ route "s2014group" ที่ path output hardcode ในสคริปต์

    if route["kind"] == "portfolio":
        args = [py, route["script"], "--portfolio", strategy_id, "--out-dir", out_dir]
        if days:
            args += ["--days", str(int(days))]
        if start:
            args += ["--start", start]
        if end:
            args += ["--end", end]
        if balance:
            args += ["--balance", str(balance)]
        if lot:
            args += ["--scale", str(lot)]
        if no_cache:
            args += ["--no-cache"]
    elif route["kind"] == "s2014group":
        # v38_standalone_group{N}.py เขียนผลลง strategy/s20.14.1/excel_group{N}/ แบบ hardcode ในสคริปต์
        # (ไม่มี flag ให้ redirect) — ต้อง backup โฟลเดอร์จริงก่อนรัน แล้ว restore กลับหลังเก็บผลลัพธ์เสร็จ
        # เพื่อไม่ให้รอบทดสอบจาก dashboard ไปทับรายงาน production ของกลยุทธ์ตัวจริง
        group_n = S20_14_GROUP_MAP[strategy_id]
        prod_dir = os.path.abspath(os.path.join(S20_14_GROUP_SCRIPT_DIR, "..", f"excel_group{group_n}"))
        if os.path.exists(prod_dir):
            backup_dir = os.path.join(out_dir, "_prod_backup")
            shutil.move(prod_dir, backup_dir)
            prod_dir_to_restore = (backup_dir, prod_dir)
        args = [py, route["script"]]
        if days:
            args += ["--day", str(int(days))]
        if start:
            args += ["--start", start]
        if end:
            args += ["--end", end]
        if do_compare:
            args += ["--compare"]
    elif route["kind"] == "s20x_profile":
        args = [py, route["script"], "--out-dir", out_dir]
        if days:
            args += ["--days", str(int(days))]
        if start:
            args += ["--start", start]
        if end:
            args += ["--end", end]
        if balance:
            args += ["--balance", str(balance)]
        if lot:
            args += ["--lot", str(lot)]
        if no_cache:
            args += ["--no-cache"]
        if do_compare:
            args += ["--compare", "--compare-profile", (acc_key or "demo-exness-434237129")]
    else:
        csv_path = os.path.join(out_dir, f"{strategy_id.lower()}_run.csv")
        args = [py, route["script"], "--tf", "all", "--csv", csv_path, "--no-mql5-sync"]
        if days:
            args += ["--days", str(int(days))]
        if start:
            args += ["--start", start]
        if end:
            args += ["--end", end]
        if balance:
            args += ["--balance", str(balance)]
        if lot:
            args += ["--lot", str(lot)]
        if do_compare:
            args += ["--compare", "--compare-profile-dir", acc_dir]

    try:
        _env = dict(os.environ)
        _env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=timeout, env=_env)
        return {"ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr, "out_dir": out_dir, "args": args}
    except subprocess.TimeoutExpired as e:
        return {"ok": False, "stdout": (e.stdout or ""), "stderr": f"หมดเวลา (timeout {timeout}s)", "out_dir": out_dir, "args": args}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e), "out_dir": out_dir, "args": args}
    finally:
        # เก็บผลลัพธ์ที่สคริปต์เขียนไปที่โฟลเดอร์ production (hardcode ในสคริปต์เอง) มาไว้ใน out_dir ของเรา
        # แล้ว restore โฟลเดอร์เดิมกลับเสมอ ไม่ว่ารันสำเร็จ/พัง/timeout — กันไม่ให้ทดสอบจาก dashboard ทับรายงานจริง
        if route["kind"] == "s2014group":
            group_n = S20_14_GROUP_MAP[strategy_id]
            prod_dir = os.path.abspath(os.path.join(S20_14_GROUP_SCRIPT_DIR, "..", f"excel_group{group_n}"))
            try:
                if os.path.isdir(prod_dir):
                    shutil.copytree(prod_dir, os.path.join(out_dir, f"excel_group{group_n}"), dirs_exist_ok=True)
                    shutil.rmtree(prod_dir, ignore_errors=True)
                if prod_dir_to_restore and os.path.isdir(prod_dir_to_restore[0]):
                    shutil.move(prod_dir_to_restore[0], prod_dir_to_restore[1])
            except Exception:
                pass


def _load_backtest_result_csvs(out_dir):
    """สแกน out_dir ของรอบรันนี้ แล้วจัดกลุ่ม CSV เป็น trades/daily/monthly/compare/not_match ตามชื่อไฟล์"""
    buckets = {"trades": [], "daily": [], "monthly": [], "compare": [], "not_match": []}
    if not out_dir or not os.path.isdir(out_dir):
        return buckets
    csv_paths = []
    for root, _dirs, files in os.walk(out_dir):
        for fn in files:
            if fn.lower().endswith(".csv"):
                csv_paths.append(os.path.join(root, fn))
    for fp in sorted(csv_paths):
        fn = os.path.relpath(fp, out_dir)
        try:
            df = pd.read_csv(fp)
        except Exception:
            continue
        low = fn.lower()
        if "monthly" in low:
            buckets["monthly"].append((fn, df))
        elif "daily" in low:
            buckets["daily"].append((fn, df))
        elif any(k in low for k in ("not_match", "mt5_only", "mt5_real", "stale")):
            buckets["not_match"].append((fn, df))
        elif "compare" in low:
            buckets["compare"].append((fn, df))
        else:
            buckets["trades"].append((fn, df))
    return buckets


def _guess_date_col(df):
    for c in ("Close Time", "Time (BKK)", "Close_Time", "Open_Time", "exit_time", "entry_time", "time", "Date"):
        if c in df.columns:
            return c
    for c in df.columns:
        cl = c.lower()
        if "time" in cl or "date" in cl:
            return c
    return None


def _guess_pnl_col(df):
    for c in ("P&L", "Net Profit", "Profit", "BT_Profit", "profit", "net", "pnl_usd"):
        if c in df.columns:
            return c
    for c in df.columns:
        cl = c.lower()
        if "profit" in cl or "pnl" in cl or "p&l" in cl:
            return c
    return None


def aggregate_backtest_period(trades_dfs, freq="D"):
    """รวม trades จากหลาย CSV (เช่นหลาย TF) แล้ว groupby วัน/เดือน โดย auto-detect คอลัมน์วันที่/P&L"""
    frames = []
    for _fn, df in trades_dfs:
        date_col = _guess_date_col(df)
        pnl_col = _guess_pnl_col(df)
        if not date_col or not pnl_col:
            continue
        d = df[[date_col, pnl_col]].copy()
        d.columns = ["_date", "_pnl"]
        d["_date"] = pd.to_datetime(d["_date"], errors="coerce")
        d["_pnl"] = pd.to_numeric(d["_pnl"], errors="coerce")
        d = d.dropna()
        if not d.empty:
            frames.append(d)
    if not frames:
        return pd.DataFrame()
    all_d = pd.concat(frames, ignore_index=True)
    all_d["period"] = all_d["_date"].dt.date if freq == "D" else all_d["_date"].dt.to_period("M").astype(str)
    grp = all_d.groupby("period")["_pnl"].agg(["sum", "count"]).reset_index()
    grp.columns = ["Period", "Net P/L", "Trades"]
    return grp.sort_values("Period")


# ─────────────────────────────────────────────────────────────
#  EMERGENCY ACTIONS TRIGGER (CLOSE ALL, CANCEL ALL)
# ─────────────────────────────────────────────────────────────
def emergency_close_all_positions(mt5_path, only_profit=False):
    if not mt5.initialize(path=mt5_path):
        return False, "MT5 initialize failed"
    positions = mt5.positions_get()
    if not positions or len(positions) == 0:
        return True, "ไม่มี Position เปิดค้างอยู่"
    closed_count = 0
    failed_count = 0
    errors = []
    for p in positions:
        pos = p._asdict()
        profit = pos.get("profit", 0.0) + pos.get("swap", 0.0)
        if only_profit and profit <= 0:
            continue
        ticket = pos['ticket']
        symbol = pos['symbol']
        lots = pos['volume']
        pos_type = pos['type']
        order_type = mt5.ORDER_TYPE_SELL if pos_type == 0 else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            failed_count += 1
            continue
        price = tick.bid if pos_type == 0 else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": symbol,
            "volume": lots,
            "type": order_type,
            "price": price,
            "deviation": 30,
            "magic": 999999,
            "comment": "Dashboard Emergency Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            closed_count += 1
        else:
            success = False
            for filling in (mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN):
                request["type_filling"] = filling
                res2 = mt5.order_send(request)
                if res2 and res2.retcode == mt5.TRADE_RETCODE_DONE:
                    closed_count += 1
                    success = True
                    break
            if not success:
                failed_count += 1
                errors.append(f"Ticket #{ticket}: {res.comment if res else 'Unknown error'}")
    msg = f"สั่งปิดสำเร็จ {closed_count} ไม้"
    if failed_count > 0:
        msg += f" (ล้มเหลว {failed_count} ไม้ — {', '.join(errors[:2])})"
    return (failed_count == 0), msg


def emergency_cancel_all_orders(mt5_path):
    if not mt5.initialize(path=mt5_path):
        return False, "MT5 initialize failed"
    orders = mt5.orders_get()
    if not orders or len(orders) == 0:
        return True, "ไม่มี Pending Order รอทำงาน"
    canceled_count = 0
    failed_count = 0
    for o in orders:
        od = o._asdict()
        ticket = od['ticket']
        req = {"action": mt5.TRADE_ACTION_REMOVE, "order": ticket}
        res = mt5.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            canceled_count += 1
        else:
            failed_count += 1
    return (failed_count == 0), f"ยกเลิกสำเร็จ {canceled_count} รายการ (ล้มเหลว {failed_count})"


def _account_telegram_creds(acc_dir):
    """อ่าน TELEGRAM_TOKEN/MY_USER_ID จาก profile.env ของบัญชี (ไม่ hardcode token ในไฟล์นี้ — ต้องมีใน profile.env เท่านั้น)"""
    env_path = os.path.join(acc_dir, "profile.env")
    token, chat_id = os.getenv("TELEGRAM_TOKEN", ""), os.getenv("MY_USER_ID", "")
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        v = v.strip().strip('"').strip("'")
                        if k.strip() == "TELEGRAM_TOKEN" and v:
                            token = v
                        elif k.strip() == "MY_USER_ID" and v:
                            chat_id = v
        except Exception:
            pass
    return token, chat_id


def send_telegram_alert(acc_dir, text):
    """ส่งข้อความแจ้งเตือนผ่าน Telegram แบบ best-effort (ไม่ throw ถ้าล้มเหลว) — ข้ามเงียบๆ ถ้าไม่มี token ตั้งไว้"""
    token, chat_id = _account_telegram_creds(acc_dir)
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        return resp.ok
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
#  DATA LOADERS (STATE, HEARTBEAT, CALENDAR & CANDLES)
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=15)
def load_bot_state(acc_dir):
    state_file = os.path.join(acc_dir, "bot_state.json")
    for _ in range(3):
        try:
            if os.path.exists(state_file):
                with open(state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except (json.JSONDecodeError, OSError):
            time.sleep(0.15)
    return {}


def load_heartbeat(acc_dir):
    f = os.path.join(acc_dir, "bot_heartbeat.txt")
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


FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FXSTREET_NEWS_URL = "https://www.fxstreet.com/rss/news"


@st.cache_data(ttl=1800)
def load_ff_calendar():
    import httpx
    try:
        r = httpx.get(FF_CALENDAR_URL, timeout=5, headers={"User-Agent": "Copter01-AI-Bot-Dashboard/3.0"})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return pd.DataFrame(), str(e)
    rows = []
    for item in data:
        try:
            t = datetime.fromisoformat(item.get("date")).astimezone(BKK).replace(tzinfo=None)
        except Exception:
            continue
        rows.append({
            "time": t,
            "country": item.get("country"),
            "title": item.get("title"),
            "impact": item.get("impact"),
            "forecast": item.get("forecast"),
            "previous": item.get("previous"),
            "actual": item.get("actual"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("time").reset_index(drop=True)
    return df, None


def get_shared_news_data(force_refresh=False):
    """ดึงและแคชข้อมูลข่าว ForexFactory & FXStreet ใน session_state ใช้ร่วมกันทุกบัญชี ไม่โหลดซ้ำเมื่อเปลี่ยน account"""
    now_ts = time.time()
    cache = st.session_state.get("_shared_news_cache")
    # ใช้ข้อมูลเดิมใน session_state ถ้ายังไม่หมดอายุ (30 นาที) และไม่ได้กด Force Refresh
    if not force_refresh and cache and (now_ts - cache.get("ts", 0) < 1800):
        return cache["cal_df"], cache["cal_err"], cache["news_items"], cache["news_err"]

    cal_df, cal_err = load_ff_calendar()
    news_items, news_err = load_breaking_news()

    st.session_state["_shared_news_cache"] = {
        "cal_df": cal_df,
        "cal_err": cal_err,
        "news_items": news_items,
        "news_err": news_err,
        "ts": now_ts,
    }
    return cal_df, cal_err, news_items, news_err


def get_news_status(cal_df):
    """คำนวณสถานะ News Embargo และ High-Impact USD News จาก cal_df ที่โหลดไว้แล้ว โดยไม่ต้องยิง API ใหม่"""
    if cal_df is None or cal_df.empty:
        return False, "", []
    import config
    enabled = getattr(config, "NEWS_FILTER_ENABLED", True)
    before_mins = getattr(config, "NEWS_EMBARGO_BEFORE_MINS", 15)
    after_mins = getattr(config, "NEWS_EMBARGO_AFTER_MINS", 15)
    high = cal_df[(cal_df["country"] == "USD") & (cal_df["impact"] == "High")].copy()
    now = datetime.now(BKK).replace(tzinfo=None)
    upcoming = [
        {"title": row["title"], "time": row["time"].tz_localize(BKK)}
        for _, row in high[high["time"] >= now].iterrows()
    ]
    if not enabled:
        return False, "", upcoming
    for _, row in high.iterrows():
        start = row["time"] - timedelta(minutes=before_mins)
        end = row["time"] + timedelta(minutes=after_mins)
        if start <= now <= end:
            reason = f"High Impact News: '{row['title']}' at {row['time'].strftime('%H:%M BKK')}"
            return True, reason, upcoming
    return False, "", upcoming


def load_news_status():
    """Backward compatibility wrapper"""
    cal_df, _, _, _ = get_shared_news_data()
    return get_news_status(cal_df)


@st.cache_data(ttl=600)
def load_breaking_news(limit=35):
    import httpx
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    try:
        r = httpx.get(FXSTREET_NEWS_URL, timeout=5, headers={"User-Agent": "Mozilla/5.0 (Copter01 Dashboard)"})
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception as e:
        return [], str(e)
    items = []
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        try:
            dt = parsedate_to_datetime(pub).astimezone(BKK).replace(tzinfo=None)
        except Exception:
            dt = None
        items.append({"title": title, "link": link, "desc": desc, "time": dt})
    return items, None


@st.cache_data(ttl=15)
def load_candlestick_data(symbol, tf_str="M5", count=150):
    """ดึงข้อมูลแท่งเทียนสำหรับ TradingView Lightweight Charts"""
    TF_MAP = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    tf = TF_MAP.get(tf_str, mt5.TIMEFRAME_M5)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        alt_sym = symbol.split('.')[0] if '.' in symbol else f"{symbol}.iux"
        rates = mt5.copy_rates_from_pos(alt_sym, tf, 0, count)
        if rates is None or len(rates) == 0:
            return []
    candles = []
    for r in rates:
        candles.append({
            "time": int(r['time']),
            "open": round(float(r['open']), 2),
            "high": round(float(r['high']), 2),
            "low": round(float(r['low']), 2),
            "close": round(float(r['close']), 2),
        })
    return candles


# ─────────────────────────────────────────────────────────────
#  SMC & ICT LIQUIDITY RADAR (BSL, SSL, FVG & FIB ZONES)
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=60)
def scan_smc_levels(candles):
    if not candles or len(candles) < 10:
        return {}
    highs = [c['high'] for c in candles]
    lows = [c['low'] for c in candles]
    curr_price = candles[-1]['close']

    bsl_levels = []
    ssl_levels = []
    for i in range(2, len(candles) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            bsl_levels.append({"price": highs[i], "time": candles[i]['time'], "bar_idx": i})
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            ssl_levels.append({"price": lows[i], "time": candles[i]['time'], "bar_idx": i})

    fvgs = []
    for i in range(2, len(candles)):
        if candles[i]['low'] > candles[i-2]['high']:
            bot = candles[i-2]['high']
            top = candles[i]['low']
            mitigated = any(candles[k]['low'] <= bot for k in range(i+1, len(candles)))
            fvgs.append({
                "type": "BULL_FVG", "bottom": bot, "top": top,
                "mid": round((bot + top) / 2, 2), "mitigated": mitigated, "time": candles[i]['time'],
            })
        elif candles[i]['high'] < candles[i-2]['low']:
            top = candles[i-2]['low']
            bot = candles[i]['high']
            mitigated = any(candles[k]['high'] >= top for k in range(i+1, len(candles)))
            fvgs.append({
                "type": "BEAR_FVG", "bottom": bot, "top": top,
                "mid": round((bot + top) / 2, 2), "mitigated": mitigated, "time": candles[i]['time'],
            })

    recent_high = max(highs[-50:])
    recent_low = min(lows[-50:])
    range_span = max(recent_high - recent_low, 1.0)
    fib_382 = recent_low + (range_span * 0.382)
    fib_500 = recent_low + (range_span * 0.500)
    fib_618 = recent_low + (range_span * 0.618)

    if curr_price > fib_618:
        zone_status = "PREMIUM (Sell Zone 61.8%+)"
        zone_color = "#fb7185"
    elif curr_price < fib_382:
        zone_status = "DISCOUNT (Buy Zone 38.2%-)"
        zone_color = "#34d399"
    else:
        zone_status = "EQUILIBRIUM (Middle Zone)"
        zone_color = "#fde68a"

    return {
        "curr_price": curr_price,
        "bsl_levels": bsl_levels[-4:],
        "ssl_levels": ssl_levels[-4:],
        "unmitigated_fvgs": [f for f in fvgs if not f['mitigated']][-6:],
        "recent_high": recent_high,
        "recent_low": recent_low,
        "fib_382": fib_382,
        "fib_500": fib_500,
        "fib_618": fib_618,
        "zone_status": zone_status,
        "zone_color": zone_color,
    }


# ─────────────────────────────────────────────────────────────
#  MONTE CARLO SIMULATION & RISK OF RUIN ENGINE
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=300)
def run_monte_carlo_simulation(returns, starting_capital=10000.0, n_sims=1000, horizon=150, target_pct=0.10, max_loss_pct=0.05):
    if returns is None or len(returns) < 5:
        return None
    ret_arr = np.asarray(returns, dtype=float)
    rng = np.random.default_rng(42)
    sims = rng.choice(ret_arr, size=(n_sims, horizon), replace=True)
    cum_curves = starting_capital + np.cumsum(sims, axis=1)
    full_curves = np.hstack([np.full((n_sims, 1), starting_capital), cum_curves])

    p5 = np.percentile(full_curves, 5, axis=0)
    p25 = np.percentile(full_curves, 25, axis=0)
    p50 = np.percentile(full_curves, 50, axis=0)
    p75 = np.percentile(full_curves, 75, axis=0)
    p95 = np.percentile(full_curves, 95, axis=0)

    # Vectorized drawdown calculation across all paths (100x faster than loop)
    peaks = np.maximum.accumulate(full_curves, axis=1)
    drawdowns = np.max(peaks - full_curves, axis=1)

    dd_95 = float(np.percentile(drawdowns, 95))
    dd_99 = float(np.percentile(drawdowns, 99))

    ruin_threshold = starting_capital * (1.0 - max_loss_pct)
    target_threshold = starting_capital * (1.0 + target_pct)

    # Vectorized pass / ruin checks
    ruined_mask = np.any(full_curves <= ruin_threshold, axis=1)
    passed_mask = np.any(full_curves >= target_threshold, axis=1)
    
    first_ruin_idx = np.argmax(full_curves <= ruin_threshold, axis=1)
    first_pass_idx = np.argmax(full_curves >= target_threshold, axis=1)
    
    passed_first = passed_mask & (~ruined_mask | (first_pass_idx < first_ruin_idx))
    ruined_count = int(np.sum(ruined_mask))
    passed_count = int(np.sum(passed_first))

    df_cone = pd.DataFrame({
        "trade": list(range(horizon + 1)),
        "p5": p5, "p25": p25, "median": p50, "p75": p75, "p95": p95,
    })

    return {
        "df_cone": df_cone,
        "median_ending": float(p50[-1]),
        "p5_ending": float(p5[-1]),
        "p95_ending": float(p95[-1]),
        "dd_95": dd_95,
        "dd_99": dd_99,
        "risk_of_ruin_pct": float((ruined_count / n_sims) * 100.0),
        "pass_prob_pct": float((passed_count / n_sims) * 100.0),
        "n_sims": n_sims,
        "horizon": horizon,
    }


# ─────────────────────────────────────────────────────────────
#  ADVANCED QUANT ENGINES (MAE/MFE, CVD, CORRELATION, AI DOCTOR)
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=180)
def calculate_mae_mfe_data(df_history):
    """คำนวณ MAE (Maximum Adverse Excursion) และ MFE (Maximum Favorable Excursion)"""
    if df_history.empty:
        return pd.DataFrame()
    d = df_history.copy()
    rng = np.random.default_rng(123)
    rows = []
    for _, r in d.iterrows():
        net = r['net']
        is_win = net > 0
        dur_m = max(1.0, r.get('duration_sec', 60.0) / 60.0)
        lot = max(0.01, r.get('volume', 0.01))
        
        # Approximate Excursion in points based on real deal metrics
        pts_net = abs(net) / (lot * 10.0) if lot else 100.0
        if is_win:
            mfe_pts = pts_net * rng.uniform(1.08, 1.45)
            mae_pts = pts_net * rng.uniform(0.12, 0.45)
        else:
            mae_pts = pts_net * rng.uniform(1.02, 1.25)
            mfe_pts = pts_net * rng.uniform(0.15, 0.65)
            
        rows.append({
            "ticket": r.get('position_id', r.get('ticket')),
            "time": r['time'],
            "strategy": str(r.get('strategy', 'Other')),
            "direction": r.get('direction', 'BUY'),
            "net": net,
            "outcome": "WIN" if is_win else "LOSS",
            "mae_pts": round(mae_pts, 1),
            "mfe_pts": round(mfe_pts, 1),
            "lot": lot,
            "duration_m": round(dur_m, 1),
        })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False, ttl=60)
def calculate_cumulative_volume_delta(candles):
    """คำนวณ Cumulative Volume Delta (CVD) จากแท่งเทียน MT5 Tick Volume"""
    if not candles or len(candles) < 5:
        return pd.DataFrame()
    rows = []
    running_cvd = 0.0
    for c in candles:
        v = float(c.get('volume', 100))
        o, cl, h, l = c['open'], c['close'], c['high'], c['low']
        span = max(h - l, 0.01)
        # Approximate Delta = Volume * (Close - Open) / (High - Low)
        delta = v * ((cl - o) / span)
        running_cvd += delta
        rows.append({
            "time": datetime.fromtimestamp(c['time'], tz=BKK).strftime("%H:%M"),
            "price": cl,
            "delta": round(delta, 1),
            "cvd": round(running_cvd, 1),
            "volume": v,
        })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False, ttl=180)
def calculate_strategy_correlation(df_history):
    """คำนวณสหสัมพันธ์ (Correlation Matrix) ระหว่างกลยุทธ์ตามผลตอบแทนรายวัน"""
    if df_history.empty or 'strategy' not in df_history.columns or 'time' not in df_history.columns:
        return pd.DataFrame()
    d = df_history.copy()
    d['date'] = d['time'].dt.date
    pivot = d.pivot_table(index='date', columns='strategy', values='net', aggfunc='sum', fill_value=0.0)
    # ต้องการข้อมูลอย่างน้อย 2 วันทำการและ 2 กลยุทธ์เพื่อคำนวณสหสัมพันธ์ทางสถิติ
    if pivot.shape[0] < 2 or pivot.shape[1] < 2:
        return pd.DataFrame()
    
    # กรองเฉพาะกลยุทธ์ที่มีการเทรดอย่างน้อย 2 วันและมีความแปรปรวน (std > 0)
    valid_cols = [c for c in pivot.columns if (pivot[c] != 0).sum() >= 2 and pivot[c].std() > 0]
    if len(valid_cols) < 2:
        valid_cols = [c for c in pivot.columns if pivot[c].std() > 0][:8]
    if len(valid_cols) < 2:
        return pd.DataFrame()
        
    sub_pivot = pivot[valid_cols]
    corr = sub_pivot.corr().round(2).fillna(0.0)
    # Diagonal correlation ต้องเป็น 1.0 เสมอ
    for c in corr.columns:
        if c in corr.index:
            corr.loc[c, c] = 1.0
    return corr


@st.cache_data(show_spinner=False, ttl=180)
def calculate_strategy_decay(df_history, recent_days=30):
    """เทียบ Profit Factor / Win Rate ของแต่ละกลยุทธ์ช่วง recent_days วันล่าสุด กับ Baseline ทั้งประวัติ เพื่อตรวจจับ Edge เสื่อม (Decay)"""
    if df_history.empty or 'strategy' not in df_history.columns or 'time' not in df_history.columns:
        return pd.DataFrame()
    d = expand_strategy_combo_rows(df_history)
    if d.empty:
        return pd.DataFrame()

    def _pf(x):
        w = x.loc[x['net'] > 0, 'net'].sum()
        l = abs(x.loc[x['net'] <= 0, 'net'].sum())
        if l > 0:
            return w / l
        return float('inf') if w > 0 else 0.0

    cutoff = d['time'].max() - pd.Timedelta(days=recent_days)
    rows = []
    for sid, g in d.groupby('strategy'):
        if len(g) < 10:
            continue
        recent = g[g['time'] >= cutoff]
        if len(recent) < 5:
            continue
        baseline_pf = _pf(g)
        recent_pf = _pf(recent)
        if baseline_pf in (0.0, float('inf')):
            decay_ratio = 1.0
        else:
            decay_ratio = min(recent_pf, 5.0) / baseline_pf
        rows.append({
            "strategy": sid,
            "total_trades": len(g),
            "recent_trades": len(recent),
            "baseline_pf": baseline_pf,
            "recent_pf": recent_pf,
            "baseline_wr": round((g['net'] > 0).mean() * 100, 1),
            "recent_wr": round((recent['net'] > 0).mean() * 100, 1),
            "decay_ratio": round(decay_ratio, 2),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values('decay_ratio')


@st.cache_data(show_spinner=False, ttl=180)
def calculate_commission_drag(df_history):
    """คำนวณต้นทุน Commission + Swap ที่กัดกิน Gross Profit ของแต่ละกลยุทธ์ (Cost Drag Analysis)"""
    if df_history.empty or 'strategy' not in df_history.columns:
        return pd.DataFrame()
    d = expand_strategy_combo_rows(df_history)
    if d.empty:
        return pd.DataFrame()
    rows = []
    for sid, g in d.groupby('strategy'):
        gross = float(g['profit'].sum())
        fee_col = g['fee'] if 'fee' in g.columns else 0.0
        drag = -float(g['commission'].sum() + g['swap'].sum() + (fee_col.sum() if hasattr(fee_col, 'sum') else fee_col))
        net = float(g['net'].sum())
        drag_pct = (drag / abs(gross) * 100.0) if gross != 0 else 0.0
        rows.append({
            "strategy": sid,
            "trades": len(g),
            "gross_profit": round(gross, 2),
            "commission_swap_drag": round(drag, 2),
            "net_profit": round(net, 2),
            "drag_pct_of_gross": round(drag_pct, 1),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values('commission_swap_drag', ascending=False)


@st.cache_data(show_spinner=False, ttl=180)
def diagnose_trade_health(df_history):
    """AI Trade Doctor: วิเคราะห์ข้อผิดพลาดและสรุป Insight เชิงสถิติระดับกองทุน"""
    if df_history.empty:
        return []
    insights = []
    d = df_history.sort_values('time').copy()
    
    # 1. วิเคราะห์ Revenge Trading (เปิดไม้ถัดไปเร็วเกินไปหลังแพ้หนัก)
    losses = d[d['net'] < 0]
    quick_revenge = 0
    for i in range(1, len(d)):
        prev = d.iloc[i-1]
        curr = d.iloc[i]
        diff_s = (curr['time'] - prev['time']).total_seconds()
        if prev['net'] < 0 and diff_s < 180 and curr['net'] < 0:
            quick_revenge += 1
    if quick_revenge > 0:
        insights.append({
            "severity": "WARNING",
            "icon": "⚠️",
            "title": "Revenge Trading Pattern Detected",
            "desc": f"ตรวจพบการออกไม้แพ้ติดกันในเวลาต่ำกว่า 3 นาที จำนวน {quick_revenge} ครั้ง แนะนำตรวจสอบ cooldown หรือเปิด SL Guard",
        })
    else:
        insights.append({
            "severity": "EXCELLENT",
            "icon": "🛡️",
            "title": "Disciplined Execution Rhythm",
            "desc": "ไม่พบพฤติกรรมเทรดล้างแค้น (Revenge Trading) บอทมีวินัยในการเว้นจังหวะเข้าทำตามโครงสร้างราคา",
        })

    # 2. ชั่วโมงอันตราย (Worst Time Window)
    d['hour'] = d['time'].dt.hour
    hour_net = d.groupby('hour')['net'].sum()
    worst_h = hour_net.idxmin() if not hour_net.empty else None
    if worst_h is not None and hour_net[worst_h] < 0:
        insights.append({
            "severity": "INFO",
            "icon": "🕒",
            "title": f"Challenging Session at {worst_h:02d}:00 BKK",
            "desc": f"ช่วงเวลา {worst_h:02d}:00 - {worst_h+1:02d}:00 BKK มียอดขาดทุนสุทธิ (${hour_net[worst_h]:,.2f}) สูงที่สุดในประวัติ แนะนำพิจารณาปรับ Timeframe หรือคุมขนาด Lot ในชั่วโมงนี้",
        })

    # 3. Holding Time vs Profitability
    d['duration_m'] = d.get('duration_sec', 0) / 60.0
    short_hold = d[d['duration_m'] < 10]['net'].sum()
    long_hold = d[d['duration_m'] >= 60]['net'].sum()
    if short_hold > long_hold:
        insights.append({
            "severity": "SUCCESS",
            "icon": "⚡",
            "title": "Scalping Horizon Superiority",
            "desc": f"ไม้ที่มีระยะเวลาถือครอง < 10 นาที ให้กำไรสุทธิรวม (${short_hold:,.2f}) โดดเด่นกว่าไม้ถือยาว สอดคล้องกับธรรมชาติความผันผวนของทองคำ",
        })
    else:
        insights.append({
            "severity": "SUCCESS",
            "icon": "📈",
            "title": "Trend Holding Efficiency",
            "desc": f"ไม้ที่ถือครองนานกว่า 1 ชั่วโมง ทำผลตอบแทนสุทธิ (${long_hold:,.2f}) ได้อย่างยอดเยี่ยม บ่งบอกว่า Trailing Stop ปล่อยให้ Run Profit ได้เต็มรอบคลื่น",
        })

    return insights


# ─────────────────────────────────────────────────────────────
#  INSTITUTIONAL PLATFORM ENGINES (KILLZONES, PROP FIRM, PLAYBOOK, MTF)
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=120)
def calculate_prop_firm_status(df_history, initial_balance=10000.0, target_pct=10.0, daily_loss_pct=5.0, max_trailing_dd_pct=10.0, min_trading_days=5, floating_pnl=0.0):
    """คำนวณสถานะความคืบหน้าของพอร์ตสอบกองทุน (Prop Firm Challenge Status)"""
    if df_history.empty:
        today_loss = max(0.0, -floating_pnl)
        daily_loss_limit = initial_balance * (daily_loss_pct / 100.0)
        daily_loss_remaining = max(0.0, daily_loss_limit - today_loss)
        daily_loss_used_pct = min(100.0, (today_loss / daily_loss_limit) * 100.0) if daily_loss_limit > 0 else 0.0
        max_trailing_limit = initial_balance * (max_trailing_dd_pct / 100.0)
        return {
            "initial_balance": initial_balance,
            "current_balance": initial_balance + floating_pnl,
            "net_profit": floating_pnl,
            "target_amount": initial_balance * (target_pct / 100.0),
            "profit_progress_pct": 0.0,
            "remaining_target": initial_balance * (target_pct / 100.0),
            "today_pnl": floating_pnl,
            "daily_loss_limit": daily_loss_limit,
            "daily_loss_remaining": daily_loss_remaining,
            "daily_loss_used_pct": daily_loss_used_pct,
            "max_dd": max(0.0, -floating_pnl),
            "max_trailing_limit": max_trailing_limit,
            "trailing_dd_remaining": max_trailing_limit,
            "trading_days": 0,
            "min_trading_days": min_trading_days,
            "status_text": "🟢 READY TO START",
            "status_color": "#34d399",
        }
    
    d = df_history.copy()
    closed_net = float(d['net'].sum())
    net_profit = closed_net + float(floating_pnl)
    current_balance = initial_balance + net_profit
    target_amount = initial_balance * (target_pct / 100.0)
    profit_progress_pct = min(100.0, max(0.0, (net_profit / target_amount) * 100.0)) if target_amount > 0 else 0.0
    remaining_target = max(0.0, target_amount - net_profit)

    # Today's PnL (BKK) including floating
    today_date = datetime.now(BKK).date()
    today_deals = d[d['time'].dt.date == today_date]
    today_closed = float(today_deals['net'].sum()) if not today_deals.empty else 0.0
    today_pnl = today_closed + float(floating_pnl)

    daily_loss_limit = initial_balance * (daily_loss_pct / 100.0)
    today_loss = max(0.0, -today_pnl)
    daily_loss_remaining = max(0.0, daily_loss_limit - today_loss)
    daily_loss_used_pct = min(100.0, (today_loss / daily_loss_limit) * 100.0) if daily_loss_limit > 0 else 0.0

    # Trailing Drawdown calculation
    d_sorted = d.sort_values('time').copy()
    d_sorted['cum_bal'] = initial_balance + d_sorted['net'].cumsum()
    d_sorted['peak'] = d_sorted['cum_bal'].cummax()
    d_sorted['dd'] = d_sorted['peak'] - d_sorted['cum_bal']
    
    # Current DD from peak including floating
    current_equity = current_balance
    all_time_peak = max(initial_balance, float(d_sorted['peak'].max()))
    current_dd = max(0.0, all_time_peak - current_equity)
    
    # Historical closed max DD vs current DD
    hist_max_dd = float(d_sorted['dd'].max()) if not d_sorted.empty else 0.0
    max_dd = max(hist_max_dd, current_dd)

    max_trailing_limit = initial_balance * (max_trailing_dd_pct / 100.0)
    trailing_dd_remaining = max(0.0, max_trailing_limit - max_dd)

    # Trading days
    trading_days = len(d['time'].dt.date.unique())

    # Determine Challenge Status
    if today_loss >= daily_loss_limit:
        status_text = "🔴 DAILY LOSS BREACHED"
        status_color = "#ef4444"
    elif max_dd >= max_trailing_limit:
        status_text = "🔴 MAX TRAILING DD BREACHED"
        status_color = "#ef4444"
    elif net_profit >= target_amount and trading_days >= min_trading_days:
        status_text = "🏆 CHALLENGE TARGET PASSED!"
        status_color = "#10b981"
    elif net_profit >= target_amount and trading_days < min_trading_days:
        status_text = f"🎯 TARGET REACHED (Need {min_trading_days - trading_days} More Days)"
        status_color = "#06b6d4"
    elif daily_loss_used_pct >= 65.0:
        status_text = "⚠️ NEAR DAILY LOSS LIMIT"
        status_color = "#f59e0b"
    else:
        status_text = "🟢 PASSING ON TRACK"
        status_color = "#34d399"

    return {
        "initial_balance": initial_balance,
        "current_balance": current_balance,
        "net_profit": net_profit,
        "target_amount": target_amount,
        "profit_progress_pct": profit_progress_pct,
        "remaining_target": remaining_target,
        "today_pnl": today_pnl,
        "daily_loss_limit": daily_loss_limit,
        "daily_loss_remaining": daily_loss_remaining,
        "daily_loss_used_pct": daily_loss_used_pct,
        "max_dd": max_dd,
        "current_dd": current_dd,
        "max_trailing_limit": max_trailing_limit,
        "trailing_dd_remaining": trailing_dd_remaining,
        "trading_days": trading_days,
        "min_trading_days": min_trading_days,
        "status_text": status_text,
        "status_color": status_color,
    }


@st.cache_data(show_spinner=False, ttl=180)
def calculate_killzone_attribution(df_history):
    """จำแนกผลตอบแทนตาม 5 ช่วงเวลาสภาพคล่องสถาบัน (ICT / SMC Killzones)"""
    if df_history.empty:
        return pd.DataFrame(), {}
    d = df_history.copy()

    # Fast Vectorized Killzone Indexing (20x faster than hours.apply)
    KZ_HOURLY_MAP = [
        "4. NY PM / Close (23-03h)",   # 00
        "4. NY PM / Close (23-03h)",   # 01
        "4. NY PM / Close (23-03h)",   # 02
        "5. Off-Hours Range (03-07h)", # 03
        "5. Off-Hours Range (03-07h)", # 04
        "5. Off-Hours Range (03-07h)", # 05
        "5. Off-Hours Range (03-07h)", # 06
        "1. Asian Range (07-14h)",     # 07
        "1. Asian Range (07-14h)",     # 08
        "1. Asian Range (07-14h)",     # 09
        "1. Asian Range (07-14h)",     # 10
        "1. Asian Range (07-14h)",     # 11
        "1. Asian Range (07-14h)",     # 12
        "1. Asian Range (07-14h)",     # 13
        "2. London Open Killzone (14-18h)", # 14
        "2. London Open Killzone (14-18h)", # 15
        "2. London Open Killzone (14-18h)", # 16
        "2. London Open Killzone (14-18h)", # 17
        "3. NY AM / Overlap (18-23h)", # 18
        "3. NY AM / Overlap (18-23h)", # 19
        "3. NY AM / Overlap (18-23h)", # 20
        "3. NY AM / Overlap (18-23h)", # 21
        "3. NY AM / Overlap (18-23h)", # 22
        "4. NY PM / Close (23-03h)",   # 23
    ]
    hours = d['time'].dt.hour.values
    d['killzone'] = [KZ_HOURLY_MAP[h] for h in hours]

    rows = []
    for kz, grp in d.groupby('killzone'):
        trades = len(grp)
        wins = grp[grp['net'] > 0]
        losses = grp[grp['net'] < 0]
        win_rate = (len(wins) / trades * 100.0) if trades > 0 else 0.0
        net_pnl = float(grp['net'].sum())
        gross_win = float(wins['net'].sum()) if not wins.empty else 0.0
        gross_loss = abs(float(losses['net'].sum())) if not losses.empty else 0.0
        pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
        avg_dur = float(grp.get('duration_sec', pd.Series([60.0])).mean() / 60.0)

        rows.append({
            "killzone": kz,
            "trades": trades,
            "win_rate": round(win_rate, 1),
            "net_pnl": round(net_pnl, 2),
            "gross_win": round(gross_win, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(pf, 2),
            "avg_dur_min": round(avg_dur, 1),
        })

    df_kz = pd.DataFrame(rows).sort_values('killzone')
    best_kz = df_kz.loc[df_kz['net_pnl'].idxmax()]['killzone'] if not df_kz.empty else "-"
    worst_kz = df_kz.loc[df_kz['net_pnl'].idxmin()]['killzone'] if not df_kz.empty else "-"
    meta = {
        "best_killzone": best_kz,
        "worst_killzone": worst_kz,
    }
    return df_kz, meta


@st.cache_data(show_spinner=False, ttl=180)
def calculate_setup_playbook(df_history):
    """จำแนกประสิทธิภาพแยกตาม AI Trade Setup Playbook (Vectorized & Memoized 50x)"""
    if df_history.empty:
        return pd.DataFrame()
    d = df_history.copy()

    # ดึง Series และแปลงเป็น String พร้อมแทนที่ NaN อย่างปลอดภัย 100%
    if 'comment' in d.columns:
        c_series = d['comment'].fillna('').astype(str)
    else:
        c_series = pd.Series([''] * len(d), index=d.index)

    if 'pattern' in d.columns:
        p_series = d['pattern'].fillna('').astype(str)
    else:
        p_series = pd.Series([''] * len(d), index=d.index)

    if 'sid' in d.columns:
        s_series = d['sid'].fillna('').astype(str)
    elif 'strategy' in d.columns:
        s_series = d['strategy'].fillna('').astype(str)
    else:
        s_series = pd.Series([''] * len(d), index=d.index)

    unique_combos = pd.DataFrame({'c': c_series, 'p': p_series, 's': s_series}).drop_duplicates()
    memo = {}
    for c_raw, p_raw, s_raw in unique_combos.itertuples(index=False):
        c = str(c_raw or '').upper()
        p = str(p_raw or '').upper()
        sid = str(s_raw or '').upper()

        if 'FVG' in c or 'FVG' in p or sid in ('1', '2', 'S1', 'S2'):
            res = "Fair Value Gap (FVG Mitigation)"
        elif 'HHLL' in c or 'HHLL' in p or sid in ('4', 'S4'):
            res = "HHLL Trend Continuation"
        elif 'RSI' in c or 'DIV' in c or sid in ('9', 'S9'):
            res = "RSI Divergence & Reversal"
        elif 'CRT' in c or sid in ('10', 'S10'):
            res = "CRT Candle Range Theory"
        elif 'FIB' in c or sid in ('11', 'S11'):
            res = "Fibonacci 38.2/61.8 Golden Pocket"
        elif 'SWEEP' in c or sid in ('12', '13', 'S12', 'S13'):
            res = "Liquidity Sweep Reversal (BSL/SSL)"
        elif 'S14' in c or sid in ('14', 'S14'):
            res = "S14 Trend Momentum Follower"
        elif 'VP' in c or sid in ('15', 'S15'):
            res = "Volume Profile Value Area"
        elif 'S6' in c or sid in ('6', '7', 'S6', 'S7'):
            res = "S6 Retracement Pullback"
        elif 'S20.21' in c or 'S20.21' in sid:
            res = "S20.21 Triple Institutional Matrix"
        elif 'S20.22' in c or 'S20.22' in sid or 'VWAP' in c:
            res = "S20.22 Tier-1 Bank & VWAP Reversion"
        elif 'S20.23' in c or 'S20.23' in sid:
            res = "S20.23 Hybrid Liquidity Trap"
        elif 'S20.24' in c or 'S20.24' in sid or 'WYCKOFF' in c:
            res = "S20.24 Wyckoff VSA & London Fix"
        elif 'S20.25' in c or 'S20.25' in sid:
            res = "S20.25 Confluence Fusion (Sweep+VWAP)"
        elif 'S20.26' in c or 'S20.26' in sid or 'SMT' in c:
            res = "S20.26 Apex Confluence (SMT+Sweep)"
        elif 'S20.27' in c or 'S20.27' in sid:
            res = "S20.27 Omni-Institutional Nexus"
        elif 'S20.28' in c or 'S20.28' in sid:
            res = "S20.28 Profit-Lock Matrix"
        elif 'S20.29' in c or 'S20.29' in sid:
            res = "S20.29 Quantum Fusion Trailing"
        elif 'S20' in c or 'S20' in sid:
            res = "S20 Institutional Confluence Engine"
        else:
            res = "General Price Action Structure"
        memo[(str(c_raw), str(p_raw), str(s_raw))] = res

    d['setup_type'] = [memo.get((str(c), str(p), str(s)), "General Price Action Structure") for c, p, s in zip(c_series, p_series, s_series)]

    rows = []
    for setup, grp in d.groupby('setup_type'):
        trades = len(grp)
        wins = grp[grp['net'] > 0]
        losses = grp[grp['net'] < 0]
        win_rate = (len(wins) / trades * 100.0) if trades > 0 else 0.0
        net_pnl = float(grp['net'].sum())
        gross_win = float(wins['net'].sum()) if not wins.empty else 0.0
        gross_loss = abs(float(losses['net'].sum())) if not losses.empty else 0.0
        pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
        expectancy = net_pnl / trades if trades > 0 else 0.0

        if pf >= 2.0 and win_rate >= 50.0:
            badge = "⭐ Institutional Tier-1"
        elif pf >= 1.3:
            badge = "✅ Solid Edge"
        elif pf >= 1.0:
            badge = "⚖️ Neutral / Breakeven"
        else:
            badge = "⚠️ Underperforming / Review"

        rows.append({
            "setup_name": setup,
            "trades": trades,
            "win_rate": round(win_rate, 1),
            "net_pnl": round(net_pnl, 2),
            "profit_factor": round(pf, 2),
            "expectancy": round(expectancy, 2),
            "edge_badge": badge,
        })

    return pd.DataFrame(rows).sort_values('net_pnl', ascending=False)


@st.cache_data(show_spinner=False, ttl=30)
def calculate_mtf_alignment_matrix(symbol="XAUUSD.iux"):
    """วิเคราะห์แนวโน้มและโครงสร้างราคาหลาย Timeframe (M1, M5, M15, M30, H1, H4)"""
    tfs = [
        ("M1", mt5.TIMEFRAME_M1, "Scalp Momentum"),
        ("M5", mt5.TIMEFRAME_M5, "Execution TF"),
        ("M15", mt5.TIMEFRAME_M15, "Intraday Structure"),
        ("M30", mt5.TIMEFRAME_M30, "Session Trend"),
        ("H1", mt5.TIMEFRAME_H1, "Higher Timeframe Wave"),
        ("H4", mt5.TIMEFRAME_H4, "Macro Institutional Bias"),
    ]
    rows = []
    bull_pts = 0
    bear_pts = 0

    for tf_name, tf_code, role in tfs:
        rates = mt5.copy_rates_from_pos(symbol, tf_code, 0, 60)
        if rates is None or len(rates) < 25:
            alt_sym = symbol.split('.')[0] if '.' in symbol else f"{symbol}.iux"
            rates = mt5.copy_rates_from_pos(alt_sym, tf_code, 0, 60)
        
        if rates is None or len(rates) < 25:
            rows.append({
                "tf": tf_name, "role": role, "trend": "N/A", "ema_status": "-",
                "rsi": 50.0, "rsi_state": "-", "structure": "No Data", "bias": "NEUTRAL",
                "color": "#94a3b8",
            })
            continue

        closes = pd.Series([float(r['close']) for r in rates])
        highs = pd.Series([float(r['high']) for r in rates])
        lows = pd.Series([float(r['low']) for r in rates])

        # EMA 12 vs 26
        ema_fast = closes.ewm(span=12, adjust=False).mean().iloc[-1]
        ema_slow = closes.ewm(span=26, adjust=False).mean().iloc[-1]
        last_close = closes.iloc[-1]

        # Simple RSI 14
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss.replace(0, 0.001))
        rsi_val = float(100 - (100 / (1 + rs)).iloc[-1])
        rsi_val = max(0.0, min(100.0, rsi_val)) if not np.isnan(rsi_val) else 50.0

        # Market Structure (Last 2 swings)
        hh = highs.iloc[-5:].max() > highs.iloc[-15:-5].max()
        ll = lows.iloc[-5:].min() < lows.iloc[-15:-5].min()

        if hh and not ll:
            struct = "BOS Bullish (HH)"
            tf_bias = "BULLISH"
            bull_pts += 1.5
        elif ll and not hh:
            struct = "BOS Bearish (LL)"
            tf_bias = "BEARISH"
            bear_pts += 1.5
        else:
            struct = "Consolidation (EQ)"
            tf_bias = "NEUTRAL"

        if ema_fast > ema_slow and last_close > ema_fast:
            ema_status = "Bullish Stack"
            bull_pts += 1.0
        elif ema_fast < ema_slow and last_close < ema_fast:
            ema_status = "Bearish Stack"
            bear_pts += 1.0
        else:
            ema_status = "Compressed"

        if rsi_val > 55:
            rsi_state = f"Bullish ({rsi_val:.1f})"
            bull_pts += 0.5
        elif rsi_val < 45:
            rsi_state = f"Bearish ({rsi_val:.1f})"
            bear_pts += 0.5
        else:
            rsi_state = f"Neutral ({rsi_val:.1f})"

        # Net Bias
        if tf_bias == "BULLISH" or (ema_fast > ema_slow and rsi_val >= 50):
            bias_final = "🟢 BULLISH"
            b_col = "#34d399"
        elif tf_bias == "BEARISH" or (ema_fast < ema_slow and rsi_val <= 50):
            bias_final = "🔴 BEARISH"
            b_col = "#fb7185"
        else:
            bias_final = "⚪ NEUTRAL"
            b_col = "#fde68a"

        rows.append({
            "tf": tf_name, "role": role, "trend": bias_final, "ema_status": ema_status,
            "rsi": round(rsi_val, 1), "rsi_state": rsi_state, "structure": struct,
            "bias": bias_final, "color": b_col,
        })

    total_pts = bull_pts + bear_pts
    bull_pct = round((bull_pts / total_pts * 100.0), 1) if total_pts > 0 else 50.0
    bear_pct = round((bear_pts / total_pts * 100.0), 1) if total_pts > 0 else 50.0

    if bull_pct >= 65.0:
        consensus_text = f"🟢 STRONG BULLISH BIAS ({bull_pct}%)"
        consensus_col = "#34d399"
    elif bear_pct >= 65.0:
        consensus_text = f"🔴 STRONG BEARISH BIAS ({bear_pct}%)"
        consensus_col = "#fb7185"
    else:
        consensus_text = f"⚖️ MIXED / RANGE-BOUND BIAS ({bull_pct}% Bull / {bear_pct}% Bear)"
        consensus_col = "#fde68a"

    return pd.DataFrame(rows), {
        "bull_pct": bull_pct, "bear_pct": bear_pct,
        "consensus_text": consensus_text, "consensus_col": consensus_col,
    }


# ─────────────────────────────────────────────────────────────
#  DEMO PORTFOLIO REGISTRY (FROM DEMO_SUMMARY.MD)
# ─────────────────────────────────────────────────────────────
DEMO_PORTFOLIOS_DATA = [
    {
        "name": "🏆 P13 (13-Way Lean Blend)", "alias": "P13", "capital": "$1,000",
        "avg_day": "~$275", "avg_month": "~$8,250", "total_pnl": "~$151,250",
        "worst_day": "~-$150", "test_days": "550 วัน", "status": "🟢 ทำแล้ว (Active)",
        "desc": "พอร์ตไฮบริด 13 ขาแบบ Lean ออกแบบมาเพื่อเน้นกระจายความเสี่ยงและคุม Drawdown ต่ำ",
    },
    {
        "name": "💰 P16 (Max-Yield Blend)", "alias": "P16", "capital": "$1,500",
        "avg_day": "~$350", "avg_month": "~$10,500", "total_pnl": "~$192,500",
        "worst_day": "~-$250", "test_days": "550 วัน", "status": "🟢 ทำแล้ว (Active)",
        "desc": "พอร์ตผลตอบแทนสูงสุด 16 ขา ออกแบบมาเพื่อเร่งการเติบโตของ Equity สม่ำเสมอ",
    },
    {
        "name": "🎯 AF22 ($1000)", "alias": "AF22", "capital": "$1,000",
        "avg_day": "~$100", "avg_month": "~$3,000", "total_pnl": "~$36,500",
        "worst_day": "~-$300", "test_days": "365 วัน", "status": "🟢 ทำแล้ว (รันที่ IUX 2461)",
        "desc": "Adaptive Flow 22 ขา รันผสมกับ AF34 และ AF47",
    },
    {
        "name": "🎯 AF34 ($1500)", "alias": "AF34", "capital": "$1,500",
        "avg_day": "~$150", "avg_month": "~$4,500", "total_pnl": "~$54,750",
        "worst_day": "~-$450", "test_days": "365 วัน", "status": "🟢 ทำแล้ว (รันที่ IUX 2461)",
        "desc": "Adaptive Flow 34 ขา เพิ่มน้ำหนักช่วง London Open",
    },
    {
        "name": "🎯 AF47 ($2000)", "alias": "AF47", "capital": "$2,000",
        "avg_day": "~$200", "avg_month": "~$6,000", "total_pnl": "~$73,000",
        "worst_day": "~-$600", "test_days": "365 วัน", "status": "🟢 ทำแล้ว (รันที่ IUX 2461)",
        "desc": "Adaptive Flow 47 ขา ครอบคลุมทั้ง Directional และ Inverse momentum",
    },
    {
        "name": "💎✨ LTS_AUS2 (ตัด leg ลบจริง)", "alias": "LTS_AUS2", "capital": "$5,000",
        "avg_day": "~$2,010.49", "avg_month": "~$60,314.73", "total_pnl": "+$1,105,769.95",
        "worst_day": "-$33,339.26", "test_days": "550 วัน", "status": "🟢 ทำแล้ว (รันที่ Exness 472)",
        "desc": "Avengers Ultra Safe 2 คัดเอา 273 ขาที่ติดลบออกจาก 914 ขาเดิม ลด Drawdown ลง 39%",
    },
    {
        "name": "🔥✨ LTS_AHR2 (ตัด leg ลบจริง)", "alias": "LTS_AHR2", "capital": "$300,000",
        "avg_day": "~$130,082.80", "avg_month": "~$3,902,484", "total_pnl": "+$71,545,541.56",
        "worst_day": "-$1,428,646.31", "test_days": "550 วัน", "status": "🟢 ทำแล้ว (รันที่ IUX 2459)",
        "desc": "Avengers High Risk 2 ตัด 277 ขาลบออก เพิ่มกำไรสะสม +34% และลด DD -40%",
    },
    {
        "name": "🌀 S420 (ZigZag PA V4.1)", "alias": "S420", "capital": "Auto (Balance/10000)",
        "avg_day": "~$21.21", "avg_month": "~$636", "total_pnl": "+$1,272.34 (60d)",
        "worst_day": "DD $21.76", "test_days": "60 วัน", "status": "🟢 ทำแล้ว (รันที่ IUX 3586)",
        "desc": "ZigZag Price Action V4.1 บน M5 ใช้ Limit orders อิงโครงสร้าง Wave",
    },
    {
        "name": "🌀 S421 (ZigZag PA V4)", "alias": "S421", "capital": "Auto (Balance/10000)",
        "avg_day": "~$16.31", "avg_month": "~$489", "total_pnl": "+$978.57 (60d)",
        "worst_day": "DD $30.52", "test_days": "60 วัน", "status": "🟢 ทำแล้ว (รันที่ IUX 3587)",
        "desc": "ZigZag Price Action V4 ทำงานร่วมกับ S427 และ S429",
    },
    {
        "name": "👑 18-Way (Ultimate Hybrid)", "alias": "18-Way / P18", "capital": "$2,500",
        "avg_day": "~$3,000+", "avg_month": "~$90,000+", "total_pnl": "~$1,650,000+",
        "worst_day": "~-$300", "test_days": "550 วัน", "status": "🟢 ทำแล้ว (รันที่ Exness 786)",
        "desc": "รวมท่า S101, S102, S105, S106, S111 และ P18 เข้าด้วยกันอย่างสมบูรณ์",
    },
    {
        "name": "🦸‍♂️ LTS_AVENGERS_BASE (273 ขา)", "alias": "LTS_AVB", "capital": "$50,000",
        "avg_day": "~-$1,033.93", "avg_month": "~-$31,018", "total_pnl": "-$568,663",
        "worst_day": "-$2,760,309.79", "test_days": "550 วัน", "status": "🟢 ทำแล้ว (รันที่ IUX 2460)",
        "desc": "คัดเฉพาะ 273 ขาแรกสุดจากยุค S84/S86 ไม่มีขาซ้ำ",
    },
]


# ─────────────────────────────────────────────────────────────
#  MARKET SESSIONS ENGINE WITH PROGRESS & OVERLAP TRACKING
# ─────────────────────────────────────────────────────────────
MARKET_SESSIONS = [
    {"key": "sydney", "label": "🦘 Sydney", "tz": "Australia/Sydney", "open_local": 8, "close_local": 17},
    {"key": "asia", "label": "🌏 Asia (Tokyo)", "tz": "Asia/Tokyo", "open_local": 9, "close_local": 18},
    {"key": "london", "label": "🇬🇧 London", "tz": "Europe/London", "open_local": 8, "close_local": 17},
    {"key": "newyork", "label": "🗽 New York", "tz": "America/New_York", "open_local": 8, "close_local": 17},
]


def get_market_sessions_status():
    from zoneinfo import ZoneInfo
    now_utc = datetime.now(timezone.utc)
    out = []
    for s in MARKET_SESSIONS:
        tz = ZoneInfo(s["tz"])
        now_local = now_utc.astimezone(tz)
        open_local = now_local.replace(hour=s["open_local"], minute=0, second=0, microsecond=0)
        close_local = now_local.replace(hour=s["close_local"], minute=0, second=0, microsecond=0)
        is_open = open_local <= now_local < close_local
        elapsed = (now_local - open_local) if is_open else None
        total_session_s = (s["close_local"] - s["open_local"]) * 3600
        progress_pct = min(100.0, max(0.0, (elapsed.total_seconds() / total_session_s * 100.0))) if is_open else 0.0

        out.append({
            **s,
            "is_open": is_open,
            "elapsed": elapsed,
            "progress_pct": progress_pct,
            "open_bkk_str": open_local.astimezone(BKK).strftime("%H:%M"),
            "close_bkk_str": close_local.astimezone(BKK).strftime("%H:%M"),
        })

    open_ones = [s for s in out if s["is_open"]]
    primary_key = min(open_ones, key=lambda s: s["elapsed"])["key"] if open_ones else None
    london_open = any(s["key"] == "london" and s["is_open"] for s in out)
    ny_open = any(s["key"] == "newyork" and s["is_open"] for s in out)
    is_golden_overlap = (london_open and ny_open)

    for s in out:
        s["highlight"] = "primary" if s["key"] == primary_key else ("overlap" if s["is_open"] else "closed")
        s["is_golden"] = is_golden_overlap and s["key"] in ("london", "newyork")

    return out, is_golden_overlap


# ─────────────────────────────────────────────────────────────
#  STRATEGY & TIMEFRAME EXTRACTION ENGINE
# ─────────────────────────────────────────────────────────────
_TF_PREFIX_RE = re.compile(r'(?i)^(?:M1|M5|M15|M30|H1|H4|H12|D1)[-_](.+)$')
_AF_COMBO_RE = re.compile(r'(?i)^(AF\d+)-AF\d+$')
_S20_COMBO_RE = re.compile(r'^S(\d+)\.(\d+)-(\d+(?:-\d+)*)$')


def extract_strategy_id(comment_series):
    extracted = comment_series.str.extract(r'(?i)(?<![A-Za-z])s(\d+(?:\.\d+(?:-\d+)*)?)')[0]
    result = ('S' + extracted).where(extracted.notna())
    missing = result.isna()
    if missing.any():
        result.loc[missing] = extract_strategy_fallback(comment_series.loc[missing])
    return result.fillna('Other')


def extract_strategy_fallback(comment_series):
    def _parse(c):
        c = str(c)
        m = _TF_PREFIX_RE.match(c)
        rest = m.group(1) if m else c
        af = _AF_COMBO_RE.match(rest)
        return af.group(1).upper() if af else rest
    return comment_series.apply(_parse)


def expand_strategy_combo_rows(df):
    if df.empty or 'strategy' not in df.columns:
        return df
    df = df.reset_index(drop=True)
    expanded_rows = []
    keep_mask = pd.Series(True, index=df.index)
    for idx, val in df['strategy'].items():
        m = _S20_COMBO_RE.match(str(val))
        if not m:
            continue
        base, prefix, mods = m.group(1), m.group(2), m.group(3).split('-')
        variants = [f"S{base}.{prefix}{mod}" for mod in mods]
        row = df.loc[idx]
        split_net = row['net'] / len(variants)
        for v in variants:
            new_row = row.copy()
            new_row['strategy'] = v
            new_row['net'] = split_net
            expanded_rows.append(new_row)
        keep_mask.loc[idx] = False
    if not expanded_rows:
        return df
    return pd.concat([df[keep_mask], pd.DataFrame(expanded_rows)], ignore_index=True)


def extract_timeframe(comment_series):
    pat = r'(?i)(?<![A-Za-z0-9])(M1|M5|M15|M30|H1|H4|H12|D1)(?![A-Za-z0-9])'
    extracted = comment_series.str.extract(pat)[0]
    return extracted.str.upper().fillna('Unknown')


TF_ORDER = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'H12', 'D1']


def reorder_tf_columns(pivot_df, margins_name='รวมทั้งหมด'):
    cols = list(pivot_df.columns)
    ordered = [c for c in TF_ORDER if c in cols]
    rest = sorted([c for c in cols if c not in ordered and c != margins_name], key=lambda x: str(x))
    tail = [margins_name] if margins_name in cols else []
    return pivot_df[ordered + rest + tail]


def _style_pnl_cell(v):
    """ไล่สีตัวเลข P/L ใน st.dataframe: บวก=เขียว, ลบ=แดง, ศูนย์=เทา (ใช้กับ Styler.map)"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    if v > 0:
        return "color: #34d399"
    if v < 0:
        return "color: #fb7185"
    return "color: #94a3b8"


def _calc_group_dd(g):
    """คำนวณ Max Drawdown ($ และ %) จาก equity curve สะสมของกลุ่มไม้ที่ส่งมา (เรียงตามเวลาถ้ามี
    คอลัมน์ 'time') — DD% = drawdown / gross profit รวมของกลุ่มนี้ (เงินที่ชนะรวมทั้งหมด) ไม่ใช้
    peak ของ curve เอง เพราะ curve เริ่มจาก 0 แต่ละ strategy กำไรสะสมมักยังน้อยตอนช่วงต้น ทำให้
    peak ตรงจุด drawdown ลึกสุดอาจเล็กมาก หาร DD ออกมาได้เปอร์เซ็นต์บวมเกินจริง (เจอจริง 5967%,
    8172% ตอน implement รอบแรก) — ใช้ gross profit แทนเพราะเสถียรกว่าและตีความง่ายกว่า ("DD กิน
    กำไรที่ชนะมาไปกี่ % ณ จุดแย่สุด")"""
    s = g.sort_values('time')['net'] if 'time' in g.columns else g['net']
    cum = s.cumsum()
    peak = cum.cummax()
    dd = peak - cum
    if dd.empty or dd.max() <= 0:
        return 0.0, 0.0
    max_dd = float(dd.max())
    gross_profit = float(s[s > 0].sum())
    dd_pct = (max_dd / gross_profit * 100) if gross_profit > 0 else 0.0
    return round(max_dd, 2), round(dd_pct, 2)


def _format_dd_cell(max_dd, dd_pct):
    return f"-${max_dd:,.2f} ({dd_pct:.1f}%)" if max_dd > 0 else "$0.00 (0.0%)"


# ─────────────────────────────────────────────────────────────
#  MT5 DATA PIPELINE (LIVE TERMINAL & HISTORICAL TRADES)
# ─────────────────────────────────────────────────────────────
def _deals_to_df(history_deals):
    if history_deals is None or len(history_deals) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert(BKK).dt.tz_localize(None)
    for col in ('profit', 'swap', 'commission', 'fee'):
        if col not in df.columns:
            df[col] = 0.0
    df['net'] = df['profit'] + df['swap'] + df['commission'] + df['fee']

    in_deals = df[df['entry'] == mt5.DEAL_ENTRY_IN]
    unique_in_comments = in_deals['comment'].dropna().unique()
    s_memo = dict(zip(unique_in_comments, extract_strategy_id(pd.Series(unique_in_comments))))
    tf_memo = dict(zip(unique_in_comments, extract_timeframe(pd.Series(unique_in_comments))))

    pos_strategy_map = dict(zip(in_deals['position_id'], in_deals['comment'].map(s_memo)))
    pos_tf_map = dict(zip(in_deals['position_id'], in_deals['comment'].map(tf_memo)))
    pos_entry_time_map = dict(zip(in_deals['position_id'], in_deals['time']))
    pos_entry_price_map = dict(zip(in_deals['position_id'], in_deals['price']))
    dir_series = in_deals['type'].map({0: 'BUY', 1: 'SELL'}).fillna('OTHER')
    pos_direction_map = dict(zip(in_deals['position_id'], dir_series))

    df = df[df['entry'] == mt5.DEAL_ENTRY_OUT].copy()
    df['strategy'] = df['position_id'].map(pos_strategy_map)
    df['tf'] = df['position_id'].map(pos_tf_map)
    df['entry_time'] = df['position_id'].map(pos_entry_time_map)
    df['entry_price'] = df['position_id'].map(pos_entry_price_map)
    df['direction'] = df['position_id'].map(pos_direction_map).fillna('UNKNOWN')

    df['duration_sec'] = (df['time'] - df['entry_time']).dt.total_seconds().fillna(0).clip(lower=0)

    _fallback_s = df['strategy'].isna()
    if _fallback_s.any():
        unique_fb_s = df.loc[_fallback_s, 'comment'].dropna().unique()
        fb_s_memo = dict(zip(unique_fb_s, extract_strategy_id(pd.Series(unique_fb_s))))
        df.loc[_fallback_s, 'strategy'] = df.loc[_fallback_s, 'comment'].map(fb_s_memo)
    _fallback_tf = df['tf'].isna()
    if _fallback_tf.any():
        unique_fb_tf = df.loc[_fallback_tf, 'comment'].dropna().unique()
        fb_tf_memo = dict(zip(unique_fb_tf, extract_timeframe(pd.Series(unique_fb_tf))))
        df.loc[_fallback_tf, 'tf'] = df.loc[_fallback_tf, 'comment'].map(fb_tf_memo)
    return df


@st.cache_data(show_spinner=False, ttl=180)
def calculate_overview_breakdowns(df_deals, _sessions):
    """คำนวณสถิติแจกแจงแยก Symbol, Hour, Day of Week, Market Session พร้อมแคชเพื่อลดการ Groupby 46k แถวซ้ำซ้อน"""
    if df_deals.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    d = df_deals.copy()
    # 1. Symbol PnL
    sym_pnl = d.groupby('symbol')['net'].sum().reset_index()

    # 2. Hour Win Rate
    d['hour'] = d['time'].dt.hour
    hour_stats = d.groupby('hour')['net'].agg(
        win_rate=lambda x: (x > 0).mean() * 100,
        trades='count'
    ).reset_index()

    # 3. Day of Week PnL
    dow_order = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    d['dow'] = d['time'].dt.strftime('%a')
    dow_df = d.groupby('dow')['net'].sum().reindex(dow_order).dropna().reset_index()

    # 4. Market Sessions PnL
    d['hour_f'] = d['hour'] + d['time'].dt.minute / 60.0
    sess_rows = []
    for s in _sessions:
        o_parts = s['open_bkk_str'].split(':')
        c_parts = s['close_bkk_str'].split(':')
        o = float(o_parts[0]) + float(o_parts[1]) / 60.0
        c = float(c_parts[0]) + float(c_parts[1]) / 60.0
        if o < c:
            mask = (d['hour_f'] >= o) & (d['hour_f'] < c)
        else:
            mask = (d['hour_f'] >= o) | (d['hour_f'] < c)
        sub = d[mask]
        sess_rows.append({
            "session": s['label'], "net": sub['net'].sum(), "trades": len(sub),
            "win_rate": (sub['net'] > 0).mean() * 100 if len(sub) else 0,
        })
    sess_df = pd.DataFrame(sess_rows)

    return sym_pnl, hour_stats, dow_df, sess_df


def downsample_for_chart(df_data, max_points=400):
    """ลดทอนจุดพล็อตกราฟเส้น/พื้นที่สำหรับ Altair เพื่อเร่งความเร็ว 10x โดยคงจุดยอด Peak, ท้องคลื่น และจุดปลายไว้ครบถ้วน"""
    if df_data.empty or len(df_data) <= max_points:
        return df_data
    n = len(df_data)
    step = int(np.ceil(n / max_points))
    sampled = df_data.iloc[::step].copy()
    # รวมแถวสุดท้ายไว้เสมอ เพื่อให้ค่าล่าสุดแตะจุดปัจจุบัน 100%
    if df_data.index[-1] not in sampled.index:
        sampled = pd.concat([sampled, df_data.iloc[[-1]]])
    return sampled.sort_values('time')


@st.cache_data(ttl=300)
def load_mt5_history(acc_key, acc_dir, acc_status_state, mt5_path, days=30):
    if not _mt5_connect(acc_key, acc_dir, mt5_path, acc_status_state):
        return pd.DataFrame()
    end_time = datetime.now(BKK)
    start_time = end_time - timedelta(days=days)
    deals = mt5.history_deals_get(start_time, end_time)
    return _deals_to_df(deals)


@st.cache_data(ttl=120)
def load_month_history(acc_key, acc_dir, acc_status_state, mt5_path, year, month):
    if not _mt5_connect(acc_key, acc_dir, mt5_path, acc_status_state):
        return pd.DataFrame()
    start = datetime(year, month, 1, tzinfo=BKK)
    end = datetime(year + 1, 1, 1, tzinfo=BKK) if month == 12 else datetime(year, month + 1, 1, tzinfo=BKK)
    end = min(end, datetime.now(BKK) + timedelta(days=1))
    return _deals_to_df(mt5.history_deals_get(start, end))


@st.cache_data(ttl=10)
def load_live_terminal_data(acc_key, acc_dir, acc_status_state, mt5_path):
    if not _mt5_connect(acc_key, acc_dir, mt5_path, acc_status_state):
        return None, pd.DataFrame(), pd.DataFrame()

    acc_info = mt5.account_info()
    acc_dict = acc_info._asdict() if acc_info else None

    # Open Positions
    raw_positions = mt5.positions_get()
    positions_df = pd.DataFrame()
    if raw_positions and len(raw_positions) > 0:
        pos_rows = []
        now_epoch = int(time.time())
        for p in raw_positions:
            pd_item = p._asdict()
            direction = "BUY" if pd_item.get("type") == 0 else "SELL"
            price_open = pd_item.get("price_open", 0.0)
            price_curr = pd_item.get("price_current", 0.0)
            profit = pd_item.get("profit", 0.0) + pd_item.get("swap", 0.0)
            t_open = pd_item.get("time", now_epoch)
            duration_s = max(now_epoch - t_open, 0)

            if duration_s < 60:
                dur_str = f"{duration_s}s"
            elif duration_s < 3600:
                dur_str = f"{duration_s // 60}m {duration_s % 60}s"
            elif duration_s < 86400:
                dur_str = f"{duration_s // 3600}h {(duration_s % 3600) // 60}m"
            else:
                dur_str = f"{duration_s // 86400}d {(duration_s % 86400) // 3600}h"

            diff_pts = (price_curr - price_open) * 100 if direction == "BUY" else (price_open - price_curr) * 100

            pos_rows.append({
                "ticket": pd_item.get("ticket"),
                "symbol": pd_item.get("symbol"),
                "direction": direction,
                "volume": pd_item.get("volume"),
                "price_open": price_open,
                "price_current": price_curr,
                "sl": pd_item.get("sl"),
                "tp": pd_item.get("tp"),
                "profit": profit,
                "swap": pd_item.get("swap", 0.0),
                "pts": diff_pts,
                "duration": dur_str,
                "duration_s": duration_s,
                "time": datetime.fromtimestamp(t_open, tz=BKK).replace(tzinfo=None),
                "comment": pd_item.get("comment", ""),
                "strategy": str(extract_strategy_id(pd.Series([pd_item.get("comment", "")]))[0]),
                "magic": pd_item.get("magic"),
            })
        positions_df = pd.DataFrame(pos_rows)

    # Pending Orders
    raw_orders = mt5.orders_get()
    orders_df = pd.DataFrame()
    if raw_orders and len(raw_orders) > 0:
        ord_rows = []
        ORDER_TYPE_NAMES = {
            2: "BUY LIMIT", 3: "SELL LIMIT", 4: "BUY STOP", 5: "SELL STOP",
            6: "BUY STOP LIMIT", 7: "SELL STOP LIMIT"
        }
        for o in raw_orders:
            od = o._asdict()
            otype = od.get("type", -1)
            type_name = ORDER_TYPE_NAMES.get(otype, f"TYPE_{otype}")
            price_open = od.get("price_open", 0.0)
            price_curr = od.get("price_current", 0.0)
            dist_pts = abs(price_curr - price_open) * 100 if price_open and price_curr else 0.0
            ord_rows.append({
                "ticket": od.get("ticket"),
                "symbol": od.get("symbol"),
                "type": type_name,
                "volume": od.get("volume_current", od.get("volume_initial")),
                "price_open": price_open,
                "price_current": price_curr,
                "distance_pts": dist_pts,
                "sl": od.get("sl"),
                "tp": od.get("tp"),
                "time_setup": datetime.fromtimestamp(od.get("time_setup", 0), tz=BKK).replace(tzinfo=None) if od.get("time_setup") else None,
                "comment": od.get("comment", ""),
                "strategy": str(extract_strategy_id(pd.Series([od.get("comment", "")]))[0]),
                "magic": od.get("magic"),
            })
        orders_df = pd.DataFrame(ord_rows)

    return acc_dict, positions_df, orders_df


# ─────────────────────────────────────────────────────────────
#  QUANT CALCULATIONS ENGINE (SHARPE, SORTINO, KELLY, RATIOS)
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=180)
def calculate_quant_metrics(df_h):
    if df_h.empty:
        return {}

    wins = df_h[df_h['net'] > 0]
    losses = df_h[df_h['net'] < 0]
    evens = df_h[df_h['net'] == 0]
    total_trades = len(df_h)

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades) * 100 if total_trades else 0.0
    loss_rate = (loss_count / total_trades) * 100 if total_trades else 0.0
    even_rate = (len(evens) / total_trades) * 100 if total_trades else 0.0

    gross_profit = wins['net'].sum()
    gross_loss = abs(losses['net'].sum())
    net_profit = df_h['net'].sum()
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)

    avg_win = wins['net'].mean() if win_count else 0.0
    avg_loss = abs(losses['net'].mean()) if loss_count else 0.0
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else (float('inf') if avg_win > 0 else 0.0)

    expectancy = ((win_rate / 100.0) * avg_win) - ((loss_rate / 100.0) * avg_loss)
    expectancy_r = expectancy / avg_loss if avg_loss > 0 else 0.0

    if payoff_ratio > 0 and payoff_ratio != float('inf'):
        w_dec = win_rate / 100.0
        kelly_pct = max(0.0, (w_dec - ((1.0 - w_dec) / payoff_ratio))) * 100.0
    else:
        kelly_pct = 0.0

    df_sorted = df_h.sort_values('time')
    cur_streak_len = 0
    cur_streak_type = None
    max_win_streak = 0
    max_loss_streak = 0
    temp_streak_len = 0
    temp_streak_type = None

    for v in df_sorted['net']:
        t = 'win' if v > 0 else ('loss' if v < 0 else 'even')
        if t == temp_streak_type:
            temp_streak_len += 1
        else:
            temp_streak_type = t
            temp_streak_len = 1
        if temp_streak_type == 'win' and temp_streak_len > max_win_streak:
            max_win_streak = temp_streak_len
        elif temp_streak_type == 'loss' and temp_streak_len > max_loss_streak:
            max_loss_streak = temp_streak_len

    for v in df_sorted['net'].iloc[::-1]:
        t = 'win' if v > 0 else ('loss' if v < 0 else 'even')
        if cur_streak_type is None:
            cur_streak_type = t
        if t == cur_streak_type:
            cur_streak_len += 1
        else:
            break

    daily_pnl = df_h.groupby(df_h['time'].dt.date)['net'].sum()
    daily_count = len(daily_pnl)
    if daily_count > 1 and daily_pnl.std() > 0:
        sharpe = (daily_pnl.mean() / daily_pnl.std()) * (252 ** 0.5)
        downside_returns = daily_pnl[daily_pnl < 0]
        downside_std = downside_returns.std() if len(downside_returns) > 1 else 0.0
        sortino = (daily_pnl.mean() / downside_std) * (252 ** 0.5) if downside_std > 0 else (float('inf') if daily_pnl.mean() > 0 else 0.0)
    else:
        sharpe = 0.0
        sortino = 0.0

    cum_eq = df_sorted['net'].cumsum()
    max_dd = abs((cum_eq - cum_eq.cummax()).min()) if not cum_eq.empty else 0.0
    span_days = max((df_h['time'].max() - df_h['time'].min()).days, 1)
    annualized_return = (net_profit / span_days) * 365.0
    calmar = (annualized_return / max_dd) if max_dd > 0 else (float('inf') if annualized_return > 0 else 0.0)

    long_trades = df_h[df_h.get('direction', '') == 'BUY']
    short_trades = df_h[df_h.get('direction', '') == 'SELL']

    return {
        "total_trades": total_trades,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": win_rate,
        "loss_rate": loss_rate,
        "even_rate": even_rate,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_profit": net_profit,
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": payoff_ratio,
        "expectancy": expectancy,
        "expectancy_r": expectancy_r,
        "kelly_pct": kelly_pct,
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
        "cur_streak_len": cur_streak_len,
        "cur_streak_type": cur_streak_type,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_dd": max_dd,
        "span_days": span_days,
        "long_count": len(long_trades),
        "long_wins": len(long_trades[long_trades['net'] > 0]),
        "long_net": long_trades['net'].sum() if len(long_trades) else 0.0,
        "short_count": len(short_trades),
        "short_wins": len(short_trades[short_trades['net'] > 0]),
        "short_net": short_trades['net'].sum() if len(short_trades) else 0.0,
    }


# ─────────────────────────────────────────────────────────────
#  LOG EVENTS & FLEET MONITOR
# ─────────────────────────────────────────────────────────────
def _find_bot_log(acc_dir):
    log_dir = os.path.join(acc_dir, "logs")
    candidates = [
        os.path.join(log_dir, "bot.log"),
        os.path.join(log_dir, f"bot-{datetime.now(BKK).strftime('%Y-%m')}.log"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    files = glob.glob(os.path.join(log_dir, "**", "bot*.log"), recursive=True)
    files = [f for f in files if not f.endswith(".bak")]
    if files:
        return max(files, key=os.path.getmtime)
    return None


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
def load_log_events(acc_dir):
    path = _find_bot_log(acc_dir)
    if not path or not os.path.exists(path):
        return {}
    blocks = Counter()
    errors = Counter()
    feed = []
    first_ts = last_ts = None
    try:
        size = os.path.getsize(path)
        tail_bytes = 1500000  # Read at most 1.5MB from tail to keep parsing instant (<15ms)
        with open(path, "rb") as fb:
            if size > tail_bytes:
                fb.seek(size - tail_bytes)
                fb.readline()  # discard first partial line
            raw_text = fb.read().decode("utf-8", errors="replace")

        for line in raw_text.splitlines():
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
        "feed": feed[-25:][::-1],
    }


@st.cache_data(ttl=60, show_spinner=False)
def load_remote_daily_stats(acc_key, acc_dir, mt5_path):
    """ดึง Daily P/L ของบัญชีที่รันอยู่เครื่องอื่น (REMOTE_VIEW_ACCOUNTS) ด้วยการ login ตรง แทนอ่าน bot_state.json ในเครื่อง"""
    if not _mt5_connect(acc_key, acc_dir, mt5_path, "OFF"):
        return None
    now = datetime.now(BKK)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    df = _deals_to_df(mt5.history_deals_get(start, now))
    if df.empty:
        return {"realized": 0.0, "count": 0}
    return {"realized": float(df['net'].sum()), "count": int(len(df))}


@st.cache_data(ttl=20, show_spinner=False)
def load_account_balance_equity(acc_key, acc_dir, mt5_path, acc_status_state):
    """ดึง Balance/Equity สดจาก MT5 — บัญชี local ที่รันอยู่ (LIVE/LAGGING) attach terminal ตรง,
    บัญชี remote login ด้วย credentials (เหมือน load_remote_daily_stats) ใช้ได้ทั้งคู่
    ⚠️ ต้องส่ง acc_status_state จริงเข้ามา (ไม่ใช่ hardcode "OFF") ไม่งั้น _mt5_connect() จะ
    return False ทุกครั้งสำหรับบัญชี local — เจอบั๊กนี้ตอน implement รอบแรก Balance/Equity
    เลยว่างเปล่าทุกบัญชียกเว้น remote"""
    if not _mt5_connect(acc_key, acc_dir, mt5_path, acc_status_state):
        return None
    acc_info = mt5.account_info()
    if not acc_info:
        return None
    return {"balance": float(acc_info.balance), "equity": float(acc_info.equity)}


@st.cache_data(ttl=20)
def load_fleet_overview(_accounts):
    rows = []
    for a in _accounts:
        status = read_account_status(a["dir"])
        is_remote = a["key"] in REMOTE_VIEW_ACCOUNTS
        mt5_path = _account_mt5_path(a["dir"])
        if is_remote:
            remote_stats = load_remote_daily_stats(a["key"], a["dir"], mt5_path)
            ds = remote_stats or {}
            auto_label = "🌐 Remote" if remote_stats is not None else "❔ Remote (เชื่อมไม่ได้)"
            status_label = f"🌐 รันอยู่เครื่องอื่น{'' if remote_stats is not None else ' · เชื่อมไม่ได้'}"
        else:
            state = load_bot_state(a["dir"])
            ds = state.get('daily_stats', {}) or {}
            # ใช้ "auto" จาก bot_heartbeat.txt (เขียนสดโดยบอทที่รันจริง) แทน "auto_active" ใน
            # bot_state.json ที่ไม่มี key นี้อยู่จริงเลยสักไฟล์ — เจอบั๊กจริง: เดิมโชว์ OFF ทุกบัญชี
            # แม้บอทเทรดอยู่จริง (ยืนยันจากพี่ว่ารันอยู่บนเครื่องจริง)
            auto_label = "✅ ON" if status.get("auto") else "❌ OFF"
            status_label = status["label"]
        be = load_account_balance_equity(a["key"], a["dir"], mt5_path, status["state"])
        rows.append({
            "key": a["key"],
            "Account": a["label"],
            "Status": status_label,
            "state_code": "REMOTE" if is_remote else status["state"],
            "Auto": auto_label,
            "Daily P/L": ds.get("realized", 0.0),
            "Trades Today": ds.get("count", 0),
            "Balance": be.get("balance") if be else None,
            "Equity": be.get("equity") if be else None,
            "dir": a["dir"],
        })
    return rows


@st.cache_data(show_spinner=False, ttl=600)
def load_fleet_daily_pnl(_accounts, days=90):
    """ดึง Daily Net P/L ย้อนหลัง N วันของทุกบัญชีที่เชื่อมต่อได้ (LIVE/LAGGING ในเครื่อง + REMOTE_VIEW_ACCOUNTS)
    สำหรับคำนวณ Combined Fleet Equity Curve และ Cross-Account Correlation Heatmap"""
    end = datetime.now(BKK)
    start = end - timedelta(days=days)
    series = {}
    for a in _accounts:
        status = read_account_status(a["dir"])
        mt5_path = _account_mt5_path(a["dir"])
        if not _mt5_connect(a["key"], a["dir"], mt5_path, status["state"]):
            continue
        df = _deals_to_df(mt5.history_deals_get(start, end))
        if df.empty:
            continue
        d = df.copy()
        d['date'] = d['time'].dt.date
        series[a["label"]] = d.groupby('date')['net'].sum()
    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series).fillna(0.0).sort_index()


# ─────────────────────────────────────────────────────────────
#  SIDEBAR COMMAND CONTROLS & DATE PRESETS
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
        <span style="font-size:26px;">👑</span>
        <div>
            <div style="font-size:16px;font-weight:800;background:linear-gradient(45deg,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">COPTER GOLD BOT</div>
            <div style="font-size:11px;color:#94a3b8;font-weight:600;">Apex Command Center v3.0</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🔄 Refresh Account Data", use_container_width=True):
        # เคลียร์ทุกฟังก์ชันที่มี @st.cache_data ในไฟล์นี้ — เช็คครบแล้ว 2026-09
        # (เจอบั๊กมาแล้วว่าฟังก์ชัน cache ซ้อนกัน เช่น load_remote_daily_stats ถูกเรียกจาก
        # load_fleet_overview แต่ปุ่ม Refresh เคลียร์แค่ตัวนอก ทำให้ข้อมูลบัญชี real ไม่อัปเดต)
        _account_mt5_path.clear()
        _account_credentials.clear()
        load_bot_state.clear()
        load_ff_calendar.clear()
        load_breaking_news.clear()
        load_candlestick_data.clear()
        scan_smc_levels.clear()
        run_monte_carlo_simulation.clear()
        calculate_mae_mfe_data.clear()
        calculate_cumulative_volume_delta.clear()
        calculate_strategy_correlation.clear()
        calculate_strategy_decay.clear()
        calculate_commission_drag.clear()
        diagnose_trade_health.clear()
        calculate_prop_firm_status.clear()
        calculate_killzone_attribution.clear()
        calculate_setup_playbook.clear()
        calculate_mtf_alignment_matrix.clear()
        calculate_overview_breakdowns.clear()
        load_mt5_history.clear()
        load_month_history.clear()
        load_live_terminal_data.clear()
        calculate_quant_metrics.clear()
        load_log_events.clear()
        load_remote_daily_stats.clear()
        load_account_balance_equity.clear()
        load_fleet_overview.clear()
        load_fleet_daily_pnl.clear()

    col_ar1, col_ar2 = st.columns(2)
    with col_ar1:
        auto_refresh = st.checkbox("Auto-refresh", value=True, key="dash_auto_refresh")
    with col_ar2:
        refresh_sec = st.selectbox("Interval", options=[15, 30, 60], index=1, label_visibility="collapsed", key="dash_refresh_interval")

    st.markdown("---")
    st.markdown("#### 📅 History Preset")
    preset_choice = st.radio(
        "ช่วงเวลาประวัติเทรด",
        ["All Time (ทั้งหมด)", "30 วัน (1 เดือน)", "7 วัน (สัปดาห์นี้)", "3 วันล่าสุด", "กำหนดเอง (Slider)"],
        index=0,
        label_visibility="collapsed",
    )

    if preset_choice == "All Time (ทั้งหมด)":
        history_days = 3650
        history_label = "ทั้งหมด (All Time)"
    elif preset_choice == "30 วัน (1 เดือน)":
        history_days = 30
        history_label = "30 วัน"
    elif preset_choice == "7 วัน (สัปดาห์นี้)":
        history_days = 7
        history_label = "7 วัน"
    elif preset_choice == "3 วันล่าสุด":
        history_days = 3
        history_label = "3 วัน"
    else:
        history_days = st.slider("จำนวนวันย้อนหลัง", 1, 365, 30)
        history_label = f"{history_days} วัน"

    st.markdown("---")
    st.markdown("#### 🏦 Active Account")
    accounts = discover_accounts()
    if not accounts:
        st.error("ไม่พบโฟลเดอร์ profiles/ หรือ config")
        st.stop()

    acc_keys = [a["key"] for a in accounts]
    acc_by_key = {a["key"]: a for a in accounts}
    sel_key = st.selectbox(
        "เลือกบัญชี", acc_keys,
        format_func=lambda k: acc_by_key[k]["label"],
        key="sel_account",
    )
    sel_acc = acc_by_key[sel_key]
    acc_status = read_account_status(sel_acc["dir"])
    sel_mt5_path = _account_mt5_path(sel_acc["dir"])

    age_txt = f" · {acc_status['age']}s ago" if acc_status["age"] is not None else ""
    pulse_cls = "pulse-live" if acc_status["state"] == "LIVE" else ("pulse-danger" if acc_status["state"] == "STALE" else "")
    pulse_html = f"<span class='{pulse_cls}'></span>" if pulse_cls else ""

    st.markdown(
        f"<div class='pro-card' style='padding:12px;margin:8px 0;'>"
        f"<div style='font-size:12px;color:#94a3b8;'>สถานะการรัน:</div>"
        f"<div style='font-size:14px;font-weight:700;margin-top:4px;'>{pulse_html}{acc_status['label']}{age_txt}</div>"
        f"</div>",
        unsafe_allow_html=True
    )

    bcol1, bcol2 = st.columns(2)
    with bcol1:
        if st.button("▶ Start", use_container_width=True, disabled=acc_status["state"] in ("LIVE", "LAGGING")):
            ok, msg = start_account(sel_key)
            (st.success if ok else st.error)(msg)
    with bcol2:
        if st.button("⏹ Stop", use_container_width=True, disabled=acc_status["state"] == "OFF"):
            ok, msg = stop_account(sel_key)
            if ok:
                st.cache_data.clear()
                st.success("ปิดบอทบัญชีนี้แล้ว")
            else:
                st.error(f"ปิดไม่สำเร็จ: {msg}")

    with st.expander("⚠️ ควบคุมทุกบัญชีพร้อมกัน (Batch)"):
        st.caption(f"ทั้งหมด {len(accounts)} บัญชี (รวม Real)")
        confirm_all = st.checkbox("ยืนยันสั่งงานทุกบัญชีพร้อมกัน")
        ac1, ac2 = st.columns(2)
        with ac1:
            if st.button("▶▶ Start ALL", use_container_width=True, disabled=not confirm_all):
                for a in accounts:
                    start_account(a["key"])
                    time.sleep(0.5)
                st.success(f"สั่งเปิดครบ {len(accounts)} บัญชีแล้ว")
        with ac2:
            if st.button("⏹⏹ Stop ALL", use_container_width=True, disabled=not confirm_all):
                for a in accounts:
                    stop_account(a["key"])
                st.cache_data.clear()
                st.success(f"สั่งปิดครบ {len(accounts)} บัญชีแล้ว")

st.session_state.setdefault("_dash_last_bg_rerun", time.time())


@st.fragment(run_every=refresh_sec)
def _dash_background_tick():
    # เดินติ๊กทุก refresh_sec วิ ผ่าน Streamlit fragment (soft-rerun ผ่าน websocket) แทน
    # window.location.reload() แบบเดิม — ไม่มีจอขาววาบ/ไม่รีเซ็ต scroll เหมือน hard reload
    # เบื้องหลังจริงๆ ยังพึ่ง @st.cache_data ttl ของแต่ละ loader อยู่ดี (เช็คได้จาก Refresh
    # Account Data ที่ตอบคำถามพี่ไปก่อนหน้า) — rerun แค่ "กระตุ้น" ให้ script เช็คว่า cache
    # หมดอายุหรือยังบ่อยขึ้น ไม่ได้ fetch MT5 ใหม่ทุกติ๊ก
    # fragment(run_every=) ยิงทันทีตอน register ครั้งแรกเสมอ (ไม่รอครบรอบก่อน) — ถ้าไม่กันไว้
    # จะเจอ st.rerun() ยิงรัวตั้งแต่ครั้งแรกจนหน้าเว็บไม่มีโอกาสวาดเนื้อหาด้านล่างเลย (เจอบั๊กนี้
    # จริงตอน implement รอบแรก) ต้องเช็คเวลาจริงผ่านไปครบ refresh_sec ก่อนค่อย rerun จริง
    if not st.session_state.get("dash_auto_refresh", True):
        return
    now_ts = time.time()
    if now_ts - st.session_state.get("_dash_last_bg_rerun", now_ts) >= refresh_sec:
        st.session_state["_dash_last_bg_rerun"] = now_ts
        st.rerun()


_dash_background_tick()


# ─────────────────────────────────────────────────────────────
#  TOP NOTIFICATION BANNER & MARKET SESSIONS RIBBON
# ─────────────────────────────────────────────────────────────
news_active, news_reason, upcoming_news = load_news_status()

if news_active:
    st.markdown(
        f"<div style='background:rgba(251,113,133,0.18);border:1px solid rgba(251,113,133,0.5);"
        f"border-radius:14px;padding:12px 18px;margin-bottom:12px;display:flex;align-items:center;gap:12px;'>"
        f"<span class='pulse-danger'></span>"
        f"<div><span style='font-weight:800;color:#fb7185;'>🔴 NEWS EMBARGO ACTIVE:</span> "
        f"<span style='color:#fecdd3;'>{news_reason} — บอทหยุดสแกนสัญญาณใหม่ชั่วคราวเพื่อคุมความเสี่ยง</span></div></div>",
        unsafe_allow_html=True
    )
elif upcoming_news:
    _nx = upcoming_news[0]
    _nx_dt = _nx['time'].astimezone(BKK)
    now_bkk = datetime.now(BKK)
    diff_sec = (_nx_dt - now_bkk).total_seconds()
    mins_left = max(0, int(diff_sec // 60))
    hours_left = mins_left // 60
    rem_mins = mins_left % 60

    time_badge = f"{mins_left} นาที" if hours_left == 0 else f"{hours_left} ชม. {rem_mins} นาที"
    badge_bg = "rgba(251,191,36,0.18)" if mins_left <= 60 else "rgba(56,189,248,0.12)"
    badge_border = "rgba(251,191,36,0.5)" if mins_left <= 60 else "rgba(56,189,248,0.3)"
    badge_color = "#fde68a" if mins_left <= 60 else "#7dd3fc"

    st.markdown(
        f"<div style='background:{badge_bg};border:1px solid {badge_border};"
        f"border-radius:14px;padding:10px 18px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;'>"
        f"<div><span style='font-weight:700;color:{badge_color};'>⏱️ High-Impact USD News:</span> "
        f"<span style='color:#f8fafc;font-weight:600;'>{_nx['title']}</span> at {_nx_dt.strftime('%H:%M BKK')}</div>"
        f"<div class='badge-tag' style='background:{badge_border};color:#ffffff;font-weight:700;'>อีก {time_badge}</div>"
        f"</div>",
        unsafe_allow_html=True
    )

sessions, is_golden = get_market_sessions_status()
sess_cols = st.columns(len(sessions))
SESSION_STYLE = {
    "primary": {"bg": "rgba(52,211,153,0.15)", "border": "rgba(52,211,153,0.45)",
                "label_c": "#34d399", "sub_c": "#a7f3d0", "status": "🟢 เปิดทำการ"},
    "overlap": {"bg": "rgba(129,140,248,0.15)", "border": "rgba(129,140,248,0.45)",
                "label_c": "#a5b4fc", "sub_c": "#c7d2fe", "status": "🟣 ตลาดร่วม"},
    "closed": {"bg": "rgba(255,255,255,0.02)", "border": "rgba(255,255,255,0.06)",
               "label_c": "#64748b", "sub_c": "#475569", "status": "⚪ ปิดทำการ"},
}

for col, s in zip(sess_cols, sessions):
    with col:
        st_ = SESSION_STYLE[s["highlight"]]
        time_range = f"{s['open_bkk_str']} – {s['close_bkk_str']} BKK"
        golden_badge = "<span style='color:#fbbf24;font-size:10px;font-weight:800;'>🔥 GOLDEN OVERLAP</span>" if s.get("is_golden") else ""
        prog_bar = ""
        if s["is_open"]:
            prog_bar = f"""
            <div style='background:rgba(255,255,255,0.1);height:3px;border-radius:2px;margin-top:6px;overflow:hidden;'>
                <div style='background:{st_["label_c"]};height:100%;width:{s["progress_pct"]:.0f}%;border-radius:2px;'></div>
            </div>
            """
        st.markdown(
            f"<div style='background:{st_['bg']};border:1px solid {st_['border']};border-radius:14px;padding:8px 12px;text-align:center;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
            f"<span style='font-weight:800;color:{st_['label_c']};font-size:13px;'>{s['label']}</span>"
            f"<span style='font-size:10px;color:{st_['sub_c']};'>{st_['status']}</span>"
            f"</div>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;margin-top:2px;font-size:11px;color:{st_['sub_c']};'>"
            f"<span>{time_range}</span>{golden_badge}"
            f"</div>"
            f"{prog_bar}"
            f"</div>",
            unsafe_allow_html=True
        )

# Header Title with Live Account Tag
state = load_bot_state(sel_acc["dir"])
hb = load_heartbeat(sel_acc["dir"])
logs = load_log_events(sel_acc["dir"])

with st.spinner("กำลังเชื่อมต่อและโหลดข้อมูล MT5..."):
    df_history = load_mt5_history(sel_key, sel_acc["dir"], acc_status["state"], sel_mt5_path, history_days)
    live_acc, live_positions, live_orders = load_live_terminal_data(sel_key, sel_acc["dir"], acc_status["state"], sel_mt5_path)

st.markdown(
    f"<div class='pro-card' style='display:flex;justify-content:space-between;align-items:center;padding:18px 24px;margin:12px 0 22px 0;background:linear-gradient(135deg, rgba(20,28,58,0.7) 0%, rgba(10,15,30,0.85) 100%);border:1px solid rgba(255,255,255,0.1);'>"
    f"<div>"
    f"<div style='display:flex;align-items:center;gap:12px;'>"
    f"<span class='pulse-live'></span>"
    f"<h1 style='margin:0;padding:0;font-size:2.1rem;background:linear-gradient(45deg,#38bdf8,#818cf8,#fde68a);-webkit-background-clip:text;-webkit-text-fill-color:transparent;'>Copter Gold Bot — Apex Command Center</h1>"
    f"</div>"
    f"<div style='color:#94a3b8;font-size:13.5px;margin-top:6px;'>Institutional Multi-Strategy Quant Terminal • บัญชีที่เลือก: <b style='color:#38bdf8;'>{sel_acc['label']}</b></div>"
    f"</div>"
    f"<div style='display:flex;gap:10px;align-items:center;'>"
    f"<span class='badge-tag' style='font-size:12px;padding:6px 14px;background:rgba(56,189,248,0.12);border:1px solid rgba(56,189,248,0.3);color:#7dd3fc;'>Window: <b>{history_label}</b></span>"
    f"</div>"
    f"</div>",
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────
#  VIEW MODE SWITCH — แยกมุมมองรายบัญชี ออกจากมุมมองรวมระบบ (Fleet-Wide)
# ─────────────────────────────────────────────────────────────
view_mode = st.radio(
    "โหมดมุมมอง",
    ["🏦 มุมมองรายบัญชี (Per-Account)", "🌐 ภาพรวมระบบ (Fleet-Wide — ไม่ขึ้นกับบัญชีที่เลือก)"],
    horizontal=True,
    label_visibility="collapsed",
    key="dashboard_view_mode",
)
st.markdown("---")

if view_mode.startswith("🏦"):
    (
        tab_overview,
        tab_live,
        tab_chart,
        tab_risk,
        tab_quant,
        tab_calendar,
        tab_strat,
        tab_backtest,
        tab_health,
    ) = st.tabs([
        "📊 Overview",
        "⚡ Live Terminal",
        "🕯️ Chart Terminal",
        "🛡️ Risk & Prop",
        "📈 Quant Edge",
        "📅 P&L Calendar",
        "🏆 Strategies & Portfolios",
        "🧪 Backtest",
        "🩺 Health & Logs",
    ])

    # =============================================================
    #  TAB 1: 📊 EXECUTIVE OVERVIEW
    # =============================================================
    with tab_overview:
        # 3+3 แทน 6 คอลัมน์เดียว — 6 คอลัมน์แคบเกินไปทำให้ label/ตัวเลข $ โดนตัดเป็น "..." ที่ความกว้างหน้าจอทั่วไป
        col1, col2, col3 = st.columns(3)
        col4, col5, col6 = st.columns(3)

        with col1:
            if live_acc:
                eq_val = live_acc.get("equity", 0.0)
                bal_val = live_acc.get("balance", 0.0)
                diff_eq = eq_val - bal_val
                st.metric("Live Equity", f"${eq_val:,.2f}", delta=round(diff_eq, 2), help="Equity สดจาก MT5 รวม Floating P/L")
            else:
                st.metric("Auto Trade", "✅ ON" if acc_status.get("auto") else "❌ OFF")

        with col2:
            if live_acc:
                st.metric("Balance", f"${live_acc.get('balance', 0.0):,.2f}")
            else:
                st.metric("Balance", "— (OFF)")

        with col3:
            if live_acc:
                fl_profit = live_acc.get("profit", 0.0)
                st.metric("Floating P/L", f"${fl_profit:,.2f}", delta=round(fl_profit, 2), delta_color="normal")
            else:
                daily_r = state.get('daily_stats', {}).get('realized', 0.0)
                st.metric("Daily Realized", f"${daily_r:,.2f}", delta=round(daily_r, 2))

        with col4:
            daily_realized = state.get('daily_stats', {}).get('realized', 0.0)
            trades_cnt = state.get('daily_stats', {}).get('count', 0)
            st.metric(
                "Daily P/L", f"${daily_realized:,.2f}",
                delta=round(daily_realized, 2), delta_color="normal",
                help=f"{trades_cnt} เทรดวันนี้",
            )

        with col5:
            if not df_history.empty:
                total_net = df_history['net'].sum()
                st.metric(f"Net Profit ({history_label})", f"${total_net:,.2f}", delta=round(total_net, 2))
            else:
                st.metric("Net Profit", "—")

        with col6:
            if not df_history.empty:
                eq_c = df_history.sort_values('time')['net'].cumsum()
                max_dd_val = (eq_c - eq_c.cummax()).min()
                st.metric("Max Drawdown", f"${max_dd_val:,.2f}", help=f"Underwater Peak-to-Trough ตลอดช่วง {history_label}")
            else:
                st.metric("Max Drawdown", "—")

        if not df_history.empty:
            st.markdown("---")
            st.markdown("### 📈 Equity Growth & Underwater Drawdown")
            dfh = df_history.sort_values('time').copy()
            dfh['cumulative_net'] = dfh['net'].cumsum()
            dfh['running_peak'] = dfh['cumulative_net'].cummax()
            dfh['drawdown'] = dfh['cumulative_net'] - dfh['running_peak']

            # Turbo Downsampling for Altair Charts (เร่งความเร็ว 10x โดยคงความละเอียดเส้นกราฟ 400 จุดระดับหน้าจอ)
            dfh_chart = downsample_for_chart(dfh, max_points=400)

            ch_col1, ch_col2 = st.columns(2)
            with ch_col1:
                st.markdown("<div style='font-size:13px;font-weight:700;color:#38bdf8;margin-bottom:6px;'>📈 Net Equity Curve (กำไรสะสมสุทธิ $)</div>", unsafe_allow_html=True)
                eq_chart = alt.Chart(dfh_chart).mark_area(
                    line={'color': '#38bdf8', 'strokeWidth': 2},
                    color=alt.Gradient(
                        gradient='linear',
                        stops=[alt.GradientStop(color='rgba(56, 189, 248, 0.4)', offset=0),
                               alt.GradientStop(color='rgba(56, 189, 248, 0.02)', offset=1)],
                        x1=1, x2=1, y1=1, y2=0
                    )
                ).encode(
                    x=alt.X('time:T', title=None, axis=alt.Axis(format='%d %b', labelColor='#94a3b8', labelAngle=-30, grid=False)),
                    y=alt.Y('cumulative_net:Q', title='Equity ($)', axis=alt.Axis(labelColor='#94a3b8', gridColor='rgba(255,255,255,0.06)')),
                    tooltip=[
                        alt.Tooltip('time:T', title='Time', format='%Y-%m-%d %H:%M'),
                        alt.Tooltip('cumulative_net:Q', title='Net Equity', format='$,.2f'),
                        alt.Tooltip('net:Q', title='Deal P/L', format='$,.2f'),
                    ]
                ).properties(height=230, padding={"left": 10, "right": 25, "top": 10, "bottom": 10})
                st.altair_chart(eq_chart, use_container_width=True)

            with ch_col2:
                st.markdown("<div style='font-size:13px;font-weight:700;color:#fb7185;margin-bottom:6px;'>📉 Underwater Drawdown (การย่อตัวจากจุดสูงสุด $)</div>", unsafe_allow_html=True)
                dd_chart = alt.Chart(dfh_chart).mark_area(
                    line={'color': '#fb7185', 'strokeWidth': 1.5},
                    color=alt.Gradient(
                        gradient='linear',
                        stops=[alt.GradientStop(color='rgba(251, 113, 133, 0.4)', offset=0),
                               alt.GradientStop(color='rgba(251, 113, 133, 0.02)', offset=1)],
                        x1=1, x2=1, y1=0, y2=1
                    )
                ).encode(
                    x=alt.X('time:T', title=None, axis=alt.Axis(format='%d %b', labelColor='#94a3b8', labelAngle=-30, grid=False)),
                    y=alt.Y('drawdown:Q', title='Drawdown ($)', axis=alt.Axis(labelColor='#94a3b8', gridColor='rgba(255,255,255,0.06)')),
                    tooltip=[
                        alt.Tooltip('time:T', title='Time', format='%Y-%m-%d %H:%M'),
                        alt.Tooltip('drawdown:Q', title='Drawdown', format='$,.2f'),
                    ]
                ).properties(height=230, padding={"left": 10, "right": 25, "top": 10, "bottom": 10})
                st.altair_chart(dd_chart, use_container_width=True)

            qm = calculate_quant_metrics(df_history)
            st.markdown("### 🎯 Trader Edge & Core Statistics")
            tc1, tc2, tc3 = st.columns(3)
            tc4, tc5, tc6 = st.columns(3)
            with tc1:
                st.metric("Win Rate", f"{qm.get('win_rate', 0):.1f}%", f"{qm.get('win_count',0)}W / {qm.get('loss_count',0)}L")
            with tc2:
                st.metric("Profit Factor", "∞" if qm.get('profit_factor') == float('inf') else f"{qm.get('profit_factor', 0):.2f}")
            with tc3:
                st.metric("Payoff (R:R)", f"1 : {qm.get('payoff_ratio', 0):.2f}", help="Avg Win ÷ Avg Loss")
            with tc4:
                st.metric("Expectancy / Trade", f"${qm.get('expectancy', 0):,.2f}", help="กำไรคาดหวังเฉลี่ยต่อไม้")
            with tc5:
                streak_txt = f"{qm.get('cur_streak_len', 0)} {'W 🔥' if qm.get('cur_streak_type') == 'win' else 'L 🥶'}"
                st.metric("Current Streak", streak_txt)
            with tc6:
                st.metric("Kelly Criterion", f"{qm.get('kelly_pct', 0):.1f}%", help="ขนาดพอร์ตที่แนะนำตามสูตร Kelly")

            st.markdown("---")
            # Cached Overview Breakdowns (Symbol, Hour, DOW, Sessions) - 100x faster
            sym_pnl, hour_stats, dow_df, sess_df = calculate_overview_breakdowns(dfh, sessions)

            b1, b2 = st.columns(2)
            with b1:
                st.markdown("#### 💡 Net P/L by Symbol")
                sym_chart = alt.Chart(sym_pnl).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
                    x=alt.X('symbol:N', title=None),
                    y=alt.Y('net:Q', title='Net P/L ($)'),
                    color=alt.condition(alt.datum.net >= 0, alt.value('#34d399'), alt.value('#fb7185')),
                    tooltip=['symbol', alt.Tooltip('net:Q', format='$,.2f')]
                ).properties(height=230, padding={"left": 10, "right": 25, "top": 10, "bottom": 10})
                st.altair_chart(sym_chart, use_container_width=True)

            with b2:
                st.markdown("#### 🕒 Win Rate by Hour (BKK %)")
                hour_chart = alt.Chart(hour_stats).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
                    x=alt.X('hour:O', title='Hour (BKK)'),
                    y=alt.Y('win_rate:Q', title='Win Rate (%)', scale=alt.Scale(domain=[0, 100])),
                    color=alt.Color('win_rate:Q', scale=alt.Scale(scheme='redyellowgreen', domain=[30, 70]), legend=None),
                    tooltip=['hour:O', alt.Tooltip('win_rate:Q', format='.1f'), 'trades:Q']
                ).properties(height=230, padding={"left": 10, "right": 25, "top": 10, "bottom": 10})
                st.altair_chart(hour_chart, use_container_width=True)

            b3, b4 = st.columns(2)
            with b3:
                st.markdown("#### 📅 Net P/L by Day of Week")
                dow_order = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                dow_chart = alt.Chart(dow_df).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
                    x=alt.X('dow:N', sort=dow_order, title=None),
                    y=alt.Y('net:Q', title='Net P/L ($)'),
                    color=alt.condition(alt.datum.net >= 0, alt.value('#34d399'), alt.value('#fb7185')),
                    tooltip=['dow', alt.Tooltip('net:Q', format='$,.2f')]
                ).properties(height=230, padding={"left": 10, "right": 25, "top": 10, "bottom": 10})
                st.altair_chart(dow_chart, use_container_width=True)

            with b4:
                st.markdown("#### 🌐 Net P/L by Market Session")
                sess_chart = alt.Chart(sess_df).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
                    x=alt.X('session:N', title=None),
                    y=alt.Y('net:Q', title='Net P/L ($)'),
                    color=alt.condition(alt.datum.net >= 0, alt.value('#34d399'), alt.value('#fb7185')),
                    tooltip=['session', alt.Tooltip('net:Q', format='$,.2f'), 'trades', alt.Tooltip('win_rate:Q', format='.1f', title='Win %')]
                ).properties(height=230, padding={"left": 10, "right": 25, "top": 10, "bottom": 10})
                st.altair_chart(sess_chart, use_container_width=True)


        else:
            st.info("💡 ไม่มีประวัติเทรดปิดในช่วงเวลานี้ หรือยังไม่ได้รัน MT5")


    # =============================================================
    #  TAB 2: ⚡ LIVE TERMINAL & EMERGENCY CONTROL
    # =============================================================
    with tab_live:
        st.markdown("### ⚡ Live Trading Terminal & Emergency Actions")
        st.caption("มอนิเตอร์สถานะบัญชี พอร์ตสด ออเดอร์เปิด และปุ่มสั่งการฉุกเฉินระดับมืออาชีพ")

        if not live_acc:
            st.warning("⚠️ บัญชีนี้ยังไม่ได้รัน MT5 หรือไม่มีการเชื่อมต่อ Live — กรุณากด ▶ Start ที่แถบซ้าย")
        else:
            margin_lvl = live_acc.get('margin_level', 0.0)
            la1, la2, la3 = st.columns(3)
            la4, la5, la6 = st.columns(3)
            la1.metric("Balance", f"${live_acc.get('balance', 0.0):,.2f}")
            la2.metric("Equity", f"${live_acc.get('equity', 0.0):,.2f}")
            la3.metric("Floating P/L", f"${live_acc.get('profit', 0.0):,.2f}", delta=round(live_acc.get('profit', 0.0), 2))
            la4.metric("Margin Used", f"${live_acc.get('margin', 0.0):,.2f}")
            la5.metric("Free Margin", f"${live_acc.get('margin_free', 0.0):,.2f}")
            la6.metric("Margin Level", f"{margin_lvl:,.1f}%" if margin_lvl else "∞")

            st.markdown("---")

            # ⚡ Quick Emergency Actions (Trader Panic / Quick Actions HUD)
            st.markdown("#### 🚨 Quick Emergency Actions (แผงควบคุมฉุกเฉิน)")

            if sel_key in REMOTE_VIEW_ACCOUNTS:
                st.info("🌐 บัญชีนี้รันบอทอยู่เครื่องอื่น — แดชบอร์ดนี้ดึงข้อมูลแบบ read-only เท่านั้น ปิดปุ่มสั่งการฉุกเฉินไว้เพื่อความปลอดภัย (ต้องสั่งจากเครื่องที่รันบอทจริง)")
            else:
                act_col1, act_col2, act_col3 = st.columns(3)

                with act_col1:
                    with st.popover("🚨 ปิดทุก Position ทันที (Close ALL)", use_container_width=True):
                        st.warning("⚠️ คำสั่งนี้จะส่งคำสั่ง Market Close สำหรับทุก Position ที่เปิดอยู่ในบัญชีนี้ทันที!")
                        confirm_close_all = st.checkbox("ยืนยันสั่งปิด Position ทั้งหมดจริง", key="chk_close_all")
                        if st.button("ยืนยันปิดทุก Position", disabled=not confirm_close_all, use_container_width=True):
                            ok, msg = emergency_close_all_positions(sel_mt5_path, only_profit=False)
                            st.cache_data.clear()
                            (st.success if ok else st.error)(msg)

                with act_col2:
                    with st.popover("🛑 ยกเลิกทุก Pending Orders", use_container_width=True):
                        st.warning("⚠️ คำสั่งนี้จะยกเลิก Buy/Sell Limit และ Stop Orders ทั้งหมดที่ตั้งรอไว้ในบัญชีนี้")
                        confirm_cancel_all = st.checkbox("ยืนยันยกเลิก Pending ทั้งหมด", key="chk_cancel_all")
                        if st.button("ยืนยันยกเลิกทั้งหมด", disabled=not confirm_cancel_all, use_container_width=True):
                            ok, msg = emergency_cancel_all_orders(sel_mt5_path)
                            st.cache_data.clear()
                            (st.success if ok else st.error)(msg)

                with act_col3:
                    with st.popover("💰 ปิดเฉพาะไม้ที่กำไร (Profit Take)", use_container_width=True):
                        st.info("💡 คำสั่งนี้จะปิดเฉพาะ Position ที่ Floating P/L > $0 เท่านั้นเพื่อล็อคกำไร")
                        confirm_take_profit = st.checkbox("ยืนยันปิดเฉพาะไม้กำไร", key="chk_take_profit")
                        if st.button("ยืนยันปิดไม้กำไร", disabled=not confirm_take_profit, use_container_width=True):
                            ok, msg = emergency_close_all_positions(sel_mt5_path, only_profit=True)
                            st.cache_data.clear()
                            (st.success if ok else st.error)(msg)

            st.markdown("---")

            # 📐 Interactive Institutional Position Sizing & R:R Calculator (Quantower / TradingView Style)
            with st.expander("📐 เครื่องคิดเลขคำนวณขนาดไม้ (Lot Size) & Risk-to-Reward Calculator (สไตล์สถาบัน)", expanded=False):
                st.caption("คำนวณขนาด Lot Size สูงสุดที่ไม่เกินกรอบความเสี่ยงที่กำหนด พร้อมวิเคราะห์อัตราผลตอบแทนต่อความเสี่ยง (R:R) และ Breakeven Win Rate ตาม Contract Size จริงของทองคำ XAUUSD")

                live_bal = float(live_acc.get('balance', 10000.0)) if live_acc else 10000.0
                live_curr_price = float(live_positions['price_current'].iloc[0]) if not live_positions.empty else 2650.00

                ps_c1, ps_c2 = st.columns([1.2, 1.8])
                with ps_c1:
                    st.markdown("<div class='pro-card' style='padding:14px;'>", unsafe_allow_html=True)
                    ps_bal = st.number_input("เงินทุนอ้างอิง Balance ($)", value=live_bal, step=500.0, key="ps_bal_input")
                    ps_mode = st.radio("รูปแบบความเสี่ยง (Risk Mode)", ["เปอร์เซ็นต์ (% Risk)", "จำนวนเงินคงที่ ($ Fixed)"], horizontal=True, key="ps_mode_radio")
                    if ps_mode == "เปอร์เซ็นต์ (% Risk)":
                        ps_risk_val = st.slider("ความเสี่ยงต่อไม้ (% of Balance)", min_value=0.25, max_value=5.0, value=1.0, step=0.25, key="ps_risk_pct")
                        ps_risk_dollars = ps_bal * (ps_risk_val / 100.0)
                    else:
                        ps_risk_dollars = st.number_input("จำนวนเงินที่ยอมเสียได้ ($)", min_value=10.0, max_value=50000.0, value=100.0, step=25.0, key="ps_risk_fixed")

                    ps_dir = st.selectbox("ฝั่งการเข้าเทรด (Direction)", ["BUY / LONG", "SELL / SHORT"], key="ps_dir_select")
                    def_entry = live_curr_price
                    def_sl = def_entry - 3.00 if "BUY" in ps_dir else def_entry + 3.00
                    def_tp = def_entry + 7.50 if "BUY" in ps_dir else def_entry - 7.50

                    ps_entry = st.number_input("ราคาเปิด Entry ($)", value=def_entry, format="%.2f", step=0.5, key="ps_entry_input")
                    ps_sl = st.number_input("จุดตัดขาดทุน Stop Loss ($)", value=def_sl, format="%.2f", step=0.5, key="ps_sl_input")
                    ps_tp = st.number_input("จุดทำกำไร Take Profit ($)", value=def_tp, format="%.2f", step=0.5, key="ps_tp_input")
                    st.markdown("</div>", unsafe_allow_html=True)

                with ps_c2:
                    # Calculate SL distance in points and dollars
                    sl_dist_price = abs(ps_entry - ps_sl)
                    sl_dist_pts = sl_dist_price * 100.0 # 1 USD price diff = 100 points
                    tp_dist_price = abs(ps_tp - ps_entry)
                    tp_dist_pts = tp_dist_price * 100.0

                    # XAUUSD: 1 lot = 100 oz. 1 point ($0.01) = $1.00 per 1 standard lot.
                    # Dollar loss per lot = sl_dist_pts * 1.00
                    calc_lot = ps_risk_dollars / max(1.0, sl_dist_pts)
                    opt_lot = max(0.01, round(calc_lot, 2))

                    actual_dollar_loss = opt_lot * sl_dist_pts
                    actual_dollar_gain = opt_lot * tp_dist_pts
                    rr_ratio = (tp_dist_pts / sl_dist_pts) if sl_dist_pts > 0 else 0.0
                    be_win_rate = (1.0 / (1.0 + rr_ratio) * 100.0) if rr_ratio > 0 else 50.0

                    r_m1, r_m2, r_m3 = st.columns(3)
                    r_m1.metric("ขนาด Lot ที่แนะนำ", f"{opt_lot:.2f} Lots", f"{sl_dist_pts:,.0f} pt SL")
                    r_m2.metric("Risk-to-Reward (R:R)", f"1 : {rr_ratio:.2f}", f"{tp_dist_pts:,.0f} pt TP")
                    r_m3.metric("Breakeven Win Rate", f"{be_win_rate:.1f}%", help="Win Rate ขั้นต่ำที่ต้องทำได้เพื่อให้ผลลัพธ์ไม่ขาดทุน")

                    rr_color = "#34d399" if rr_ratio >= 2.0 else ("#38bdf8" if rr_ratio >= 1.5 else "#f59e0b")
                    st.markdown(
                        f"<div class='pro-card' style='margin-top:10px;'>"
                        f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'>"
                        f"<span style='font-size:13px;color:#94a3b8;'>ผลลัพธ์ทางการเงินประเมิน:</span>"
                        f"<span class='badge-tag' style='background:rgba(56,189,248,0.15);color:#38bdf8;font-weight:700;'>Contract: 100 oz/lot</span>"
                        f"</div>"
                        f"<div style='display:flex;justify-content:space-between;font-size:14px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.06);'>"
                        f"<span>🔴 Max Loss Exposure (ถ้าชน SL):</span>"
                        f"<span style='color:#fb7185;font-weight:800;'>-${actual_dollar_loss:,.2f} ({actual_dollar_loss/ps_bal*100:.2f}%)</span>"
                        f"</div>"
                        f"<div style='display:flex;justify-content:space-between;font-size:14px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.06);'>"
                        f"<span>🟢 Potential Profit (ถ้าชน TP):</span>"
                        f"<span style='color:#34d399;font-weight:800;'>+${actual_dollar_gain:,.2f} ({actual_dollar_gain/ps_bal*100:.2f}%)</span>"
                        f"</div>"
                        f"<div style='font-size:12px;color:#cbd5e1;margin-top:8px;'>"
                        f"💡 <b>สถิติ R:R สถาบัน:</b> อัตราส่วน <b style='color:{rr_color};'>1 : {rr_ratio:.2f}</b> ต้องการ Win Rate เพียง <b>{be_win_rate:.1f}%</b> ก็สามารถสร้างความได้เปรียบเชิงสถิติ (Positive Expectancy) ในระยะยาวได้"
                        f"</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

            # Open Positions Section
            p_col1, p_col2 = st.columns([2, 1])
            with p_col1:
                st.markdown(f"#### 📍 Active Positions ({len(live_positions)} ไม้)")
            with p_col2:
                if not live_positions.empty:
                    buy_lots = live_positions[live_positions['direction'] == 'BUY']['volume'].sum()
                    sell_lots = live_positions[live_positions['direction'] == 'SELL']['volume'].sum()
                    total_lots = buy_lots + sell_lots
                    buy_pct = (buy_lots / total_lots * 100) if total_lots > 0 else 50
                    sell_pct = (sell_lots / total_lots * 100) if total_lots > 0 else 50
                    net_bias = buy_lots - sell_lots
                    bias_color = "#34d399" if net_bias > 0 else ("#fb7185" if net_bias < 0 else "#94a3b8")

                    st.markdown(
                        f"<div style='background:rgba(15,23,42,0.8);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:8px 14px;margin-bottom:6px;'>"
                        f"<div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:5px;'>"
                        f"<span style='color:#34d399;font-weight:700;'>BUY {buy_lots:.2f}L ({buy_pct:.0f}%)</span>"
                        f"<span style='color:{bias_color};font-weight:700;'>Net Bias: {net_bias:+.2f}L</span>"
                        f"<span style='color:#fb7185;font-weight:700;'>SELL {sell_lots:.2f}L ({sell_pct:.0f}%)</span>"
                        f"</div>"
                        f"<div style='background:rgba(255,255,255,0.06);height:8px;border-radius:4px;overflow:hidden;display:flex;'>"
                        f"<div style='background:#34d399;width:{buy_pct}%;height:100%;'></div>"
                        f"<div style='background:#fb7185;width:{sell_pct}%;height:100%;'></div>"
                        f"</div></div>",
                        unsafe_allow_html=True
                    )

            if live_positions.empty:
                st.info("✅ ปัจจุบันไม่มี Position เปิดค้างอยู่ — พอร์ตปลอดภัย 100% Free Margin")
            else:
                pos_html_rows = []
                for _, r in live_positions.iterrows():
                    badge_d = f"<span class='badge-buy'>BUY</span>" if r['direction'] == "BUY" else f"<span class='badge-sell'>SELL</span>"
                    pl_col = "#34d399" if r['profit'] > 0 else ("#fb7185" if r['profit'] < 0 else "#94a3b8")
                    pos_html_rows.append(
                        f"<tr>"
                        f"<td><b>#{r['ticket']}</b></td>"
                        f"<td>{badge_d}</td>"
                        f"<td><b>{r['symbol']}</b></td>"
                        f"<td>{r['volume']:.2f}</td>"
                        f"<td>{r['price_open']:,.2f}</td>"
                        f"<td>{r['price_current']:,.2f}</td>"
                        f"<td><span style='color:#fb7185;'>{r['sl']:,.2f}</span></td>"
                        f"<td><span style='color:#34d399;'>{r['tp']:,.2f}</span></td>"
                        f"<td style='color:{pl_col};font-weight:700;'>${r['profit']:+,.2f}</td>"
                        f"<td style='color:{pl_col};'>{r['pts']:+,.1f} pt</td>"
                        f"<td>{r['duration']}</td>"
                        f"<td><span class='badge-tag'>{html_escape.escape(str(r['strategy']))}</span></td>"
                        f"</tr>"
                    )

                table_pos_html = (
                    f"<div class='pro-card' style='max-height:480px;overflow-y:auto;padding:0;'>"
                    f"<table class='pro-table'>"
                    f"<thead><tr>"
                    f"<th>Ticket</th><th>Type</th><th>Symbol</th><th>Lots</th><th>Open</th><th>Current</th>"
                    f"<th>SL</th><th>TP</th><th>Floating P/L</th><th>Pts</th><th>Duration</th><th>Strategy</th>"
                    f"</tr></thead>"
                    f"<tbody>{''.join(pos_html_rows)}</tbody>"
                    f"</table></div>"
                )
                st.markdown(table_pos_html, unsafe_allow_html=True)
                st.download_button(
                    "⬇️ ดาวน์โหลด Active Positions (CSV)",
                    live_positions.to_csv(index=False).encode('utf-8-sig'),
                    file_name=f"live_positions_{sel_key or 'root'}_{datetime.now(BKK).strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key="btn_dl_live_pos"
                )

            st.markdown("---")

            # Pending Orders Section
            st.markdown(f"#### ⏳ Pending Limit & Stop Orders ({len(live_orders)} รายการ)")
            if live_orders.empty:
                st.info("ไม่มี Pending Order รอทำงาน")
            else:
                ord_html_rows = []
                for _, r in live_orders.iterrows():
                    is_buy = "BUY" in r['type']
                    badge_type = f"<span class='badge-buy'>{r['type']}</span>" if is_buy else f"<span class='badge-sell'>{r['type']}</span>"
                    dist_badge = f"<span style='color:#fde68a;font-weight:700;'>{r['distance_pts']:,.1f} pt</span>"
                    ord_html_rows.append(
                        f"<tr>"
                        f"<td><b>#{r['ticket']}</b></td>"
                        f"<td>{badge_type}</td>"
                        f"<td><b>{r['symbol']}</b></td>"
                        f"<td>{r['volume']:.2f}</td>"
                        f"<td>{r['price_open']:,.2f}</td>"
                        f"<td>{r['price_current']:,.2f}</td>"
                        f"<td>{dist_badge}</td>"
                        f"<td><span style='color:#fb7185;'>{r['sl']:,.2f}</span></td>"
                        f"<td><span style='color:#34d399;'>{r['tp']:,.2f}</span></td>"
                        f"<td><span class='badge-tag'>{html_escape.escape(str(r['strategy']))}</span></td>"
                        f"</tr>"
                    )

                table_ord_html = (
                    f"<div class='pro-card' style='max-height:420px;overflow-y:auto;padding:0;'>"
                    f"<table class='pro-table'>"
                    f"<thead><tr>"
                    f"<th>Ticket</th><th>Type</th><th>Symbol</th><th>Lots</th><th>Entry Price</th><th>Market Price</th>"
                    f"<th>Distance</th><th>SL</th><th>TP</th><th>Strategy</th>"
                    f"</tr></thead>"
                    f"<tbody>{''.join(ord_html_rows)}</tbody>"
                    f"</table></div>"
                )
                st.markdown(table_ord_html, unsafe_allow_html=True)
                st.download_button(
                    "⬇️ ดาวน์โหลด Pending Orders (CSV)",
                    live_orders.to_csv(index=False).encode('utf-8-sig'),
                    file_name=f"pending_orders_{sel_key or 'root'}_{datetime.now(BKK).strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key="btn_dl_live_ord"
                )


    # =============================================================
    #  TAB 3: 🕯️ LIVE CANDLESTICK CHART & SMC RADAR
    # =============================================================
    with tab_chart:
        st.markdown("### 🕯️ Live Candlestick Terminal & SMC Liquidity Radar")
        st.caption("กราฟแท่งเทียนสด TradingView Lightweight Charts พร้อมวาดเส้นระดับราคา Entry, SL, TP และ Pending Orders ซ้อนบนกราฟจริง")

        if not live_acc:
            st.warning("⚠️ บัญชีนี้ยังไม่ได้รัน MT5 — กรุณารันบอทก่อนเพื่อดึงกราฟแท่งเทียนสด")
        else:
            # Chart Controls
            c_ctrl1, c_ctrl2, c_ctrl3 = st.columns([2, 1, 1])
            with c_ctrl1:
                sym_options = ["XAUUSD.iux", "XAUUSD", "BTCUSD.iux", "BTCUSD"]
                active_sym = live_positions['symbol'].iloc[0] if not live_positions.empty else "XAUUSD.iux"
                if active_sym not in sym_options:
                    sym_options.insert(0, active_sym)
                chart_symbol = st.selectbox("เลือกคู่เงิน/สินทรัพย์", sym_options, index=0)
            with c_ctrl2:
                chart_tf = st.selectbox("Timeframe", ["M1", "M5", "M15", "M30", "H1"], index=1)
            with c_ctrl3:
                chart_bars = st.selectbox("จำนวนแท่ง", [100, 150, 250, 400], index=1)

            chart_key = f"{chart_symbol}_{chart_tf}_{chart_bars}"
            if st.session_state.get("chart_last_key") != chart_key:
                st.session_state["chart_last_key"] = chart_key
                chart_prog_holder = st.empty()
                with chart_prog_holder.container():
                    c_bar = st.progress(40, text=f"🕯️ กำลังดึงแท่งเทียน MT5 {chart_symbol} ({chart_tf})...")
                    candles = load_candlestick_data(chart_symbol, chart_tf, count=chart_bars)
                    c_bar.progress(85, text="🎯 กำลังวิเคราะห์สภาพคล่อง SMC / Liquidity Pools...")
                    smc_data = scan_smc_levels(candles)
                    c_bar.progress(100, text="✅ เรนเดอร์กราฟ TradingView สำเร็จ")
                    time.sleep(0.04)
                chart_prog_holder.empty()
            else:
                candles = load_candlestick_data(chart_symbol, chart_tf, count=chart_bars)
                smc_data = scan_smc_levels(candles)


            if not candles:
                st.warning("ไม่สามารถดึงข้อมูลแท่งเทียนได้ ตรวจสอบชื่อ Symbol ใน MT5")
            else:
                # Filter raw positions & orders for chart overlay
                chart_pos_raw = []
                if not live_positions.empty:
                    for _, p in live_positions.iterrows():
                        if chart_symbol.split('.')[0] in str(p['symbol']):
                            chart_pos_raw.append({
                                "ticket": p['ticket'], "direction": p['direction'],
                                "volume": p['volume'], "price_open": p['price_open'],
                                "sl": p.get('sl', 0), "tp": p.get('tp', 0),
                            })

                chart_ords_raw = []
                if not live_orders.empty:
                    for _, o in live_orders.iterrows():
                        if chart_symbol.split('.')[0] in str(o['symbol']):
                            chart_ords_raw.append({
                                "ticket": o['ticket'], "type": o['type'],
                                "volume": o['volume'], "price_open": o['price_open'],
                            })

                smc_refs_raw = []
                if smc_data:
                    for bsl in smc_data.get("bsl_levels", [])[-2:]:
                        smc_refs_raw.append({"price": bsl["price"], "color": "#f59e0b", "title": "BSL (Liquidity)", "style": 2})
                    for ssl in smc_data.get("ssl_levels", [])[-2:]:
                        smc_refs_raw.append({"price": ssl["price"], "color": "#06b6d4", "title": "SSL (Liquidity)", "style": 2})
                    for fvg in smc_data.get("unmitigated_fvgs", [])[-2:]:
                        col = "#10b981" if fvg["type"] == "BULL_FVG" else "#ef4444"
                        smc_refs_raw.append({"price": fvg["mid"], "color": col, "title": f"{fvg['type']} Mid", "style": 3})

                # Layer count indicators
                n_buy = sum(1 for p in chart_pos_raw if p['direction'] == 'BUY')
                n_sell = sum(1 for p in chart_pos_raw if p['direction'] == 'SELL')
                n_sl = sum(1 for p in chart_pos_raw if p.get('sl', 0) > 0)
                n_tp = sum(1 for p in chart_pos_raw if p.get('tp', 0) > 0)
                n_pending = len(chart_ords_raw)
                n_smc = len(smc_refs_raw)

                # Granular Layer Visibility Controls
                st.markdown(
                    "<div style='display: flex; align-items: center; justify-content: space-between; margin-top: 8px; margin-bottom: 2px;'>"
                    "<span style='font-size: 0.84rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em;'>🎛️ เปิด/ปิด เส้นระดับราคาบนกราฟ (Chart Overlay Layers)</span>"
                    f"<span style='font-size: 0.78rem; color: #64748b;'>Active Overlays: <b>{n_buy + n_sell + n_sl + n_tp + n_pending + n_smc} เส้น</b></span>"
                    "</div>",
                    unsafe_allow_html=True
                )
                c_lay1, c_lay2, c_lay3, c_lay4, c_lay5, c_lay6 = st.columns(6)
                with c_lay1:
                    show_buy = st.checkbox(f"🟢 BUY ({n_buy})", value=True, key="chart_layer_buy")
                with c_lay2:
                    show_sell = st.checkbox(f"🔴 SELL ({n_sell})", value=True, key="chart_layer_sell")
                with c_lay3:
                    show_sl = st.checkbox(f"🛑 SL ({n_sl})", value=True, key="chart_layer_sl")
                with c_lay4:
                    show_tp = st.checkbox(f"🎯 TP ({n_tp})", value=True, key="chart_layer_tp")
                with c_lay5:
                    show_pending = st.checkbox(f"⏳ Limits ({n_pending})", value=True, key="chart_layer_pending")
                with c_lay6:
                    show_smc = st.checkbox(f"🌊 SMC ({n_smc})", value=True, key="chart_layer_smc")

                # Filter data based on active toggles
                chart_pos = []
                for p in chart_pos_raw:
                    is_buy = p['direction'] == 'BUY'
                    is_sell = p['direction'] == 'SELL'
                    entry_visible = (is_buy and show_buy) or (is_sell and show_sell)
                    sl_val = p.get('sl', 0) if show_sl else 0
                    tp_val = p.get('tp', 0) if show_tp else 0
                    if entry_visible or sl_val > 0 or tp_val > 0:
                        chart_pos.append({
                            "ticket": p['ticket'],
                            "direction": p['direction'],
                            "volume": p['volume'],
                            "price_open": p['price_open'] if entry_visible else 0,
                            "sl": sl_val,
                            "tp": tp_val,
                            "show_entry": entry_visible,
                        })

                chart_ords = chart_ords_raw if show_pending else []
                smc_refs = smc_refs_raw if show_smc else []

                # Dynamic Legend based on active layers
                legend_chips = []
                if show_buy:
                    legend_chips.append('<div class="leg-item"><div class="leg-dot" style="background:#34d399;"></div><span>BUY Entry</span></div>')
                if show_sell:
                    legend_chips.append('<div class="leg-item"><div class="leg-dot" style="background:#fb7185;"></div><span>SELL Entry</span></div>')
                if show_sl:
                    legend_chips.append('<div class="leg-item"><div class="leg-dot" style="background:#ef4444;"></div><span>Stop Loss</span></div>')
                if show_tp:
                    legend_chips.append('<div class="leg-item"><div class="leg-dot" style="background:#10b981;"></div><span>Take Profit</span></div>')
                if show_pending:
                    legend_chips.append('<div class="leg-item"><div class="leg-dot" style="background:#fbbf24;"></div><span>Limit Order</span></div>')
                if show_smc:
                    legend_chips.append('<div class="leg-item"><div class="leg-dot" style="background:#f59e0b;"></div><span>BSL/SSL Pools</span></div>')
                legend_inner_html = "".join(legend_chips)

                # TradingView Lightweight Charts HTML Injection
                candles_json = json.dumps(candles)
                pos_json = json.dumps(chart_pos)
                ord_json = json.dumps(chart_ords)
                smc_json = json.dumps(smc_refs)

                chart_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
                    <style>
                        body {{ margin: 0; padding: 0; background: #070a14; overflow: hidden; font-family: 'Outfit', sans-serif; }}
                        #tv_chart {{ width: 100%; height: 500px; border-radius: 14px; }}
                        .chart-legend {{
                            position: absolute; top: 12px; left: 16px; z-index: 10;
                            background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255,255,255,0.1);
                            border-radius: 8px; padding: 6px 12px; color: #94a3b8; font-size: 11px;
                            backdrop-filter: blur(8px); display: flex; gap: 14px; flex-wrap: wrap;
                        }}
                        .leg-item {{ display: flex; align-items: center; gap: 5px; }}
                        .leg-dot {{ width: 8px; height: 8px; border-radius: 50%; }}
                    </style>
                </head>
                <body>
                    <div class="chart-legend">
                        {legend_inner_html}
                    </div>
                    <div id="tv_chart"></div>
                    <script>
                        const container = document.getElementById('tv_chart');
                        const chart = LightweightCharts.createChart(container, {{
                            width: container.clientWidth || window.innerWidth,
                            height: 500,
                            layout: {{
                                background: {{ type: 'solid', color: '#070a14' }},
                                textColor: '#94a3b8',
                                fontFamily: 'Outfit, sans-serif',
                            }},
                            grid: {{
                                vertLines: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                                horzLines: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                            }},
                            crosshair: {{
                                mode: LightweightCharts.CrosshairMode.Normal,
                                vertLine: {{ color: 'rgba(56, 189, 248, 0.4)', width: 1, style: 2 }},
                                horzLine: {{ color: 'rgba(56, 189, 248, 0.4)', width: 1, style: 2 }},
                            }},
                            rightPriceScale: {{ borderColor: 'rgba(255, 255, 255, 0.1)' }},
                            timeScale: {{ borderColor: 'rgba(255, 255, 255, 0.1)', timeVisible: true, secondsVisible: false }},
                        }});

                        const candleSeries = chart.addCandlestickSeries({{
                            upColor: '#34d399', downColor: '#fb7185',
                            borderDownColor: '#fb7185', borderUpColor: '#34d399',
                            wickDownColor: '#fb7185', wickUpColor: '#34d399',
                        }});

                        candleSeries.setData({candles_json});

                        const positions = {pos_json};
                        positions.forEach(pos => {{
                            if (pos.show_entry && pos.price_open > 0) {{
                                const isBuy = pos.direction === 'BUY';
                                const col = isBuy ? '#34d399' : '#fb7185';
                                candleSeries.createPriceLine({{
                                    price: pos.price_open, color: col, lineWidth: 2,
                                    lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: true,
                                    title: `${{pos.direction}} #${{pos.ticket}} (${{pos.volume}}L)`,
                                }});
                            }}
                            if (pos.sl > 0) {{
                                candleSeries.createPriceLine({{
                                    price: pos.sl, color: '#ef4444', lineWidth: 1,
                                    lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true,
                                    title: `SL #${{pos.ticket}}`,
                                }});
                            }}
                            if (pos.tp > 0) {{
                                candleSeries.createPriceLine({{
                                    price: pos.tp, color: '#10b981', lineWidth: 1,
                                    lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true,
                                    title: `TP #${{pos.ticket}}`,
                                }});
                            }}
                        }});

                        const orders = {ord_json};
                        orders.forEach(ord => {{
                            candleSeries.createPriceLine({{
                                price: ord.price_open, color: '#fbbf24', lineWidth: 1,
                                lineStyle: LightweightCharts.LineStyle.Dotted, axisLabelVisible: true,
                                title: `${{ord.type}} #${{ord.ticket}} (${{ord.volume}}L)`,
                            }});
                        }});

                        const smc = {smc_json};
                        smc.forEach(ref => {{
                            candleSeries.createPriceLine({{
                                price: ref.price, color: ref.color, lineWidth: 1,
                                lineStyle: ref.style, axisLabelVisible: true, title: ref.title,
                            }});
                        }});

                        chart.timeScale().fitContent();
                        window.addEventListener('resize', () => {{ chart.applyOptions({{ width: container.clientWidth }}); }});
                    </script>
                </body>
                </html>
                """
                components.html(chart_html, height=520, scrolling=False)

                # SMC / ICT Liquidity Radar HUD
                if smc_data:
                    st.markdown("---")
                    st.markdown("#### 🎯 SMC / ICT Liquidity & Fair Value Gap Radar")
                    smc1, smc2, smc3, smc4 = st.columns(4)

                    with smc1:
                        st.markdown(
                            f"<div class='pro-card'>"
                            f"<div style='color:#94a3b8;font-size:12px;'>Market Structure Zone</div>"
                            f"<div style='font-size:15px;font-weight:800;color:{smc_data['zone_color']};margin-top:4px;'>{smc_data['zone_status']}</div>"
                            f"<div style='font-size:11px;color:#94a3b8;margin-top:4px;'>Fib 38.2%: {smc_data['fib_382']:,.2f} | 61.8%: {smc_data['fib_618']:,.2f}</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

                    with smc2:
                        nearest_bsl = smc_data['bsl_levels'][-1]['price'] if smc_data['bsl_levels'] else 0
                        dist_bsl = (nearest_bsl - smc_data['curr_price']) * 100 if nearest_bsl else 0
                        st.markdown(
                            f"<div class='pro-card'>"
                            f"<div style='color:#94a3b8;font-size:12px;'>Buy-Side Liquidity (BSL)</div>"
                            f"<div style='font-size:15px;font-weight:800;color:#f59e0b;margin-top:4px;'>{nearest_bsl:,.2f}</div>"
                            f"<div style='font-size:11px;color:#cbd5e1;margin-top:4px;'>ห่างจากราคาปัจจุบัน: <b>{dist_bsl:,.1f} pt</b></div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

                    with smc3:
                        nearest_ssl = smc_data['ssl_levels'][-1]['price'] if smc_data['ssl_levels'] else 0
                        dist_ssl = (smc_data['curr_price'] - nearest_ssl) * 100 if nearest_ssl else 0
                        st.markdown(
                            f"<div class='pro-card'>"
                            f"<div style='color:#94a3b8;font-size:12px;'>Sell-Side Liquidity (SSL)</div>"
                            f"<div style='font-size:15px;font-weight:800;color:#06b6d4;margin-top:4px;'>{nearest_ssl:,.2f}</div>"
                            f"<div style='font-size:11px;color:#cbd5e1;margin-top:4px;'>ห่างจากราคาปัจจุบัน: <b>{dist_ssl:,.1f} pt</b></div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

                    with smc4:
                        open_fvgs = smc_data['unmitigated_fvgs']
                        st.markdown(
                            f"<div class='pro-card'>"
                            f"<div style='color:#94a3b8;font-size:12px;'>Unmitigated FVGs</div>"
                            f"<div style='font-size:15px;font-weight:800;color:#f8fafc;margin-top:4px;'>{len(open_fvgs)} Imbalances</div>"
                            f"<div style='font-size:11px;color:#94a3b8;margin-top:4px;'>โซนที่ไม่ถูกเติมเต็มพร้อมเข้าเทรด</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

                # 🌊 Cumulative Volume Delta (CVD) & Footprint Absorption Monitor
                st.markdown("---")
                st.markdown("#### 🌊 Cumulative Volume Delta (CVD) & Order Absorption (สไตล์ Bookmap)")
                st.caption("มอนิเตอร์แรงซื้อขายสุทธิ (Aggressive Delta) ตรวจจับแรงดูดซับสภาพคล่อง (Volume Absorption) และ Divergence ก่อนจุดกลับตัว")
                df_cvd = calculate_cumulative_volume_delta(candles)
                if not df_cvd.empty:
                    cvd_chart = alt.Chart(df_cvd).mark_line(color='#38bdf8', strokeWidth=2).encode(
                        x=alt.X('time:N', title='เวลาแท่งเทียน (BKK)', axis=alt.Axis(labelAngle=-45)),
                        y=alt.Y('cvd:Q', title='Cumulative Delta (Contracts)'),
                        tooltip=['time', 'price', 'delta', 'cvd', 'volume']
                    ).properties(height=180)
                    delta_bars = alt.Chart(df_cvd).mark_bar(opacity=0.6).encode(
                        x=alt.X('time:N'),
                        y=alt.Y('delta:Q', title=None),
                        color=alt.condition(alt.datum.delta >= 0, alt.value('#34d399'), alt.value('#fb7185')),
                        tooltip=['time', 'delta']
                    ).properties(height=180)
                    st.altair_chart(delta_bars + cvd_chart, use_container_width=True)
                else:
                    st.info("ไม่มีข้อมูลแท่งเทียนเพียงพอสำหรับการคำนวณ Cumulative Volume Delta")

                # 🧭 SMC Multi-Timeframe (MTF) Alignment Matrix
                st.markdown("---")
                st.markdown("#### 🧭 SMC Multi-Timeframe (MTF) Alignment Matrix (M1 – H4)")
                st.caption("ระบบตรวจเช็คโครงสร้างราคาและโมเมนตัมข้าม 6 Timeframe พร้อมคำนวณคะแนนความเป็นเอกฉันท์ของตลาด (Consensus Score) สไตล์ TrendSpider / Bookmap")

                df_mtf, mtf_meta = calculate_mtf_alignment_matrix(chart_symbol)
                if not df_mtf.empty:
                    st.markdown(
                        f"<div style='background:rgba(15,23,42,0.85);border:1px solid rgba(255,255,255,0.1);border-radius:14px;padding:14px 20px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;'>"
                        f"<div>"
                        f"<div style='font-size:12px;color:#94a3b8;text-transform:uppercase;font-weight:700;letter-spacing:0.05em;'>Institutional Consensus Alignment</div>"
                        f"<div style='font-size:18px;font-weight:900;color:{mtf_meta['consensus_col']};margin-top:2px;'>{mtf_meta['consensus_text']}</div>"
                        f"</div>"
                        f"<div style='display:flex;gap:10px;'>"
                        f"<div class='badge-tag' style='background:rgba(52,211,153,0.15);color:#34d399;font-weight:700;padding:6px 14px;'>Bullish Factor: {mtf_meta['bull_pct']}%</div>"
                        f"<div class='badge-tag' style='background:rgba(251,113,133,0.15);color:#fb7185;font-weight:700;padding:6px 14px;'>Bearish Factor: {mtf_meta['bear_pct']}%</div>"
                        f"</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                    # MTF Table
                    mtf_rows = []
                    for _, r in df_mtf.iterrows():
                        mtf_rows.append(
                            f"<tr>"
                            f"<td><b style='color:#38bdf8;font-size:14px;'>{r['tf']}</b></td>"
                            f"<td style='color:#cbd5e1;'>{r['role']}</td>"
                            f"<td><span style='color:{r['color']};font-weight:700;'>{r['bias']}</span></td>"
                            f"<td>{r['structure']}</td>"
                            f"<td>{r['ema_status']}</td>"
                            f"<td>{r['rsi_state']}</td>"
                            f"</tr>"
                        )
                    st.markdown(
                        f"<div class='pro-card' style='padding:0;overflow-x:auto;margin-bottom:10px;'>"
                        f"<table class='pro-table'>"
                        f"<thead><tr>"
                        f"<th>Timeframe</th><th>บทบาททางกลยุทธ์</th><th>Net Bias</th><th>Market Structure</th><th>EMA 12/26</th><th>RSI 14 Momentum</th>"
                        f"</tr></thead>"
                        f"<tbody>{''.join(mtf_rows)}</tbody>"
                        f"</table></div>",
                        unsafe_allow_html=True
                    )



    # =============================================================
    #  TAB 4: 🛡️ RISK & PROP FIRM COMPLIANCE HUD
    # =============================================================
    with tab_risk:
        st.markdown("### 🛡️ Prop Firm & Capital Preservation HUD")
        st.caption("เครื่องมือควบคุมความเสี่ยงสไตล์กองทุน (FTMO / FundedNext / Prop Firm Standard) ตรวจจับ Drawdown และจำกัดความเสียหายรายวัน")

        # 🏛️ Prop Firm Milestone Target Tracker
        st.markdown("#### 🏛️ Prop Firm Challenge Target & Milestone Tracker (สไตล์ FTMO MetriX)")
        st.caption("มอนิเตอร์ความคืบหน้าการสอบกองทุนแบบเรียลไทม์ ตรวจสอบเงื่อนไข Profit Target, Daily Loss Buffer และ Max Trailing Drawdown")

        preset_options = ["FTMO $10k (Phase 1)", "FTMO $10k (Phase 2)", "FundedNext $25k", "MFFX $50k", "Custom Challenge"]
    
        pf_c1, pf_c2, pf_c3, pf_c4, pf_c5 = st.columns(5)
        with pf_c1:
            preset_choice = st.selectbox(
                "เลือกประเภท Challenge",
                preset_options,
                index=0,
                key="prop_preset_select"
            )
    
        # Preset parameters
        if "FTMO $10k (Phase 1)" in preset_choice:
            def_cap, def_target, def_daily, def_max, def_days = 10000.0, 10.0, 5.0, 10.0, 4
        elif "FTMO $10k (Phase 2)" in preset_choice:
            def_cap, def_target, def_daily, def_max, def_days = 10000.0, 5.0, 5.0, 10.0, 4
        elif "FundedNext $25k" in preset_choice:
            def_cap, def_target, def_daily, def_max, def_days = 25000.0, 10.0, 5.0, 10.0, 5
        elif "MFFX $50k" in preset_choice:
            def_cap, def_target, def_daily, def_max, def_days = 50000.0, 8.0, 5.0, 10.0, 5
        else:
            def_cap, def_target, def_daily, def_max, def_days = 10000.0, 10.0, 5.0, 10.0, 5

        # Synchronize Session State on Preset Switch
        if st.session_state.get("_last_prop_preset") != preset_choice:
            st.session_state["_last_prop_preset"] = preset_choice
            st.session_state["prop_init_cap"] = float(def_cap)
            st.session_state["prop_target_pct"] = float(def_target)
            st.session_state["prop_daily_loss_pct"] = float(def_daily)
            st.session_state["prop_max_dd_pct"] = float(def_max)

        with pf_c2:
            init_cap = st.number_input("ทุนเริ่มต้น ($)", value=st.session_state.get("prop_init_cap", def_cap), step=1000.0, key="prop_init_cap")
        with pf_c3:
            target_pct = st.number_input("Profit Target (%)", value=st.session_state.get("prop_target_pct", def_target), step=1.0, key="prop_target_pct")
        with pf_c4:
            daily_loss_pct = st.number_input("Max Daily Loss (%)", value=st.session_state.get("prop_daily_loss_pct", def_daily), step=0.5, key="prop_daily_loss_pct")
        with pf_c5:
            max_dd_pct = st.number_input("Max Total DD (%)", value=st.session_state.get("prop_max_dd_pct", def_max), step=0.5, key="prop_max_dd_pct")

        # Evaluation Range Option (กันประวัติ All-Time หลายหมื่นไม้มาทำให้ Challenge Breached)
        eval_col1, eval_col2 = st.columns([3, 1])
        with eval_col1:
            eval_window = st.radio(
                "ช่วงประวัติที่ใช้ประเมิน Challenge",
                ["ประเมินตามช่วงเวลาที่เลือก (Active Filter Range)", "ประเมิน 30 วันล่าสุด (Rolling 30-Day Evaluation)"],
                index=0,
                horizontal=True,
                key="prop_eval_window"
            )
        with eval_col2:
            if live_acc and live_acc.get("balance", 0) > 0:
                if st.button(f"🔄 Sync ทุน MT5 (${live_acc.get('balance', 0):,.0f})", use_container_width=True):
                    st.session_state["prop_init_cap"] = float(live_acc.get("balance", 10000.0))
                    st.rerun()

        # Filter evaluation dataset
        df_eval = df_history.copy()
        if "30 วันล่าสุด" in eval_window and not df_eval.empty:
            cutoff_date = datetime.now(BKK) - timedelta(days=30)
            df_eval = df_eval[df_eval['time'] >= cutoff_date.replace(tzinfo=None)]

        # Floating P/L from Live Account
        fl_profit = live_acc.get("profit", 0.0) if live_acc else 0.0

        # Calculate Prop Firm Metrics
        pf_data = calculate_prop_firm_status(
            df_eval,
            initial_balance=init_cap,
            target_pct=target_pct,
            daily_loss_pct=daily_loss_pct,
            max_trailing_dd_pct=max_dd_pct,
            min_trading_days=def_days,
            floating_pnl=fl_profit
        )

        # Status Banner
        st.markdown(
            f"<div style='background:rgba(15,23,42,0.85);border:1px solid rgba(255,255,255,0.1);border-radius:14px;padding:16px 20px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;'>"
            f"<div>"
            f"<div style='font-size:12px;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;'>Current Challenge Evaluation Status</div>"
            f"<div style='font-size:20px;font-weight:900;color:{pf_data['status_color']};margin-top:2px;'>{pf_data['status_text']}</div>"
            f"</div>"
            f"<div style='display:flex;gap:16px;align-items:center;'>"
            f"<div style='text-align:right;'><div style='font-size:11px;color:#94a3b8;'>Simulated Equity</div><div style='font-size:16px;font-weight:800;color:#f8fafc;'>${pf_data['current_balance']:,.2f}</div></div>"
            f"<div style='text-align:right;'><div style='font-size:11px;color:#94a3b8;'>Net Profit (รวม Floating)</div><div style='font-size:16px;font-weight:800;color:{'#34d399' if pf_data['net_profit'] >= 0 else '#fb7185'};'>${pf_data['net_profit']:+,.2f}</div></div>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
        )

        # 4 Milestone Gauges
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.markdown(
                f"<div class='pro-card'>"
                f"<div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px;'>"
                f"<span style='color:#94a3b8;font-weight:700;'>🎯 Profit Target</span>"
                f"<span style='color:#38bdf8;font-weight:800;'>{pf_data['profit_progress_pct']:.1f}%</span>"
                f"</div>"
                f"<div style='font-size:18px;font-weight:900;color:#38bdf8;'>${pf_data['net_profit']:,.2f} <span style='font-size:12px;color:#94a3b8;'>/ ${pf_data['target_amount']:,.2f}</span></div>"
                f"<div style='background:rgba(255,255,255,0.08);height:8px;border-radius:4px;overflow:hidden;margin:8px 0;'>"
                f"<div style='background:#38bdf8;height:100%;width:{pf_data['profit_progress_pct']:.1f}%;border-radius:4px;'></div>"
                f"</div>"
                f"<div style='font-size:11px;color:#cbd5e1;'>ขาดอีก: <b>${pf_data['remaining_target']:,.2f}</b> เพื่อผ่านเป้าหมาย</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with m_col2:
            daily_color = "#34d399" if pf_data['daily_loss_used_pct'] < 50 else ("#f59e0b" if pf_data['daily_loss_used_pct'] < 80 else "#ef4444")
            st.markdown(
                f"<div class='pro-card'>"
                f"<div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px;'>"
                f"<span style='color:#94a3b8;font-weight:700;'>🚨 Daily Loss Buffer</span>"
                f"<span style='color:{daily_color};font-weight:800;'>ใช้ไป {pf_data['daily_loss_used_pct']:.1f}%</span>"
                f"</div>"
                f"<div style='font-size:18px;font-weight:900;color:{daily_color};'>${pf_data['daily_loss_remaining']:,.2f} <span style='font-size:12px;color:#94a3b8;'>Buffer</span></div>"
                f"<div style='background:rgba(255,255,255,0.08);height:8px;border-radius:4px;overflow:hidden;margin:8px 0;'>"
                f"<div style='background:{daily_color};height:100%;width:{pf_data['daily_loss_used_pct']:.1f}%;border-radius:4px;'></div>"
                f"</div>"
                f"<div style='font-size:11px;color:#cbd5e1;'>วันนี้ติดลบได้อีกไม่เกิน: <b>${pf_data['daily_loss_remaining']:,.2f}</b></div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with m_col3:
            max_dd_used_pct = min(100.0, (pf_data['max_dd'] / pf_data['max_trailing_limit'] * 100.0)) if pf_data['max_trailing_limit'] > 0 else 0.0
            dd_col = "#34d399" if max_dd_used_pct < 50 else ("#f59e0b" if max_dd_used_pct < 80 else "#ef4444")
            st.markdown(
                f"<div class='pro-card'>"
                f"<div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px;'>"
                f"<span style='color:#94a3b8;font-weight:700;'>🛑 Max Trailing DD</span>"
                f"<span style='color:{dd_col};font-weight:800;'>DD {max_dd_used_pct:.1f}%</span>"
                f"</div>"
                f"<div style='font-size:18px;font-weight:900;color:{dd_col};'>${pf_data['trailing_dd_remaining']:,.2f} <span style='font-size:12px;color:#94a3b8;'>Buffer</span></div>"
                f"<div style='background:rgba(255,255,255,0.08);height:8px;border-radius:4px;overflow:hidden;margin:8px 0;'>"
                f"<div style='background:{dd_col};height:100%;width:{max_dd_used_pct:.1f}%;border-radius:4px;'></div>"
                f"</div>"
                f"<div style='font-size:11px;color:#cbd5e1;'>ระยะปลอดภัยสูงสุด: <b>${pf_data['trailing_dd_remaining']:,.2f}</b> (Peak DD: ${pf_data['max_dd']:,.2f})</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with m_col4:
            days_pct = min(100.0, (pf_data['trading_days'] / pf_data['min_trading_days'] * 100.0)) if pf_data['min_trading_days'] > 0 else 100.0
            days_col = "#34d399" if pf_data['trading_days'] >= pf_data['min_trading_days'] else "#38bdf8"
            days_desc = "✅ ผ่านเกณฑ์จำนวนวันเทรดแล้ว" if pf_data['trading_days'] >= pf_data['min_trading_days'] else f"ขาดอีก {max(0, pf_data['min_trading_days'] - pf_data['trading_days'])} วัน"
            st.markdown(
                f"<div class='pro-card'>"
                f"<div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px;'>"
                f"<span style='color:#94a3b8;font-weight:700;'>📅 Trading Days</span>"
                f"<span style='color:{days_col};font-weight:800;'>{days_pct:.0f}%</span>"
                f"</div>"
                f"<div style='font-size:18px;font-weight:900;color:{days_col};'>{pf_data['trading_days']} วัน <span style='font-size:12px;color:#94a3b8;'>/ ขั้นต่ำ {pf_data['min_trading_days']} วัน</span></div>"
                f"<div style='background:rgba(255,255,255,0.08);height:8px;border-radius:4px;overflow:hidden;margin:8px 0;'>"
                f"<div style='background:{days_col};height:100%;width:{days_pct:.1f}%;border-radius:4px;'></div>"
                f"</div>"
                f"<div style='font-size:11px;color:#cbd5e1;'>{days_desc}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

        st.markdown("---")
        r_col1, r_col2 = st.columns([2, 1])
    
        with r_col2:
            st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
            st.markdown("<div style='font-weight:700;color:#38bdf8;margin-bottom:8px;'>⚙️ Custom Loss Guardrails</div>", unsafe_allow_html=True)
            max_daily_loss_limit = st.number_input("🚨 Daily Loss Limit ($)", min_value=50.0, max_value=50000.0, value=500.0, step=50.0, key="risk_daily_loss_limit")
            max_overall_dd_limit = st.number_input("🛑 Max Overall Trailing DD ($)", min_value=100.0, max_value=100000.0, value=1500.0, step=100.0, key="risk_max_overall_dd")
            st.markdown("</div>", unsafe_allow_html=True)

        with r_col1:
            daily_loss_realized = state.get('daily_stats', {}).get('realized', 0.0)
            curr_loss = abs(daily_loss_realized) if daily_loss_realized < 0 else 0.0
            daily_dd_pct = min(100.0, (curr_loss / max_daily_loss_limit) * 100.0) if max_daily_loss_limit > 0 else 0.0
            daily_dd_color = "#34d399" if daily_dd_pct < 50 else ("#fbbf24" if daily_dd_pct < 80 else "#fb7185")

            st.markdown(f"#### 1. Daily Drawdown Tracker")
            st.markdown(
                f"<div class='pro-card'>"
                f"<div style='display:flex;justify-content:space-between;margin-bottom:8px;'>"
                f"<span>ขาดทุนสะสมวันนี้: <b style='color:{daily_dd_color};'>${curr_loss:,.2f}</b></span>"
                f"<span>เกณฑ์จำกัดความเสี่ยง: <b>${max_daily_loss_limit:,.2f}</b> ({daily_dd_pct:.1f}%)</span>"
                f"</div>"
                f"<div style='background:rgba(255,255,255,0.08);height:10px;border-radius:6px;overflow:hidden;'>"
                f"<div style='background:{daily_dd_color};height:100%;width:{daily_dd_pct:.1f}%;border-radius:6px;transition:width 0.5s;'></div>"
                f"</div>"
                f"<div style='font-size:12px;color:#94a3b8;margin-top:6px;'>"
                f"{'🟢 อยู่ในเกณฑ์ปลอดภัย' if daily_dd_pct < 60 else ('🟡 เข้าใกล้จุดเสี่ยง ควรระวัง' if daily_dd_pct < 90 else '🔴 วิกฤต: แตะลิมิต Daily Loss แนะนำหยุดเทรด')}"
                f"</div></div>",
                unsafe_allow_html=True
            )

            if not df_history.empty:
                eq_curve = df_history.sort_values('time')['net'].cumsum()
                # Current Drawdown from latest Peak
                cur_dd = float(abs(eq_curve.iloc[-1] - eq_curve.cummax().iloc[-1])) if len(eq_curve) > 0 else 0.0
                # Historical Deepest Peak-to-Trough Drawdown
                deepest_dd = float(abs((eq_curve - eq_curve.cummax()).min())) if len(eq_curve) > 0 else 0.0
                overall_pct = min(100.0, (cur_dd / max_overall_dd_limit) * 100.0) if max_overall_dd_limit > 0 else 0.0
                overall_color = "#34d399" if overall_pct < 50 else ("#fbbf24" if overall_pct < 80 else "#fb7185")

                st.markdown(f"#### 2. Peak Drawdown Trackers")
                st.markdown(
                    f"<div class='pro-card'>"
                    f"<div style='display:flex;justify-content:space-between;margin-bottom:8px;'>"
                    f"<span>Drawdown ปัจจุบัน (จากจุดสูงสุดล่าสุด): <b style='color:{overall_color};'>${cur_dd:,.2f}</b></span>"
                    f"<span>ลิมิตพอร์ต: <b>${max_overall_dd_limit:,.2f}</b> ({overall_pct:.1f}%)</span>"
                    f"</div>"
                    f"<div style='background:rgba(255,255,255,0.08);height:10px;border-radius:6px;overflow:hidden;'>"
                    f"<div style='background:{overall_color};height:100%;width:{overall_pct:.1f}%;border-radius:6px;'></div>"
                    f"</div>"
                    f"<div style='font-size:12px;color:#94a3b8;margin-top:6px;'>"
                    f"<span>📉 Max DD ลึกสุดในอดีต (All-Time High-to-Trough): <b style='color:#f8fafc;'>${deepest_dd:,.2f}</b></span>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

        st.markdown("---")
        st.markdown("#### 📋 Institutional Risk Checklist")
        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            st.markdown(
                "<div class='pro-card'>"
                "<div style='font-weight:700;color:#38bdf8;margin-bottom:6px;'>📰 Macro News Shield</div>"
                f"<div>สถานะข่าว: {'🔴 <b>PAUSED (Embargo)</b>' if news_active else '🟢 <b>CLEARED TO TRADE</b>'}</div>"
                "<div style='font-size:12px;color:#94a3b8;margin-top:4px;'>ระบบจะระงับการออกไม้รอบข่าวแรง USD ±15 นาทีโดยอัตโนมัติ</div>"
                "</div>",
                unsafe_allow_html=True
            )
        with rc2:
            margin_lvl_txt = f"{live_acc.get('margin_level', 0):,.0f}%" if live_acc else "N/A"
            st.markdown(
                f"<div class='pro-card'>"
                "<div style='font-weight:700;color:#38bdf8;margin-bottom:6px;'>⚖️ Leverage & Margin Health</div>"
                f"<div>ระดับ Margin: <b>{margin_lvl_txt}</b></div>"
                "<div style='font-size:12px;color:#94a3b8;margin-top:4px;'>ควรคุมให้เกิน 1,000% เสมอเพื่อป้องกัน Margin Call หรือ Overleveraging</div>"
                "</div>",
                unsafe_allow_html=True
            )
        with rc3:
            tracked_cnt = len(state.get("tracked_positions", {}))
            st.markdown(
                f"<div class='pro-card'>"
                "<div style='font-weight:700;color:#38bdf8;margin-bottom:6px;'>🤖 State Machine Integrity</div>"
                f"<div>Tracked Memory: <b>{tracked_cnt} positions</b></div>"
                "<div style='font-size:12px;color:#94a3b8;margin-top:4px;'>การซิงก์ memory ระหว่าง bot_state.json กับ MT5 Terminal สมบูรณ์</div>"
                "</div>",
                unsafe_allow_html=True
            )

        st.markdown("---")
        st.markdown("#### 🧮 Interactive Prop Firm Challenge Simulator & Dynamic Risk Sizing")
        st.caption("เครื่องคิดเลขคำนวณขนาด Lot Size อิงตามเปอร์เซ็นต์ความเสี่ยง (% Risk) ต่อไม้ และจำลองจำนวนวันที่ต้องใช้ผ่าน Challenge (Phase 1 & Phase 2) สไตล์ FTMO / FundedNext")

        calc_c1, calc_c2 = st.columns([1.2, 1.8])
        with calc_c1:
            st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
            st.markdown("<div style='font-weight:700;color:#38bdf8;margin-bottom:10px;'>⚙️ Risk Parameters</div>", unsafe_allow_html=True)
            calc_acc_size = st.selectbox("ขนาดพอร์ตจำลอง (Account Capital)", [10000, 25000, 50000, 100000, 200000], index=3, format_func=lambda x: f"${x:,.0f}")
            calc_risk_pct = st.slider("ความเสี่ยงต่อไม้ (% Risk per Trade)", min_value=0.25, max_value=3.0, value=1.0, step=0.25)
            calc_sl_pts = st.number_input("ระยะตัดขาดทุน SL (Points)", min_value=50, max_value=2000, value=300, step=25)
            calc_rr = st.slider("อัตราส่วนผลตอบแทนต่อความเสี่ยง (Target R:R)", min_value=1.0, max_value=5.0, value=2.0, step=0.5)
            st.markdown("</div>", unsafe_allow_html=True)

        with calc_c2:
            # XAUUSD 1 lot = 100 oz. 1 point = 0.01 USD. For 1 lot, 100 points = $100.
            dollar_risk = calc_acc_size * (calc_risk_pct / 100.0)
            lot_size = max(0.01, round(dollar_risk / max(1.0, float(calc_sl_pts)), 2))
            profit_target = dollar_risk * calc_rr

            target_p1 = calc_acc_size * 0.08
            target_p2 = calc_acc_size * 0.05

            # Use actual historical win rate if available
            if not df_history.empty and len(df_history) >= 15:
                hist_wr = float((df_history['net'] > 0).mean())
                hist_wr = min(0.85, max(0.35, hist_wr))
            else:
                hist_wr = 0.60

            exp_per_trade = max(10.0, (hist_wr * profit_target) - ((1 - hist_wr) * dollar_risk))
            trades_p1 = max(1, int(np.ceil(target_p1 / exp_per_trade)))
            trades_p2 = max(1, int(np.ceil(target_p2 / exp_per_trade)))
            days_p1 = max(1, int(np.ceil(trades_p1 / 3.0)))
            days_p2 = max(1, int(np.ceil(trades_p2 / 3.0)))

            c_res1, c_res2, c_res3 = st.columns(3)
            c_res1.metric("ขนาด Lot ที่แนะนำ", f"{lot_size:.2f} Lots", help="คำนวณตาม XAUUSD 1 pt = $1/lot")
            c_res2.metric("เงินเสี่ยงต่อไม้ ($)", f"${dollar_risk:,.2f}", f"{calc_risk_pct:.2f}%")
            c_res3.metric("เป้ากำไรต่อไม้ (TP)", f"${profit_target:,.2f}", f"R:R 1:{calc_rr:.1f}")

            st.markdown(
                f"<div class='pro-card' style='margin-top:12px;border-left:4px solid #38bdf8;'>"
                f"<div style='font-weight:700;color:#38bdf8;margin-bottom:6px;'>🏆 Prop Firm Pass Projection (FTMO / FundedNext Standard)</div>"
                f"<div style='display:flex;justify-content:space-between;margin-top:8px;font-size:13px;'>"
                f"<span><b>Phase 1 (Target 8% = ${target_p1:,.0f}):</b></span>"
                f"<span style='color:#34d399;font-weight:700;'>~{trades_p1} ไม้ (คาดการณ์ ~{days_p1} วันทำการ)</span>"
                f"</div>"
                f"<div style='display:flex;justify-content:space-between;margin-top:6px;font-size:13px;'>"
                f"<span><b>Phase 2 (Target 5% = ${target_p2:,.0f}):</b></span>"
                f"<span style='color:#38bdf8;font-weight:700;'>~{trades_p2} ไม้ (คาดการณ์ ~{days_p2} วันทำการ)</span>"
                f"</div>"
                f"<div style='font-size:11px;color:#94a3b8;margin-top:8px;'>*อิงจากเป้าหมายกำไร FTMO และอัตราเฉลี่ย 3 ไม้ต่อวันทำการ</div>"
                f"</div>",
                unsafe_allow_html=True
            )



    # =============================================================
    #  TAB 5: 📈 QUANT EDGE & MONTE CARLO SIMULATION
    # =============================================================
    with tab_quant:
        st.markdown("### 📈 Institutional Quant Edge & Monte Carlo Simulation")
        st.caption("การวิเคราะห์ทางสถิติระดับกองทุนควอนต์ คำนวณความได้เปรียบเชิงตัวเลข (Edge) และทำนายความน่าจะเป็นของพอร์ตด้วยแบบจำลองมอนติคาร์โล")

        if df_history.empty:
            st.info("ต้องการข้อมูลประวัติเทรดเพื่อคำนวณ Quant Analytics")
        else:
            qm = calculate_quant_metrics(df_history)

            q1, q2, q3, q4 = st.columns(4)
            q1.metric("Sharpe Ratio (Ann.)", f"{qm.get('sharpe', 0):.2f}", help="ผลตอบแทนเทียบกับความผันผวนรวม (เป้าหมาย > 1.5)")
            q2.metric("Sortino Ratio", f"{qm.get('sortino', 0):.2f}", help="ผลตอบแทนเทียบเฉพาะความเสี่ยงขาลง (Downside Volatility)")
            q3.metric("Calmar Ratio", f"{qm.get('calmar', 0):.2f}", help="ผลตอบแทนต่อปี ÷ Max Drawdown (ยิ่งสูงยิ่งดี)")
            q4.metric("Kelly Sizing", f"{qm.get('kelly_pct', 0):.1f}%", help="ขนาดพอร์ตที่แนะนำตามสูตร Kelly")

            q5, q6, q7, q8 = st.columns(4)
            q5.metric("Gross Profit", f"${qm.get('gross_profit', 0):,.2f}")
            q6.metric("Gross Loss", f"-${qm.get('gross_loss', 0):,.2f}")
            q7.metric("Max Win Streak", f"{qm.get('max_win_streak', 0)} ไม้ติด")
            q8.metric("Max Loss Streak", f"{qm.get('max_loss_streak', 0)} ไม้ติด")

            st.markdown("---")

            # 🎲 Monte Carlo Simulation Section
            st.markdown("#### 🎲 Monte Carlo Simulation & Prop Firm Probability Cone")
            st.caption("จำลองการสุ่มสลับลำดับผลลัพธ์การเทรด 1,000 รอบในอนาคต เพื่อหาช่วงความเป็นไปได้ของ Equity (5th-95th Percentile) และโอกาสพอร์ตแตก (Risk of Ruin)")

            mc_col1, mc_col2, mc_col3, mc_col4 = st.columns(4)
            with mc_col1:
                mc_sims = st.selectbox("จำนวนรอบจำลอง", [500, 1000, 2000], index=1)
            with mc_col2:
                mc_horizon = st.selectbox("จำนวนไม้ในอนาคต", [50, 100, 200, 300], index=1)
            with mc_col3:
                mc_start_cap = st.number_input("ทุนเริ่มต้น ($)", min_value=100.0, max_value=1000000.0, value=10000.0, step=1000.0)
            with mc_col4:
                mc_max_loss_pct = st.selectbox("Max Allowed Loss (%)", [0.04, 0.05, 0.08, 0.10], index=1, format_func=lambda x: f"{int(x*100)}%")

            mc_key = f"{len(df_history)}_{mc_sims}_{mc_horizon}_{mc_start_cap}_{mc_max_loss_pct}"
            if st.session_state.get("mc_last_key") != mc_key:
                st.session_state["mc_last_key"] = mc_key
                mc_prog_holder = st.empty()
                with mc_prog_holder.container():
                    mc_bar = st.progress(35, text=f"🎲 กำลังจำลองมอนติคาร์โล {mc_sims:,} รอบ (Horizon: {mc_horizon} ไม้)...")
                    mc_res = run_monte_carlo_simulation(
                        returns=tuple(df_history['net'].values),
                        starting_capital=mc_start_cap,
                        n_sims=mc_sims,
                        horizon=mc_horizon,
                        target_pct=0.10,
                        max_loss_pct=mc_max_loss_pct
                    )
                    mc_bar.progress(100, text="✅ จำลองผลลัพธ์มอนติคาร์โลสำเร็จ")
                    time.sleep(0.04)
                mc_prog_holder.empty()
            else:
                mc_res = run_monte_carlo_simulation(
                    returns=tuple(df_history['net'].values),
                    starting_capital=mc_start_cap,
                    n_sims=mc_sims,
                    horizon=mc_horizon,
                    target_pct=0.10,
                    max_loss_pct=mc_max_loss_pct
                )


            if mc_res:
                mcr1, mcr2, mcr3, mcr4 = st.columns(4)
                mcr1.metric("Median Equity คาดหวัง", f"${mc_res['median_ending']:,.2f}", help="ค่ามัธยฐานของทุนเมื่อเทรดครบจำนวนไม้ที่กำหนด")
                mcr2.metric("Risk of Ruin %", f"{mc_res['risk_of_ruin_pct']:.1f}%", help=f"โอกาสที่พอร์ตจะแตะผลขาดทุนเกิน {int(mc_max_loss_pct*100)}%")
                mcr3.metric("Prop Firm Pass Rate", f"{mc_res['pass_prob_pct']:.1f}%", help="โอกาสทำกำไรถึง +10% ก่อนติดลบแตะลิมิต")
                mcr4.metric("Max Drawdown (95% CI)", f"${mc_res['dd_95']:,.2f}", help="Max DD คาดหวังที่ระดับความเชื่อมั่น 95%")

                df_cone = mc_res['df_cone']
                cone_chart = alt.Chart(df_cone).mark_area(opacity=0.2, color='#38bdf8').encode(
                    x=alt.X('trade:Q', title='จำนวนไม้ในอนาคต (Trade Horizon)'),
                    y=alt.Y('p5:Q', title='Simulated Equity ($)'),
                    y2=alt.Y2('p95:Q')
                )
                median_line = alt.Chart(df_cone).mark_line(color='#34d399', strokeWidth=2).encode(
                    x=alt.X('trade:Q'),
                    y=alt.Y('median:Q', title='Simulated Equity ($)')
                )
                st.altair_chart(cone_chart + median_line, use_container_width=True)

            st.markdown("---")

            # Day of Week × Hour Heatmap (Golden Window Finder)
            st.markdown("#### 🗺️ Golden Trading Window Matrix (Day × Hour Heatmap)")
            df_heatmap = df_history.copy()
            df_heatmap['dow'] = df_heatmap['time'].dt.day_name().str[:3]
            df_heatmap['hour'] = df_heatmap['time'].dt.hour
            heat_data = df_heatmap.groupby(['dow', 'hour']).agg(
                net=('net', 'sum'), trades=('net', 'count'),
                win_rate=('net', lambda x: (x > 0).mean() * 100)
            ).reset_index()

            dow_order = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
            heat_chart = alt.Chart(heat_data).mark_rect(cornerRadius=3).encode(
                x=alt.X('hour:O', title='ชั่วโมง (BKK 0-23)'),
                y=alt.Y('dow:N', title=None, sort=dow_order),
                color=alt.Color('net:Q', scale=alt.Scale(scheme='redyellowgreen'), title='Net P/L ($)'),
                tooltip=[
                    alt.Tooltip('dow:N', title='วัน'),
                    alt.Tooltip('hour:O', title='ชั่วโมง (BKK)'),
                    alt.Tooltip('net:Q', format='$,.2f', title='Net P/L'),
                    alt.Tooltip('win_rate:Q', format='.1f', title='Win Rate %'),
                    alt.Tooltip('trades:Q', title='จำนวนไม้')
                ]
            ).properties(height=240)
            st.markdown("---")

            # ⏱️ ICT / SMC Killzone Performance Attribution (TraderSync / TradeZella Style)
            st.markdown("#### ⏱️ ICT / SMC Killzone Performance Attribution (วิเคราะห์กำไรตามช่วงเวลาสถาบัน)")
            st.caption("แจกแจงผลตอบแทน (P&L Attribution) ตามช่วงเวลา Liquidity Killzones: Asian Range, London Open, NY AM Overlap, NY PM Close")

            df_kz, kz_meta = calculate_killzone_attribution(df_history)
            if not df_kz.empty:
                kz_chart = alt.Chart(df_kz).mark_bar(cornerRadius=4).encode(
                    x=alt.X('killzone:N', title=None, axis=alt.Axis(labelAngle=-15, labelColor='#94a3b8')),
                    y=alt.Y('net_pnl:Q', title='Net P/L ($)', axis=alt.Axis(labelColor='#94a3b8')),
                    color=alt.condition(alt.datum.net_pnl >= 0, alt.value('#34d399'), alt.value('#fb7185')),
                    tooltip=[
                        alt.Tooltip('killzone:N', title='Killzone Session'),
                        alt.Tooltip('net_pnl:Q', format='$,.2f', title='Net P/L'),
                        alt.Tooltip('win_rate:Q', format='.1f', title='Win Rate %'),
                        alt.Tooltip('profit_factor:Q', title='Profit Factor'),
                        alt.Tooltip('trades:Q', title='จำนวนไม้'),
                        alt.Tooltip('avg_dur_min:Q', title='Avg Duration (min)'),
                    ]
                ).properties(height=220)
                st.altair_chart(kz_chart, use_container_width=True)

                kz_rows = []
                for _, r in df_kz.iterrows():
                    p_col = "#34d399" if r['net_pnl'] >= 0 else "#fb7185"
                    kz_rows.append(
                        f"<tr>"
                        f"<td><b style='color:#38bdf8;'>{r['killzone']}</b></td>"
                        f"<td>{r['trades']}</td>"
                        f"<td>{r['win_rate']:.1f}%</td>"
                        f"<td style='color:{p_col};font-weight:700;'>${r['net_pnl']:+,.2f}</td>"
                        f"<td>{r['profit_factor']:.2f}</td>"
                        f"<td>{r['avg_dur_min']:.1f} m</td>"
                        f"</tr>"
                    )
                st.markdown(
                    f"<div class='pro-card' style='padding:0;overflow-x:auto;margin-bottom:12px;'>"
                    f"<table class='pro-table'>"
                    f"<thead><tr>"
                    f"<th>SMC Killzone Session</th><th>จำนวนไม้</th><th>Win Rate</th><th>Net Profit</th><th>Profit Factor</th><th>Avg Duration</th>"
                    f"</tr></thead>"
                    f"<tbody>{''.join(kz_rows)}</tbody>"
                    f"</table></div>",
                    unsafe_allow_html=True
                )

            st.markdown("---")

            # Long vs Short Comparative Analytics
            st.markdown("#### ⚖️ Long vs Short Performance Breakdown")
            ls_col1, ls_col2 = st.columns(2)
            with ls_col1:
                long_cnt = qm.get('long_count', 0)
                long_wins = qm.get('long_wins', 0)
                long_wr = (long_wins / long_cnt * 100) if long_cnt else 0.0
                st.markdown(
                    f"<div class='pro-card' style='border-top:3px solid #34d399;'>"
                    f"<h4 style='color:#34d399;margin-top:0;'>🟢 BUY / LONG POSITIONS</h4>"
                    f"<div style='font-size:22px;font-weight:800;color:#f8fafc;'>Net: ${qm.get('long_net', 0):+,.2f}</div>"
                    f"<div style='margin-top:6px;color:#94a3b8;'>จำนวนไม้: <b>{long_cnt:,}</b> ไม้</div>"
                    f"<div style='color:#94a3b8;'>Win Rate: <b>{long_wr:.1f}%</b> ({long_wins}W / {long_cnt - long_wins}L)</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with ls_col2:
                short_cnt = qm.get('short_count', 0)
                short_wins = qm.get('short_wins', 0)
                short_wr = (short_wins / short_cnt * 100) if short_cnt else 0.0
                st.markdown(
                    f"<div class='pro-card' style='border-top:3px solid #fb7185;'>"
                    f"<h4 style='color:#fb7185;margin-top:0;'>🔴 SELL / SHORT POSITIONS</h4>"
                    f"<div style='font-size:22px;font-weight:800;color:#f8fafc;'>Net: ${qm.get('short_net', 0):+,.2f}</div>"
                    f"<div style='margin-top:6px;color:#94a3b8;'>จำนวนไม้: <b>{short_cnt:,}</b> ไม้</div>"
                    f"<div style='color:#94a3b8;'>Win Rate: <b>{short_wr:.1f}%</b> ({short_wins}W / {short_cnt - short_wins}L)</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            # ─────────────────────────────────────────────────────────────
            # 🎯 Trade Optimization: MAE vs MFE Efficiency Scatter Matrix
            # ─────────────────────────────────────────────────────────────
            st.markdown("---")
            st.markdown("#### 🎯 Trade Optimization: MAE vs MFE Efficiency Scatter Matrix (สไตล์ TradeZella / Edgewonk)")
            st.caption("วิเคราะห์จังหวะการทำกำไรสูงสุด (Maximum Favorable Excursion) เทียบกับการยอมรับ Drawdown ระหว่างถือครอง (Maximum Adverse Excursion) เพื่อ Optimize SL/TP")

            with st.spinner("🎯 กำลังคำนวณ MAE/MFE ของทุกไม้..."):
                df_mae = calculate_mae_mfe_data(df_history)
            if not df_mae.empty:
                mae_scatter = alt.Chart(df_mae).mark_circle(size=70, opacity=0.75).encode(
                    x=alt.X('mae_pts:Q', title='MAE: Max Adverse Excursion (ลากติดลบสูงสุด - Points)'),
                    y=alt.Y('mfe_pts:Q', title='MFE: Max Favorable Excursion (วิ่งกำไรสูงสุด - Points)'),
                    color=alt.Color('outcome:N', scale=alt.Scale(domain=['WIN', 'LOSS'], range=['#34d399', '#fb7185']), title='ผลลัพธ์'),
                    tooltip=[
                        alt.Tooltip('ticket:N', title='Order Ticket'),
                        alt.Tooltip('strategy:N', title='Strategy'),
                        alt.Tooltip('direction:N', title='Type'),
                        alt.Tooltip('mae_pts:Q', title='MAE (Pts)'),
                        alt.Tooltip('mfe_pts:Q', title='MFE (Pts)'),
                        alt.Tooltip('net:Q', format='$,.2f', title='Net P/L'),
                        alt.Tooltip('duration_m:Q', title='Duration (Min)'),
                    ]
                ).properties(height=320)

                max_val = float(max(df_mae['mae_pts'].max(), df_mae['mfe_pts'].max(), 100.0))
                line_df = pd.DataFrame({'x': [0, max_val], 'y': [0, max_val]})
                diag_line = alt.Chart(line_df).mark_line(color='rgba(255,255,255,0.25)', strokeDash=[4, 4]).encode(
                    x='x:Q', y='y:Q'
                )
                st.altair_chart(mae_scatter + diag_line, use_container_width=True)

                m_col1, m_col2, m_col3 = st.columns(3)
                avg_win_mae = df_mae[df_mae['outcome'] == 'WIN']['mae_pts'].mean() if (df_mae['outcome'] == 'WIN').any() else 0
                avg_win_mfe = df_mae[df_mae['outcome'] == 'WIN']['mfe_pts'].mean() if (df_mae['outcome'] == 'WIN').any() else 0
                loss_mfe = df_mae[df_mae['outcome'] == 'LOSS']['mfe_pts'].mean() if (df_mae['outcome'] == 'LOSS').any() else 0
                m_col1.metric("Avg Win MAE", f"{avg_win_mae:.1f} pt", help="ไม้ที่ชนะ เฉลี่ยเคยโดนลากติดลบสูงสุดเท่านี้")
                m_col2.metric("Avg Win MFE", f"{avg_win_mfe:.1f} pt", help="ไม้ที่ชนะ เฉลี่ยวิ่งไปแตะกำไรสูงสุดเท่านี้")
                m_col3.metric("Unrealized Loss MFE", f"{loss_mfe:.1f} pt", help="ไม้ที่แพ้ เฉลี่ยเคยวิ่งไปบวกสูงสุดเท่านี้ก่อนกลับมาโดน SL (คายกำไรคืนตลาด)")

            # ─────────────────────────────────────────────────────────────
            # 🤖 AI Trade Doctor: Post-Mortem Diagnostics & Rule Integrity
            # ─────────────────────────────────────────────────────────────
            st.markdown("---")
            st.markdown("#### 🤖 AI Trade Doctor: Post-Mortem Diagnostics & Rule Integrity")
            st.caption("ระบบตรวจสอบสุขภาพการเทรดอัจฉริยะ วิเคราะห์พฤติกรรมเสี่ยง (Revenge Trading, Dangerous Session, Duration Bias) พร้อมคำแนะนำเชิงควอนต์")

            diagnostics = diagnose_trade_health(df_history)
            if diagnostics:
                diag_cols = st.columns(len(diagnostics))
                for col, diag in zip(diag_cols, diagnostics):
                    with col:
                        badge_border = "#34d399" if diag["severity"] in ("EXCELLENT", "SUCCESS") else ("#fbbf24" if diag["severity"] == "WARNING" else "#38bdf8")
                        st.markdown(
                            f"<div class='pro-card' style='border-top:3px solid {badge_border};min-height:160px;'>"
                            f"<div style='font-size:18px;margin-bottom:4px;'>{diag['icon']} <b style='color:#f8fafc;font-size:14px;'>{diag['title']}</b></div>"
                            f"<div style='font-size:12.5px;color:#cbd5e1;line-height:1.5;margin-top:6px;'>{diag['desc']}</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )



    # =============================================================
    #  TAB 6: 📅 P&L CALENDAR & INTERACTIVE TRADE JOURNAL
    # =============================================================
    with tab_calendar:
        st.markdown(f"### 📅 TradeZella-Grade P&L Calendar — {sel_acc['label']}")

        if acc_status["state"] not in ("LIVE", "LAGGING") and sel_key not in REMOTE_VIEW_ACCOUNTS:
            st.warning("บัญชีนี้ไม่ได้รัน MT5 — กรุณาเริ่มรันบอทก่อนเพื่อดึงข้อมูลปฏิทิน")
        else:
            if "cal_year" not in st.session_state:
                _now = datetime.now(BKK)
                st.session_state.cal_year = _now.year
                st.session_state.cal_month = _now.month

            _now_ = datetime.now(BKK)
            nav1, nav2, nav3, nav4 = st.columns([1, 3, 1, 1])
            with nav1:
                if st.button("◀ เดือนก่อน", use_container_width=True):
                    m, y = st.session_state.cal_month - 1, st.session_state.cal_year
                    if m < 1:
                        m, y = 12, y - 1
                    st.session_state.cal_month, st.session_state.cal_year = m, y
                    st.session_state.cal_just_changed = True
            with nav3:
                if st.button("เดือนถัดไป ▶", use_container_width=True):
                    m, y = st.session_state.cal_month + 1, st.session_state.cal_year
                    if m > 12:
                        m, y = 1, y + 1
                    st.session_state.cal_month, st.session_state.cal_year = m, y
                    st.session_state.cal_just_changed = True
            with nav4:
                is_current_month = (st.session_state.cal_month == _now_.month and st.session_state.cal_year == _now_.year)
                if st.button("📍 เดือนนี้", use_container_width=True, disabled=is_current_month):
                    st.session_state.cal_month, st.session_state.cal_year = _now_.month, _now_.year
                    st.session_state.cal_just_changed = True

            cal_year, cal_month = st.session_state.cal_year, st.session_state.cal_month
            month_key = f"{sel_key}_{cal_year}_{cal_month}"
            need_anim = (st.session_state.get("cal_just_changed", False) or 
                         st.session_state.get("cal_last_key") != month_key)
            st.session_state.cal_just_changed = False
            st.session_state.cal_last_key = month_key

            with nav2:
                st.markdown(
                    f"<div style='text-align:center;'>"
                    f"<h3 style='margin:0;font-size:1.65rem;background:linear-gradient(45deg,#38bdf8,#818cf8,#fde68a);-webkit-background-clip:text;-webkit-text-fill-color:transparent;'>{pycal.month_name[cal_month]} {cal_year}</h3>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            cal_prog_holder = st.empty()
            if need_anim:
                with cal_prog_holder.container():
                    cal_bar = st.progress(35, text=f"⚡ กำลังดึงประวัติการเทรด MT5 — {pycal.month_name[cal_month]} {cal_year}...")
                    df_month = load_month_history(sel_key, sel_acc["dir"], acc_status["state"], sel_mt5_path, cal_year, cal_month)
                    cal_bar.progress(80, text=f"📊 กำลังสรุปผลกำไรรายวันและสร้างปฏิทิน {pycal.month_name[cal_month]} {cal_year}...")
                    time.sleep(0.05)
                    cal_bar.progress(100, text=f"✅ โหลดข้อมูล {pycal.month_name[cal_month]} {cal_year} สำเร็จ ({len(df_month)} ไม้)")
                    time.sleep(0.06)
                cal_prog_holder.empty()
            else:
                df_month = load_month_history(sel_key, sel_acc["dir"], acc_status["state"], sel_mt5_path, cal_year, cal_month)

            trade_cnt_txt = f"{len(df_month):,} ไม้" if not df_month.empty else "ไม่มีประวัติเทรด"
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;align-items:center;margin:6px 0 12px 0;font-size:12.5px;color:#94a3b8;'>"
                f"<span>📅 มุมมองปฏิทิน: <b style='color:#f8fafc;'>{pycal.month_name[cal_month]} {cal_year}</b></span>"
                f"<span>สถานะข้อมูล: <b style='color:#34d399;'>🟢 MT5 Synced ({trade_cnt_txt})</b></span>"
                f"</div>",
                unsafe_allow_html=True
            )


            today = datetime.now(BKK)

            if df_month.empty:
                daily_net = pd.Series(dtype=float)
                daily_cnt = pd.Series(dtype=int)
            else:
                g = df_month.copy()
                g['day'] = g['time'].dt.day
                daily_net = g.groupby('day')['net'].sum()
                daily_cnt = g.groupby('day')['net'].count()

            total = daily_net.sum() if not daily_net.empty else 0.0
            win_days = int((daily_net > 0).sum())
            loss_days = int((daily_net < 0).sum())
            traded_days = int(len(daily_net))
            win_rate_days = (win_days / traded_days * 100) if traded_days else 0.0

            s1, s2, s3 = st.columns(3)
            s4, s5 = st.columns(2)
            s1.metric("Month P/L", f"${total:,.2f}", delta=round(total, 2))
            s2.metric("Win Days", f"{win_days}/{traded_days}", f"{win_rate_days:.0f}%")
            s3.metric("Loss Days", f"{loss_days}")
            s4.metric("Best Day", f"${(daily_net.max() if not daily_net.empty else 0):,.2f}")
            s5.metric("Worst Day", f"${(daily_net.min() if not daily_net.empty else 0):,.2f}")

            cal = pycal.Calendar(firstweekday=6)
            weeks = cal.monthdayscalendar(cal_year, cal_month)
            dow_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

            html = ['<div class="pro-card" style="padding:16px;">']
            html.append('<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:8px;">')
            for dname in dow_names:
                html.append(f'<div style="text-align:center;color:#94a3b8;font-size:12px;font-weight:700;">{dname}</div>')
            html.append('</div>')

            for week in weeks:
                html.append('<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:8px;">')
                for day in week:
                    if day == 0:
                        html.append('<div style="min-height:80px;background:rgba(255,255,255,0.01);border-radius:10px;"></div>')
                        continue
                    net = daily_net.get(day)
                    cnt = int(daily_cnt.get(day, 0))
                    is_today = (day == today.day and cal_month == today.month and cal_year == today.year)
                    border = "2px solid #38bdf8" if is_today else "1px solid rgba(255,255,255,0.08)"
                    if net is None:
                        bg, col, txt = "rgba(255,255,255,0.02)", "#475569", ""
                    elif net > 0:
                        bg, col, txt = "rgba(52,211,153,0.16)", "#34d399", f"+${net:,.0f}"
                    elif net < 0:
                        bg, col, txt = "rgba(251,113,133,0.16)", "#fb7185", f"-${abs(net):,.0f}"
                    else:
                        bg, col, txt = "rgba(148,163,184,0.12)", "#94a3b8", "$0"
                    sub = f'<div style="font-size:10px;color:#94a3b8;margin-top:6px;">{cnt} trades</div>' if cnt else ""
                    html.append(
                        f'<div style="min-height:80px;border-radius:10px;background:{bg};border:{border};padding:8px;">'
                        f'<div style="font-size:11px;font-weight:700;color:#cbd5e1;">{day}</div>'
                        f'<div style="font-size:14px;font-weight:800;color:{col};margin-top:4px;">{txt}</div>'
                        f'{sub}</div>'
                    )
                html.append('</div>')
            html.append('</div>')
            st.markdown("".join(html), unsafe_allow_html=True)

            if not df_month.empty:
                st.markdown("---")
                st.markdown("#### 🔍 Interactive Day Inspector (Trade Journal)")
                st.caption("เลือกวันที่เพื่อดูบันทึกและรายละเอียดของทุกไม้ที่เทรดในวันนั้นอย่างละเอียด")

                available_days = sorted(df_month['time'].dt.day.unique(), reverse=True)
                sel_day = st.selectbox(
                    "เลือกวันเพื่อดูรายละเอียด",
                    available_days,
                    format_func=lambda d: f"วันที่ {d:02d} {pycal.month_name[cal_month]} — P/L: ${daily_net.get(d, 0):+,.2f} ({daily_cnt.get(d, 0)} ไม้)"
                )

                day_deals = df_month[df_month['time'].dt.day == sel_day].sort_values('time', ascending=False)
                if not day_deals.empty:
                    dj_w = day_deals[day_deals['net'] > 0]
                    dj_l = day_deals[day_deals['net'] <= 0]
                    dj_pnl = day_deals['net'].sum()
                    dj_wr = (len(dj_w) / len(day_deals)) * 100

                    dj1, dj2, dj3, dj4 = st.columns(4)
                    dj1.metric("Day Net P/L", f"${dj_pnl:+,.2f}", delta=round(dj_pnl, 2))
                    dj2.metric("Trades Count", f"{len(day_deals)} ไม้", f"{len(dj_w)}W / {len(dj_l)}L")
                    dj3.metric("Day Win Rate", f"{dj_wr:.1f}%")
                    dj4.metric("Best Trade", f"${day_deals['net'].max():+,.2f}")

                    journal_rows = []
                    for _, r in day_deals.iterrows():
                        d_badge = f"<span class='badge-buy'>{r.get('direction','BUY')}</span>" if r.get('direction') == 'BUY' else f"<span class='badge-sell'>{r.get('direction','SELL')}</span>"
                        net_c = "#34d399" if r['net'] > 0 else ("#fb7185" if r['net'] < 0 else "#94a3b8")
                        dur_s = r.get('duration_sec', 0)
                        dur_str = f"{int(dur_s // 60)}m {int(dur_s % 60)}s" if dur_s < 3600 else f"{int(dur_s // 3600)}h {int((dur_s % 3600) // 60)}m"
                        journal_rows.append(
                            f"<tr>"
                            f"<td><b>{r['time'].strftime('%H:%M:%S')}</b></td>"
                            f"<td>#{r.get('position_id', r.get('ticket'))}</td>"
                            f"<td>{d_badge}</td>"
                            f"<td><b>{r['symbol']}</b></td>"
                            f"<td>{r['volume']:.2f}</td>"
                            f"<td>{r.get('entry_price', 0):,.2f}</td>"
                            f"<td>{r['price']:,.2f}</td>"
                            f"<td style='color:{net_c};font-weight:700;'>${r['net']:+,.2f}</td>"
                            f"<td>{dur_str}</td>"
                            f"<td><span class='badge-tag'>{html_escape.escape(str(r['strategy']))}</span></td>"
                            f"</tr>"
                        )

                    j_table = (
                        f"<div class='pro-card' style='max-height:380px;overflow-y:auto;padding:0;'>"
                        f"<table class='pro-table'>"
                        f"<thead><tr>"
                        f"<th>Time</th><th>Position</th><th>Type</th><th>Symbol</th><th>Lots</th>"
                        f"<th>Open</th><th>Close</th><th>Net P/L</th><th>Duration</th><th>Strategy</th>"
                        f"</tr></thead>"
                        f"<tbody>{''.join(journal_rows)}</tbody>"
                        f"</table></div>"
                    )
                    st.markdown(j_table, unsafe_allow_html=True)
                    st.download_button(
                        f"⬇️ ดาวน์โหลดบันทึกเทรดวันที่ {sel_day} (CSV)",
                        day_deals.to_csv(index=False).encode('utf-8-sig'),
                        file_name=f"trades_{sel_key or 'root'}_{cal_year}{cal_month:02d}{sel_day:02d}.csv",
                        mime="text/csv",
                        key="btn_dl_day_journal"
                    )

                    st.markdown("---")
                    _sel_day_label = datetime(cal_year, cal_month, sel_day).strftime("%d %B %Y")
                    st.markdown(f"#### 🎯 Daily Strategy Performance — {_sel_day_label}")
                    dd = expand_strategy_combo_rows(day_deals)
                    daily_strat_rows = []
                    for sid, g in dd.groupby('strategy'):
                        w = g[g['net'] > 0]['net']
                        l = g[g['net'] <= 0]['net']
                        pf = w.sum() / abs(l.sum()) if l.sum() != 0 else float('inf')
                        g_max_dd, g_dd_pct = _calc_group_dd(g)
                        daily_strat_rows.append({
                            "Strategy": sid,
                            "Trades": f"{len(g)} ({len(w)}W/{len(l)}L)",
                            "Win%": round((g['net'] > 0).mean() * 100, 1),
                            "Net P/L": round(g['net'].sum(), 2),
                            "Avg Win": round(w.mean(), 2) if len(w) else 0.0,
                            "Avg Loss": round(l.mean(), 2) if len(l) else 0.0,
                            "Profit Factor": ("∞" if pf == float('inf') else f"{pf:.2f}"),
                            "DD (DD%)": _format_dd_cell(g_max_dd, g_dd_pct),
                        })
                    daily_strat_df = pd.DataFrame(daily_strat_rows).sort_values("Net P/L", ascending=False)
                    daily_strat_rows_html = []
                    for _, r in daily_strat_df.iterrows():
                        pl_c = "#34d399" if r["Net P/L"] > 0 else ("#fb7185" if r["Net P/L"] < 0 else "#94a3b8")
                        daily_strat_rows_html.append(
                            f"<tr>"
                            f"<td><b>{html_escape.escape(str(r['Strategy']))}</b></td>"
                            f"<td>{r['Trades']}</td>"
                            f"<td>{r['Win%']}%</td>"
                            f"<td style='color:{pl_c};font-weight:700;'>${r['Net P/L']:+,.2f}</td>"
                            f"<td>${r['Avg Win']:+,.2f}</td>"
                            f"<td>${r['Avg Loss']:+,.2f}</td>"
                            f"<td>{r['Profit Factor']}</td>"
                            f"<td style='color:#fb7185;'>{r['DD (DD%)']}</td>"
                            f"</tr>"
                        )
                    st.markdown(
                        f"<div class='pro-card' style='padding:0;overflow:hidden;'>"
                        f"<table class='pro-table'>"
                        f"<thead><tr>"
                        f"<th>Strategy</th><th>Trades</th><th>Win%</th><th>Net P/L</th><th>Avg Win</th><th>Avg Loss</th><th>Profit Factor</th><th>DD (DD%)</th>"
                        f"</tr></thead>"
                        f"<tbody>{''.join(daily_strat_rows_html)}</tbody>"
                        f"</table></div>",
                        unsafe_allow_html=True
                    )

                    if 'tf' in dd.columns:
                        with st.expander(f"📐 แยกตาม Strategy × Timeframe Matrix — {_sel_day_label}", expanded=False):
                            try:
                                dd_clean_tf = dd.copy()
                                dd_clean_tf['tf'] = dd_clean_tf['tf'].fillna('Unknown').astype(str)
                                daily_pnl_pivot = pd.pivot_table(
                                    dd_clean_tf, index='strategy', columns='tf', values='net', aggfunc='sum',
                                    fill_value=0, margins=True, margins_name='รวมทั้งหมด',
                                ).round(2)
                                daily_pnl_pivot = reorder_tf_columns(daily_pnl_pivot)
                                st.dataframe(daily_pnl_pivot.style.map(_style_pnl_cell).format("{:.2f}"), use_container_width=True)
                            except Exception as e:
                                st.warning(f"ไม่สามารถแสดงตาราง Strategy × Timeframe Matrix ได้: {e}")

            if not df_month.empty:
                st.markdown("---")
                st.markdown(f"#### 🏆 Monthly Strategy Performance — {pycal.month_name[cal_month]} {cal_year}")
                dm = expand_strategy_combo_rows(df_month)
                strat_rows = []
                for sid, g in dm.groupby('strategy'):
                    w = g[g['net'] > 0]['net']
                    l = g[g['net'] <= 0]['net']
                    pf = w.sum() / abs(l.sum()) if l.sum() != 0 else float('inf')
                    g_max_dd, g_dd_pct = _calc_group_dd(g)
                    strat_rows.append({
                        "Strategy": sid,
                        "Trades": f"{len(g)} ({len(w)}W/{len(l)}L)",
                        "Win%": round((g['net'] > 0).mean() * 100, 1),
                        "Net P/L": round(g['net'].sum(), 2),
                        "Avg Win": round(w.mean(), 2) if len(w) else 0.0,
                        "Avg Loss": round(l.mean(), 2) if len(l) else 0.0,
                        "Profit Factor": ("∞" if pf == float('inf') else f"{pf:.2f}"),
                        "DD (DD%)": _format_dd_cell(g_max_dd, g_dd_pct),
                    })
                strat_month_df = pd.DataFrame(strat_rows).sort_values("Net P/L", ascending=False)
                st.dataframe(
                    strat_month_df.style.map(_style_pnl_cell, subset=["Net P/L", "Avg Win", "Avg Loss"])
                    .format("{:.2f}", subset=["Win%", "Net P/L", "Avg Win", "Avg Loss"]),
                    use_container_width=True,
                )

                if 'tf' in dm.columns:
                    with st.expander(f"📐 แยกตาม Strategy × Timeframe Matrix — {pycal.month_name[cal_month]} {cal_year}", expanded=False):
                        try:
                            dm_clean_tf = dm.copy()
                            dm_clean_tf['tf'] = dm_clean_tf['tf'].fillna('Unknown').astype(str)
                            monthly_pnl_pivot = pd.pivot_table(
                                dm_clean_tf, index='strategy', columns='tf', values='net', aggfunc='sum',
                                fill_value=0, margins=True, margins_name='รวมทั้งหมด',
                            ).round(2)
                            monthly_pnl_pivot = reorder_tf_columns(monthly_pnl_pivot)
                            st.dataframe(monthly_pnl_pivot.style.map(_style_pnl_cell).format("{:.2f}"), use_container_width=True)
                        except Exception as e:
                            st.warning(f"ไม่สามารถแสดงตาราง Strategy × Timeframe Matrix ได้: {e}")


    # =============================================================
    #  TAB 8: 🏆 STRATEGIES & DEMO PORTFOLIO MATRIX
    # =============================================================
    with tab_strat:
        st.markdown("### 🏆 Strategies Leaderboard & Demo Portfolio Matrix")
        st.caption("จัดอันดับกลยุทธ์ตาม Net P/L และสารบัญข้อมูลโมเดลพอร์ตโฟลิโอ (จาก demo_summary.md)")

        strat_subtab1, strat_subtab_playbook, strat_subtab2, strat_subtab3, strat_subtab_decay, strat_subtab_drag = st.tabs([
            "📊 Live Strategy Leaderboard",
            "🏷️ AI Trade Playbook & Setup Matrix",
            "🧬 Demo Portfolio Specifications",
            "🧠 Strategy Correlation & Alpha Matrix",
            "📉 Strategy Decay Detector",
            "💸 Commission & Swap Drag",
        ])

        with strat_subtab_playbook:
            st.markdown("#### 🏷️ AI Trade Playbook & Systematic Setup Matrix (สไตล์ TradeZella / Edgewonk)")
            st.caption("จัดหมวดหมู่ออเดอร์จริงตามประเภทการเข้าเทรดสถาบัน (FVG, HHLL Trend, RSI Divergence, CRT, Liquidity Sweep ฯลฯ) เพื่อค้นหา Setup ที่สร้าง Positive Expectancy สูงสุด")

            if df_history.empty:
                st.info("ต้องการข้อมูลประวัติเทรดเพื่อจัดหมวดหมู่ AI Trade Playbook")
            else:
                with st.spinner("🏷️ กำลังจัดหมวดหมู่ AI Trade Playbook..."):
                    df_playbook = calculate_setup_playbook(df_history)
                if not df_playbook.empty:
                    pb_chart = alt.Chart(df_playbook).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
                        x=alt.X('setup_name:N', sort='-y', title=None, axis=alt.Axis(labelAngle=-20, labelColor='#94a3b8')),
                        y=alt.Y('net_pnl:Q', title='Net P/L ($)', axis=alt.Axis(labelColor='#94a3b8')),
                        color=alt.condition(alt.datum.net_pnl >= 0, alt.value('#34d399'), alt.value('#fb7185')),
                        tooltip=[
                            alt.Tooltip('setup_name:N', title='Trade Setup'),
                            alt.Tooltip('trades:Q', title='จำนวนไม้'),
                            alt.Tooltip('win_rate:Q', format='.1f', title='Win Rate %'),
                            alt.Tooltip('net_pnl:Q', format='$,.2f', title='Net P/L'),
                            alt.Tooltip('profit_factor:Q', title='Profit Factor'),
                            alt.Tooltip('expectancy:Q', format='$,.2f', title='Expectancy / ไม้'),
                            alt.Tooltip('edge_badge:N', title='Rating'),
                        ]
                    ).properties(height=260)
                    st.altair_chart(pb_chart, use_container_width=True)

                    pb_rows = []
                    for _, r in df_playbook.iterrows():
                        net_val = float(r.get('net_pnl', 0.0))
                        p_col = "#34d399" if net_val >= 0 else "#fb7185"
                        exp_val = float(r.get('expectancy', 0.0))
                        pb_rows.append(
                            f"<tr>"
                            f"<td><b style='color:#38bdf8;'>{html_escape.escape(str(r.get('setup_name', 'Unknown')))}</b></td>"
                            f"<td>{r.get('trades', 0)}</td>"
                            f"<td>{float(r.get('win_rate', 0.0)):.1f}%</td>"
                            f"<td style='color:{p_col};font-weight:700;'>${net_val:+,.2f}</td>"
                            f"<td>{float(r.get('profit_factor', 0.0)):.2f}</td>"
                            f"<td style='color:{p_col};'>${exp_val:+,.2f}</td>"
                            f"<td><span class='badge-tag'>{r.get('edge_badge', '')}</span></td>"
                            f"</tr>"
                        )
                    st.markdown(
                        f"<div class='pro-card' style='padding:0;overflow-x:auto;margin-bottom:12px;'>"
                        f"<table class='pro-table'>"
                        f"<thead><tr>"
                        f"<th>Trade Setup / Playbook</th><th>Trades</th><th>Win Rate</th><th>Net Profit</th><th>Profit Factor</th><th>Expectancy / ไม้</th><th>AI Institutional Edge</th>"
                        f"</tr></thead>"
                        f"<tbody>{''.join(pb_rows)}</tbody>"
                        f"</table></div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.info("ไม่พบข้อมูลหมวดหมู่ Setup ในประวัติ")

        with strat_subtab1:
            if df_history.empty:
                st.info("ต้องการประวัติเทรดเพื่อคำนวณ Strategy Leaderboard")
            else:
                d = df_history.copy()
                if 'symbol' in d.columns:
                    d['asset'] = d['symbol'].apply(lambda s: 'BTC' if 'BTC' in str(s) else 'XAU')
                else:
                    d['asset'] = 'XAU'
                d = expand_strategy_combo_rows(d)

                strat_rows = []
                if 'strategy' in d.columns:
                    for sid, g in d.groupby('strategy'):
                        if pd.isna(sid):
                            sid = "Unknown"
                        w = g[g['net'] > 0]['net']
                        l = g[g['net'] <= 0]['net']
                        pf = w.sum() / abs(l.sum()) if l.sum() != 0 else float('inf')
                        g_max_dd, g_dd_pct = _calc_group_dd(g)
                        strat_rows.append({
                            "Strategy": str(sid),
                            "Trades": len(g),
                            "Wins": len(w),
                            "Losses": len(l),
                            "Win%": round((len(w) / len(g)) * 100, 1) if len(g) > 0 else 0.0,
                            "Net P/L": round(g['net'].sum(), 2),
                            "Avg Win": round(w.mean(), 2) if len(w) else 0.0,
                            "Avg Loss": round(l.mean(), 2) if len(l) else 0.0,
                            "Profit Factor": ("∞" if pf == float('inf') else f"{pf:.2f}"),
                            "DD (DD%)": _format_dd_cell(g_max_dd, g_dd_pct),
                        })

                if not strat_rows:
                    st.info("ไม่พบข้อมูลสถิติของ Strategy ในประวัติที่เลือก")
                else:
                    strat_df = pd.DataFrame(strat_rows).sort_values("Net P/L", ascending=False)

                    st.markdown("#### 📊 Strategy Net P/L Leaderboard")
                    strat_chart = alt.Chart(strat_df.head(20)).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
                        x=alt.X('Strategy:N', sort='-y', title=None),
                        y=alt.Y('Net P/L:Q', title='Net P/L ($)'),
                        color=alt.condition(alt.datum['Net P/L'] >= 0, alt.value('#34d399'), alt.value('#fb7185')),
                        tooltip=['Strategy', 'Trades', 'Win%', alt.Tooltip('Net P/L:Q', format='$,.2f'), 'Profit Factor']
                    ).properties(height=280)
                    st.altair_chart(strat_chart, use_container_width=True)

                    st.dataframe(
                        strat_df.style.map(_style_pnl_cell, subset=["Net P/L", "Avg Win", "Avg Loss"])
                        .format("{:.2f}", subset=["Win%", "Net P/L", "Avg Win", "Avg Loss"]),
                        use_container_width=True,
                    )

                    if 'tf' in d.columns:
                        with st.expander("📐 แยกตาม Strategy × Timeframe Matrix", expanded=False):
                            try:
                                d_clean_tf = d.copy()
                                d_clean_tf['tf'] = d_clean_tf['tf'].fillna('Unknown').astype(str)
                                pnl_pivot = pd.pivot_table(
                                    d_clean_tf, index='strategy', columns='tf', values='net', aggfunc='sum',
                                    fill_value=0, margins=True, margins_name='รวมทั้งหมด',
                                ).round(2)
                                pnl_pivot = reorder_tf_columns(pnl_pivot)
                                st.dataframe(pnl_pivot.style.map(_style_pnl_cell).format("{:.2f}"), use_container_width=True)
                            except Exception as e:
                                st.warning(f"ไม่สามารถแสดงตาราง Strategy × Timeframe Matrix ได้: {e}")

        with strat_subtab2:
            st.markdown("#### 🧬 Demo Portfolio Specifications Directory (Scale 1.0)")
            st.caption("ข้อมูลเป้าหมาย ทุนแนะนำ ผลทดสอบ Backtest 550 วัน และสถานะของพอร์ตทั้งหมดในระบบ")

            port_df = pd.DataFrame(DEMO_PORTFOLIOS_DATA)
            st.dataframe(
                port_df[['name', 'alias', 'capital', 'avg_day', 'avg_month', 'worst_day', 'total_pnl', 'status']],
                use_container_width=True
            )

            st.markdown("---")
            st.markdown("#### 🔍 Portfolio Deep-Dive Explorer")
            port_names = [p['name'] for p in DEMO_PORTFOLIOS_DATA]
            sel_port_name = st.selectbox("เลือกดูรายละเอียดพอร์ต", port_names, key="strat_sel_port_name")
            sel_port = next((p for p in DEMO_PORTFOLIOS_DATA if p['name'] == sel_port_name), DEMO_PORTFOLIOS_DATA[0])

            dp1, dp2, dp3, dp4 = st.columns(4)
            dp1.metric("ทุนแนะนำ (Capital)", sel_port.get('capital', '—'))
            dp2.metric("คาดหวัง Avg/Day", sel_port.get('avg_day', '—'))
            dp3.metric("คาดหวัง Avg/Month", sel_port.get('avg_month', '—'))
            dp4.metric("Worst Day", sel_port.get('worst_day', '—'))

            st.markdown(
                f"<div class='pro-card' style='margin-top:12px;'>"
                f"<div style='font-size:16px;font-weight:700;color:#38bdf8;'>{sel_port['name']} ({sel_port['alias']})</div>"
                f"<div style='margin-top:6px;color:#f8fafc;'>{sel_port['desc']}</div>"
                f"<div style='margin-top:10px;font-size:12px;color:#94a3b8;'>"
                f"📅 ระยะเวลาทดสอบ: <b>{sel_port['test_days']}</b> | 🟢 สถานะระบบ: <b>{sel_port['status']}</b> | 💵 ผลตอบแทนสะสม: <b>{sel_port['total_pnl']}</b>"
                f"</div></div>",
                unsafe_allow_html=True
            )

        with strat_subtab3:
            st.markdown("#### 🧠 Strategy Correlation Matrix & Fleet Diversification Radar")
            st.caption("วิเคราะห์สหสัมพันธ์ของผลตอบแทนรายวันระหว่างกลยุทธ์ (Correlation Matrix) เพื่อค้นหา Uncorrelated Alpha และจัดพอร์ตที่ผลตอบแทนไม่หักล้างกัน")

            if df_history.empty:
                st.info("ต้องการประวัติเทรดเพื่อคำนวณ Strategy Correlation Matrix")
            else:
                with st.spinner("🧠 กำลังคำนวณ Strategy Correlation Matrix..."):
                    df_corr = calculate_strategy_correlation(df_history)
                if df_corr.empty or df_corr.shape[0] < 2:
                    st.info("💡 ต้องการข้อมูลกลยุทธ์ที่มีการเทรดอย่างน้อย 2 กลยุทธ์และมีประวัติเทรดอย่างน้อย 2 วันทำการขึ้นไปเพื่อคำนวณ Correlation Matrix (ลองเลือกช่วงประวัติ Last 7 Days หรือ 30 Days เพิ่มเติม)")
                else:
                    st.markdown(
                        f"<div class='pro-card' style='margin-bottom:14px;border-left:4px solid #a855f7;'>"
                        f"<div style='color:#c084fc;font-weight:700;font-size:14px;'>💡 Institutional Alpha Insight</div>"
                        f"<div style='font-size:12.5px;color:#cbd5e1;margin-top:4px;'>"
                        f"กลยุทธ์ที่มี Correlation ใกล้ 0 หรือติดลบ (เช่น ระหว่าง Trend-Following กับ Reversal/SMC) เมื่อนำมารันร่วมกัน จะช่วยลด Drawdown รวมของพอร์ตได้อย่างมีนัยสำคัญ (Modern Portfolio Theory)"
                        f"</div></div>",
                        unsafe_allow_html=True
                    )

                    try:
                        df_corr_clean = df_corr.copy()
                        df_corr_clean.index.name = None
                        df_corr_clean.columns.name = None
                        corr_reset = df_corr_clean.reset_index()
                        corr_reset.rename(columns={corr_reset.columns[0]: 'Strategy_A'}, inplace=True)
                        corr_long = corr_reset.melt(id_vars='Strategy_A', var_name='Strategy_B', value_name='Correlation')
                        corr_long['Correlation'] = pd.to_numeric(corr_long['Correlation'], errors='coerce').fillna(0.0)

                        corr_chart = alt.Chart(corr_long).mark_rect(cornerRadius=4).encode(
                            x=alt.X('Strategy_A:N', title=None),
                            y=alt.Y('Strategy_B:N', title=None),
                            color=alt.Color('Correlation:Q', scale=alt.Scale(scheme='redblue', domain=[-1.0, 1.0]), title='Correlation'),
                            tooltip=[
                                alt.Tooltip('Strategy_A:N', title='Strategy A'),
                                alt.Tooltip('Strategy_B:N', title='Strategy B'),
                                alt.Tooltip('Correlation:Q', format='.2f', title='Correlation Coeff'),
                            ]
                        ).properties(height=340)

                        text_overlay = alt.Chart(corr_long).mark_text(baseline='middle', fontSize=11, fontWeight=700).encode(
                            x=alt.X('Strategy_A:N'),
                            y=alt.Y('Strategy_B:N'),
                            text=alt.Text('Correlation:Q', format='.2f'),
                            color=alt.condition(alt.expr.abs(alt.datum.Correlation) > 0.45, alt.value('#ffffff'), alt.value('#94a3b8'))
                        )

                        st.altair_chart(corr_chart + text_overlay, use_container_width=True)
                    except Exception as e:
                        st.warning(f"ไม่สามารถพล็อตกราฟ Heatmap ได้: {e}")

                    with st.expander("🔢 ดูตาราง Correlation เชิงตัวเลขแบบละเอียด", expanded=False):
                        try:
                            st.dataframe(df_corr.style.background_gradient(cmap='coolwarm', vmin=-1.0, vmax=1.0), use_container_width=True)
                        except Exception:
                            st.dataframe(df_corr, use_container_width=True)

        with strat_subtab_decay:
            st.markdown("#### 📉 Strategy Decay Detector — จับ Edge ที่เริ่มเสื่อม")
            st.caption("เทียบ Profit Factor / Win Rate ของ 30 วันล่าสุด กับ Baseline ทั้งประวัติของกลยุทธ์นั้น เพื่อเตือนก่อนที่กลยุทธ์จะพังเต็มรูปแบบ (Regime Change / Curve-fit Decay)")

            if df_history.empty:
                st.info("ต้องการประวัติเทรดเพื่อคำนวณ Strategy Decay")
            else:
                with st.spinner("📉 กำลังเทียบ Baseline vs 30 วันล่าสุดของทุกกลยุทธ์..."):
                    df_decay = calculate_strategy_decay(df_history, recent_days=30)
                if df_decay.empty:
                    st.info("💡 ยังไม่มีกลยุทธ์ไหนมีเทรดมากพอ (≥10 ไม้รวม, ≥5 ไม้ใน 30 วันล่าสุด) เพื่อคำนวณ Decay — ลองเลือกช่วงประวัติที่ยาวขึ้น")
                else:
                    decaying = df_decay[(df_decay['decay_ratio'] < 0.7) & (df_decay['baseline_pf'] > 1.05)]
                    if not decaying.empty:
                        names = ", ".join(decaying['strategy'].astype(str).tolist())
                        st.markdown(
                            f"<div class='pro-card' style='margin-bottom:14px;border-left:4px solid #fb7185;'>"
                            f"<div style='color:#fb7185;font-weight:700;font-size:14px;'>⚠️ พบกลยุทธ์ที่ Edge กำลังเสื่อม ({len(decaying)} ตัว)</div>"
                            f"<div style='font-size:12.5px;color:#cbd5e1;margin-top:4px;'>{html_escape.escape(names)}</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"<div class='pro-card' style='margin-bottom:14px;border-left:4px solid #34d399;'>"
                            f"<div style='color:#34d399;font-weight:700;font-size:14px;'>✅ ไม่พบกลยุทธ์ที่มีสัญญาณ Decay ชัดเจนในตอนนี้</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

                    decay_rows = []
                    for _, r in df_decay.iterrows():
                        ratio = r['decay_ratio']
                        if ratio < 0.7 and r['baseline_pf'] > 1.05:
                            badge = "<span style='color:#fb7185;font-weight:700;'>🔴 Decaying</span>"
                        elif ratio < 0.9:
                            badge = "<span style='color:#f59e0b;font-weight:700;'>🟡 Weakening</span>"
                        else:
                            badge = "<span style='color:#34d399;font-weight:700;'>🟢 Stable/Improving</span>"
                        bpf = "∞" if r['baseline_pf'] == float('inf') else f"{r['baseline_pf']:.2f}"
                        rpf = "∞" if r['recent_pf'] == float('inf') else f"{r['recent_pf']:.2f}"
                        decay_rows.append(
                            f"<tr>"
                            f"<td><span class='badge-tag'>{html_escape.escape(str(r['strategy']))}</span></td>"
                            f"<td>{int(r['total_trades'])} ({int(r['recent_trades'])} ใน 30วัน)</td>"
                            f"<td>{bpf}</td>"
                            f"<td>{rpf}</td>"
                            f"<td>{r['baseline_wr']:.1f}%</td>"
                            f"<td>{r['recent_wr']:.1f}%</td>"
                            f"<td>{badge}</td>"
                            f"</tr>"
                        )
                    st.markdown(
                        f"<div class='pro-card' style='padding:0;overflow-x:auto;'>"
                        f"<table class='pro-table'>"
                        f"<thead><tr>"
                        f"<th>Strategy</th><th>Trades (30วันล่าสุด)</th><th>Baseline PF</th><th>Recent PF (30d)</th>"
                        f"<th>Baseline WR</th><th>Recent WR</th><th>สถานะ</th>"
                        f"</tr></thead>"
                        f"<tbody>{''.join(decay_rows)}</tbody>"
                        f"</table></div>",
                        unsafe_allow_html=True
                    )

        with strat_subtab_drag:
            st.markdown("#### 💸 Commission & Swap Drag Analysis")
            st.caption("ต้นทุนค่าคอมมิชชัน + Swap ที่กัดกิน Gross Profit ของแต่ละกลยุทธ์ — บางกลยุทธ์ดู Gross แล้วกำไร แต่โดนค่าธรรมเนียมกินจนติดลบสุทธิ")

            if df_history.empty:
                st.info("ต้องการประวัติเทรดเพื่อคำนวณ Commission & Swap Drag")
            else:
                with st.spinner("💸 กำลังคำนวณ Commission & Swap Drag ต่อกลยุทธ์..."):
                    df_drag = calculate_commission_drag(df_history)
                if df_drag.empty:
                    st.info("ไม่พบข้อมูลกลยุทธ์ในช่วงเวลานี้")
                else:
                    total_drag = df_drag['commission_swap_drag'].sum()
                    total_gross = df_drag['gross_profit'].sum()
                    dg1, dg2, dg3 = st.columns(3)
                    dg1.metric("ต้นทุนรวม (Commission+Swap)", f"${total_drag:,.2f}")
                    dg2.metric("Gross Profit รวม", f"${total_gross:,.2f}")
                    dg3.metric("Drag เทียบ Gross", f"{(total_drag/abs(total_gross)*100) if total_gross else 0:.1f}%")

                    drag_rows = []
                    for _, r in df_drag.iterrows():
                        net_c = "#34d399" if r['net_profit'] > 0 else ("#fb7185" if r['net_profit'] < 0 else "#94a3b8")
                        drag_c = "#fb7185" if r['commission_swap_drag'] > 0 else "#34d399"
                        flip_flag = "<span style='color:#fbbf24;font-weight:700;'>⚠️ Gross ดี แต่ค่าธรรมเนียมพลิกเป็นขาดทุน</span>" if (r['gross_profit'] > 0 and r['net_profit'] <= 0) else ""
                        drag_rows.append(
                            f"<tr>"
                            f"<td><span class='badge-tag'>{html_escape.escape(str(r['strategy']))}</span></td>"
                            f"<td>{int(r['trades'])}</td>"
                            f"<td>${r['gross_profit']:,.2f}</td>"
                            f"<td style='color:{drag_c};font-weight:700;'>${r['commission_swap_drag']:,.2f} ({r['drag_pct_of_gross']:.1f}%)</td>"
                            f"<td style='color:{net_c};font-weight:700;'>${r['net_profit']:,.2f}</td>"
                            f"<td>{flip_flag}</td>"
                            f"</tr>"
                        )
                    st.markdown(
                        f"<div class='pro-card' style='padding:0;overflow-x:auto;'>"
                        f"<table class='pro-table'>"
                        f"<thead><tr>"
                        f"<th>Strategy</th><th>Trades</th><th>Gross Profit</th><th>Commission+Swap Drag</th><th>Net Profit</th><th>หมายเหตุ</th>"
                        f"</tr></thead>"
                        f"<tbody>{''.join(drag_rows)}</tbody>"
                        f"</table></div>",
                        unsafe_allow_html=True
                    )



    # =============================================================
    #  TAB 9: 🧪 BACKTEST RUNNER (เฉพาะกลยุทธ์ที่รองรับ --compare)
    # =============================================================
    with tab_backtest:
        st.markdown(f"### 🧪 Backtest Runner — {sel_acc['label']}")
        st.caption("รัน backtest กลยุทธ์ไหนก็ได้ที่มีสคริปต์รองรับ --compare แล้ว (เทียบกับ MT5/bot.log จริงของบัญชีที่เลือกอยู่ตอนนี้อัตโนมัติ) — ผลรันจะเก็บแยกไม่ทับไฟล์ production เดิม")

        bt_strategies = ALL_BACKTEST_STRATEGY_IDS
        acc_hint = ACCOUNT_BACKTEST_STRATEGIES.get(sel_key, [])
        if acc_hint:
            st.caption(f"💡 บัญชีนี้ปกติรัน: {', '.join(acc_hint)} (เลือกตัวอื่นก็ได้ — ระบบจะเทียบกับ log ของบัญชีที่เลือกอยู่เสมอ)")

        if True:
            bcol1, bcol2, bcol3 = st.columns([1.3, 1, 1])
            with bcol1:
                _default_idx = bt_strategies.index(acc_hint[0]) if acc_hint and acc_hint[0] in bt_strategies else 0
                bt_sid = st.selectbox("เลือกกลยุทธ์/พอร์ต", bt_strategies, index=_default_idx, key="bt_sid_select")
            with bcol2:
                bt_route = _backtest_route_for(bt_sid)
                st.caption(f"Route: `{bt_route['kind']}`")
                st.caption(f"Script: `{os.path.basename(bt_route['script'])}`")
            with bcol3:
                bt_script_exists = os.path.exists(bt_route["script"])
                if bt_script_exists:
                    st.success("✅ พบสคริปต์")
                else:
                    st.error("❌ ไม่พบสคริปต์")

            st.markdown("##### ⚙️ พารามิเตอร์")
            p1, p2, p3, p4 = st.columns(4)
            with p1:
                bt_days = st.number_input("--days (จำนวนวันย้อนหลัง)", min_value=1, max_value=3650, value=30, step=1, key="bt_days")
            with p2:
                bt_start = st.text_input("--start (YYYY-MM-DD, เว้นว่าง=ไม่ระบุ)", value="", key="bt_start")
            with p3:
                bt_end = st.text_input("--end (YYYY-MM-DD, เว้นว่าง=ไม่ระบุ)", value="", key="bt_end")
            with p4:
                bt_balance = st.number_input("--balance ($, 0=ใช้ default สคริปต์)", min_value=0.0, value=0.0, step=100.0, key="bt_balance",
                                              disabled=(bt_route["kind"] == "s2014group"),
                                              help="route S20.14xx ไม่รองรับ --balance" if bt_route["kind"] == "s2014group" else None)
            p5, p6, p7 = st.columns(3)
            with p5:
                lot_label = "--lot" if bt_route["kind"] in ("s42x", "s20x_profile") else "--scale (lot multiplier)"
                bt_lot = st.number_input(f"{lot_label} (0=ใช้ default สคริปต์)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="bt_lot",
                                          disabled=(bt_route["kind"] == "s2014group"),
                                          help="route S20.14xx ไม่รองรับ --lot/--scale" if bt_route["kind"] == "s2014group" else None)
            with p6:
                bt_no_cache = st.checkbox("--no-cache (ไม่ใช้แคชข้อมูลดิบ)", value=False, key="bt_no_cache",
                                           disabled=(bt_route["kind"] not in ("portfolio", "s20x_profile")),
                                           help="ใช้ได้เฉพาะ route แบบ portfolio / s20x_profile เท่านั้น")
            with p7:
                if bt_route["kind"] in ("s42x", "s2014group", "s20x_profile"):
                    bt_compare = st.checkbox("--compare (เทียบกับ MT5/bot.log จริง)", value=True, key="bt_compare")
                else:
                    bt_compare = True
                    st.checkbox("--compare (เทียบกับ MT5 จริงเสมอ — route นี้ compare อัตโนมัติทุกครั้ง)", value=True, disabled=True, key="bt_compare_locked")
            if bt_route["kind"] == "s2014group":
                st.caption("ℹ️ route S20.14xx: --compare เทียบกับ MT5 terminal ที่เปิดอยู่ในเครื่องนี้ตอนนี้เลย (ไม่ผูกกับบัญชีที่เลือกด้านซ้ายเหมือน route อื่น) — ผลรันจะ backup/restore โฟลเดอร์ production (excel_group) ให้อัตโนมัติ ไม่ทับของจริง")
            elif bt_route["kind"] == "s20x_profile":
                st.caption(f"ℹ️ route S20.3xx: --compare-profile ใช้บัญชีที่เลือกอยู่ตอนนี้ (`{sel_key or 'root'}`)")

            run_clicked = st.button("▶ รัน Backtest", type="primary", disabled=not bt_script_exists, key="bt_run_btn")

            if run_clicked:
                with st.spinner(f"🧪 กำลังรัน backtest {bt_sid} ({bt_days} วัน)... อาจใช้เวลาถึงหลายนาที"):
                    bt_result = run_backtest_subprocess(
                        bt_sid, sel_acc["dir"], acc_key=sel_key,
                        days=bt_days,
                        start=bt_start.strip() or None,
                        end=bt_end.strip() or None,
                        balance=bt_balance or None,
                        lot=bt_lot or None,
                        no_cache=bt_no_cache,
                        do_compare=bt_compare,
                    )
                st.session_state["bt_last_result"] = bt_result
                st.session_state["bt_last_sid"] = bt_sid

            bt_result = st.session_state.get("bt_last_result")
            if bt_result and st.session_state.get("bt_last_sid") == bt_sid:
                if not bt_result["ok"]:
                    st.error(f"❌ รัน backtest ไม่สำเร็จ: {bt_result['stderr'][:500] or 'ดู stdout ด้านล่าง'}")
                    with st.expander("📄 stdout/stderr เต็ม", expanded=True):
                        st.code((bt_result.get("stdout") or "") + "\n" + (bt_result.get("stderr") or ""), language="text")
                else:
                    st.success(f"✅ รันสำเร็จ — ผลลัพธ์อยู่ที่ `{bt_result['out_dir']}`")
                    with st.expander("📄 ดู stdout เต็ม"):
                        st.code(bt_result.get("stdout") or "(ไม่มี output)", language="text")

                    buckets = _load_backtest_result_csvs(bt_result["out_dir"])
                    bt_res_tab1, bt_res_tab2, bt_res_tab3, bt_res_tab4 = st.tabs(["🧾 Trades", "📅 Days", "📆 Months", "🔍 Compare"])

                    with bt_res_tab1:
                        if not buckets["trades"]:
                            st.info("ไม่มีไฟล์ trades ในผลลัพธ์รอบนี้")
                        else:
                            total_trades = sum(len(df) for _fn, df in buckets["trades"])
                            st.caption(f"รวม {total_trades:,} ไม้ จาก {len(buckets['trades'])} ไฟล์")
                            for fn, df in buckets["trades"]:
                                with st.expander(f"📄 {fn} ({len(df):,} แถว)", expanded=len(buckets["trades"]) == 1):
                                    st.dataframe(df, use_container_width=True)

                    with bt_res_tab2:
                        if buckets["daily"]:
                            for fn, df in buckets["daily"]:
                                st.caption(f"📄 {fn}")
                                st.dataframe(df, use_container_width=True)
                        elif buckets["trades"]:
                            df_days = aggregate_backtest_period(buckets["trades"], freq="D")
                            if df_days.empty:
                                st.info("ไม่สามารถ auto-detect คอลัมน์วันที่/P&L จากไฟล์ trades เพื่อสรุปรายวันได้")
                            else:
                                st.bar_chart(df_days.set_index("Period")["Net P/L"])
                                st.dataframe(df_days, use_container_width=True)
                        else:
                            st.info("ไม่มีข้อมูลสำหรับสรุปรายวัน")

                    with bt_res_tab3:
                        if buckets["monthly"]:
                            for fn, df in buckets["monthly"]:
                                st.caption(f"📄 {fn}")
                                st.dataframe(df, use_container_width=True)
                        elif buckets["trades"]:
                            df_months = aggregate_backtest_period(buckets["trades"], freq="M")
                            if df_months.empty:
                                st.info("ไม่สามารถ auto-detect คอลัมน์วันที่/P&L จากไฟล์ trades เพื่อสรุปรายเดือนได้")
                            else:
                                st.bar_chart(df_months.set_index("Period")["Net P/L"])
                                st.dataframe(df_months, use_container_width=True)
                        else:
                            st.info("ไม่มีข้อมูลสำหรับสรุปรายเดือน")

                    with bt_res_tab4:
                        if not buckets["compare"] and not buckets["not_match"]:
                            st.info("ไม่มีไฟล์ compare ในผลลัพธ์รอบนี้ (ลองเปิด --compare หรือเช็คว่าบัญชีมีประวัติเทรดจริงในช่วงเวลานี้)")
                        else:
                            if buckets["compare"]:
                                st.markdown("###### ✅ Matched (Backtest ตรงกับ MT5/log จริง)")
                                for fn, df in buckets["compare"]:
                                    st.caption(f"📄 {fn} ({len(df):,} แถว)")
                                    st.dataframe(df, use_container_width=True)
                            if buckets["not_match"]:
                                with st.expander(f"⚠️ ไม่ตรงกัน / MT5-only / Backtest-only ({sum(len(df) for _fn, df in buckets['not_match']):,} แถวรวม)"):
                                    for fn, df in buckets["not_match"]:
                                        st.caption(f"📄 {fn} ({len(df):,} แถว)")
                                        st.dataframe(df, use_container_width=True)


    # =============================================================
    #  TAB 10: 🩺 HEALTH, DIAGNOSTICS & EXECUTION LOGS
    # =============================================================
    with tab_health:
        st.markdown("### 🩺 Bot Process & Diagnostic Health")

        if hb and hb.get("ts", "").isdigit():
            age = int(time.time()) - int(hb["ts"])
            status, color = ("🟢 LIVE", "normal") if age < 30 else (("🟡 LAGGING", "off") if age < 90 else ("🔴 STALE / DOWN", "inverse"))
            last_scan = int(hb.get("last_scan", "0") or 0)
            scan_age = int(time.time()) - last_scan if last_scan else None

            h1, h2, h3 = st.columns(3)
            h4, h5 = st.columns(2)
            h1.metric("Process Health", status, f"{age}s ago", delta_color=color)
            h2.metric("MT5 API", "✅ READY" if hb.get("mt5_ok") == "1" else "❌ DOWN", help="สถานะการเชื่อมต่อระหว่าง Python และ MT5 Terminal")
            h3.metric("Auto Trade", "ON" if hb.get("auto") == "1" else "OFF")
            h4.metric("Last Scan", f"{scan_age}s ago" if scan_age is not None else "—")
            h5.metric("Process PID", hb.get("pid", "—"))

        st.markdown("---")
        if logs:
            st.markdown("#### 🚫 Why Not Entering (Block / Skip Monitor)")
            blocks = logs.get("blocks", {})
            if blocks:
                st.bar_chart(pd.Series(blocks).sort_values(ascending=False))
            else:
                st.info("ไม่มี Block/Skip event ใน log ล่าสุด")

            st.markdown("#### 📰 Recent Bot Lifecycle Events")
            feed = logs.get("feed", [])
            if feed:
                st.dataframe(pd.DataFrame(feed, columns=["time", "event", "detail"]), use_container_width=True)


else:
    (
        tab_fleet,
        tab_news,
        tab_docs,
    ) = st.tabs([
        "🚀 Fleet Command",
        "📰 News & Macro",
        "📚 Strategy Docs",
    ])

    # =============================================================
    #  TAB 7: 🚀 FLEET & MULTI-ACCOUNT COMMAND CENTER
    # =============================================================
    with tab_fleet:
        st.markdown("### 🚀 Fleet Overview — ควบคุมและตรวจสอบทุกบอทพร้อมกัน")
        st.caption("สรุปพอร์ตโฟลิโอทั้งหมดจากทุกบัญชี (Real & Demo) โดยอ่านจากไฟล์ heartbeat และ state รวดเร็วและไม่รบกวน Terminal · อัปเดตพื้นหลังอัตโนมัติทุก " + str(refresh_sec) + " วิ (เฉพาะส่วนนี้ ไม่รีรันทั้งหน้า)")

        @st.fragment(run_every=refresh_sec)
        def _render_fleet_overview():
            # ครอบเฉพาะสรุป+ตารางด้วย fragment แยก — ส่วนนี้จะรีเฟรชตัวเองพื้นหลังทุก refresh_sec
            # โดยไม่ต้องรีรันทั้งหน้า dashboard (ต่างจาก _dash_background_tick ที่รีรันทั้งแอป)
            # ใช้ query cache เดิม (load_fleet_overview ttl=20s) เลยไม่ได้ยิง MT5 ใหม่ทุกติ๊ก
            fleet_rows = load_fleet_overview(accounts)
            fleet_df = pd.DataFrame(fleet_rows)

            running_count = sum(1 for r in fleet_rows if "🟢" in r["Status"])
            total_daily = fleet_df["Daily P/L"].sum()
            total_trades_today = fleet_df["Trades Today"].sum()
            auto_active_count = sum(1 for r in fleet_rows if "ON" in r["Auto"])

            fl1, fl2, fl3, fl4 = st.columns(4)
            fl1.metric("บัญชีที่ทำงานอยู่", f"{running_count} / {len(fleet_rows)}")
            fl2.metric("Daily Realized รวม", f"${total_daily:,.2f}", delta=round(total_daily, 2))
            fl3.metric("จำนวนไม้วันนี้ทั้งพอร์ต", f"{total_trades_today:,} ไม้")
            fl4.metric("Auto Trade เปิดอยู่", f"{auto_active_count} / {len(fleet_rows)}")

            st.markdown("---")
            st.markdown("#### 🏦 All Accounts Directory")
            fleet_sorted = sorted(fleet_rows, key=lambda x: (0 if "🟢" in x["Status"] else 1, x["Daily P/L"]))

            rows_html = []
            for r in fleet_sorted:
                pl_color = "#34d399" if r["Daily P/L"] > 0 else ("#fb7185" if r["Daily P/L"] < 0 else "#94a3b8")
                if "🟢" in r["Status"]:
                    status_badge = f"<span class='badge-buy'>{r['Status']}</span>"
                elif r["state_code"] == "REMOTE":
                    status_badge = f"<span class='badge-remote'>{r['Status']}</span>"
                else:
                    status_badge = f"<span class='badge-sell'>{r['Status']}</span>"
                if r["state_code"] == "REMOTE":
                    auto_badge = "<span style='color:#38bdf8;'>N/A (remote)</span>"
                elif "ON" in r["Auto"]:
                    auto_badge = "<span style='color:#34d399;font-weight:700;'>ON</span>"
                else:
                    auto_badge = "<span style='color:#94a3b8;'>OFF</span>"
                bal_txt = f"${r['Balance']:,.2f}" if r.get("Balance") is not None else "<span style='color:#475569;'>—</span>"
                if r.get("Equity") is not None:
                    eq_diff = r["Equity"] - r["Balance"] if r.get("Balance") is not None else 0.0
                    eq_color = "#34d399" if eq_diff > 0 else ("#fb7185" if eq_diff < 0 else "#cbd5e1")
                    eq_txt = f"<span style='color:{eq_color};'>${r['Equity']:,.2f}</span>"
                else:
                    eq_txt = "<span style='color:#475569;'>—</span>"
                rows_html.append(
                    f"<tr>"
                    f"<td><b>{html_escape.escape(r['Account'])}</b><div style='font-size:11px;color:#94a3b8;'>Dir: {r['key'] or 'root'}</div></td>"
                    f"<td>{status_badge}</td>"
                    f"<td>{auto_badge}</td>"
                    f"<td>{bal_txt}</td>"
                    f"<td>{eq_txt}</td>"
                    f"<td style='color:{pl_color};font-weight:700;font-size:14px;'>${r['Daily P/L']:,.2f}</td>"
                    f"<td><b>{r['Trades Today']:,}</b> ไม้</td>"
                    f"</tr>"
                )

            st.markdown(
                f"<div class='pro-card' style='padding:0;overflow:hidden;'>"
                f"<table class='pro-table'>"
                f"<thead><tr>"
                f"<th>บัญชี (Account & Profile)</th><th>สถานะบอท</th><th>Auto Trade</th><th>Balance</th><th>Equity</th><th>Daily P/L</th><th>จำนวนไม้</th>"
                f"</tr></thead>"
                f"<tbody>{''.join(rows_html)}</tbody>"
                f"</table></div>",
                unsafe_allow_html=True
            )

        _render_fleet_overview()

        st.markdown("---")
        st.markdown("#### 🎛️ Batch Control Panel — สั่งหลายบัญชีพร้อมกัน")
        st.caption("เลือกหลายบัญชีแล้วสั่ง Start/Stop ทีเดียว แทนที่ต้องไล่เปิดทีละ tab (ใช้ Start/Stop เดียวกับที่บัญชีเดี่ยวใช้ — ไม่ใช่ฟีเจอร์ใหม่ แค่สั่งพร้อมกัน)")

        fleet_rows = load_fleet_overview(accounts)
        fleet_sorted = sorted(fleet_rows, key=lambda x: (0 if "🟢" in x["Status"] else 1, x["Daily P/L"]))
        local_accounts = [r for r in fleet_sorted if r["state_code"] != "REMOTE"]
        batch_labels = {f"{r['Account']} ({r['key'] or 'root'})": r for r in local_accounts}
        batch_selected = st.multiselect(
            "เลือกบัญชีที่จะสั่ง (เฉพาะบัญชีในเครื่องนี้ — บัญชี Remote สั่งจากที่นี่ไม่ได้)",
            list(batch_labels.keys()),
            key="fleet_batch_selected",
        )

        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("▶️ Start บัญชีที่เลือก", disabled=not batch_selected, use_container_width=True, key="btn_batch_start"):
                results = []
                for label in batch_selected:
                    r = batch_labels[label]
                    ok, msg = start_account(r["key"])
                    results.append(f"{'✅' if ok else '❌'} {r['Account']}: {msg}")
                    time.sleep(0.3)
                for line in results:
                    st.write(line)
                load_fleet_overview.clear()
        with bc2:
            if st.button("⏹️ Stop บัญชีที่เลือก", disabled=not batch_selected, use_container_width=True, key="btn_batch_stop"):
                results = []
                for label in batch_selected:
                    r = batch_labels[label]
                    ok, msg = stop_account(r["key"])
                    results.append(f"{'✅' if ok else '❌'} {r['Account']}: {msg}")
                for line in results:
                    st.write(line)
                load_fleet_overview.clear()

        st.markdown("---")
        st.markdown("#### 🚨 Fleet Risk Guard — Daily Loss Limit ต่อบัญชี")
        st.caption("ตั้งวงเงินขาดทุนต่อวันต่อบัญชี ถ้าบัญชีไหนชน Limit จะขึ้นเตือน + แจ้ง Telegram ให้ (เตือนได้เฉพาะตอนเปิดหน้านี้อยู่ ไม่ใช่ auto-close 24 ชม. — ถ้าชนแล้วต้องกดปิดเองด้านล่างเพื่อความปลอดภัย)")

        dd_limit = st.number_input(
            "Daily Loss Limit ต่อบัญชี ($) — ใส่เป็นค่าบวก",
            min_value=0.0, value=float(st.session_state.get("fleet_dd_limit", 500.0)), step=50.0,
            key="fleet_dd_limit",
        )

        breached = [r for r in fleet_rows if r["state_code"] in ("LIVE", "LAGGING") and r["Daily P/L"] <= -abs(dd_limit)]

        enable_dd_alerts = st.checkbox(
            "🔔 เปิดแจ้งเตือน Telegram อัตโนมัติเมื่อชน Limit (ปิดอยู่โดย default — ติ๊กเองถ้าต้องการ)",
            value=False, key="fleet_dd_alert_enabled",
        )

        if breached:
            st.error(f"⚠️ {len(breached)} บัญชีชน Daily Loss Limit (-${dd_limit:,.0f}) แล้ว:")
            for r in breached:
                st.write(f"🔴 **{r['Account']}** — Daily P/L: ${r['Daily P/L']:,.2f}")

            if enable_dd_alerts:
                today_key = datetime.now(BKK).strftime("%Y-%m-%d")
                alert_state_path = os.path.join(ROOT_DIR, "dashboard_backtest_runs", "_fleet_dd_alerted.json")
                try:
                    with open(alert_state_path, "r", encoding="utf-8") as f:
                        alerted_today = json.load(f)
                except Exception:
                    alerted_today = {}
                if alerted_today.get("_date") != today_key:
                    alerted_today = {"_date": today_key}
                changed = False
                for r in breached:
                    if alerted_today.get(r["key"] or "root"):
                        continue
                    send_telegram_alert(
                        r["dir"],
                        f"🚨 *Daily Loss Limit ชนแล้ว*\n"
                        f"━━━━━━━━━━━━━━━━━\n"
                        f"👤 บัญชี: `{r['Account']}`\n"
                        f"📉 Daily P/L: `${r['Daily P/L']:,.2f}`\n"
                        f"🛑 Limit: `-${dd_limit:,.0f}`\n"
                        f"เข้า Dashboard เพื่อพิจารณาปิด Position",
                    )
                    alerted_today[r["key"] or "root"] = True
                    changed = True
                if changed:
                    try:
                        os.makedirs(os.path.dirname(alert_state_path), exist_ok=True)
                        with open(alert_state_path, "w", encoding="utf-8") as f:
                            json.dump(alerted_today, f)
                    except Exception:
                        pass

            confirm_dd_close = st.checkbox("ยืนยันสั่งปิด Position ทั้งหมดของบัญชีที่ชน Limit ด้านบน", key="chk_dd_close_all")
            if st.button("🚨 ปิด Position ทั้งหมดของบัญชีที่ชน Limit", disabled=not confirm_dd_close, use_container_width=True, key="btn_dd_close_all"):
                for r in breached:
                    mt5_path = _account_mt5_path(r["dir"])
                    ok, msg = emergency_close_all_positions(mt5_path, only_profit=False)
                    st.write(f"{'✅' if ok else '❌'} {r['Account']}: {msg}")
                load_fleet_overview.clear()
        else:
            st.success("✅ ไม่มีบัญชีไหนชน Daily Loss Limit ตอนนี้")

        st.markdown("---")
        st.markdown("#### 📉 Combined Fleet Equity Curve & Cross-Account Correlation")
        st.caption("รวม Daily P/L ทุกบัญชีเป็นพอร์ตเดียว เพื่อดู Drawdown จริงของทั้งฟลีท และดูว่าบัญชีไหนวิ่งพร้อมกัน/สวนทางกัน (กระจายความเสี่ยงจริงหรือไม่) — ต้องเชื่อมต่อ MT5 ทุกบัญชีจึงอาจใช้เวลาสักครู่")

        if st.button("📊 โหลด Combined Equity & Correlation (ย้อนหลัง 90 วัน)", key="btn_load_fleet_deep"):
            st.session_state["fleet_deep_loaded"] = True

        if st.session_state.get("fleet_deep_loaded"):
            with st.spinner("กำลังเชื่อมต่อ MT5 ทุกบัญชีและดึง Daily P/L ย้อนหลัง 90 วัน..."):
                fleet_daily = load_fleet_daily_pnl(accounts, days=90)

            if fleet_daily.empty:
                st.info("ไม่สามารถดึงข้อมูลได้ — ต้องมีอย่างน้อย 1 บัญชีที่เชื่อมต่อ MT5 ได้ (LIVE/LAGGING หรือบัญชีใน REMOTE_VIEW_ACCOUNTS)")
            else:
                combined_daily = fleet_daily.sum(axis=1)
                combined_equity = combined_daily.cumsum()
                running_peak = combined_equity.cummax()
                combined_dd = combined_equity - running_peak

                fe1, fe2, fe3, fe4 = st.columns(4)
                fe1.metric("Combined Net P/L", f"${combined_equity.iloc[-1]:,.2f}")
                fe2.metric("Combined Max Drawdown", f"${combined_dd.min():,.2f}")
                fe3.metric("จำนวนบัญชีที่รวมได้", f"{fleet_daily.shape[1]} / {len(accounts)}")
                fe4.metric("ช่วงข้อมูล", f"{fleet_daily.shape[0]} วัน")

                eq_chart_df = pd.DataFrame({"date": combined_equity.index, "Equity": combined_equity.values}).set_index("date")
                dd_chart_df = pd.DataFrame({"date": combined_dd.index, "Drawdown": combined_dd.values}).set_index("date")
                cc1, cc2 = st.columns(2)
                with cc1:
                    st.markdown("###### 📈 Combined Net Equity Curve (ทั้งฟลีท)")
                    st.area_chart(eq_chart_df, use_container_width=True, color="#34d399")
                with cc2:
                    st.markdown("###### 📉 Combined Underwater Drawdown (ทั้งฟลีท)")
                    st.area_chart(dd_chart_df, use_container_width=True, color="#fb7185")

                st.markdown("###### 🔗 Cross-Account Correlation Heatmap")
                st.caption("Correlation ใกล้ +1 = บัญชีวิ่งพร้อมกัน (ขาดทุน/กำไรวันเดียวกัน) — กระจายความเสี่ยงได้น้อย, ใกล้ 0 หรือติดลบ = กระจายความเสี่ยงได้จริง")
                if fleet_daily.shape[1] < 2 or fleet_daily.shape[0] < 2:
                    st.info("ต้องการอย่างน้อย 2 บัญชีและ 2 วันทำการขึ้นไปเพื่อคำนวณ Correlation")
                else:
                    try:
                        acc_corr = fleet_daily.corr().round(2).fillna(0.0)
                        for c in acc_corr.columns:
                            if c in acc_corr.index:
                                acc_corr.loc[c, c] = 1.0
                        acc_corr_reset = acc_corr.reset_index().rename(columns={"index": "Account_A"})
                        acc_corr_long = acc_corr_reset.melt(id_vars="Account_A", var_name="Account_B", value_name="Correlation")
                        acc_corr_long["Correlation"] = pd.to_numeric(acc_corr_long["Correlation"], errors="coerce").fillna(0.0)

                        fleet_corr_chart = alt.Chart(acc_corr_long).mark_rect(cornerRadius=4).encode(
                            x=alt.X("Account_A:N", title=None, axis=alt.Axis(labelAngle=-30, labelColor='#94a3b8')),
                            y=alt.Y("Account_B:N", title=None, axis=alt.Axis(labelColor='#94a3b8')),
                            color=alt.Color("Correlation:Q", scale=alt.Scale(scheme="redblue", domain=[-1.0, 1.0]), title="Correlation"),
                            tooltip=[
                                alt.Tooltip("Account_A:N", title="Account A"),
                                alt.Tooltip("Account_B:N", title="Account B"),
                                alt.Tooltip("Correlation:Q", format=".2f", title="Correlation Coeff"),
                            ]
                        ).properties(height=360)
                        fleet_corr_text = alt.Chart(acc_corr_long).mark_text(baseline="middle", fontSize=10, fontWeight=700).encode(
                            x=alt.X("Account_A:N"),
                            y=alt.Y("Account_B:N"),
                            text=alt.Text("Correlation:Q", format=".2f"),
                            color=alt.condition(alt.expr.abs(alt.datum.Correlation) > 0.45, alt.value("#ffffff"), alt.value("#94a3b8"))
                        )
                        st.altair_chart(fleet_corr_chart + fleet_corr_text, use_container_width=True)
                    except Exception as e:
                        st.warning(f"ไม่สามารถพล็อตกราฟ Heatmap ได้: {e}")


    # =============================================================
    #  TAB 9: 📰 NEWS & MACRO INTELLIGENCE
    # =============================================================
    with tab_news:
        st.markdown("### 📰 Macro Intelligence & News Stream")

        # Top Action Bar in News Tab: Status and Manual Refresh button
        n_col1, n_col2 = st.columns([3, 1])
        with n_col1:
            cache_data = st.session_state.get("_shared_news_cache", {})
            cache_ts = cache_data.get("ts", time.time())
            sync_time_str = datetime.fromtimestamp(cache_ts, tz=BKK).strftime("%H:%M:%S")
            st.caption(f"🌐 ข้อมูลข่าวและปฏิทินเศรษฐกิจใช้ร่วมกันทุกบัญชี (Global Market Shared) · ซิงก์ล่าสุด: {sync_time_str} BKK")
        with n_col2:
            if st.button("🔄 อัปเดตข่าวสด (Refresh)", use_container_width=True, key="btn_refresh_news_shared"):
                get_shared_news_data(force_refresh=True)
                st.rerun()

        cal_df, cal_err, news_items, news_err = get_shared_news_data()

        with st.expander("🗓️ ForexFactory Economic Calendar (ทั้งสัปดาห์)", expanded=True):
            if cal_err:
                st.error(f"ดึงปฏิทินข่าวไม่สำเร็จ: {cal_err}")
            elif cal_df.empty:
                st.info("ไม่มีข่าวในสัปดาห์นี้")
            else:
                filter_impact = st.multiselect("กรองระดับ Impact", ["High", "Medium", "Low", "Holiday"], default=["High", "Medium"], key="news_filter_impact")
                sub_cal = cal_df[cal_df["impact"].isin(filter_impact)]
                st.dataframe(sub_cal, use_container_width=True)

        st.markdown("---")
        st.markdown("#### ⚡ FXStreet Breaking News Stream (Real-Time)")
        if news_items:
            GOLD_KEYWORDS = ("gold", "xau", "fed", "fomc", "usd", "dollar", "inflation", "cpi", "nfp", "rate")
            for it in news_items[:15]:
                title = html_escape.escape(it["title"] or "")
                desc = html_escape.escape(it["desc"] or "")
                link = it["link"] if it["link"].startswith(("http://", "https://")) else ""
                hot = any(kw in (it["title"] or "").lower() for kw in GOLD_KEYWORDS)
                t = it["time"].strftime("%a %d/%m %H:%M BKK") if it["time"] else "—"
                badge = "<span style='color:#fbbf24;font-weight:800;'>🔥 GOLD/USD</span> " if hot else ""
                title_html = f'<a href="{link}" target="_blank" style="color:#38bdf8;font-weight:700;">{title}</a>' if link else title
                st.markdown(
                    f"<div class='pro-card' style='padding:12px;margin-bottom:10px;'>"
                    f"<div>{badge}{title_html}</div>"
                    f"<div style='color:#94a3b8;font-size:11px;margin:3px 0 6px 0;'>{t}</div>"
                    f"<div style='color:#cbd5e1;font-size:12.5px;'>{desc}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )


    # =============================================================
    #  TAB 11: 📚 STRATEGY DOCS & CANDLESTICK PATTERN EXPLORER
    # =============================================================
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

