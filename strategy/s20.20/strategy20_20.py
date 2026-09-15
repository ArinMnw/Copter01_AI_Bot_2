# -*- coding: utf-8 -*-
"""strategy20_20.py — S20.20 Institutional Dual-Engine:
1. Engine A: Asymmetric R:R (1:7+) — HTF Macro Liquidity Run + LTF Sniper Mitigation.
2. Engine B: High Winrate (65%+) — Asian Session Liquidity Sweep & Mean Reversion (Judas Swing).
"""

import pandas as pd
import numpy as np
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


def compute_indicators_df(rates):
    """Compute indicators for S20.20."""
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    # BKK is UTC+7, server time is UTC+6 -> BKK = server + 1 hr
    # We can use bar hour directly
    df['hour'] = df['time_dt'].dt.hour

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

    # Volume
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # LTF Micro Swings (10 bars)
    df['ltf_low_10'] = df['low'].rolling(10).min().shift(1)
    df['ltf_high_10'] = df['high'].rolling(10).max().shift(1)

    # HTF Macro Swings (60 bars ~ 5 hours on M5 or 15 hours on M15)
    df['htf_target_high'] = df['high'].rolling(60).max().shift(1)
    df['htf_target_low'] = df['low'].rolling(60).min().shift(1)

    return df


def evaluate_asymmetric_rr(df, idx, tf="M5", min_rr=7.0):
    """Engine A: Asymmetric R:R (1:7+).
    Takes trades where LTF risk is small ($2.5 - $3.5) and HTF Target offers >= 7x reward.
    """
    if idx < 65 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    if pd.isna(cur['atr']) or pd.isna(cur['ema_200']):
        return None

    atr = cur['atr']
    if atr <= 0.05:
        return None

    # Rollover filter
    if cur['hour'] in (23, 0):
        return None

    # Trend Alignment with EMA 200
    is_uptrend = cur['close'] > cur['ema_200']
    is_downtrend = cur['close'] < cur['ema_200']

    # 1. BUY SETUP (Trend Following Dip + HTF Expansion)
    # Swept micro swing low during pullback
    swept_ltf_low = cur['low'] < cur['ltf_low_10']
    has_lower_rejection = cur['lower_wick_pct'] >= 0.40 or cur['lower_wick'] >= cur['body']
    closed_up = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    vol_surge = cur['vol_ratio'] >= 1.25

    if is_uptrend and swept_ltf_low and has_lower_rejection and closed_up and vol_surge:
        entry = round(cur['close'], 2)
        sl_buffer = max(0.20 * atr, 0.25)
        sl = round(cur['low'] - sl_buffer, 2)
        risk = entry - sl
        
        # Micro risk only ($2.00 - $4.00)
        if 2.0 <= risk <= 4.5:
            htf_target = cur['htf_target_high']
            reward = htf_target - entry
            rr_ratio = reward / risk
            
            if rr_ratio >= min_rr:
                tp = round(htf_target, 2)
                return {
                    "signal": "BUY",
                    "engine": "Asymmetric_RR",
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "risk": risk,
                    "reward": reward,
                    "rr_ratio": round(rr_ratio, 1),
                    "be_trigger": round(entry + (risk * 2.0), 2)  # Move to BE at 2R profit
                }

    # 2. SELL SETUP (Trend Following Rally + HTF Expansion)
    swept_ltf_high = cur['high'] > cur['ltf_high_10']
    has_upper_rejection = cur['upper_wick_pct'] >= 0.40 or cur['upper_wick'] >= cur['body']
    closed_down = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

    if is_downtrend and swept_ltf_high and has_upper_rejection and closed_down and vol_surge:
        entry = round(cur['close'], 2)
        sl_buffer = max(0.20 * atr, 0.25)
        sl = round(cur['high'] + sl_buffer, 2)
        risk = sl - entry

        if 2.0 <= risk <= 4.5:
            htf_target = cur['htf_target_low']
            reward = entry - htf_target
            rr_ratio = reward / risk

            if rr_ratio >= min_rr:
                tp = round(htf_target, 2)
                return {
                    "signal": "SELL",
                    "engine": "Asymmetric_RR",
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "risk": risk,
                    "reward": reward,
                    "rr_ratio": round(rr_ratio, 1),
                    "be_trigger": round(entry - (risk * 2.0), 2)  # Move to BE at 2R profit
                }

    return None


def evaluate_asian_mean_reversion(df, idx, tf="M5"):
    """Engine B: High Winrate Asian Range Sweep & Mean Reversion.
    Asian Session: 06:00 - 12:00 server time.
    London/NY Sweep: 13:00 - 19:00 server time.
    Target: Asian Equilibrium (Midpoint).
    """
    if idx < 60 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    hour = cur['hour']

    # Only trade during active London & NY open (12:00 - 19:00 server time)
    if not (12 <= hour <= 19):
        return None

    # Find today's Asian range (hours 5 to 11 server time)
    # Look back up to 40 bars to find bars in Asian hours
    lookback = df.iloc[max(0, idx - 60):idx]
    asian_bars = lookback[(lookback['hour'] >= 5) & (lookback['hour'] <= 11)]
    if len(asian_bars) < 15:
        return None

    asian_high = asian_bars['high'].max()
    asian_low = asian_bars['low'].min()
    asian_mid = (asian_high + asian_low) / 2.0
    asian_range = asian_high - asian_low

    # Asian range must be reasonable (not crazy news day)
    if asian_range < 4.0 or asian_range > 25.0:
        return None

    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05:
        return None

    # 1. BEARISH SWEEP OF ASIAN HIGH (SELL to Asian Midpoint)
    swept_asian_high = (cur['high'] > asian_high) and (cur['close'] < asian_high)
    has_upper_wick = cur['upper_wick_pct'] >= 0.35
    if swept_asian_high and has_upper_wick and cur['vol_ratio'] >= 1.20:
        entry = round(cur['close'], 2)
        sl = round(cur['high'] + max(0.20 * atr, 0.30), 2)
        tp = round(asian_mid, 2)
        risk = sl - entry
        reward = entry - tp
        if risk > 0 and reward > risk * 1.1:
            return {
                "signal": "SELL",
                "engine": "Asian_Mean_Reversion",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "risk": risk,
                "reward": reward,
                "rr_ratio": round(reward / risk, 1),
                "be_trigger": round(entry - (risk * 1.0), 2)
            }

    # 2. BULLISH SWEEP OF ASIAN LOW (BUY to Asian Midpoint)
    swept_asian_low = (cur['low'] < asian_low) and (cur['close'] > asian_low)
    has_lower_wick = cur['lower_wick_pct'] >= 0.35
    if swept_asian_low and has_lower_wick and cur['vol_ratio'] >= 1.20:
        entry = round(cur['close'], 2)
        sl = round(cur['low'] - max(0.20 * atr, 0.30), 2)
        tp = round(asian_mid, 2)
        risk = entry - sl
        reward = tp - entry
        if risk > 0 and reward > risk * 1.1:
            return {
                "signal": "BUY",
                "engine": "Asian_Mean_Reversion",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "risk": risk,
                "reward": reward,
                "rr_ratio": round(reward / risk, 1),
                "be_trigger": round(entry + (risk * 1.0), 2)
            }

    return None
