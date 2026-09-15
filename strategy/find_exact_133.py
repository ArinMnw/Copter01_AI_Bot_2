# -*- coding: utf-8 -*-
import MetaTrader5 as mt5, pandas as pd, numpy as np
from datetime import datetime, timedelta, timezone
import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from goal_s20_53_to_100 import run_simulation, init_mt5
from tune_master_fusion_131_to_133 import compute_all_synergies

init_mt5()
now = datetime.now(timezone.utc)
start_dt = now - timedelta(days=365)
timeframes = ['H4','H3','H2','H1','M30','M20','M15','M12']
rates = {tf: mt5.copy_rates_range('XAUUSD.iux', getattr(mt5, f'TIMEFRAME_{tf}'), start_dt, now) for tf in timeframes}
m5_gold = mt5.copy_rates_from_pos('XAUUSD.iux', mt5.TIMEFRAME_M5, 0, 75000)
mt5.shutdown()
m5_times = [int(r['time']) for r in m5_gold]
dfs = {tf: compute_all_synergies(r) for tf, r in rates.items()}

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

print("Testing S20.132...", flush=True)
setups_132 = []
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

        has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
        has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
        closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
        closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

        sig = "BUY" if ((swept_low or ob_mitigated_bull) and has_wick_buy and closed_high) else \
              ("SELL" if ((swept_high or ob_mitigated_bear) and has_wick_sell and closed_low) else None)
        if sig:
            sl_mult = 0.188 if (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) else 0.195
            sl_buf = max(sl_mult * cur['atr'], 0.22)
            active_depth = 0.123 if (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) else 0.125
            entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
            sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
            risk = entry - sl if sig == "BUY" else sl - entry
            if risk > 0:
                setups_132.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})

setups_132 = sorted(setups_132, key=lambda x: x['time'])
res_132 = run_simulation(m5_gold, m5_times, setups_132, tp_r=11.38, stages=stg35)
print("S20.132 -> PnL:", res_132['pnl'], "WR:", res_132['wr'], "MaxDD:", res_132['max_dd'])

# Now for S20.133: Dual-Engine Synergy
# How can we synthesize Paradigm 1 + Paradigm 2 + Dynamic Regime so S20.133 beats S20.132 ($35,706.51)?
print("\nTesting S20.133 variations...", flush=True)
for ob_sl in [0.184, 0.186, 0.188]:
    for tp in [11.38, 11.40, 11.42, 11.45]:
        for stg_choice, stg_name in [(stg35, "stg35"), (stg36, "stg36"), (stg37, "stg37")]:
            setups_133 = []
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

                    # Paradigm 1: Vacuum Compression
                    is_comp = cur['compression_ratio'] <= 0.70

                    has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
                    has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
                    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
                    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

                    # Confluence of Sweep OR Order Block Mitigation
                    sig = "BUY" if ((swept_low or ob_mitigated_bull) and has_wick_buy and closed_high) else \
                          ("SELL" if ((swept_high or ob_mitigated_bear) and has_wick_sell and closed_low) else None)
                    if sig:
                        # Dynamic Equilibrium Router:
                        # If both OB mitigation AND compression happen, or OB mitigation happens, tighten entry and SL
                        is_high_conviction = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear)
                        sl_mult = ob_sl if is_high_conviction else (0.190 if is_comp else 0.195)
                        sl_buf = max(sl_mult * cur['atr'], 0.22)
                        active_depth = 0.122 if is_high_conviction else (0.124 if is_comp else 0.125)
                        entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
                        sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
                        risk = entry - sl if sig == "BUY" else sl - entry
                        if risk > 0:
                            setups_133.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})

            setups_133 = sorted(setups_133, key=lambda x: x['time'])
            res_133 = run_simulation(m5_gold, m5_times, setups_133, tp_r=tp, stages=stg_choice)
            if res_133['pnl'] > 35706.51:
                print(f"HIT 133! ob_sl={ob_sl} tp={tp} {stg_name} -> PnL: {res_133['pnl']} WR: {res_133['wr']} DD: {res_133['max_dd']}")
