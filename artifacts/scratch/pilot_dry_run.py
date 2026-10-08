# -*- coding: utf-8 -*-
"""Pilot dry-run: detect_s20_40 and detect_s20_30 live-style wrappers.
READ-ONLY: fetches live rates, runs signal detection, prints result.
Does NOT place any order, does NOT touch config/bot_state.
"""
import sys, os
sys.path.insert(0, os.path.abspath("strategy"))
sys.path.insert(0, os.path.abspath("strategy/s20.40"))
sys.path.insert(0, os.path.abspath("strategy/s20.30"))
import MetaTrader5 as mt5
import strategy20_40
import strategy20_30

def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-exness-434237129\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()

STAGES_S20_40 = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3)]
TP_R_S20_40 = 5.0

def detect_s20_40(rates, tf_name="M15", symbol="XAUUSDm"):
    """Pilot live wrapper for S20.40 (group 1). Multi-TF backtest used H4/H2/H1/M30/M15."""
    if tf_name.upper() not in ("H4", "H2", "H1", "M30", "M15"):
        return {"signal": "WAIT", "reason": f"S20.40 only evaluates H4/H2/H1/M30/M15 (got {tf_name})"}
    if len(rates) < 60:
        return {"signal": "WAIT", "reason": "not enough bars"}
    try:
        df = strategy20_40.compute_indicators(rates)
        setups = strategy20_40.extract_setups(df, tf_name, min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=(3, 22), use_pqh=True)
        last_bar_time = int(rates[-1]['time'])
        matches = [s for s in setups if s['time'] == last_bar_time]
        if not matches:
            return {"signal": "WAIT", "reason": "no setup on latest closed bar"}
        s = matches[0]
        return {
            "signal": s["signal"], "entry": s["entry"], "sl": s["sl"],
            "tp": round(s["entry"] + TP_R_S20_40 * s["risk"], 2) if s["signal"] == "BUY" else round(s["entry"] - TP_R_S20_40 * s["risk"], 2),
            "risk": s["risk"], "stages": STAGES_S20_40, "order_mode": "limit",
            "sid": 20.40, "pattern": f"S20.40_Pilot_{symbol}",
        }
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.40 error: {e}"}

def detect_s20_30(rates, tf_name="M5", symbol="XAUUSDm"):
    """Pilot live wrapper for S20.30 (group 2, combo_baseline_sweep)."""
    if tf_name.upper() != "M5":
        return {"signal": "WAIT", "reason": f"S20.30 only evaluates M5 (got {tf_name})"}
    if len(rates) < 60:
        return {"signal": "WAIT", "reason": "not enough bars"}
    try:
        df = strategy20_30.compute_indicators_df(rates)
        idx = len(rates) - 1
        res = strategy20_30.evaluate_s20_30_bar(df, idx, combo="combo_baseline_sweep")
        if not res:
            return {"signal": "WAIT", "reason": "no setup on latest closed bar"}
        entry, risk, sig = res["entry"], res["risk"], res["signal"]
        tp2 = entry + 4.0 * risk if sig == "BUY" else entry - 4.0 * risk
        return {
            "signal": sig, "entry": entry, "sl": res["sl"], "tp": round(tp2, 2),
            "risk": risk, "stages": [(1.8, 0.8)], "order_mode": "limit",
            "sid": 20.30, "pattern": f"S20.30_Pilot_{symbol}",
        }
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.30 error: {e}"}


if __name__ == "__main__":
    if not init_mt5():
        print("MT5 init failed")
        sys.exit(1)

    print("=" * 80)
    print("PILOT DRY-RUN (read-only, no orders placed)")
    print("=" * 80)

    for tf_name, mt5_tf in [("M15", mt5.TIMEFRAME_M15), ("M30", mt5.TIMEFRAME_M30), ("H1", mt5.TIMEFRAME_H1)]:
        rates = mt5.copy_rates_from_pos("XAUUSDm", mt5_tf, 0, 300)
        if rates is None:
            print(f"S20.40 [{tf_name}]: failed to fetch rates")
            continue
        res = detect_s20_40(rates, tf_name=tf_name, symbol="XAUUSDm")
        print(f"S20.40 [{tf_name}] latest bar {rates[-1]['time']}: {res}")

    rates_m5 = mt5.copy_rates_from_pos("XAUUSDm", mt5.TIMEFRAME_M5, 0, 300)
    if rates_m5 is not None:
        res = detect_s20_30(rates_m5, tf_name="M5", symbol="XAUUSDm")
        print(f"S20.30 [M5] latest bar {rates_m5[-1]['time']}: {res}")

    mt5.shutdown()
    print("=" * 80)
    print("Dry-run complete. No orders were placed.")
