# -*- coding: utf-8 -*-
"""strategy20_22.py — S20.22 Tier-1 Bank & Quant Hedge Fund Strategies:
1. Engine 1: Session Anchored VWAP ±2.0/2.5σ Standard Deviation Reversion
2. Engine 2: Asian Range Fibonacci Expansion Multiplier (1.618x / 2.0x Daily Extreme)
3. Engine 3: Institutional Opening Range Breakout (ORB 30m with Volume Surge)
"""

import pandas as pd
import numpy as np
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


def compute_indicators_df(rates):
    """Compute indicators including Daily Anchored VWAP, Std Dev Bands, and Anatomy."""
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

    # Volume metrics
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # Trend moving averages
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

    # -------------------------------------------------------------
    # 1. DAILY ANCHORED VWAP & STANDARD DEVIATION BANDS
    # -------------------------------------------------------------
    df['pv'] = df['typical_price'] * df['tick_volume']
    
    # Calculate cumulative per day
    df['cum_pv'] = df.groupby('date')['pv'].cumsum()
    df['cum_vol'] = df.groupby('date')['tick_volume'].cumsum()
    df['vwap'] = df['cum_pv'] / (df['cum_vol'] + 1e-5)

    # Cumulative variance: Sum(Volume * (Price - VWAP)^2) / Sum(Volume)
    df['dev_sq'] = df['tick_volume'] * ((df['typical_price'] - df['vwap']) ** 2)
    df['cum_dev_sq'] = df.groupby('date')['dev_sq'].cumsum()
    df['vwap_std'] = np.sqrt(df['cum_dev_sq'] / (df['cum_vol'] + 1e-5))

    df['vwap_upper_2'] = df['vwap'] + (2.0 * df['vwap_std'])
    df['vwap_upper_25'] = df['vwap'] + (2.5 * df['vwap_std'])
    df['vwap_lower_2'] = df['vwap'] - (2.0 * df['vwap_std'])
    df['vwap_lower_25'] = df['vwap'] - (2.5 * df['vwap_std'])

    return df


# -----------------------------------------------------------------------------
# ENGINE 1: ANCHORED VWAP 2.0-2.5σ REVERSION
# -----------------------------------------------------------------------------
def evaluate_vwap_reversion(df, idx, tf="M15", target_mode="VWAP"):
    """Engine 1: Mean Reversion to VWAP when price is stretched beyond 2.0 - 2.5 Standard Deviations."""
    if idx < 20 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05 or pd.isna(cur['vwap_std']) or cur['vwap_std'] < 1.0:
        return None

    # Do not trade late rollover
    if cur['hour'] in (23, 0):
        return None

    # 1. SELL SETUP: Price stretched above Upper Band 2.0/2.5σ
    stretched_above = cur['high'] >= cur['vwap_upper_2']
    rejected_down = (cur['close'] < cur['vwap_upper_25']) and (cur['upper_wick_pct'] >= 0.35)
    closed_red_or_bear = cur['close'] <= (cur['high'] - 0.40 * cur['range'])

    if stretched_above and rejected_down and closed_red_or_bear and cur['vol_ratio'] >= 1.15:
        entry = round(cur['close'], 2)
        sl = round(cur['high'] + max(0.20 * atr, 0.30), 2)
        tp = round(cur['vwap'] + (0.5 * cur['vwap_std']), 2)  # Target near upper 0.5σ / VWAP
        risk = sl - entry
        reward = entry - tp
        if risk > 0 and reward >= risk * 1.3:
            return {"signal": "SELL", "engine": "VWAP_Reversion", "entry": entry, "sl": sl, "tp": tp, "risk": risk, "be_ratio": 0.40}

    # 2. BUY SETUP: Price stretched below Lower Band 2.0/2.5σ
    stretched_below = cur['low'] <= cur['vwap_lower_2']
    rejected_up = (cur['close'] > cur['vwap_lower_25']) and (cur['lower_wick_pct'] >= 0.35)
    closed_green_or_bull = cur['close'] >= (cur['low'] + 0.40 * cur['range'])

    if stretched_below and rejected_up and closed_green_or_bull and cur['vol_ratio'] >= 1.15:
        entry = round(cur['close'], 2)
        sl = round(cur['low'] - max(0.20 * atr, 0.30), 2)
        tp = round(cur['vwap'] - (0.5 * cur['vwap_std']), 2)  # Target near lower 0.5σ / VWAP
        risk = entry - sl
        reward = tp - entry
        if risk > 0 and reward >= risk * 1.3:
            return {"signal": "BUY", "engine": "VWAP_Reversion", "entry": entry, "sl": sl, "tp": tp, "risk": risk, "be_ratio": 0.40}

    return None


