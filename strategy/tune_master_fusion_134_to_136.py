# -*- coding: utf-8 -*-
"""tune_master_fusion_134_to_136.py
Exploration & Fine-Tuning for S20.134, S20.135, and S20.136.
Requirements:
1. Fixed 0.01 lot single position ($1.00/pt) throughout 365 days.
2. Single-candle multi-strategy confluence.
3. Zero lookahead bias, causal shift(1) backward-looking indicators.
4. Pessimistic intrabar sequential M5 SL-First engine across 75,000+ real bars.
5. Realistic 2-hour limit retest timeout (no magic fill).
6. Monotonically increasing net profit:
   - Baseline S20.133: $36,018.35
   - S20.134 > $36,018.35 (Paradigm 4: Balanced Price Range BPR & Breakaway Void)
   - S20.135 > S20.134 (Paradigm 5: Auction Market Theory HVN/LVN Absorption Climax)
   - S20.136 > S20.135 (Paradigm 6: Institutional Inducement Theorem LIT + Dual-Engine Quantum Matrix)
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import os, sys
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from goal_s20_53_to_100 import run_simulation, init_mt5
from test_confluence_abc import compute_advanced_features

def compute_extended_synergies(rates):
    # Base advanced features (CVD, Judas, VolRegime, FVG, Fibo, VP, Swings)
    df = compute_advanced_features(rates, fvg_depth=6)

    # 1. Paradigm 1: Range Compression Ratio
    range_10 = df['high'].rolling(10).max().shift(1) - df['low'].rolling(10).min().shift(1)
    range_30 = df['high'].rolling(30).max().shift(1) - df['low'].rolling(30).min().shift(1)
    df['compression_ratio'] = range_10 / (range_30 + 1e-5)
    df['is_compressed'] = df['compression_ratio'] <= 0.70

    # 2. Paradigm 2: Order Block Origin & Displacement
    df['is_bull_displacement'] = (df['close'] > df['open']) & (df['body_pct'] >= 0.60) & (df['range'] >= 1.2 * df['atr'])
    df['is_bear_displacement'] = (df['close'] < df['open']) & (df['body_pct'] >= 0.60) & (df['range'] >= 1.2 * df['atr'])
    df['bull_ob_zone'] = np.where(df['is_bull_displacement'].shift(1), df['high'].shift(2), np.nan)
    df['bear_ob_zone'] = np.where(df['is_bear_displacement'].shift(1), df['low'].shift(2), np.nan)
    df['bull_ob_zone'] = df['bull_ob_zone'].ffill(limit=8)
    df['bear_ob_zone'] = df['bear_ob_zone'].ffill(limit=8)

    # 3. Paradigm 4: Balanced Price Range (BPR)
    # Overlap of recent Bullish FVG and Bearish FVG
    bull_fvg_top = np.where((df['low'] > df['high'].shift(2)).shift(1), df['low'].shift(1), np.nan)
    bull_fvg_bot = np.where((df['low'] > df['high'].shift(2)).shift(1), df['high'].shift(3), np.nan)
    bear_fvg_top = np.where((df['high'] < df['low'].shift(2)).shift(1), df['low'].shift(3), np.nan)
    bear_fvg_bot = np.where((df['high'] < df['low'].shift(2)).shift(1), df['high'].shift(1), np.nan)

    df['bull_fvg_top'] = pd.Series(bull_fvg_top, index=df.index).ffill(limit=10)
    df['bull_fvg_bot'] = pd.Series(bull_fvg_bot, index=df.index).ffill(limit=10)
    df['bear_fvg_top'] = pd.Series(bear_fvg_top, index=df.index).ffill(limit=10)
    df['bear_fvg_bot'] = pd.Series(bear_fvg_bot, index=df.index).ffill(limit=10)

    # BPR Overlap Condition: Bull FVG and Bear FVG overlap
    bpr_low = np.maximum(df['bull_fvg_bot'], df['bear_fvg_bot'])
    bpr_high = np.minimum(df['bull_fvg_top'], df['bear_fvg_top'])
    df['has_bpr'] = bpr_high > bpr_low
    df['bpr_low'] = np.where(df['has_bpr'], bpr_low, np.nan)
    df['bpr_high'] = np.where(df['has_bpr'], bpr_high, np.nan)

    # 4. Paradigm 5: Auction Absorption Climax
    # Volume climax with large rejection wick and tick volume exhaustion
    df['is_absorption_buy'] = (df['vol_ratio'] >= 1.12) & (df['lower_wick_pct'] >= 0.18) & (df['close'] > df['open'])
    df['is_absorption_sell'] = (df['vol_ratio'] >= 1.12) & (df['upper_wick_pct'] >= 0.18) & (df['close'] < df['open'])

    # 5. Paradigm 6: Minor Inducement (5-bar swing) vs Major Structure (12-bar swing)
    df['minor_swing_low_5'] = df['low'].rolling(5).min().shift(1)
    df['minor_swing_high_5'] = df['high'].rolling(5).max().shift(1)
    df['swept_idm_buy'] = df['low'] <= df['minor_swing_low_5']
    df['swept_idm_sell'] = df['high'] >= df['minor_swing_high_5']

    # Trend Bias
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean().shift(1)
    df['trend_bias'] = np.where(df['close'].shift(1) > df['ema_50'], 1, np.where(df['close'].shift(1) < df['ema_50'], -1, 0))

    return df

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

    print(f"\nTarget baseline to beat (S20.133): $36,018.35")

    # Explore S20.134: BPR Confluence
    print("\n--- Tuning S20.134 (Paradigm 4: Balanced Price Range BPR Confluence) ---", flush=True)
    for bpr_weight in [True, False]:
        for sl_bpr in [0.184, 0.186, 0.188]:
            for tp in [11.45, 11.50, 11.55]:
                for stg, sname in [(stg37, "stg37"), (stg38, "stg38")]:
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

                            # BPR Tap
                            bpr_tap_bull = (cur['has_bpr'] and cur['low'] <= cur['bpr_high'] and cur['high'] >= cur['bpr_low'])
                            bpr_tap_bear = (cur['has_bpr'] and cur['high'] >= cur['bpr_low'] and cur['low'] <= cur['bpr_high'])

                            has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
                            has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
                            closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
                            closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

                            is_comp = cur['compression_ratio'] <= 0.70

                            sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull) and has_wick_buy and closed_high) else \
                                  ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear) and has_wick_sell and closed_low) else None)

                            if sig:
                                is_hc = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or (bpr_tap_bull if sig == "BUY" else bpr_tap_bear)
                                sl_mult = sl_bpr if is_hc else (0.190 if is_comp else 0.195)
                                sl_buf = max(sl_mult * cur['atr'], 0.22)
                                active_depth = 0.122 if is_hc else (0.124 if is_comp else 0.125)
                                entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
                                sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
                                risk = entry - sl if sig == "BUY" else sl - entry
                                if risk > 0:
                                    setups.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})

                    setups = sorted(setups, key=lambda x: x['time'])
                    res = run_simulation(m5_gold, m5_times, setups, tp_r=tp, stages=stg)
                    if res['pnl'] > 36018.35:
                        print(f"FOUND S20.134: sl={sl_bpr} tp={tp} {sname} -> PnL: ${res['pnl']:,.2f} WR: {res['wr']:.1f}% DD: ${res['max_dd']:.2f}")

if __name__ == "__main__":
    main()
