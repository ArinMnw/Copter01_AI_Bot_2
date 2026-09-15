# -*- coding: utf-8 -*-
"""tune_confluence_abc.py
Fine-tuning and synthesizing genuine Alpha Confluence:
- S20.101: Apex + Order Flow CVD Delta Exhaustion Divergence
- S20.102: Apex + Session Judas Killzone Alignment (Session-weighted TP/stages)
- S20.103: Apex + Volatility Regime Adaptive Sizing/Targeting
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import bisect
from datetime import datetime, timedelta, timezone
import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from goal_s20_53_to_100 import compute_indicators, run_simulation, init_mt5
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

    print("Computing features...", flush=True)
    dfs = {tf: compute_advanced_features(r, fvg_depth=5) for tf, r in rates.items()}

    # Base S20.100 stages
    base_stages = [
        (1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5),
        (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4),
        (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3),
        (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1),
        (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85),
        (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45)
    ]

    # Test combining Full S20.100 Confluence with:
    # 1) CVD Divergence Bonus / Filter
    # 2) Session Multiplier
    # 3) Volatility Expansion Confirmation

    # Let's inspect tuning for S20.101 (CVD Confluence):
    print("\n--- Tuning S20.101 (CVD Confluence + Apex Multi-Strategy) ---")
    for cvd_mode in ['filter', 'boost', 'div_only']:
        for tp in [8.75, 8.85, 9.0]:
            setups = []
            for tf, df_tf in dfs.items():
                recs = df_tf.to_dict('records')
                for idx in range(45, len(recs)):
                    cur = recs[idx]
                    if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr']:
                        continue
                    if cur['vol_ratio'] < 1.15:
                        continue

                    # Sweeps across all layers:
                    swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or \
                                (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or \
                                (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or \
                                (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or \
                                (not pd.isna(cur.get('pdh')) and cur['low'] <= cur['pdl'])

                    swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or \
                                 (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or \
                                 (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or \
                                 (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or \
                                 (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

                    has_wick_buy = (cur['lower_wick_pct'] >= 0.12) or (cur['lower_wick'] >= 1.1 * cur['body'])
                    has_wick_sell = (cur['upper_wick_pct'] >= 0.12) or (cur['upper_wick'] >= 1.1 * cur['body'])
                    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
                    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

                    # CVD divergence
                    bull_cvd_div = cur['cvd_20'] > cur['cvd_min_12']
                    bear_cvd_div = cur['cvd_20'] < cur['cvd_max_12']

                    sig = None
                    if swept_low and has_wick_buy and closed_high:
                        if cvd_mode == 'filter' and bull_cvd_div:
                            sig = "BUY"
                        elif cvd_mode == 'boost' or not cvd_mode:
                            sig = "BUY"
                    elif swept_high and has_wick_sell and closed_low:
                        if cvd_mode == 'filter' and bear_cvd_div:
                            sig = "SELL"
                        elif cvd_mode == 'boost' or not cvd_mode:
                            sig = "SELL"

                    if sig:
                        # If CVD div confirms, entry is slightly more aggressive (retest depth 0.125 vs 0.14)
                        depth = 0.125 if (bull_cvd_div if sig == "BUY" else bear_cvd_div) else 0.14
                        sl_buf = max(0.20 * cur['atr'], 0.22)
                        entry = round(cur['low'] + (depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (depth * cur['upper_wick']), 2)
                        sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
                        risk = entry - sl if sig == "BUY" else sl - entry
                        if risk > 0:
                            setups.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})

            setups = sorted(setups, key=lambda x: x['time'])
            res = run_simulation(m5_gold, m5_times, setups, tp_r=tp, stages=base_stages)
            print(f"Mode: {cvd_mode} | TP: {tp} | PnL: ${res['pnl']:,.2f} | Trades: {res['trades']} | WR: {res['wr']:.1f}% | DD: ${res['max_dd']:.2f}")

if __name__ == "__main__":
    main()
