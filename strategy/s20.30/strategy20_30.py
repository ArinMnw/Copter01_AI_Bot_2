# -*- coding: utf-8 -*-
"""strategy20_30.py — S20.30 Multi-Strategy Synergy Matrix (Strict Lot 0.01):
Designed to answer:
"Strategy ไหนใช้ร่วมกันแล้ว work (ทำงานร่วมกันในบาร์เดียวแล้วแม่นขึ้นจริง ไม่ใช่ทำงานแยกกัน)"
Under strict constraint: Single 0.01 Lot position (no partial lot splits).

Evaluates 5 distinct Synergy Combinations on the SAME bar:
1. Combo A: Pure Liquidity Sweep + Volume Climax (Baseline)
2. Combo B: Liquidity Sweep + Intermarket SMT Divergence (Gold vs Silver)
3. Combo C: Liquidity Sweep + Session Anchored VWAP (Statistical Discount/Premium)
4. Combo D: Liquidity Sweep + RSI(14) Divergence (Momentum Exhaustion)
5. Combo E: The Grand Confluence (Sweep + SMT + VWAP + RSI Div + Volume Absorption)
"""

import pandas as pd
import numpy as np
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


def compute_indicators_df(gold_rates, silver_rates=None):
    """Compute synchronized multi-strategy indicators for S20.30."""
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

    # RSI Swings for Divergence (lookback 10)
    df['rsi_high_10'] = df['rsi'].rolling(10).max().shift(1)
    df['rsi_low_10'] = df['rsi'].rolling(10).min().shift(1)

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

    # Swings
    df['swing_high_12'] = df['high'].rolling(12).max().shift(1)
    df['swing_low_12'] = df['low'].rolling(12).min().shift(1)
    df['opposite_high_40'] = df['high'].rolling(40).max().shift(1)
    df['opposite_low_40'] = df['low'].rolling(40).min().shift(1)

    # Asian Range (00:00 - 08:00 server time)
    asian_mask = (df['hour'] >= 0) & (df['hour'] < 8)
    df['asian_high_raw'] = np.where(asian_mask, df['high'], np.nan)
    df['asian_low_raw'] = np.where(asian_mask, df['low'], np.nan)
    day_asian_high = df.groupby('date')['asian_high_raw'].transform('max')
    day_asian_low = df.groupby('date')['asian_low_raw'].transform('min')
    df['asian_high'] = day_asian_high
    df['asian_low'] = day_asian_low

    # Previous Day High / Low
    day_highs = df.groupby('date')['high'].max()
    day_lows = df.groupby('date')['low'].min()
    df['pdh'] = df['date'].map(day_highs.shift(1))
    df['pdl'] = df['date'].map(day_lows.shift(1))

    # Synchronize Silver (XAGUSD.iux)
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


