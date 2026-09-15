# -*- coding: utf-8 -*-
"""strategy20_23.py — S20.23 Hybrid Liquidity Trap & Scalp-Runner Engine
Tailor-made for Trader DNA (1.AB, 2.AB, 3.1):
1. Liquidity Sweep & Stop Hunt: Piercing recent swing highs/lows with institutional volume surge.
2. Rejection Signature: Rejection wick >= 38% with Fibo 38.2% limit entry.
3. Hybrid Dual-Exit Management:
   - Target 1 (Fast Scalp): 1.8R (Hits in 15-45 mins, locks profit & moves SL to Breakeven).
   - Target 2 (Session Runner): Opposite swing extreme (aiming for 3.5R - 5.0R trend expansion).
4. London & NY Session Filter (14:00 - 00:00 BKK / 09:00 - 19:00 server time).
"""

import pandas as pd
import numpy as np
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


def compute_indicators_df(rates):
    """Compute indicators for S20.23 Hybrid Engine."""
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    df['hour'] = df['time_dt'].dt.hour
    df['minute'] = df['time_dt'].dt.minute

    # Price Anatomy
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

    # Volume Climax
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # Fast RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))

    # Swing Extremes (12 bars for micro-liquidity, 40 bars for macro opposite target)
    df['swing_high_12'] = df['high'].rolling(12).max().shift(1)
    df['swing_low_12'] = df['low'].rolling(12).min().shift(1)
    df['opposite_high_40'] = df['high'].rolling(40).max().shift(1)
    df['opposite_low_40'] = df['low'].rolling(40).min().shift(1)

    return df


def evaluate_hybrid_setup(df, idx, tf="M30", min_vol=1.25, min_wick=0.38, retest_depth=0.382, scalp_rr=1.8):
    """Evaluate bar for S20.23 Hybrid Liquidity Trap & Runner setup."""
    if idx < 45 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05 or cur['range'] < 0.45 * atr:
        return None

    hour = cur['hour']
    # Active London & NY Sessions (08:00 - 18:00 server time)
    if not (8 <= hour <= 18):
        return None

    if cur['vol_ratio'] < min_vol:
        return None

    # -------------------------------------------------------------
    # 1. BULLISH LIQUIDITY TRAP (BUY)
    # -------------------------------------------------------------
    swept_low = cur['low'] <= cur['swing_low_12']
    has_wick_buy = (cur['lower_wick_pct'] >= min_wick) or (cur['lower_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    rsi_ok_buy = cur['rsi'] <= 68.0

    if swept_low and has_wick_buy and closed_high and rsi_ok_buy:
        sl_buf = max(0.20 * atr, 0.25)
        sl = round(cur['low'] - sl_buf, 2)
        entry = round(cur['low'] + (retest_depth * cur['lower_wick']), 2)
        risk = entry - sl

        if risk > 0:
            tp_scalp = round(entry + (risk * scalp_rr), 2)
            # Runner target: Opposite Swing High or minimum 3.5R
            macro_target = cur['opposite_high_40']
            tp_runner = round(max(macro_target, entry + (risk * 3.5)), 2)
            return {
                "signal": "BUY",
                "entry": entry,
                "sl": sl,
                "tp_scalp": tp_scalp,
                "tp_runner": tp_runner,
                "risk": risk,
                "pattern": f"S20.23 Bull Trap (Vol {cur['vol_ratio']:.1f}x | Wick {cur['lower_wick_pct']*100:.0f}%)",
                "be_ratio": 0.40
            }

    # -------------------------------------------------------------
    # 2. BEARISH LIQUIDITY TRAP (SELL)
    # -------------------------------------------------------------
    swept_high = cur['high'] >= cur['swing_high_12']
    has_wick_sell = (cur['upper_wick_pct'] >= min_wick) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
    rsi_ok_sell = cur['rsi'] >= 32.0

    if swept_high and has_wick_sell and closed_low and rsi_ok_sell:
        sl_buf = max(0.20 * atr, 0.25)
        sl = round(cur['high'] + sl_buf, 2)
        entry = round(cur['high'] - (retest_depth * cur['upper_wick']), 2)
        risk = sl - entry

        if risk > 0:
            tp_scalp = round(entry - (risk * scalp_rr), 2)
            macro_target = cur['opposite_low_40']
            tp_runner = round(min(macro_target, entry - (risk * 3.5)), 2)
            return {
                "signal": "SELL",
                "entry": entry,
                "sl": sl,
                "tp_scalp": tp_scalp,
                "tp_runner": tp_runner,
                "risk": risk,
                "pattern": f"S20.23 Bear Trap (Vol {cur['vol_ratio']:.1f}x | Wick {cur['upper_wick_pct']*100:.0f}%)",
                "be_ratio": 0.40
            }

    return None
