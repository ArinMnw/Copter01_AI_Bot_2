# -*- coding: utf-8 -*-
"""strategy20_24.py — S20.24 Dual Institutional Engines:
1. Engine A: Wyckoff VSA (Volume Spread Analysis — Stopping Volume + No Supply/Demand Test)
2. Engine B: London Close Reversal (16:00 London Fixing Profit-Taking Snapback)
"""

import pandas as pd
import numpy as np
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


def compute_indicators_df(rates):
    """Compute VSA and Daily Range metrics for S20.24."""
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time_dt'].dt.date
    df['hour'] = df['time_dt'].dt.hour
    df['minute'] = df['time_dt'].dt.minute

    # Anatomy
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

    # Moving averages
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

    # Volume metrics
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # Swings
    df['swing_high_10'] = df['high'].rolling(10).max().shift(1)
    df['swing_low_10'] = df['low'].rolling(10).min().shift(1)

    # Daily Cumulative High & Low (up to current bar)
    df['day_high'] = df.groupby('date')['high'].cummax()
    df['day_low'] = df.groupby('date')['low'].cummin()
    df['day_range'] = df['day_high'] - df['day_low']

    return df


# -----------------------------------------------------------------------------
# ENGINE A: WYCKOFF VSA (STOPPING VOLUME + NO SUPPLY/DEMAND TEST)
# -----------------------------------------------------------------------------
def evaluate_wyckoff_vsa(df, idx, tf="M15", rr=2.0):
    """Engine A: Wyckoff Volume Spread Analysis (2-Step Confirmation).
    Step 1 (Bar i-1 or i-2): Ultra-high volume stopping bar.
    Step 2 (Bar i): Low-volume narrow-spread test bar (No Supply / No Demand).
    """
    if idx < 25 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    prev1 = df.iloc[idx - 1]
    prev2 = df.iloc[idx - 2]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05 or cur['hour'] in (23, 0):
        return None

    # 1. BULLISH VSA: (Stopping Volume at Support followed by No Supply Bar)
    # Step 1: Climax stopping volume on prev1 or prev2 (Vol >= 1.5x, long lower wick)
    climax_bar = None
    if prev1['vol_ratio'] >= 1.45 and (prev1['lower_wick_pct'] >= 0.35 or prev1['close'] > prev1['low'] + 0.4 * prev1['range']):
        climax_bar = prev1
    elif prev2['vol_ratio'] >= 1.45 and (prev2['lower_wick_pct'] >= 0.35 or prev2['close'] > prev2['low'] + 0.4 * prev2['range']):
        climax_bar = prev2

    if climax_bar is not None:
        # Step 2: Current bar is a "No Supply" test bar:
        # - Narrow range (narrow spread < 0.85 ATR)
        # - Volume dries up (< 1.05x average, lower than climax)
        # - Price holds above or near climax low
        is_narrow_spread = cur['range'] <= 0.85 * atr
        is_low_volume = cur['vol_ratio'] <= 1.05 and cur['tick_volume'] < climax_bar['tick_volume'] * 0.75
        holds_low = cur['low'] >= (climax_bar['low'] - 0.20 * atr)

        if is_narrow_spread and is_low_volume and holds_low and cur['close'] > cur['open']:
            entry = round(cur['close'], 2)
            sl = round(min(climax_bar['low'], cur['low']) - max(0.20 * atr, 0.30), 2)
            risk = entry - sl
            if 1.5 <= risk <= 6.0:
                tp = round(entry + (risk * rr), 2)
                return {
                    "signal": "BUY",
                    "engine": "Wyckoff_VSA",
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "risk": risk,
                    "pattern": f"VSA Bull Test (Climax Vol: {climax_bar['vol_ratio']:.1f}x -> Test Vol: {cur['vol_ratio']:.1f}x)",
                    "be_ratio": 0.40
                }

    # 2. BEARISH VSA: (Stopping Volume at Resistance followed by No Demand Bar)
    climax_sell = None
    if prev1['vol_ratio'] >= 1.45 and (prev1['upper_wick_pct'] >= 0.35 or prev1['close'] < prev1['high'] - 0.4 * prev1['range']):
        climax_sell = prev1
    elif prev2['vol_ratio'] >= 1.45 and (prev2['upper_wick_pct'] >= 0.35 or prev2['close'] < prev2['high'] - 0.4 * prev2['range']):
        climax_sell = prev2

    if climax_sell is not None:
        # Step 2: "No Demand" test bar
        is_narrow_spread = cur['range'] <= 0.85 * atr
        is_low_volume = cur['vol_ratio'] <= 1.05 and cur['tick_volume'] < climax_sell['tick_volume'] * 0.75
        holds_high = cur['high'] <= (climax_sell['high'] + 0.20 * atr)

        if is_narrow_spread and is_low_volume and holds_high and cur['close'] < cur['open']:
            entry = round(cur['close'], 2)
            sl = round(max(climax_sell['high'], cur['high']) + max(0.20 * atr, 0.30), 2)
            risk = sl - entry
            if 1.5 <= risk <= 6.0:
                tp = round(entry - (risk * rr), 2)
                return {
                    "signal": "SELL",
                    "engine": "Wyckoff_VSA",
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "risk": risk,
                    "pattern": f"VSA Bear Test (Climax Vol: {climax_sell['vol_ratio']:.1f}x -> Test Vol: {cur['vol_ratio']:.1f}x)",
                    "be_ratio": 0.40
                }

    return None