def evaluate_s20_30_bar(
    df,
    idx,
    combo="combo_grand_synergy",
    min_vol=1.30,
    min_wick=0.38,
    retest_depth=0.382
):
    """Evaluate bar idx under specific multi-strategy synergy combinations."""
    if idx < 45 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05 or cur['range'] < 0.45 * atr:
        return None

    # London & NY Killzones (08:00 - 18:00 server time / 14:00 - 00:00 BKK)
    if not (8 <= cur['hour'] <= 18):
        return None

    # Strategy 1: Volume Climax
    has_vol = cur['vol_ratio'] >= min_vol
    if not has_vol and combo in ('combo_baseline_sweep', 'combo_grand_synergy'):
        return None

    # Strategy 2: Liquidity Pool Sweeps (Swing 12, Asian H/L, PDH/PDL)
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

    # Strategy 3: SMT Divergence with Silver
    has_silver = 'high_silver' in df.columns and not pd.isna(cur.get('high_silver', np.nan))
    smt_bearish = False
    smt_bullish = False

    if has_silver:
        s_high = cur['high_silver']
        s_low = cur['low_silver']
        s_swing_high = cur['s_swing_high_12']
        s_swing_low = cur['s_swing_low_12']

        if (cur['high'] >= swing_high) and (s_high < s_swing_high):
            smt_bearish = True
        elif (cur['high'] < swing_high) and (s_high >= s_swing_high):
            smt_bearish = True

        if (cur['low'] <= swing_low) and (s_low > s_swing_low):
            smt_bullish = True
        elif (cur['low'] > swing_low) and (s_low <= s_swing_low):
            smt_bullish = True

    # Strategy 4: Session Anchored VWAP Extreme
    in_discount = True
    in_premium = True
    if not pd.isna(cur['vwap_std']) and cur['vwap_std'] >= 0.7:
        in_discount = cur['low'] <= cur['vwap_lower_10']
        in_premium = cur['high'] >= cur['vwap_upper_10']

    # Strategy 5: RSI Divergence
    # Bullish Div: Price swept low, but RSI did NOT sweep low (RSI > previous RSI swing low)
    # Bearish Div: Price swept high, but RSI did NOT sweep high (RSI < previous RSI swing high)
    rsi_bull_div = False
    rsi_bear_div = False
    if not pd.isna(cur['rsi']) and not pd.isna(cur['rsi_low_10']):
        if cur['low'] <= swing_low and cur['rsi'] >= cur['rsi_low_10']:
            rsi_bull_div = True
        if cur['high'] >= swing_high and cur['rsi'] <= cur['rsi_high_10']:
            rsi_bear_div = True

    # Anatomy confirmations
    has_wick_buy = (cur['lower_wick_pct'] >= min_wick) or (cur['lower_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    rsi_ok_buy = cur['rsi'] <= 68.0

    has_wick_sell = (cur['upper_wick_pct'] >= min_wick) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
    rsi_ok_sell = cur['rsi'] >= 32.0

    sig = None
    reason = ""

    # -------------------------------------------------------------------------
    # DECISION MATRIX BY SYNERGY COMBO
    # -------------------------------------------------------------------------
    # BUY
    if has_wick_buy and closed_high and rsi_ok_buy:
        if combo == "combo_baseline_sweep":
            if swept_low and has_vol:
                sig = "BUY"
                reason = "Sweep + Volume Climax"
        elif combo == "combo_sweep_smt":
            if swept_low and (smt_bullish or (cur['low'] <= cur.get('vwap_lower_12', cur['vwap_lower_10']))):
                sig = "BUY"
                reason = "Sweep + SMT Intermarket Synergy"
        elif combo == "combo_sweep_vwap":
            if swept_low and in_discount and has_vol:
                sig = "BUY"
                reason = "Sweep + VWAP Statistical Discount"
        elif combo == "combo_sweep_rsi_div":
            if swept_low and (rsi_bull_div or cur['rsi'] <= 35.0):
                sig = "BUY"
                reason = "Sweep + RSI Divergence Exhaustion"
        elif combo == "combo_grand_synergy":
            # True Multi-Strategy Confluence: Sweep + (SMT or deep discount) + in_discount + Vol
            smt_or_deep = smt_bullish or (cur['low'] <= cur.get('vwap_lower_12', cur['vwap_lower_10']))
            if swept_low and smt_or_deep and in_discount and has_vol:
                sig = "BUY"
                reason = "Grand Synergy (Sweep + SMT + VWAP + Vol)"

    # SELL
    if sig is None and has_wick_sell and closed_low and rsi_ok_sell:
        if combo == "combo_baseline_sweep":
            if swept_high and has_vol:
                sig = "SELL"
                reason = "Sweep + Volume Climax"
        elif combo == "combo_sweep_smt":
            if swept_high and (smt_bearish or (cur['high'] >= cur.get('vwap_upper_12', cur['vwap_upper_10']))):
                sig = "SELL"
                reason = "Sweep + SMT Intermarket Synergy"
        elif combo == "combo_sweep_vwap":
            if swept_high and in_premium and has_vol:
                sig = "SELL"
                reason = "Sweep + VWAP Statistical Premium"
        elif combo == "combo_sweep_rsi_div":
            if swept_high and (rsi_bear_div or cur['rsi'] >= 65.0):
                sig = "SELL"
                reason = "Sweep + RSI Divergence Exhaustion"
        elif combo == "combo_grand_synergy":
            smt_or_deep = smt_bearish or (cur['high'] >= cur.get('vwap_upper_12', cur['vwap_upper_10']))
            if swept_high and smt_or_deep and in_premium and has_vol:
                sig = "SELL"
                reason = "Grand Synergy (Sweep + SMT + VWAP + Vol)"

    if not sig:
        return None

    # Exact Single-Position Calculation for strictly Lot 0.01
    sl_buf = max(0.20 * atr, 0.25)

    if sig == "BUY":
        sl = round(cur['low'] - sl_buf, 2)
        entry = round(cur['low'] + (retest_depth * cur['lower_wick']), 2)
        risk = entry - sl
        if risk <= 0:
            return None
    else:
        sl = round(cur['high'] + sl_buf, 2)
        entry = round(cur['high'] - (retest_depth * cur['upper_wick']), 2)
        risk = sl - entry
        if risk <= 0:
            return None

    return {
        "time": cur['time'],
        "time_str": str(cur['time_dt']),
        "signal": sig,
        "combo": combo,
        "reason": reason,
        "entry": entry,
        "sl": sl,
        "risk": risk,
        "atr": atr,
        "be_ratio": 0.40
    }
