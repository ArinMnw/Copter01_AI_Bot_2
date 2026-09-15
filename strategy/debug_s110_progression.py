# -*- coding: utf-8 -*-
"""debug_s110_progression.py
Check grid parameters to beat S20.109 ($32,318.96)
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import os, sys
from datetime import datetime, timedelta, timezone

from goal_s20_53_to_100 import run_simulation, init_mt5
from test_confluence_abc import compute_advanced_features

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

    dfs = {tf: compute_advanced_features(r, fvg_depth=5) for tf, r in rates.items()}

    cur_champion_pnl = 32318.96

    stages = [
        (1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5),
        (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4),
        (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3),
        (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1),
        (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85),
        (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.80, 8.60), (8.95, 8.75)
    ]

    # Test wider search space:
    # 1. More stages
    # 2. Variable volume ratios: 1.13, 1.14, 1.15
    # 3. Dynamic hours: (0, 23) continuous coverage
    # 4. Wider range of wick: 0.08 to 0.16
    for hrs in [(0, 22), (0, 23)]:
        for vsa in [1.13, 1.14, 1.15]:
            for wick in [0.08, 0.09, 0.10, 0.11, 0.12]:
                for depth in [0.125, 0.124, 0.126]:
                    setups = []
                    for tf, df_tf in dfs.items():
                        recs = df_tf.to_dict('records')
                        for idx in range(45, len(recs)):
                            cur = recs[idx]
                            if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr']:
                                continue
                            if not (hrs[0] <= cur['hour'] <= hrs[1]):
                                continue
                            if cur['vol_ratio'] < vsa:
                                continue

                            swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or \
                                        (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or \
                                        (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or \
                                        (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or \
                                        (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl'])

                            swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or \
                                         (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or \
                                         (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or \
                                         (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or \
                                         (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

                            has_wick_buy = (cur['lower_wick_pct'] >= wick) or (cur['lower_wick'] >= 1.1 * cur['body'])
                            has_wick_sell = (cur['upper_wick_pct'] >= wick) or (cur['upper_wick'] >= 1.1 * cur['body'])
                            closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
                            closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

                            is_judas = cur['is_judas_window']
                            is_expanding = cur['is_vol_expansion']

                            sig = None
                            if swept_low and has_wick_buy and closed_high:
                                sig = "BUY"
                            elif swept_high and has_wick_sell and closed_low:
                                sig = "SELL"

                            if sig:
                                sl_mult = 0.19 if is_expanding else 0.20
                                sl_buf = max(sl_mult * cur['atr'], 0.22)
                                active_depth = 0.120 if is_judas else depth
                                entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
                                sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
                                risk = entry - sl if sig == "BUY" else sl - entry
                                if risk > 0:
                                    setups.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})

                    setups = sorted(setups, key=lambda x: x['time'])
                    for tp in [9.05, 9.10, 9.15, 9.20, 9.25]:
                        res = run_simulation(m5_gold, m5_times, setups, tp_r=tp, stages=stages)
                        if res['pnl'] > cur_champion_pnl and res['wr'] >= 83.0 and res['max_dd'] <= 22.0:
                            print(f"FOUND: hrs={hrs} vsa={vsa} wick={wick} depth={depth} TP={tp} -> PnL: ${res['pnl']:,.2f} Trades: {res['trades']} WR: {res['wr']:.1f}% DD: ${res['max_dd']:.2f}", flush=True)

if __name__ == "__main__":
    main()