# -----------------------------------------------------------------------------
# ENGINE 2: ASIAN RANGE FIBONACCI EXPANSION (1.618x / 2.0x EXTREME)
# -----------------------------------------------------------------------------
def evaluate_asian_expansion(df, idx, tf="M15", mult=1.618):
    """Engine 2: Counter-trend reversal at Asian Range 1.618x / 2.0x mathematical projection."""
    if idx < 40 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05:
        return None

    hour = cur['hour']
    # Expansion targets typically hit during London or NY (10:00 - 18:00 server time)
    if not (10 <= hour <= 19):
        return None

    # Get Asian session bars (hours 0 to 7 server time of today)
    today = cur['date']
    day_bars = df[(df['date'] == today) & (df.index < idx) & (df['hour'] < 8)]
    if len(day_bars) < 8:
        return None

    asian_high = day_bars['high'].max()
    asian_low = day_bars['low'].min()
    asian_range = asian_high - asian_low
    if asian_range < 5.0 or asian_range > 25.0:
        return None

    # Fibonacci Expansion levels
    upper_extreme = asian_high + (asian_range * mult)
    lower_extreme = asian_low - (asian_range * mult)

    # 1. BEARISH EXHAUSTION AT UPPER EXPANSION
    hit_upper = cur['high'] >= upper_extreme
    rejection_upper = cur['upper_wick_pct'] >= 0.35 and cur['close'] < cur['high'] - 0.40 * cur['range']
    if hit_upper and rejection_upper and cur['vol_ratio'] >= 1.20:
        entry = round(cur['close'], 2)
        sl = round(cur['high'] + max(0.20 * atr, 0.30), 2)
        tp = round(asian_high + (asian_range * 0.5), 2)  # Pullback to 50% extension
        risk = sl - entry
        reward = entry - tp
        if risk > 0 and reward >= risk * 1.4:
            return {"signal": "SELL", "engine": "Asian_Expansion", "entry": entry, "sl": sl, "tp": tp, "risk": risk, "be_ratio": 0.40}

    # 2. BULLISH EXHAUSTION AT LOWER EXPANSION
    hit_lower = cur['low'] <= lower_extreme
    rejection_lower = cur['lower_wick_pct'] >= 0.35 and cur['close'] > cur['low'] + 0.40 * cur['range']
    if hit_lower and rejection_lower and cur['vol_ratio'] >= 1.20:
        entry = round(cur['close'], 2)
        sl = round(cur['low'] - max(0.20 * atr, 0.30), 2)
        tp = round(asian_low - (asian_range * 0.5), 2)  # Pullback to 50% extension
        risk = entry - sl
        reward = tp - entry
        if risk > 0 and reward >= risk * 1.4:
            return {"signal": "BUY", "engine": "Asian_Expansion", "entry": entry, "sl": sl, "tp": tp, "risk": risk, "be_ratio": 0.40}

    return None


# -----------------------------------------------------------------------------
# ENGINE 3: INSTITUTIONAL OPENING RANGE BREAKOUT (ORB 30m + VOLUME SURGE)
# -----------------------------------------------------------------------------
def evaluate_institutional_orb(df, idx, tf="M15", rr=2.0):
    """Engine 3: Trend Breakout of London 30m Opening Range (08:00-08:30 UTC / 09:00-09:30 server time)."""
    if idx < 40 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05:
        return None

    hour = cur['hour']
    # Trade in the breakout window (09:30 to 12:00 server time)
    if not (9 <= hour <= 12):
        return None

    today = cur['date']
    # 30-min Opening Range bars: bars at hour 9, minute 0 and 15 on M15
    orb_bars = df[(df['date'] == today) & (df['hour'] == 9) & (df.index < idx)]
    if len(orb_bars) < 2:
        return None

    orb_high = orb_bars['high'].max()
    orb_low = orb_bars['low'].min()
    orb_range = orb_high - orb_low
    if orb_range < 3.0 or orb_range > 15.0:
        return None

    prev_bar = df.iloc[idx - 1]
    # 1. BULLISH BREAKOUT
    breakout_buy = (cur['close'] > orb_high) and (prev_bar['close'] <= orb_high)
    strong_body_buy = cur['close'] > cur['open'] and cur['body_pct'] >= 0.50
    if breakout_buy and strong_body_buy and cur['vol_ratio'] >= 1.30:
        entry = round(cur['close'], 2)
        sl = round(orb_high - (0.5 * orb_range), 2)  # SL at mid of ORB
        risk = entry - sl
        if 1.5 <= risk <= 6.0:
            tp = round(entry + (risk * rr), 2)
            return {"signal": "BUY", "engine": "Institutional_ORB", "entry": entry, "sl": sl, "tp": tp, "risk": risk, "be_ratio": 0.40}

    # 2. BEARISH BREAKOUT
    breakout_sell = (cur['close'] < orb_low) and (prev_bar['close'] >= orb_low)
    strong_body_sell = cur['close'] < cur['open'] and cur['body_pct'] >= 0.50
    if breakout_sell and strong_body_sell and cur['vol_ratio'] >= 1.30:
        entry = round(cur['close'], 2)
        sl = round(orb_low + (0.5 * orb_range), 2)
        risk = sl - entry
        if 1.5 <= risk <= 6.0:
            tp = round(entry - (risk * rr), 2)
            return {"signal": "SELL", "engine": "Institutional_ORB", "entry": entry, "sl": sl, "tp": tp, "risk": risk, "be_ratio": 0.40}

    return None