# -----------------------------------------------------------------------------
# ENGINE B: LONDON CLOSE REVERSAL (16:00 LONDON FIXING / 22:00 BKK)
# -----------------------------------------------------------------------------
def evaluate_london_close_reversal(df, idx, tf="M15", retrace_pct=0.35):
    """Engine B: London Close Reversal (Fixing Window).
    Hours 16 to 18 server time (UTC+6, corresponding to 15:00-17:00 UTC / 22:00-00:00 BKK).
    Occurs when market had a strong directional expansion and European desks square books.
    """
    if idx < 40 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05:
        return None

    hour = cur['hour']
    # London Fixing window: hours 16, 17, 18 server time
    if hour not in (16, 17, 18):
        return None

    day_range = cur['day_range']
    # Day must have expanded at least 15 USD in Gold
    if day_range < 15.0:
        return None

    day_high = cur['day_high']
    day_low = cur['day_low']

    # 1. BEARISH REVERSAL FROM DAY HIGH (Selling the London Top)
    # Price is within 20% of Day High, shows upper wick rejection
    dist_from_high = day_high - cur['close']
    at_day_high = dist_from_high <= (0.25 * day_range)
    has_upper_wick = cur['upper_wick_pct'] >= 0.35 and cur['close'] < cur['open']

    if at_day_high and has_upper_wick and cur['vol_ratio'] >= 1.15:
        entry = round(cur['close'], 2)
        sl = round(cur['high'] + max(0.20 * atr, 0.30), 2)
        # Target: 35% retracement of the entire daily range
        tp = round(day_high - (day_range * retrace_pct), 2)
        risk = sl - entry
        reward = entry - tp
        if risk > 0 and reward >= risk * 1.5:
            return {
                "signal": "SELL",
                "engine": "London_Close_Reversal",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "risk": risk,
                "pattern": f"London Close Fix Short (Day Range ${day_range:.1f} -> Target -{retrace_pct*100:.0f}%)",
                "be_ratio": 0.40
            }

    # 2. BULLISH REVERSAL FROM DAY LOW (Buying the London Bottom)
    dist_from_low = cur['close'] - day_low
    at_day_low = dist_from_low <= (0.25 * day_range)
    has_lower_wick = cur['lower_wick_pct'] >= 0.35 and cur['close'] > cur['open']

    if at_day_low and has_lower_wick and cur['vol_ratio'] >= 1.15:
        entry = round(cur['close'], 2)
        sl = round(cur['low'] - max(0.20 * atr, 0.30), 2)
        tp = round(day_low + (day_range * retrace_pct), 2)
        risk = entry - sl
        reward = tp - entry
        if risk > 0 and reward >= risk * 1.5:
            return {
                "signal": "BUY",
                "engine": "London_Close_Reversal",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "risk": risk,
                "pattern": f"London Close Fix Long (Day Range ${day_range:.1f} -> Target +{retrace_pct*100:.0f}%)",
                "be_ratio": 0.40
            }

    return None
