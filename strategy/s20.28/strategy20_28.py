# -*- coding: utf-8 -*-
"""strategy20_28.py — S20.28 Hyper-Confluence & Adaptive Dynamic Runner Matrix:
Goal: Maximize Net Profit beyond S20.26 by unlocking the trapped runner potential!

Core Signal: S20.26 Quad-Engine
1. Session Liquidity Pool Sweep (Asian Range H/L, PDH/PDL, Swing 12)
2. Intermarket SMT Divergence (Gold XAUUSD vs Silver XAGUSD)
3. Volume Delta & Absorption Wick (Vol >= 1.30x, Wick >= 38%)
4. Session Anchored VWAP Statistical Zones (Discount/Premium)

Execution Engines:
- Engine A: Benchmark Static BE (S20.26 baseline)
- Engine B: Profit-Lock Step Trail (Locks +0.6R at TP1, trails 3-bar swing)
- Engine C: ATR Chandelier Dynamic Trailing (Locks +0.8R at TP1, trails 1.5x ATR)
- Engine D: Tri-Tier Scaling (TP1 1.5R 40% lot, TP2 3.0R 30% lot, TP3 5.0R+ 30% lot)
"""

import pandas as pd
import numpy as np
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


def compute_indicators_df(gold_rates, silver_rates=None):
    """Compute synchronized indicators for S20.28."""
    df = pd.DataFrame(gold_rates)
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

    # RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-5)
    df['rsi'] = 100 - (100 / (1 + rs))

    # Trend moving averages
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
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
    df['vwap_upper_10'] = df['vwap'] + (1.0 * df['vwap_std'])
    df['vwap_lower_10'] = df['vwap'] - (1.0 * df['vwap_std'])
    df['vwap_upper_12'] = df['vwap'] + (1.2 * df['vwap_std'])
    df['vwap_lower_12'] = df['vwap'] - (1.2 * df['vwap_std'])

    # Local Swings (lookback 12 and trailing swing lookback 3)
    df['swing_high_12'] = df['high'].rolling(12).max().shift(1)
    df['swing_low_12'] = df['low'].rolling(12).min().shift(1)
    df['trail_low_3'] = df['low'].rolling(3).min().shift(1)
    df['trail_high_3'] = df['high'].rolling(3).max().shift(1)
    df['opposite_high_40'] = df['high'].rolling(40).max().shift(1)
    df['opposite_low_40'] = df['low'].rolling(40).min().shift(1)

    # Asian Session Range (00:00 - 08:00 server time)
    asian_mask = (df['hour'] >= 0) & (df['hour'] < 8)
    df['asian_high_raw'] = np.where(asian_mask, df['high'], np.nan)
    df['asian_low_raw'] = np.where(asian_mask, df['low'], np.nan)
    day_asian_high = df.groupby('date')['asian_high_raw'].transform('max')
    day_asian_low = df.groupby('date')['asian_low_raw'].transform('min')
    df['asian_high'] = day_asian_high
    df['asian_low'] = day_asian_low

    # Previous Day High & Low (PDH / PDL)
    day_highs = df.groupby('date')['high'].max()
    day_lows = df.groupby('date')['low'].min()
    df['pdh'] = df['date'].map(day_highs.shift(1))
    df['pdl'] = df['date'].map(day_lows.shift(1))

    # Synchronize Silver (XAGUSD.iux) if provided
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


