"""
edge_test_s25.py — เทียบ edge-improvement 2 แนวทางที่ต่างกันโดยสิ้นเชิง (S25)
ตาม Exhaustion Checklist ข้อ 2 ของ docs/new_strategy_research_template.md

Baseline = best config จาก grid round 1 (lookback=15, pierce=0.05, wick=0.55, RR=2.0, trend=against)
A = ATR_REGIME_FILTER (เพิ่ม confirmation filter ใหม่ - volatility regime)
B = BREAKEVEN_AFTER_R (ปรับ exit logic ให้ฉลาดขึ้น - breakeven หลัง 1R)
A+B = ทั้งสองรวมกัน
"""
import MetaTrader5 as mt5

import config
from sim_s25_backtest import TF_MAP, fetch_bars, fmt_summary, replay_tf, simulate_equity, summarize, append_summary_csv
from strategy25 import S25_DEFAULTS

DAYS = 60
TF_LIST = ["M5", "M15"]
SPREAD = 0.20

BASE = dict(S25_DEFAULTS)
BASE.update({
    "SWING_LOOKBACK": 15, "SWEEP_MIN_PIERCE_ATR": 0.05, "REJECTION_WICK_PCT": 0.55,
    "RSI_OVERBOUGHT": 62.0, "RSI_OVERSOLD": 38.0, "SL_ATR_MULT": 0.6, "TP_RR": 2.0,
    "TREND_FILTER": "against", "RISK_PCT": 1.0,
})

variants = {
    "baseline_best": dict(BASE),
    "A_atr_regime_1.0": {**BASE, "ATR_REGIME_FILTER": True, "ATR_REGIME_MULT": 1.0},
    "A_atr_regime_1.2": {**BASE, "ATR_REGIME_FILTER": True, "ATR_REGIME_MULT": 1.2},
    "B_breakeven_0.5R": {**BASE, "BREAKEVEN_AFTER_R": 0.5},
    "B_breakeven_1.0R": {**BASE, "BREAKEVEN_AFTER_R": 1.0},
    "AB_combined": {**BASE, "ATR_REGIME_FILTER": True, "ATR_REGIME_MULT": 1.0, "BREAKEVEN_AFTER_R": 1.0},
}

if not mt5.initialize():
    print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
    raise SystemExit(1)

bars_by_tf = {}
for tf in TF_LIST:
    bars = fetch_bars(config.SYMBOL, tf, DAYS)
    bars_by_tf[tf] = bars
    print(f"{tf}: {len(bars)} bars")
mt5.shutdown()

print("=" * 100)
for label, cfg in variants.items():
    all_raw = []
    for tf, bars in bars_by_tf.items():
        all_raw += replay_tf(bars, tf, SPREAD, cfg)
    trades, eq = simulate_equity(all_raw, cfg["RISK_PCT"])
    s = summarize(trades, eq, cfg["RISK_PCT"], DAYS)
    print(f"{label}:")
    print(f"  {fmt_summary(s) if s else 'no trades'}")
    if s:
        append_summary_csv(label, s, cfg, cfg["RISK_PCT"])
