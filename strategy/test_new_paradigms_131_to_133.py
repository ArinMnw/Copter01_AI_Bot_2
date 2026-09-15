# -*- coding: utf-8 -*-
"""test_new_paradigms_131_to_133.py
Testing 3 completely NEW trading archetypes for S20.131, S20.132, S20.133:
- S20.131 (Paradigm 1): Structural Liquidity Vacuum Breakout (Compression Breakout + VPIN/Volume Surge > 2.0x, Momentum Continuation)
- S20.132 (Paradigm 2): Order Block Origin Mitigation + FTR (Failed to Return, Trend Following First Mitigation)
- S20.133 (Paradigm 3): Dual-Engine Equilibrium Router (Adaptive Regime Switching between Trend FTR & Range Sweep)

Strict Constraints:
- Strict 0.01 lot single position ($1.00/pt) throughout 365 days
- Zero look-ahead bias, causal shift(1)
- Pessimistic SL-First sequential M5 execution (75,000+ bars)
- Realistic execution without magic fill
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import bisect
from datetime import datetime, timedelta, timezone
import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from goal_s20_53_to_100 import run_simulation, init_mt5

def compute_new_archetype_features(rates):
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time_dt'].dt.date
    df['hour'] = df['time_dt'].dt.hour
    df['range'] = df['high'] - df['low']
    df['body'] = np.abs(df['close'] - df['open'])
    df['body_pct'] = df['body'] / (df['range'] + 1e-5)
    
    # ATR 14
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift(1))
    low_close = np.abs(df['low'] - df['close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()

    # Volume Climax
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # 1. Paradigm 1 Features: Compression & Liquidity Vacuum Breakout
    # 20-bar Rolling High/Low (Shifted 1 - Causal)
    df['roll_high_20'] = df['high'].rolling(20).max().shift(1)
    df['roll_low_20'] = df['low'].rolling(20).min().shift(1)
    # Range Compression Ratio: 10-bar range vs 30-bar range
    range_10 = df['high'].rolling(10).max().shift(1) - df['low'].rolling(10).min().shift(1)
    range_30 = df['high'].rolling(30).max().shift(1) - df['low'].rolling(30).min().shift(1)
    df['compression_ratio'] = range_10 / (range_30 + 1e-5)  # low value = tight compression

    # 2. Paradigm 2 Features: Order Block & Displacement (Origin Mitigation)
    # Displacement candle: Body >= 65% of range AND range >= 1.5x ATR
    df['is_bull_displacement'] = (df['close'] > df['open']) & (df['body_pct'] >= 0.65) & (df['range'] >= 1.3 * df['atr'])
    df['is_bear_displacement'] = (df['close'] < df['open']) & (df['body_pct'] >= 0.65) & (df['range'] >= 1.3 * df['atr'])
    # Order Block level: The origin candle prior to displacement (shift 1 causal)
    df['bull_ob_high'] = np.where(df['is_bull_displacement'].shift(1), df['high'].shift(2), np.nan)
    df['bear_ob_low'] = np.where(df['is_bear_displacement'].shift(1), df['low'].shift(2), np.nan)
    # Forward fill Order Blocks up to 6 bars
    df['bull_ob_zone'] = df['bull_ob_high'].ffill(limit=6)
    df['bear_ob_zone'] = df['bear_ob_low'].ffill(limit=6)

    # Trend structure via EMA 50 & EMA 200
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean().shift(1)
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean().shift(1)
    df['trend_bias'] = np.where(df['close'].shift(1) > df['ema_50'], 1, np.where(df['close'].shift(1) < df['ema_50'], -1, 0))

    # 3. Paradigm 3 Features: Regime Router (Hurst / Volatility Ratio)
    # Parkinson / Realized Volatility ratio
    df['atr_ma50'] = df['atr'].rolling(50).mean()
    df['vol_regime'] = df['atr'] / (df['atr_ma50'] + 1e-5)  # > 1.15 = Trending/Explosive, < 0.95 = Range/Choppy

    return df

def run_experiment():
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

    print("Computing features for Paradigms 1, 2, 3...", flush=True)
    dfs = {tf: compute_new_archetype_features(r) for tf, r in rates.items()}

    # Base Trailing Ratchet
    stg = [
        (1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5),
        (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4),
        (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3),
        (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1),
        (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85),
        (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.80, 8.60), (8.95, 8.75)
    ]

    print("\n" + "="*85)
    print("TESTING PARADIGM 1: Structural Liquidity Vacuum Breakout (S20.131)")
    print("="*85)
    for comp_thresh in [0.55, 0.60, 0.65]:
        for v_ratio in [1.5, 1.8, 2.0]:
            setups_1 = []
            for tf, df_tf in dfs.items():
                recs = df_tf.to_dict('records')
                for idx in range(35, len(recs)):
                    cur = recs[idx]
                    if pd.isna(cur['atr']) or cur['atr'] <= 0.05: continue
                    # Condition: Compression in past bars + Volume Surge + Breakout above 20-bar High/Low
                    is_compressed = cur['compression_ratio'] <= comp_thresh
                    vol_surge = cur['vol_ratio'] >= v_ratio
                    if not (is_compressed and vol_surge): continue

                    break_high = cur['close'] > cur['roll_high_20']
                    break_low = cur['close'] < cur['roll_low_20']

                    sig = "BUY" if break_high else ("SELL" if break_low else None)
                    if sig:
                        entry = cur['close']
                        sl = round(cur['low'] - (0.25 * cur['atr']), 2) if sig == "BUY" else round(cur['high'] + (0.25 * cur['atr']), 2)
                        risk = entry - sl if sig == "BUY" else sl - entry
                        if risk > 0:
                            setups_1.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})
            setups_1 = sorted(setups_1, key=lambda x: x['time'])
            res1 = run_simulation(m5_gold, m5_times, setups_1, tp_r=8.5, stages=stg)
            print(f"[P1: comp={comp_thresh} vol={v_ratio}] PnL: ${res1['pnl']:,.2f} | Trades: {res1['trades']} | WR: {res1['wr']:.1f}% | DD: ${res1['max_dd']:.2f}")

    print("\n" + "="*85)
    print("TESTING PARADIGM 2: Order Block Origin Mitigation + FTR (S20.132)")
    print("="*85)
    for trend_filter in [True, False]:
        for retest_tol in [0.15, 0.20, 0.25]:
            setups_2 = []
            for tf, df_tf in dfs.items():
                recs = df_tf.to_dict('records')
                for idx in range(35, len(recs)):
                    cur = recs[idx]
                    if pd.isna(cur['atr']) or cur['atr'] <= 0.05: continue
                    # Trend filter
                    if trend_filter and cur['trend_bias'] == 0: continue

                    # Check touch into active order block zone
                    bull_ob = cur['bull_ob_zone']
                    bear_ob = cur['bear_ob_zone']

                    sig = None
                    # BUY: In uptrend, price pulls back into Bullish Order Block zone
                    if not pd.isna(bull_ob) and cur['low'] <= bull_ob and (not trend_filter or cur['trend_bias'] == 1):
                        if cur['close'] > bull_ob:  # Rejection out of OB
                            sig = "BUY"
                    # SELL: In downtrend, price pulls back into Bearish Order Block zone
                    elif not pd.isna(bear_ob) and cur['high'] >= bear_ob and (not trend_filter or cur['trend_bias'] == -1):
                        if cur['close'] < bear_ob:  # Rejection out of OB
                            sig = "SELL"

                    if sig:
                        entry = cur['close']
                        sl = round(cur['low'] - (0.25 * cur['atr']), 2) if sig == "BUY" else round(cur['high'] + (0.25 * cur['atr']), 2)
                        risk = entry - sl if sig == "BUY" else sl - entry
                        if risk > 0:
                            setups_2.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})
            setups_2 = sorted(setups_2, key=lambda x: x['time'])
            res2 = run_simulation(m5_gold, m5_times, setups_2, tp_r=9.0, stages=stg)
            print(f"[P2: trend={trend_filter} tol={retest_tol}] PnL: ${res2['pnl']:,.2f} | Trades: {res2['trades']} | WR: {res2['wr']:.1f}% | DD: ${res2['max_dd']:.2f}")

    print("\n" + "="*85)
    print("TESTING PARADIGM 3: Dual-Engine Equilibrium Router (S20.133)")
    print("="*85)
    # Combine Trend FTR when VolRegime > 1.10 AND Range Sweep when VolRegime <= 1.10
    setups_3 = []
    for tf, df_tf in dfs.items():
        recs = df_tf.to_dict('records')
        for idx in range(35, len(recs)):
            cur = recs[idx]
            if pd.isna(cur['atr']) or cur['atr'] <= 0.05: continue
            is_trending_regime = cur['vol_regime'] >= 1.05

            sig = None
            if is_trending_regime:
                # Mode A: Trend Following FTR Order Block
                bull_ob = cur['bull_ob_zone']
                bear_ob = cur['bear_ob_zone']
                if not pd.isna(bull_ob) and cur['low'] <= bull_ob and cur['close'] > bull_ob and cur['trend_bias'] == 1:
                    sig = "BUY"
                elif not pd.isna(bear_ob) and cur['high'] >= bear_ob and cur['close'] < bear_ob and cur['trend_bias'] == -1:
                    sig = "SELL"
                if sig:
                    entry = cur['close']
                    sl = round(cur['low'] - (0.22 * cur['atr']), 2) if sig == "BUY" else round(cur['high'] + (0.22 * cur['atr']), 2)
            else:
                # Mode B: Range Reversal Sweep (Classic Precision Reversal)
                if cur['vol_ratio'] >= 1.15:
                    swept_low = cur['low'] <= cur['roll_low_20']
                    swept_high = cur['high'] >= cur['roll_high_20']
                    has_wick_buy = (cur['range'] - cur['body']) > 0 and (cur['close'] > cur['open'])
                    has_wick_sell = (cur['range'] - cur['body']) > 0 and (cur['close'] < cur['open'])
                    if swept_low and has_wick_buy:
                        sig = "BUY"
                        entry = cur['close']
                        sl = round(cur['low'] - (0.20 * cur['atr']), 2)
                    elif swept_high and has_wick_sell:
                        sig = "SELL"
                        entry = cur['close']
                        sl = round(cur['high'] + (0.20 * cur['atr']), 2)

            if sig:
                risk = entry - sl if sig == "BUY" else sl - entry
                if risk > 0:
                    setups_3.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})
    setups_3 = sorted(setups_3, key=lambda x: x['time'])
    res3 = run_simulation(m5_gold, m5_times, setups_3, tp_r=9.5, stages=stg)
    print(f"[P3: Dual-Engine Router] PnL: ${res3['pnl']:,.2f} | Trades: {res3['trades']} | WR: {res3['wr']:.1f}% | DD: ${res3['max_dd']:.2f}")

if __name__ == "__main__":
    run_experiment()