def evaluate_s20_28_bar(
    df,
    idx,
    tf="M30",
    min_vol=1.30,
    min_wick=0.38,
    retest_depth=0.382
):
    """Evaluate bar idx for S20.28 Quad-Engine Setup."""
    if idx < 45 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05 or cur['range'] < 0.45 * atr:
        return None

    # London & NY Killzones (08:00 - 18:00 server time / 14:00 - 00:00 BKK)
    if not (8 <= cur['hour'] <= 18):
        return None

    # Volume Climax
    if cur['vol_ratio'] < min_vol:
        return None

    # VWAP Discount/Premium
    in_discount = True
    in_premium = True
    if not pd.isna(cur['vwap_std']) and cur['vwap_std'] >= 0.7:
        in_discount = cur['low'] <= cur['vwap_lower_10']
        in_premium = cur['high'] >= cur['vwap_upper_10']

    # Swings & Session Pools
    swing_high = cur['swing_high_12']
    swing_low = cur['swing_low_12']
    asian_high = cur['asian_high']
    asian_low = cur['asian_low']
    pdh = cur['pdh']
    pdl = cur['pdl']

    gold_swept_high = cur['high'] >= swing_high
    gold_swept_low = cur['low'] <= swing_low

    session_swept_high = False
    session_swept_low = False
    if not pd.isna(asian_high) and cur['high'] >= asian_high:
        session_swept_high = True
    if not pd.isna(asian_low) and cur['low'] <= asian_low:
        session_swept_low = True
    if not pd.isna(pdh) and cur['high'] >= pdh:
        session_swept_high = True
    if not pd.isna(pdl) and cur['low'] <= pdl:
        session_swept_low = True

    # SMT Divergence
    has_silver = 'high_silver' in df.columns and not pd.isna(cur.get('high_silver', np.nan))
    smt_bearish = False
    smt_bullish = False

    if has_silver:
        s_high = cur['high_silver']
        s_low = cur['low_silver']
        s_swing_high = cur['s_swing_high_12']
        s_swing_low = cur['s_swing_low_12']

        if gold_swept_high and (s_high < s_swing_high):
            smt_bearish = True
        elif (not gold_swept_high) and (s_high >= s_swing_high and cur['high'] < swing_high):
            smt_bearish = True

        if gold_swept_low and (s_low > s_swing_low):
            smt_bullish = True
        elif (not gold_swept_low) and (s_low <= s_swing_low and cur['low'] > swing_low):
            smt_bullish = True

    # Anatomy Confirmations
    has_wick_buy = (cur['lower_wick_pct'] >= min_wick) or (cur['lower_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    rsi_ok_buy = cur['rsi'] <= 68.0

    has_wick_sell = (cur['upper_wick_pct'] >= min_wick) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
    rsi_ok_sell = cur['rsi'] >= 32.0

    sig = None

    # BUY
    if has_wick_buy and closed_high and rsi_ok_buy:
        has_sweep = gold_swept_low or session_swept_low
        smt_or_deep = smt_bullish or (cur['low'] <= cur.get('vwap_lower_12', cur['vwap_lower_10']))
        if has_sweep and smt_or_deep and in_discount:
            sig = "BUY"

    # SELL
    if sig is None and has_wick_sell and closed_low and rsi_ok_sell:
        has_sweep = gold_swept_high or session_swept_high
        smt_or_deep = smt_bearish or (cur['high'] >= cur.get('vwap_upper_12', cur['vwap_upper_10']))
        if has_sweep and smt_or_deep and in_premium:
            sig = "SELL"

    if not sig:
        return None

    # Base targets
    sl_buf = max(0.20 * atr, 0.25)
    scalp_rr = 1.8

    if sig == "BUY":
        sl = round(cur['low'] - sl_buf, 2)
        entry = round(cur['low'] + (retest_depth * cur['lower_wick']), 2)
        risk = entry - sl
        if risk <= 0:
            return None
        tp_scalp = round(entry + (risk * scalp_rr), 2)
        macro_target = cur['opposite_high_40']
        tp_runner = round(max(macro_target, entry + (risk * 4.0)), 2)
    else:
        sl = round(cur['high'] + sl_buf, 2)
        entry = round(cur['high'] - (retest_depth * cur['upper_wick']), 2)
        risk = sl - entry
        if risk <= 0:
            return None
        tp_scalp = round(entry - (risk * scalp_rr), 2)
        macro_target = cur['opposite_low_40']
        tp_runner = round(min(macro_target, entry - (risk * 4.0)), 2)

    return {
        "time": cur['time'],
        "time_str": str(cur['time_dt']),
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "risk": risk,
        "atr": atr,
        "tp_scalp": tp_scalp,
        "tp_runner": tp_runner,
        "vol_ratio": cur['vol_ratio'],
        "be_ratio": 0.40
    }
