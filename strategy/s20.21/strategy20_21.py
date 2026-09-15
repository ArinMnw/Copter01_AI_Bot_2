# -*- coding: utf-8 -*-
"""strategy20_21.py — S20.21 Triple Institutional Matrix:
1. Engine 1: SMT Divergence (Gold vs Silver Intermarket Divergence)
2. Engine 2: London & NY Judas Swing (Open Drive Liquidity Trap)
3. Engine 3: Breaker Block & Mitigation (Institutional Order Flow Flip)
"""

import pandas as pd
import numpy as np
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


def compute_indicators_df(rates, correlated_rates=None):
    """Compute indicators for Gold and optional correlated asset (e.g. Silver XAGUSD.iux)."""
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
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

    # Trend MA
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

    # Volume
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # Swings (lookback 10)
    df['swing_high_10'] = df['high'].rolling(10).max().shift(1)
    df['swing_low_10'] = df['low'].rolling(10).min().shift(1)

    # If correlated asset provided (e.g. Silver)
    if correlated_rates is not None:
        c_df = pd.DataFrame(correlated_rates)
        c_df['c_swing_high_10'] = c_df['high'].rolling(10).max().shift(1)
        c_df['c_swing_low_10'] = c_df['low'].rolling(10).min().shift(1)
        # Merge on time
        df = pd.merge_asof(df, c_df[['time', 'high', 'low', 'close', 'c_swing_high_10', 'c_swing_low_10']],
                           on='time', suffixes=('', '_corr'))

    return df


# -----------------------------------------------------------------------------
# ENGINE 1: SMT DIVERGENCE (GOLD VS CORRELATED ASSET / SILVER)
# -----------------------------------------------------------------------------
def evaluate_smt_divergence(df, idx, tf="M15", rr=2.0):
    """Engine 1: SMT Divergence.
    Compares Gold swings with Correlated Asset (Silver or Internal HTF Correlation).
    """
    if idx < 20 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05 or cur['hour'] in (23, 0):
        return None

    # Check if external correlated columns exist
    has_corr = 'high_corr' in df.columns and not pd.isna(cur.get('high_corr', np.nan))

    if has_corr:
        # True Intermarket SMT (Gold vs Silver)
        gold_high_sweep = cur['high'] > cur['swing_high_10']
        silver_high_sweep = cur['high_corr'] > cur['c_swing_high_10']

        gold_low_sweep = cur['low'] < cur['swing_low_10']
        silver_low_sweep = cur['low_corr'] < cur['c_swing_low_10']

        # BEARISH SMT: Gold made Higher High, but Silver failed to make Higher High!
        bearish_smt = gold_high_sweep and not silver_high_sweep and cur['upper_wick_pct'] >= 0.35
        # BULLISH SMT: Gold made Lower Low, but Silver refused to make Lower Low!
        bullish_smt = gold_low_sweep and not silver_low_sweep and cur['lower_wick_pct'] >= 0.35
    else:
        # Single-market SMT (Price vs CVD/Momentum Divergence)
        # Gold sweeps high but RSI/Volume fails
        bearish_smt = (cur['high'] > cur['swing_high_10']) and (cur['close'] < cur['swing_high_10']) and (cur['upper_wick_pct'] >= 0.40) and (cur['vol_ratio'] >= 1.25)
        bullish_smt = (cur['low'] < cur['swing_low_10']) and (cur['close'] > cur['swing_low_10']) and (cur['lower_wick_pct'] >= 0.40) and (cur['vol_ratio'] >= 1.25)

    if bullish_smt:
        entry = round(cur['close'], 2)
        sl = round(cur['low'] - max(0.20 * atr, 0.30), 2)
        risk = entry - sl
        if 1.5 <= risk <= 6.0:
            tp = round(entry + (risk * rr), 2)
            return {"signal": "BUY", "engine": "SMT_Divergence", "entry": entry, "sl": sl, "tp": tp, "risk": risk, "be_ratio": 0.40}

    if bearish_smt:
        entry = round(cur['close'], 2)
        sl = round(cur['high'] + max(0.20 * atr, 0.30), 2)
        risk = sl - entry
        if 1.5 <= risk <= 6.0:
            tp = round(entry - (risk * rr), 2)
            return {"signal": "SELL", "engine": "SMT_Divergence", "entry": entry, "sl": sl, "tp": tp, "risk": risk, "be_ratio": 0.40}

    return None


