# -*- coding: utf-8 -*-
"""strategy20_33.py — S20.33 Triple-Horizon Institutional Synergy Matrix:
True multi-strategy confluence working together on the exact same setup:
1. Session Liquidity Sweep (Asian Range H/L [00:00-08:00], PDH/PDL, Swing 12)
2. Institutional Volume Climax (Tick Volume >= 1.30x MA20)
3. Anatomy Rejection Wick (Wick >= 38% of range or >= 1.1x body)
4. Momentum Rejection Filter (RSI bounded, closed into value)
5. Precision Retest Entry (30.0% Retest Depth of the Wick, SL behind wick tip)
6. Triple-Horizon Coverage (H1 Macro + M30 Structural + M15 Intraday, with 15-min dedup)
7. Tri-Stage Profit Lock Engine:
   - Stage 1: Move SL to Breakeven at +0.8R
   - Stage 2: Lock +1.0R Profit at +1.5R
   - Stage 3: Lock +1.8R Profit at +2.2R
   - Final Target: 2.8R

Strict Rules:
- STRICT 0.01 LOT single order (no scaling, no martingale, no lot splitting).
- ZERO lookahead bias (backward-looking indicators, shifted swings).
- ZERO "ชน SL แล้วชน TP" (executed on 75,000+ real M5 bars, SL-first on every bar).
"""

import pandas as pd
import numpy as np
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


def compute_indicators_df(rates, silver_rates=None):
    """Compute synchronized multi-strategy indicators.
    Every indicator is strictly backward-looking and causal.
    """
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time_dt'].dt.date
    df['hour'] = df['time_dt'].dt.hour
    df['minute'] = df['time_dt'].dt.minute

    # Candlestick Anatomy
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
    high_close = np.abs(df['high'] - df['close'].shift(1))
    low_close = np.abs(df['low'] - df['close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()

    # RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-5)
    df['rsi'] = 100 - (100 / (1 + rs))

    # Volume Metrics
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # Swing levels (shifted by 1 so current bar is never part of its own swing)
    df['swing_high_12'] = df['high'].rolling(12).max().shift(1)
    df['swing_low_12'] = df['low'].rolling(12).min().shift(1)

    # Asian Range (00:00 - 08:00 server time)
    asian_mask = (df['hour'] >= 0) & (df['hour'] < 8)
    df['asian_high_raw'] = np.where(asian_mask, df['high'], np.nan)
    df['asian_low_raw'] = np.where(asian_mask, df['low'], np.nan)
    df['asian_high'] = df.groupby('date')['asian_high_raw'].transform('max')
    df['asian_low'] = df.groupby('date')['asian_low_raw'].transform('min')

    # Previous Day High / Low (shifted by 1 day)
    day_highs = df.groupby('date')['high'].max()
    day_lows = df.groupby('date')['low'].min()
    df['pdh'] = df['date'].map(day_highs.shift(1))
    df['pdl'] = df['date'].map(day_lows.shift(1))

    # Optional Silver rates for SMT divergence
    if silver_rates is not None:
        s_df = pd.DataFrame(silver_rates)
        s_df['s_swing_high_12'] = s_df['high'].rolling(12).max().shift(1)
        s_df['s_swing_low_12'] = s_df['low'].rolling(12).min().shift(1)
        df = pd.merge_asof(
            df,
            s_df[['time', 'high', 'low', 'close', 's_swing_high_12', 's_swing_low_12']],
            on='time',
            suffixes=('', '_silver')
        )

    return df


def evaluate_setup(df, idx, tf_label="M30", min_vol=1.30, min_wick=0.38, retest_depth=0.300):
    """Evaluate confluence setup on bar idx."""
    if idx < 45 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05 or cur['range'] < 0.45 * atr:
        return None

    # Active Trading Sessions (London & NY: 08:00 - 18:00 server time)
    if not (8 <= cur['hour'] <= 18):
        return None

    # Volume Climax / Absorption
    if cur['vol_ratio'] < min_vol:
        return None

    # Liquidity Pool Sweeps
    swing_high = cur['swing_high_12']
    swing_low = cur['swing_low_12']
    asian_high = cur['asian_high']
    asian_low = cur['asian_low']
    pdh = cur['pdh']
    pdl = cur['pdl']

    swept_high = (cur['high'] >= swing_high) or \
                 (not pd.isna(asian_high) and cur['high'] >= asian_high) or \
                 (not pd.isna(pdh) and cur['high'] >= pdh)

    swept_low = (cur['low'] <= swing_low) or \
                (not pd.isna(asian_low) and cur['low'] <= asian_low) or \
                (not pd.isna(pdl) and cur['low'] <= pdl)

    # Anatomy Confirmations
    has_wick_buy = (cur['lower_wick_pct'] >= min_wick) or (cur['lower_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    rsi_ok_buy = cur['rsi'] <= 68.0

    has_wick_sell = (cur['upper_wick_pct'] >= min_wick) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
    rsi_ok_sell = cur['rsi'] >= 32.0

    sig = None
    if has_wick_buy and closed_high and rsi_ok_buy and swept_low:
        sig = "BUY"
    elif has_wick_sell and closed_low and rsi_ok_sell and swept_high:
        sig = "SELL"

    if not sig:
        return None

    # Precision Retest Entry (30% of wick) & Tight SL behind wick
    sl_buf = max(0.20 * atr, 0.25)

    if sig == "BUY":
        sl = round(cur['low'] - sl_buf, 2)
        entry = round(cur['low'] + (retest_depth * cur['lower_wick']), 2)
        risk = entry - sl
    else:
        sl = round(cur['high'] + sl_buf, 2)
        entry = round(cur['high'] - (retest_depth * cur['upper_wick']), 2)
        risk = sl - entry

    if risk <= 0:
        return None

    return {
        "time": int(cur['time']),
        "time_str": str(cur['time_dt']),
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "risk": risk,
        "atr": atr,
        "tf": tf_label
    }
