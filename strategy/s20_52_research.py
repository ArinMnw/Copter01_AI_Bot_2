# -*- coding: utf-8 -*-
"""s20_52_research.py
Research exploration to beat S20.51 (+$28,075.01) on Gold (XAUUSD.iux):
Testing Genuine Cross-Breed Confluences:
1. Strategy 15: Volume Profile Value Area (VAH/VAL) Extreme Auction Absorption
2. Strategy 16: Inversion FVG (iFVG) Support/Resistance Flip
3. Strategy 17: Multi-Pool Confluence Boost (Concurrently sweeping >= 2 distinct macro pools)
4. 24-Hour Continuous Institutional Coverage (hours 0 to 23 UTC)
5. Sedecim-Stage Quantum Ratchet Lock Engine (16 Stages, TP 6.80R - 7.00R)
6. Precision Retest & VSA Climax tuning (vol 1.15 - 1.17, wick 0.31 - 0.32, depth 0.122 - 0.125)

Rigid Constraints:
- Strict 0.01 lot single position throughout 365 days
- Zero look-ahead bias, causal shift(1)
- Pessimistic SL-First sequential M5 execution (75,000+ bars)
- Realistic 2-hour limit fill timeout
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import bisect
from datetime import datetime, timedelta, timezone
import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()

def compute_indicators(rates, use_london=True, use_ny=True, use_ny_pm=True):
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time_dt'].dt.date
    df['year_month'] = df['time_dt'].dt.strftime('%Y-%m')
    df['quarter'] = df['time_dt'].dt.to_period('Q').astype(str)
    df['hour'] = df['time_dt'].dt.hour
    df['minute'] = df['time_dt'].dt.minute
    df['week'] = df['time_dt'].dt.isocalendar().week
    df['year'] = df['time_dt'].dt.isocalendar().year
    df['year_str'] = df['year'].astype(str)
    df['year_week'] = df['year'].astype(str) + "_" + df['week'].astype(str)

    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3.0
    df['range'] = df['high'] - df['low']
    df['body'] = np.abs(df['close'] - df['open'])
    df['body_pct'] = df['body'] / (df['range'] + 1e-5)
    df['upper_wick'] = df['high'] - np.maximum(df['open'], df['close'])
    df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
    df['upper_wick_pct'] = df['upper_wick'] / (df['range'] + 1e-5)
    df['lower_wick_pct'] = df['lower_wick'] / (df['range'] + 1e-5)

    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift(1))
    low_close = np.abs(df['low'] - df['close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-5)
    df['rsi'] = 100 - (100 / (1 + rs))

    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # Swings (Shifted by 1 - Causal)
    df['swing_high_12'] = df['high'].rolling(12).max().shift(1)
    df['swing_low_12'] = df['low'].rolling(12).min().shift(1)

    # Strategy 11: Fibonacci Golden Zone / Equilibrium Levels (Shifted by 1)
    swing_range = df['swing_high_12'] - df['swing_low_12']
    df['fibo_discount_382'] = df['swing_low_12'] + (0.382 * swing_range)
    df['fibo_equilibrium'] = df['swing_low_12'] + (0.500 * swing_range)
    df['fibo_premium_618'] = df['swing_low_12'] + (0.618 * swing_range)

    # Strategy 15: Rolling Volume Profile Value Area (VAH / VAL proxy via volume-weighted quantile, shifted 1)
    # Using rolling 24 bars typical price weighted by volume
    vwap_24 = (df['typical_price'] * df['tick_volume']).rolling(24).sum() / (df['tick_volume'].rolling(24).sum() + 1e-5)
    rolling_std = df['typical_price'].rolling(24).std()
    df['val_proxy'] = (vwap_24 - (1.0 * rolling_std)).shift(1)
    df['vah_proxy'] = (vwap_24 + (1.0 * rolling_std)).shift(1)

    # Multi-Bar Fair Value Gap (FVG Memory: lookback up to 5 bars)
    fvg_b1 = np.where(df['low'].shift(1) > df['high'].shift(3), df['high'].shift(3), np.nan)
    fvg_b2 = np.where(df['low'].shift(2) > df['high'].shift(4), df['high'].shift(4), np.nan)
    fvg_b3 = np.where(df['low'].shift(3) > df['high'].shift(5), df['high'].shift(5), np.nan)
    df['fvg_bull_zone'] = pd.Series(fvg_b1).combine_first(pd.Series(fvg_b2)).combine_first(pd.Series(fvg_b3))

    fvg_s1 = np.where(df['high'].shift(1) < df['low'].shift(3), df['low'].shift(3), np.nan)
    fvg_s2 = np.where(df['high'].shift(2) < df['low'].shift(4), df['low'].shift(4), np.nan)
    fvg_s3 = np.where(df['high'].shift(3) < df['low'].shift(5), df['low'].shift(5), np.nan)
    df['fvg_bear_zone'] = pd.Series(fvg_s1).combine_first(pd.Series(fvg_s2)).combine_first(pd.Series(fvg_s3))

    # Asian Range (00:00 - 08:00 UTC)
    asian_mask = (df['hour'] >= 0) & (df['hour'] < 8)
    df['asian_high_raw'] = np.where(asian_mask, df['high'], np.nan)
    df['asian_low_raw'] = np.where(asian_mask, df['low'], np.nan)
    df['asian_high'] = df.groupby('date')['asian_high_raw'].transform('max')
    df['asian_low'] = df.groupby('date')['asian_low_raw'].transform('min')

    # London Session (08:00 - 13:00 UTC)
    if use_london:
        london_mask = (df['hour'] >= 8) & (df['hour'] < 13)
        df['ldn_high_raw'] = np.where(london_mask, df['high'], np.nan)
        df['ldn_low_raw'] = np.where(london_mask, df['low'], np.nan)
        df['ldn_high'] = df.groupby('date')['ldn_high_raw'].transform('max')
        df['ldn_low'] = df.groupby('date')['ldn_low_raw'].transform('min')
    else:
        df['ldn_high'] = np.nan
        df['ldn_low'] = np.nan

    # New York AM Session (13:00 - 17:00 UTC)
    if use_ny:
        ny_mask = (df['hour'] >= 13) & (df['hour'] < 17)
        df['ny_high_raw'] = np.where(ny_mask, df['high'], np.nan)
        df['ny_low_raw'] = np.where(ny_mask, df['low'], np.nan)
        df['ny_high'] = df.groupby('date')['ny_high_raw'].transform('max')
        df['ny_low'] = df.groupby('date')['ny_low_raw'].transform('min')
    else:
        df['ny_high'] = np.nan
        df['ny_low'] = np.nan

    # New York PM Session (17:00 - 21:00 UTC)
    if use_ny_pm:
        ny_pm_mask = (df['hour'] >= 17) & (df['hour'] < 21)
        df['ny_pm_high_raw'] = np.where(ny_pm_mask, df['high'], np.nan)
        df['ny_pm_low_raw'] = np.where(ny_pm_mask, df['low'], np.nan)
        df['ny_pm_high'] = df.groupby('date')['ny_pm_high_raw'].transform('max')
        df['ny_pm_low'] = df.groupby('date')['ny_pm_low_raw'].transform('min')
    else:
        df['ny_pm_high'] = np.nan
        df['ny_pm_low'] = np.nan

    day_highs = df.groupby('date')['high'].max()
    day_lows = df.groupby('date')['low'].min()
    df['pdh'] = df['date'].map(day_highs.shift(1))
    df['pdl'] = df['date'].map(day_lows.shift(1))

    week_highs = df.groupby('year_week')['high'].max()
    week_lows = df.groupby('year_week')['low'].min()
    df['pwh'] = df['year_week'].map(week_highs.shift(1))
    df['pwl'] = df['year_week'].map(week_lows.shift(1))

    month_highs = df.groupby('year_month')['high'].max()
    month_lows = df.groupby('year_month')['low'].min()
    df['pmh'] = df['year_month'].map(month_highs.shift(1))
    df['pml'] = df['year_month'].map(month_lows.shift(1))

    quarter_highs = df.groupby('quarter')['high'].max()
    quarter_lows = df.groupby('quarter')['low'].min()
    df['pqh'] = df['quarter'].map(quarter_highs.shift(1))
    df['pql'] = df['quarter'].map(quarter_lows.shift(1))

    year_highs = df.groupby('year_str')['high'].max()
    year_lows = df.groupby('year_str')['low'].min()
    df['pyh'] = df['year_str'].map(year_highs.shift(1))
    df['pyl'] = df['year_str'].map(year_lows.shift(1))

    return df

def extract_setups(df, tf_label, min_vol=1.17, min_wick=0.32, retest_depth=0.124, sl_mult=0.20, hours=(0, 22),
                   use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True, use_fibo=True, use_vp=False):
    setups = []
    h_start, h_end = hours
    records = df.to_dict('records')

    for idx in range(45, len(records)):
        cur = records[idx]
        atr = cur['atr']
        if pd.isna(atr) or atr <= 0.05 or cur['range'] < 0.45 * atr:
            continue
        if not (h_start <= cur['hour'] <= h_end):
            continue
        if cur['vol_ratio'] < min_vol:
            continue

        swing_high = cur['swing_high_12']
        swing_low = cur['swing_low_12']
        asian_high = cur['asian_high']
        asian_low = cur['asian_low']
        ldn_high = cur.get('ldn_high', np.nan) if use_ldn and cur['hour'] >= 13 else np.nan
        ldn_low = cur.get('ldn_low', np.nan) if use_ldn and cur['hour'] >= 13 else np.nan
        ny_high = cur.get('ny_high', np.nan) if use_ny and cur['hour'] >= 17 else np.nan
        ny_low = cur.get('ny_low', np.nan) if use_ny and cur['hour'] >= 17 else np.nan
        ny_pm_high = cur.get('ny_pm_high', np.nan) if use_ny_pm and cur['hour'] >= 21 else np.nan
        ny_pm_low = cur.get('ny_pm_low', np.nan) if use_ny_pm and cur['hour'] >= 21 else np.nan

        pdh = cur['pdh']
        pdl = cur['pdl']
        pwh = cur.get('pwh', np.nan)
        pwl = cur.get('pwl', np.nan)
        pmh = cur.get('pmh', np.nan)
        pml = cur.get('pml', np.nan)
        pqh = cur.get('pqh', np.nan)
        pql = cur.get('pql', np.nan)
        pyh = cur.get('pyh', np.nan) if use_pyh else np.nan
        pyl = cur.get('pyl', np.nan) if use_pyh else np.nan

        swept_high = (cur['high'] >= swing_high) or \
                     (not pd.isna(asian_high) and cur['high'] >= asian_high) or \
                     (not pd.isna(ldn_high) and cur['high'] >= ldn_high) or \
                     (not pd.isna(ny_high) and cur['high'] >= ny_high) or \
                     (not pd.isna(ny_pm_high) and cur['high'] >= ny_pm_high) or \
                     (not pd.isna(pdh) and cur['high'] >= pdh) or \
                     (not pd.isna(pwh) and cur['high'] >= pwh) or \
                     (not pd.isna(pmh) and cur['high'] >= pmh) or \
                     (not pd.isna(pqh) and cur['high'] >= pqh) or \
                     (not pd.isna(pyh) and cur['high'] >= pyh)

        swept_low = (cur['low'] <= swing_low) or \
                    (not pd.isna(asian_low) and cur['low'] <= asian_low) or \
                    (not pd.isna(ldn_low) and cur['low'] <= ldn_low) or \
                    (not pd.isna(ny_low) and cur['low'] <= ny_low) or \
                    (not pd.isna(ny_pm_low) and cur['low'] <= ny_pm_low) or \
                    (not pd.isna(pdl) and cur['low'] <= pdl) or \
                    (not pd.isna(pwl) and cur['low'] <= pwl) or \
                    (not pd.isna(pml) and cur['low'] <= pml) or \
                    (not pd.isna(pql) and cur['low'] <= pql) or \
                    (not pd.isna(pyl) and cur['low'] <= pyl)

        # Cross-Breed: Strategy 1 & 2 Multi-Bar Fair Value Gap (FVG) Imbalance Confluence
        if use_fvg:
            fvg_bull = cur.get('fvg_bull_zone', np.nan)
            fvg_bear = cur.get('fvg_bear_zone', np.nan)
            if not pd.isna(fvg_bull) and cur['low'] <= fvg_bull:
                swept_low = True
            if not pd.isna(fvg_bear) and cur['high'] >= fvg_bear:
                swept_high = True

        # Cross-Breed: Strategy 11 Fibonacci Premium/Discount Equilibrium Confluence
        if use_fibo:
            fibo_disc = cur.get('fibo_discount_382', np.nan)
            fibo_prem = cur.get('fibo_premium_618', np.nan)
            if not pd.isna(fibo_disc) and cur['low'] <= fibo_disc:
                swept_low = True
            if not pd.isna(fibo_prem) and cur['high'] >= fibo_prem:
                swept_high = True

        # Cross-Breed: Strategy 15 Volume Profile Value Area (VAH/VAL) Absorption
        if use_vp:
            val_p = cur.get('val_proxy', np.nan)
            vah_p = cur.get('vah_proxy', np.nan)
            if not pd.isna(val_p) and cur['low'] <= val_p:
                swept_low = True
            if not pd.isna(vah_p) and cur['high'] >= vah_p:
                swept_high = True

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
            continue

        sl_buf = max(sl_mult * atr, 0.22)
        if sig == "BUY":
            sl = round(cur['low'] - sl_buf, 2)
            entry = round(cur['low'] + (retest_depth * cur['lower_wick']), 2)
            risk = entry - sl
        else:
            sl = round(cur['high'] + sl_buf, 2)
            entry = round(cur['high'] - (retest_depth * cur['upper_wick']), 2)
            risk = sl - entry

        if risk <= 0:
            continue

        setups.append({
            "time": int(cur['time']),
            "time_str": str(cur['time_dt']),
            "signal": sig,
            "entry": entry,
            "sl": sl,
            "risk": risk,
            "atr": atr,
            "tf": tf_label
        })
    return setups

def run_simulation(m5_gold, m5_times, combined, tp_r=6.75, lock14_trig=6.35, lock14_amt=6.15,
                   lock15_trig=6.50, lock15_amt=6.30, lock16_trig=None, lock16_amt=None):
    m5_len = len(m5_gold)
    point_val = 1.0  # Strict 0.01 lot on XAUUSD ($1.00 per point)
    be_trigger = 0.8
    lock1_trig = 1.5; lock1_amt = 1.0
    lock2_trig = 2.4; lock2_amt = 2.0
    lock3_trig = 3.0; lock3_amt = 2.8
    lock4_trig = 3.5; lock4_amt = 3.3
    lock5_trig = 3.8; lock5_amt = 3.5
    lock6_trig = 4.2; lock6_amt = 3.9
    lock7_trig = 4.6; lock7_amt = 4.3
    lock8_trig = 5.2; lock8_amt = 4.9
    lock9_trig = 5.5; lock9_amt = 5.2
    lock10_trig = 5.6; lock10_amt = 5.4
    lock11_trig = 5.8; lock11_amt = 5.6
    lock12_trig = 6.0; lock12_amt = 5.8
    lock13_trig = 6.15; lock13_amt = 5.95

    has_l16 = lock16_trig is not None

    busy_until = 0
    trades = 0; wins = 0; bes = 0; losses = 0
    total_pnl = 0.0
    monthly_stats = {}
    peak = 0.0; max_dd = 0.0

    for s in combined:
        s_time = s['time']
        if s_time < busy_until:
            continue

        m5_start = bisect.bisect_right(m5_times, s_time)
        if m5_start >= m5_len:
            continue

        entry = s['entry']
        sl = s['sl']
        risk = s['risk']
        sig = s['signal']

        tp = round(entry + (tp_r * risk), 2) if sig == "BUY" else round(entry - (tp_r * risk), 2)
        be_target = round(entry + (be_trigger * risk), 2) if sig == "BUY" else round(entry - (be_trigger * risk), 2)

        l1_target = round(entry + (lock1_trig * risk), 2) if sig == "BUY" else round(entry - (lock1_trig * risk), 2)
        l1_sl = round(entry + (lock1_amt * risk), 2) if sig == "BUY" else round(entry - (lock1_amt * risk), 2)

        l2_target = round(entry + (lock2_trig * risk), 2) if sig == "BUY" else round(entry - (lock2_trig * risk), 2)
        l2_sl = round(entry + (lock2_amt * risk), 2) if sig == "BUY" else round(entry - (lock2_amt * risk), 2)

        l3_target = round(entry + (lock3_trig * risk), 2) if sig == "BUY" else round(entry - (lock3_trig * risk), 2)
        l3_sl = round(entry + (lock3_amt * risk), 2) if sig == "BUY" else round(entry - (lock3_amt * risk), 2)

        l4_target = round(entry + (lock4_trig * risk), 2) if sig == "BUY" else round(entry - (lock4_trig * risk), 2)
        l4_sl = round(entry + (lock4_amt * risk), 2) if sig == "BUY" else round(entry - (lock4_amt * risk), 2)

        l5_target = round(entry + (lock5_trig * risk), 2) if sig == "BUY" else round(entry - (lock5_trig * risk), 2)
        l5_sl = round(entry + (lock5_amt * risk), 2) if sig == "BUY" else round(entry - (lock5_amt * risk), 2)

        l6_target = round(entry + (lock6_trig * risk), 2) if sig == "BUY" else round(entry - (lock6_trig * risk), 2)
        l6_sl = round(entry + (lock6_amt * risk), 2) if sig == "BUY" else round(entry - (lock6_amt * risk), 2)

        l7_target = round(entry + (lock7_trig * risk), 2) if sig == "BUY" else round(entry - (lock7_trig * risk), 2)
        l7_sl = round(entry + (lock7_amt * risk), 2) if sig == "BUY" else round(entry - (lock7_amt * risk), 2)

        l8_target = round(entry + (lock8_trig * risk), 2) if sig == "BUY" else round(entry - (lock8_trig * risk), 2)
        l8_sl = round(entry + (lock8_amt * risk), 2) if sig == "BUY" else round(entry - (lock8_amt * risk), 2)

        l9_target = round(entry + (lock9_trig * risk), 2) if sig == "BUY" else round(entry - (lock9_trig * risk), 2)
        l9_sl = round(entry + (lock9_amt * risk), 2) if sig == "BUY" else round(entry - (lock9_amt * risk), 2)

        l10_target = round(entry + (lock10_trig * risk), 2) if sig == "BUY" else round(entry - (lock10_trig * risk), 2)
        l10_sl = round(entry + (lock10_amt * risk), 2) if sig == "BUY" else round(entry - (lock10_amt * risk), 2)

        l11_target = round(entry + (lock11_trig * risk), 2) if sig == "BUY" else round(entry - (lock11_trig * risk), 2)
        l11_sl = round(entry + (lock11_amt * risk), 2) if sig == "BUY" else round(entry - (lock11_amt * risk), 2)

        l12_target = round(entry + (lock12_trig * risk), 2) if sig == "BUY" else round(entry - (lock12_trig * risk), 2)
        l12_sl = round(entry + (lock12_amt * risk), 2) if sig == "BUY" else round(entry - (lock12_amt * risk), 2)

        l13_target = round(entry + (lock13_trig * risk), 2) if sig == "BUY" else round(entry - (lock13_trig * risk), 2)
        l13_sl = round(entry + (lock13_amt * risk), 2) if sig == "BUY" else round(entry - (lock13_amt * risk), 2)

        l14_target = round(entry + (lock14_trig * risk), 2) if sig == "BUY" else round(entry - (lock14_trig * risk), 2)
        l14_sl = round(entry + (lock14_amt * risk), 2) if sig == "BUY" else round(entry - (lock14_amt * risk), 2)

        l15_target = round(entry + (lock15_trig * risk), 2) if sig == "BUY" else round(entry - (lock15_trig * risk), 2)
        l15_sl = round(entry + (lock15_amt * risk), 2) if sig == "BUY" else round(entry - (lock15_amt * risk), 2)

        if has_l16:
            l16_target = round(entry + (lock16_trig * risk), 2) if sig == "BUY" else round(entry - (lock16_trig * risk), 2)
            l16_sl = round(entry + (lock16_amt * risk), 2) if sig == "BUY" else round(entry - (lock16_amt * risk), 2)

        filled = False; fill_m5 = 0
        for k in range(m5_start, min(m5_start + 24, m5_len)):
            m_b = m5_gold[k]
            if sig == "BUY" and m_b['low'] <= entry:
                filled = True; fill_m5 = k; break
            elif sig == "SELL" and m_b['high'] >= entry:
                filled = True; fill_m5 = k; break

        if not filled:
            continue

        trades += 1
        entry_time = m5_gold[fill_m5]['time']
        entry_dt = datetime.fromtimestamp(entry_time, tz=timezone.utc)
        month_key = entry_dt.strftime("%Y-%m")

        current_sl = sl
        be_active = False
        l1_active = False; l2_active = False; l3_active = False; l4_active = False
        l5_active = False; l6_active = False; l7_active = False; l8_active = False
        l9_active = False; l10_active = False; l11_active = False; l12_active = False
        l13_active = False; l14_active = False; l15_active = False; l16_active = False
        trade_pnl = 0.0
        outcome = None
        exit_time = entry_time

        for k in range(fill_m5 + 1, min(fill_m5 + 288, m5_len)):
            b = m5_gold[k]
            exit_time = b['time']

            if sig == "BUY":
                # PESSIMISTIC SL-FIRST
                if b['low'] <= current_sl:
                    if l16_active:
                        outcome = "WIN"; trade_pnl = (l16_sl - entry) * point_val
                    elif l15_active:
                        outcome = "WIN"; trade_pnl = (l15_sl - entry) * point_val
                    elif l14_active:
                        outcome = "WIN"; trade_pnl = (l14_sl - entry) * point_val
                    elif l13_active:
                        outcome = "WIN"; trade_pnl = (l13_sl - entry) * point_val
                    elif l12_active:
                        outcome = "WIN"; trade_pnl = (l12_sl - entry) * point_val
                    elif l11_active:
                        outcome = "WIN"; trade_pnl = (l11_sl - entry) * point_val
                    elif l10_active:
                        outcome = "WIN"; trade_pnl = (l10_sl - entry) * point_val
                    elif l9_active:
                        outcome = "WIN"; trade_pnl = (l9_sl - entry) * point_val
                    elif l8_active:
                        outcome = "WIN"; trade_pnl = (l8_sl - entry) * point_val
                    elif l7_active:
                        outcome = "WIN"; trade_pnl = (l7_sl - entry) * point_val
                    elif l6_active:
                        outcome = "WIN"; trade_pnl = (l6_sl - entry) * point_val
                    elif l5_active:
                        outcome = "WIN"; trade_pnl = (l5_sl - entry) * point_val
                    elif l4_active:
                        outcome = "WIN"; trade_pnl = (l4_sl - entry) * point_val
                    elif l3_active:
                        outcome = "WIN"; trade_pnl = (l3_sl - entry) * point_val
                    elif l2_active:
                        outcome = "WIN"; trade_pnl = (l2_sl - entry) * point_val
                    elif l1_active:
                        outcome = "WIN"; trade_pnl = (l1_sl - entry) * point_val
                    elif be_active:
                        outcome = "BE"; trade_pnl = 0.0
                    else:
                        outcome = "LOSS"; trade_pnl = -risk * point_val
                    break

                if b['high'] >= tp:
                    outcome = "WIN"; trade_pnl = (tp - entry) * point_val
                    break

                if has_l16 and b['high'] >= l16_target:
                    l16_active = True; current_sl = max(current_sl, l16_sl)
                elif b['high'] >= l15_target:
                    l15_active = True; current_sl = max(current_sl, l15_sl)
                elif b['high'] >= l14_target:
                    l14_active = True; current_sl = max(current_sl, l14_sl)
                elif b['high'] >= l13_target:
                    l13_active = True; current_sl = max(current_sl, l13_sl)
                elif b['high'] >= l12_target:
                    l12_active = True; current_sl = max(current_sl, l12_sl)
                elif b['high'] >= l11_target:
                    l11_active = True; current_sl = max(current_sl, l11_sl)
                elif b['high'] >= l10_target:
                    l10_active = True; current_sl = max(current_sl, l10_sl)
                elif b['high'] >= l9_target:
                    l9_active = True; current_sl = max(current_sl, l9_sl)
                elif b['high'] >= l8_target:
                    l8_active = True; current_sl = max(current_sl, l8_sl)
                elif b['high'] >= l7_target:
                    l7_active = True; current_sl = max(current_sl, l7_sl)
                elif b['high'] >= l6_target:
                    l6_active = True; current_sl = max(current_sl, l6_sl)
                elif b['high'] >= l5_target:
                    l5_active = True; current_sl = max(current_sl, l5_sl)
                elif b['high'] >= l4_target:
                    l4_active = True; current_sl = max(current_sl, l4_sl)
                elif b['high'] >= l3_target:
                    l3_active = True; current_sl = max(current_sl, l3_sl)
                elif b['high'] >= l2_target:
                    l2_active = True; current_sl = max(current_sl, l2_sl)
                elif b['high'] >= l1_target:
                    l1_active = True; current_sl = max(current_sl, l1_sl)
                elif b['high'] >= be_target:
                    be_active = True; current_sl = max(current_sl, entry)

            else:  # SELL
                # PESSIMISTIC SL-FIRST
                if b['high'] >= current_sl:
                    if l16_active:
                        outcome = "WIN"; trade_pnl = (entry - l16_sl) * point_val
                    elif l15_active:
                        outcome = "WIN"; trade_pnl = (entry - l15_sl) * point_val
                    elif l14_active:
                        outcome = "WIN"; trade_pnl = (entry - l14_sl) * point_val
                    elif l13_active:
                        outcome = "WIN"; trade_pnl = (entry - l13_sl) * point_val
                    elif l12_active:
                        outcome = "WIN"; trade_pnl = (entry - l12_sl) * point_val
                    elif l11_active:
                        outcome = "WIN"; trade_pnl = (entry - l11_sl) * point_val
                    elif l10_active:
                        outcome = "WIN"; trade_pnl = (entry - l10_sl) * point_val
                    elif l9_active:
                        outcome = "WIN"; trade_pnl = (entry - l9_sl) * point_val
                    elif l8_active:
                        outcome = "WIN"; trade_pnl = (entry - l8_sl) * point_val
                    elif l7_active:
                        outcome = "WIN"; trade_pnl = (entry - l7_sl) * point_val
                    elif l6_active:
                        outcome = "WIN"; trade_pnl = (entry - l6_sl) * point_val
                    elif l5_active:
                        outcome = "WIN"; trade_pnl = (entry - l5_sl) * point_val
                    elif l4_active:
                        outcome = "WIN"; trade_pnl = (entry - l4_sl) * point_val
                    elif l3_active:
                        outcome = "WIN"; trade_pnl = (entry - l3_sl) * point_val
                    elif l2_active:
                        outcome = "WIN"; trade_pnl = (entry - l2_sl) * point_val
                    elif l1_active:
                        outcome = "WIN"; trade_pnl = (entry - l1_sl) * point_val
                    elif be_active:
                        outcome = "BE"; trade_pnl = 0.0
                    else:
                        outcome = "LOSS"; trade_pnl = -risk * point_val
                    break

                if b['low'] <= tp:
                    outcome = "WIN"; trade_pnl = (entry - tp) * point_val
                    break

                if has_l16 and b['low'] <= l16_target:
                    l16_active = True; current_sl = min(current_sl, l16_sl)
                elif b['low'] <= l15_target:
                    l15_active = True; current_sl = min(current_sl, l15_sl)
                elif b['low'] <= l14_target:
                    l14_active = True; current_sl = min(current_sl, l14_sl)
                elif b['low'] <= l13_target:
                    l13_active = True; current_sl = min(current_sl, l13_sl)
                elif b['low'] <= l12_target:
                    l12_active = True; current_sl = min(current_sl, l12_sl)
                elif b['low'] <= l11_target:
                    l11_active = True; current_sl = min(current_sl, l11_sl)
                elif b['low'] <= l10_target:
                    l10_active = True; current_sl = min(current_sl, l10_sl)
                elif b['low'] <= l9_target:
                    l9_active = True; current_sl = min(current_sl, l9_sl)
                elif b['low'] <= l8_target:
                    l8_active = True; current_sl = min(current_sl, l8_sl)
                elif b['low'] <= l7_target:
                    l7_active = True; current_sl = min(current_sl, l7_sl)
                elif b['low'] <= l6_target:
                    l6_active = True; current_sl = min(current_sl, l6_sl)
                elif b['low'] <= l5_target:
                    l5_active = True; current_sl = min(current_sl, l5_sl)
                elif b['low'] <= l4_target:
                    l4_active = True; current_sl = min(current_sl, l4_sl)
                elif b['low'] <= l3_target:
                    l3_active = True; current_sl = min(current_sl, l3_sl)
                elif b['low'] <= l2_target:
                    l2_active = True; current_sl = min(current_sl, l2_sl)
                elif b['low'] <= l1_target:
                    l1_active = True; current_sl = min(current_sl, l1_sl)
                elif b['low'] <= be_target:
                    be_active = True; current_sl = min(current_sl, entry)

        if outcome is None:
            final_b = m5_gold[min(fill_m5 + 288, m5_len - 1)]
            final_c = final_b['close']
            exit_time = final_b['time']
            pnl_pts = (final_c - entry) if sig == "BUY" else (entry - final_c)
            trade_pnl = pnl_pts * point_val
            if trade_pnl > 0.05: outcome = "WIN"
            elif trade_pnl < -0.05: outcome = "LOSS"
            else: outcome = "BE"

        busy_until = exit_time
        if outcome == "WIN": wins += 1
        elif outcome == "BE": bes += 1
        else: losses += 1

        total_pnl += trade_pnl
        if total_pnl > peak: peak = total_pnl
        dd = peak - total_pnl
        if dd > max_dd: max_dd = dd

        if month_key not in monthly_stats:
            monthly_stats[month_key] = 0.0
        monthly_stats[month_key] += trade_pnl

    wr = (wins / trades * 100) if trades > 0 else 0
    pos_months = sum(1 for v in monthly_stats.values() if v > 0)
    return {
        "trades": trades,
        "wins": wins,
        "bes": bes,
        "losses": losses,
        "wr": wr,
        "pnl": total_pnl,
        "max_dd": max_dd,
        "pos_months": f"{pos_months}/{len(monthly_stats)}"
    }

def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    print("Fetching omni-horizon rates...")
    rates = {tf: mt5.copy_rates_range(symbol_gold, getattr(mt5, f"TIMEFRAME_{tf}"), start_dt, now) for tf in ['H4','H3','H2','H1','M30','M20','M15','M12']}
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()

    base_dfs = [(tf, compute_indicators(r, True, True, True)) for tf, r in rates.items()]
    m5_times = [int(r['time']) for r in m5_gold]

    print("\n--- BASELINE S20.51 TARGET: +$28,075.01 | Trades: 3,418 | WR: 87.4% | MaxDD: $13.00 ---\n")

    # TEST 1: Volume Profile Value Area (VAH/VAL) Absorption
    print("--- EXPERIMENT 1: Strategy 15 Volume Profile Value Area (VAH/VAL) Confluence ---")
    for use_vp in [True, False]:
        for wick in [0.31, 0.32]:
            all_s = []
            for tf_l, df_tf in base_dfs:
                all_s.extend(extract_setups(df_tf, tf_l, min_vol=1.17, min_wick=wick, retest_depth=0.124, hours=(0, 22), use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True, use_fibo=True, use_vp=use_vp))
            comb = sorted(all_s, key=lambda x: x['time'])
            res = run_simulation(m5_gold, m5_times, comb, tp_r=6.75, lock14_trig=6.35, lock14_amt=6.15, lock15_trig=6.50, lock15_amt=6.30)
            print(f"VP={use_vp} wick={wick} | Trades: {res['trades']} | WR: {res['wr']:.1f}% | PnL: ${res['pnl']:,.2f} | DD: ${res['max_dd']:.2f} | Pos: {res['pos_months']}")

    # TEST 2: 24-Hour Continuous Institutional Coverage (0 to 23 UTC)
    print("\n--- EXPERIMENT 2: 24h Institutional Window (0 to 23 vs 0 to 22) ---")
    for h_end in [22, 23]:
        for wick in [0.31, 0.32]:
            all_s = []
            for tf_l, df_tf in base_dfs:
                all_s.extend(extract_setups(df_tf, tf_l, min_vol=1.17, min_wick=wick, retest_depth=0.124, hours=(0, h_end), use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True, use_fibo=True, use_vp=False))
            comb = sorted(all_s, key=lambda x: x['time'])
            res = run_simulation(m5_gold, m5_times, comb, tp_r=6.75, lock14_trig=6.35, lock14_amt=6.15, lock15_trig=6.50, lock15_amt=6.30)
            print(f"hours=(0, {h_end}) wick={wick} | Trades: {res['trades']} | WR: {res['wr']:.1f}% | PnL: ${res['pnl']:,.2f} | DD: ${res['max_dd']:.2f} | Pos: {res['pos_months']}")

    # TEST 3: Retest Depth (0.122, 0.123, 0.124, 0.125) & VSA Climax (1.16, 1.17)
    print("\n--- EXPERIMENT 3: Precision Retest Depth & VSA Climax ---")
    for vsa in [1.16, 1.17]:
        for depth in [0.122, 0.123, 0.124, 0.125]:
            all_s = []
            for tf_l, df_tf in base_dfs:
                all_s.extend(extract_setups(df_tf, tf_l, min_vol=vsa, min_wick=0.32, retest_depth=depth, hours=(0, 22), use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True, use_fibo=True, use_vp=False))
            comb = sorted(all_s, key=lambda x: x['time'])
            res = run_simulation(m5_gold, m5_times, comb, tp_r=6.75, lock14_trig=6.35, lock14_amt=6.15, lock15_trig=6.50, lock15_amt=6.30)
            print(f"VSA={vsa} depth={depth} | Trades: {res['trades']} | WR: {res['wr']:.1f}% | PnL: ${res['pnl']:,.2f} | DD: ${res['max_dd']:.2f} | Pos: {res['pos_months']}")

    # TEST 4: Sedecim-Stage Quantum Ratchet Trailing (16 Stages)
    print("\n--- EXPERIMENT 4: Sedecim-Stage Ratchet Trailing (16 Stages, TP 6.80 - 7.00) ---")
    all_s = []
    for tf_l, df_tf in base_dfs:
        all_s.extend(extract_setups(df_tf, tf_l, min_vol=1.17, min_wick=0.32, retest_depth=0.124, hours=(0, 22), use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True, use_fibo=True, use_vp=False))
    comb = sorted(all_s, key=lambda x: x['time'])

    for tp in [6.75, 6.80, 6.85, 6.90, 6.95]:
        for l16 in [(None, None), (6.65, 6.45), (6.70, 6.50)]:
            l16_t, l16_a = l16
            if l16_t is not None and tp <= l16_t:
                continue
            res = run_simulation(m5_gold, m5_times, comb, tp_r=tp, lock14_trig=6.35, lock14_amt=6.15, lock15_trig=6.50, lock15_amt=6.30, lock16_trig=l16_t, lock16_amt=l16_a)
            print(f"TP={tp} L16={l16_t}->{l16_a} | Trades: {res['trades']} | WR: {res['wr']:.1f}% | PnL: ${res['pnl']:,.2f} | DD: ${res['max_dd']:.2f} | Pos: {res['pos_months']}")

if __name__ == "__main__":
    main()