# -----------------------------------------------------------------------------
# ENGINE 2: LONDON & NY OPEN JUDAS SWING
# -----------------------------------------------------------------------------
def evaluate_judas_swing(df, idx, tf="M15", rr=2.2):
    """Engine 2: Judas Swing.
    Detects false drive in the first 45 mins of London (08:00-09:30 UTC / 09:00-10:30 server)
    or NY Open (13:30-15:00 UTC / 14:30-16:00 server).
    """
    if idx < 40 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05:
        return None

    hour = cur['hour']
    # London Open window: hours 8, 9 server time | NY Open window: hours 14, 15 server time
    is_killzone = hour in (8, 9, 14, 15)
    if not is_killzone:
        return None

    # Asian session range (hours 0 to 7 server time)
    prev_bars = df.iloc[max(0, idx - 30):idx]
    asian_bars = prev_bars[prev_bars['hour'] < 8]
    if len(asian_bars) < 8:
        return None

    asian_high = asian_bars['high'].max()
    asian_low = asian_bars['low'].min()
    asian_mid = (asian_high + asian_low) / 2.0

    # 1. BEARISH JUDAS: Fake rally piercing Asian High then rejecting
    swept_asian_high = (cur['high'] > asian_high) and (cur['close'] < asian_high)
    has_upper_wick = cur['upper_wick_pct'] >= 0.35
    if swept_asian_high and has_upper_wick and cur['vol_ratio'] >= 1.20:
        entry = round(cur['close'], 2)
        sl = round(cur['high'] + max(0.20 * atr, 0.30), 2)
        risk = sl - entry
        if 1.5 <= risk <= 6.0:
            tp = round(entry - (risk * rr), 2)
            return {"signal": "SELL", "engine": "Judas_Swing", "entry": entry, "sl": sl, "tp": tp, "risk": risk, "be_ratio": 0.35}

    # 2. BULLISH JUDAS: Fake dump piercing Asian Low then rejecting
    swept_asian_low = (cur['low'] < asian_low) and (cur['close'] > asian_low)
    has_lower_wick = cur['lower_wick_pct'] >= 0.35
    if swept_asian_low and has_lower_wick and cur['vol_ratio'] >= 1.20:
        entry = round(cur['close'], 2)
        sl = round(cur['low'] - max(0.20 * atr, 0.30), 2)
        risk = entry - sl
        if 1.5 <= risk <= 6.0:
            tp = round(entry + (risk * rr), 2)
            return {"signal": "BUY", "engine": "Judas_Swing", "entry": entry, "sl": sl, "tp": tp, "risk": risk, "be_ratio": 0.35}

    return None


# -----------------------------------------------------------------------------
# ENGINE 3: INSTITUTIONAL BREAKER BLOCK & MITIGATION
# -----------------------------------------------------------------------------
def evaluate_breaker_block(df, idx, tf="M15", rr=2.0):
    """Engine 3: Breaker Block (BOS + Order Block Mitigation).
    A failed swing high/low that caused a liquidity sweep, then got broken violently.
    """
    if idx < 25 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05 or cur['hour'] in (23, 0):
        return None

    recent_10 = df.iloc[idx - 10:idx]
    local_high = recent_10['high'].max()
    local_low = recent_10['low'].min()

    # 1. BULLISH BREAKER:
    # Price swept low earlier, then violently broke above local_high (BOS).
    # Current bar pulls back to test the broken zone (Mitigation)
    prev_bar = df.iloc[idx - 1]
    was_breaking_up = prev_bar['close'] > local_high
    retesting_zone_buy = (cur['low'] <= local_high) and (cur['close'] >= local_high) and (cur['close'] > cur['open'])

    if was_breaking_up and retesting_zone_buy and cur['close'] > cur['ema_50']:
        entry = round(cur['close'], 2)
        sl = round(local_high - (0.6 * atr), 2)
        risk = entry - sl
        if 1.5 <= risk <= 6.0:
            tp = round(entry + (risk * rr), 2)
            return {"signal": "BUY", "engine": "Breaker_Block", "entry": entry, "sl": sl, "tp": tp, "risk": risk, "be_ratio": 0.40}

    # 2. BEARISH BREAKER:
    # Price swept high earlier, then violently broke below local_low (BOS).
    # Current bar pulls back to retest the broken zone
    was_breaking_down = prev_bar['close'] < local_low
    retesting_zone_sell = (cur['high'] >= local_low) and (cur['close'] <= local_low) and (cur['close'] < cur['open'])

    if was_breaking_down and retesting_zone_sell and cur['close'] < cur['ema_50']:
        entry = round(cur['close'], 2)
        sl = round(local_low + (0.6 * atr), 2)
        risk = sl - entry
        if 1.5 <= risk <= 6.0:
            tp = round(entry - (risk * rr), 2)
            return {"signal": "SELL", "engine": "Breaker_Block", "entry": entry, "sl": sl, "tp": tp, "risk": risk, "be_ratio": 0.40}

    return None
