# -*- coding: utf-8 -*-
"""tune_new_archetypes.py
Upgrading Paradigms 1, 2, 3 with precision Retest limit entries,
CRT momentum, and structural alignment to achieve high WR and profit.
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from goal_s20_53_to_100 import run_simulation, init_mt5
from test_new_paradigms_131_to_133 import compute_new_archetype_features

def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)
    timeframes = ['H4','H3','H2','H1','M30','M20','M15','M12']
    rates = {tf: mt5.copy_rates_range(symbol_gold, getattr(mt5, f"TIMEFRAME_{tf}"), start_dt, now) for tf in timeframes}
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()
    m5_times = [int(r['time']) for r in m5_gold]

    print("Computing features...", flush=True)
    dfs = {tf: compute_new_archetype_features(r) for tf, r in rates.items()}

    # Trailing Ratchet
    stg = [
        (1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5),
        (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4),
        (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3),
        (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1),
        (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85),
        (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.80, 8.60), (8.95, 8.75)
    ]

    print("\n--- Tuning Paradigm 1: Vacuum Breakout with Pullback Retest Entry ---")
    for depth in [0.20, 0.30, 0.40]:
        setups = []
        for tf, df_tf in dfs.items():
            recs = df_tf.to_dict('records')
            for idx in range(35, len(recs)):
                cur = recs[idx]
                if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['vol_ratio'] < 1.4: continue
                # Breakout
                break_high = cur['close'] > cur['roll_high_20'] and cur['close'] > cur['open']
                break_low = cur['close'] < cur['roll_low_20'] and cur['close'] < cur['open']
                sig = "BUY" if break_high else ("SELL" if break_low else None)
                if sig:
                    # Precision limit entry at pullback into breakout candle body
                    entry = round(cur['close'] - (depth * cur['body']), 2) if sig == "BUY" else round(cur['close'] + (depth * cur['body']), 2)
                    sl = round(cur['low'] - (0.20 * cur['atr']), 2) if sig == "BUY" else round(cur['high'] + (0.20 * cur['atr']), 2)
                    risk = entry - sl if sig == "BUY" else sl - entry
                    if risk > 0:
                        setups.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})
        setups = sorted(setups, key=lambda x: x['time'])
        res = run_simulation(m5_gold, m5_times, setups, tp_r=7.5, stages=stg)
        print(f"P1 Pullback depth={depth} -> PnL: ${res['pnl']:,.2f} Trades: {res['trades']} WR: {res['wr']:.1f}% DD: ${res['max_dd']:.2f}")

    print("\n--- Tuning Paradigm 2: Order Block Origin Mitigation with Tight Limit Entry ---")
    for ob_depth in [0.25, 0.50, 0.75]:
        setups = []
        for tf, df_tf in dfs.items():
            recs = df_tf.to_dict('records')
            for idx in range(35, len(recs)):
                cur = recs[idx]
                if pd.isna(cur['atr']) or cur['atr'] <= 0.05: continue
                bull_ob = cur['bull_ob_zone']
                bear_ob = cur['bear_ob_zone']
                sig = None
                if not pd.isna(bull_ob) and cur['low'] <= bull_ob and cur['trend_bias'] == 1:
                    sig = "BUY"
                    entry = round(bull_ob - (ob_depth * 0.1 * cur['atr']), 2)
                    sl = round(cur['low'] - (0.20 * cur['atr']), 2)
                elif not pd.isna(bear_ob) and cur['high'] >= bear_ob and cur['trend_bias'] == -1:
                    sig = "SELL"
                    entry = round(bear_ob + (ob_depth * 0.1 * cur['atr']), 2)
                    sl = round(cur['high'] + (0.20 * cur['atr']), 2)
                if sig:
                    risk = entry - sl if sig == "BUY" else sl - entry
                    if risk > 0:
                        setups.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})
        setups = sorted(setups, key=lambda x: x['time'])
        res = run_simulation(m5_gold, m5_times, setups, tp_r=8.0, stages=stg)
        print(f"P2 OB depth={ob_depth} -> PnL: ${res['pnl']:,.2f} Trades: {res['trades']} WR: {res['wr']:.1f}% DD: ${res['max_dd']:.2f}")

if __name__ == "__main__":
    main()
