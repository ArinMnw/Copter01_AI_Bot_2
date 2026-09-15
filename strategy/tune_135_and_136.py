# -*- coding: utf-8 -*-
"""tune_135_and_136.py
Search for S20.135 and S20.136 champions:
- Target to beat for S20.135: > $36,164.96 (S20.134)
- Target to beat for S20.136: > S20.135
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import os, sys
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from goal_s20_53_to_100 import run_simulation, init_mt5
from tune_master_fusion_134_to_136 import compute_extended_synergies

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

    print("Computing extended institutional synergies...", flush=True)
    dfs = {tf: compute_extended_synergies(r) for tf, r in rates.items()}

    # Base ratchet stages
    stg31 = [
        (1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5),
        (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4),
        (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3),
        (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1),
        (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85),
        (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.80, 8.60), (8.95, 8.75)
    ]
    stg34 = stg31 + [(9.10, 8.90), (9.25, 9.05), (9.40, 9.20)]
    stg35 = stg34 + [(9.55, 9.35)]
    stg36 = stg35 + [(9.70, 9.50)]
    stg37 = stg36 + [(9.85, 9.65)]
    stg38 = stg37 + [(10.00, 9.80)]
    stg39 = stg38 + [(10.15, 9.95)]
    stg40 = stg39 + [(10.30, 10.10)]

    print("\n--- Tuning S20.135 (Paradigm 5: Auction Absorption Climax) ---", flush=True)
    best_135 = None
    for abs_bonus in [True, False]:
        for sl_abs in [0.182, 0.185, 0.188]:
            for tp in [11.50, 11.55, 11.60]:
                for stg, sname in [(stg38, "stg38"), (stg39, "stg39")]:
                    setups = []
                    for tf, df_tf in dfs.items():
                        for cur in df_tf.to_dict('records'):
                            if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
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

                            bull_ob = cur['bull_ob_zone']
                            bear_ob = cur['bear_ob_zone']
                            ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
                            ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

                            bpr_tap_bull = (cur['has_bpr'] and cur['low'] <= cur['bpr_high'] and cur['high'] >= cur['bpr_low'])
                            bpr_tap_bear = (cur['has_bpr'] and cur['high'] >= cur['bpr_low'] and cur['low'] <= cur['bpr_high'])

                            # Auction Absorption:
                            is_abs_buy = cur['is_absorption_buy']
                            is_abs_sell = cur['is_absorption_sell']

                            has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
                            has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
                            closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
                            closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

                            is_comp = cur['compression_ratio'] <= 0.70

                            sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull or (is_abs_buy if abs_bonus else False)) and has_wick_buy and closed_high) else \
                                  ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear or (is_abs_sell if abs_bonus else False)) and has_wick_sell and closed_low) else None)

                            if sig:
                                is_hc = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or \
                                        (bpr_tap_bull if sig == "BUY" else bpr_tap_bear) or \
                                        (is_abs_buy if sig == "BUY" else is_abs_sell)
                                sl_mult = sl_abs if is_hc else (0.190 if is_comp else 0.195)
                                sl_buf = max(sl_mult * cur['atr'], 0.22)
                                active_depth = 0.121 if is_hc else (0.124 if is_comp else 0.125)
                                entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
                                sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
                                risk = entry - sl if sig == "BUY" else sl - entry
                                if risk > 0:
                                    setups.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})

                    setups = sorted(setups, key=lambda x: x['time'])
                    res = run_simulation(m5_gold, m5_times, setups, tp_r=tp, stages=stg)
                    if res['pnl'] > 36164.96:
                        print(f"FOUND S20.135: abs_bonus={abs_bonus} sl={sl_abs} tp={tp} {sname} -> PnL: ${res['pnl']:,.2f} WR: {res['wr']:.1f}% DD: ${res['max_dd']:.2f}")
                        if best_135 is None or res['pnl'] > best_135['pnl']:
                            best_135 = {'res': res, 'pnl': res['pnl'], 'params': (abs_bonus, sl_abs, tp, sname)}

    if best_135:
        print(f"\nBEST S20.135: {best_135['params']} -> PnL: ${best_135['pnl']:,.2f}")
        pnl_135 = best_135['pnl']
    else:
        pnl_135 = 36164.96

    print("\n--- Tuning S20.136 (Paradigm 6: Institutional Inducement LIT + Dual-Engine Quantum) ---", flush=True)
    for sl_lit in [0.180, 0.182, 0.185]:
        for tp in [11.55, 11.60, 11.65]:
            for stg, sname in [(stg39, "stg39"), (stg40, "stg40")]:
                setups = []
                for tf, df_tf in dfs.items():
                    for cur in df_tf.to_dict('records'):
                        if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
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

                        bull_ob = cur['bull_ob_zone']
                        bear_ob = cur['bear_ob_zone']
                        ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
                        ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

                        bpr_tap_bull = (cur['has_bpr'] and cur['low'] <= cur['bpr_high'] and cur['high'] >= cur['bpr_low'])
                        bpr_tap_bear = (cur['has_bpr'] and cur['high'] >= cur['bpr_low'] and cur['low'] <= cur['bpr_high'])

                        is_abs_buy = cur['is_absorption_buy']
                        is_abs_sell = cur['is_absorption_sell']

                        # LIT Inducement Swept:
                        swept_idm_buy = cur['swept_idm_buy']
                        swept_idm_sell = cur['swept_idm_sell']

                        has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
                        has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
                        closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
                        closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

                        is_comp = cur['compression_ratio'] <= 0.70

                        # S20.136 Confluence: Swept IDM OR Major Level, with OB / BPR / Absorption confirmation
                        sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull or is_abs_buy or swept_idm_buy) and has_wick_buy and closed_high) else \
                              ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear or is_abs_sell or swept_idm_sell) and has_wick_sell and closed_low) else None)

                        if sig:
                            is_apex = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or \
                                      (bpr_tap_bull if sig == "BUY" else bpr_tap_bear) or \
                                      (is_abs_buy if sig == "BUY" else is_abs_sell)
                            sl_mult = sl_lit if is_apex else (0.188 if is_comp else 0.195)
                            sl_buf = max(sl_mult * cur['atr'], 0.22)
                            active_depth = 0.120 if is_apex else (0.123 if is_comp else 0.125)
                            entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
                            sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
                            risk = entry - sl if sig == "BUY" else sl - entry
                            if risk > 0:
                                setups.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})

                setups = sorted(setups, key=lambda x: x['time'])
                res = run_simulation(m5_gold, m5_times, setups, tp_r=tp, stages=stg)
                if res['pnl'] > pnl_135:
                    print(f"FOUND S20.136 CHAMPION: sl={sl_lit} tp={tp} {sname} -> PnL: ${res['pnl']:,.2f} WR: {res['wr']:.1f}% DD: ${res['max_dd']:.2f}")

if __name__ == "__main__":
    main()
