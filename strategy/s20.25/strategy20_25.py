# -*- coding: utf-8 -*-
"""strategy20_25.py — S20.25 Institutional Confluence Fusion Engine
Synergistic Multi-Strategy Matrix (ทำงานร่วมกันในบาร์เดียวเพื่อความแม่นยำสูงสุด):
- Pillar 1 (S99/S100/S20.18): Liquidity Sweep of Swing Extreme with Rejection Wick.
- Pillar 2 (S20.22 VWAP): Price must be at Statistical Discount/Premium (Outside VWAP ±1.2σ).
- Pillar 3 (S20.18/S105): Institutional Volume Absorption Spike (Vol >= 1.35x).
- Pillar 4 (S20.23 Execution): Fibo 38.2% Wick Retest Entry + Dual-Exit (TP1 1.8R + Runner 3.5R+).
- Pillar 5 (Timing): London & NY Active Killzones (08:00 - 18:00 server time).
"""

import pandas as pd
import numpy as np
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


def compute_indicators_df(rates):
    """Compute combined indicators for S20.25 Fusion."""
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time_dt'].dt.date
    df['hour'] = df['time_dt'].dt.hour
    df['minute'] = df['time_dt'].dt.minute

    # Anatomy
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3.0
    df['range'] = df['high'] - df['low']
    df['body'] = np.abs(df['close'] - df['open'])
    df['body_pct'] = df['body'] / (df['range'] + 1e-5)
    df['upper_wick'] = df['high'] - np.maximum(df['open'], df['close'])
    df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
    df['upper_wick_pct'] = df['upper_wick'] / (df['range'] + 1e-5)
    df['lower_wick_pct'] = df['lower_wick'] / (df['range'] + 1e-5)

    # ATR (14)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()

    # Trend moving averages
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

    # Volume metrics
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # Daily Anchored VWAP & Standard Deviation Bands
    df['pv'] = df['typical_price'] * df['tick_volume']
    df['cum_pv'] = df.groupby('date')['pv'].cumsum()
    df['cum_vol'] = df.groupby('date')['tick_volume'].cumsum()
    df['vwap'] = df['cum_pv'] / (df['cum_vol'] + 1e-5)

    df['dev_sq'] = df['tick_volume'] * ((df['typical_price'] - df['vwap']) ** 2)
    df['cum_dev_sq'] = df.groupby('date')['dev_sq'].cumsum()
    df['vwap_std'] = np.sqrt(df['cum_dev_sq'] / (df['cum_vol'] + 1e-5))
    df['vwap_upper_12'] = df['vwap'] + (1.2 * df['vwap_std'])
    df['vwap_lower_12'] = df['vwap'] - (1.2 * df['vwap_std'])

    # Swings
    df['swing_high_12'] = df['high'].rolling(12).max().shift(1)
    df['swing_low_12'] = df['low'].rolling(12).min().shift(1)
    df['opposite_high_40'] = df['high'].rolling(40).max().shift(1)
    df['opposite_low_40'] = df['low'].rolling(40).min().shift(1)

    return df


def evaluate_confluence_bar(df, idx, tf="M30", require_vwap=True, min_vol=1.30, min_wick=0.38, retest_depth=0.382):
    """Evaluate bar with full multi-strategy confluence."""
    if idx < 45 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05 or cur['range'] < 0.45 * atr:
        return None

    # Killzone Filter (08:00 - 18:00 server time)
    if not (8 <= cur['hour'] <= 18):
        return None

    # Pillar 3: Volume Climax
    if cur['vol_ratio'] < min_vol:
        return None

    # Pillar 2: VWAP Statistical Zone Confluence
    if require_vwap:
        if pd.isna(cur['vwap_std']) or cur['vwap_std'] < 0.8:
            return None
        in_discount = cur['low'] <= cur['vwap_lower_12']
        in_premium = cur['high'] >= cur['vwap_upper_12']
    else:
        in_discount = True
        in_premium = True

    # -------------------------------------------------------------
    # 1. BULLISH FUSION SETUP
    # -------------------------------------------------------------
    # Pillar 1: Liquidity Sweep
    swept_low = cur['low'] <= cur['swing_low_12']
    has_wick_buy = (cur['lower_wick_pct'] >= min_wick) or (cur['lower_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])

    if in_discount and swept_low and has_wick_buy and closed_high:
        sl_buf = max(0.20 * atr, 0.25)
        sl = round(cur['low'] - sl_buf, 2)
        entry = round(cur['low'] + (retest_depth * cur['lower_wick']), 2)
        risk = entry - sl

        if risk > 0:
            tp_scalp = round(entry + (risk * 1.8), 2)
            macro_target = cur['opposite_high_40']
            tp_runner = round(max(macro_target, entry + (risk * 3.5)), 2)
            return {
                "signal": "BUY",
                "entry": entry,
                "sl": sl,
                "tp_scalp": tp_scalp,
                "tp_runner": tp_runner,
                "risk": risk,
                "be_ratio": 0.40,
                "confluence": f"Discount VWAP ({cur['vwap']:.1f}) + Sweep Low + Vol {cur['vol_ratio']:.1f}x"
            }

    # -------------------------------------------------------------
    # 2. BEARISH FUSION SETUP
    # -------------------------------------------------------------
    swept_high = cur['high'] >= cur['swing_high_12']
    has_wick_sell = (cur['upper_wick_pct'] >= min_wick) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

    if in_premium and swept_high and has_wick_sell and closed_low:
        sl_buf = max(0.20 * atr, 0.25)
        sl = round(cur['high'] + sl_buf, 2)
        entry = round(cur['high'] - (retest_depth * cur['upper_wick']), 2)
        risk = sl - entry

        if risk > 0:
            tp_scalp = round(entry - (risk * 1.8), 2)
            macro_target = cur['opposite_low_40']
            tp_runner = round(min(macro_target, entry - (risk * 3.5)), 2)
            return {
                "signal": "SELL",
                "entry": entry,
                "sl": sl,
                "tp_scalp": tp_scalp,
                "tp_runner": tp_runner,
                "risk": risk,
                "be_ratio": 0.40,
                "confluence": f"Premium VWAP ({cur['vwap']:.1f}) + Sweep High + Vol {cur['vol_ratio']:.1f}x"
            }

    return None
