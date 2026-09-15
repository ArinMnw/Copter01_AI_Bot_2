# -*- coding: utf-8 -*-
"""s20_47_research.py
Explore breakthroughs to beat S20.46 (+$24,855.94) on STRICT LOT 0.01:
Hard Constraints:
1. Strict 0.01 lot single position throughout 365 days.
2. True Strategy Confluence on the same candle.
3. Zero look-ahead bias, causal backward-looking indicators (shift 1).
4. Pessimistic SL-First sequential engine across 75,000+ real M5 bars.
5. Realistic pending limit fill within 2 hours.
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

def compute_indicators(rates, use_london=True, use_ny=True):
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

    df['swing_high_12'] = df['high'].rolling(12).max().shift(1)
    df['swing_low_12'] = df['low'].rolling(12).min().shift(1)

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

def extract_setups(df, tf_label, min_vol=1.18, min_wick=0.36, retest_depth=0.121, sl_mult=0.20, hours=(0, 22), use_pyh=True, use_ldn=True, use_ny=True):
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
                     (not pd.isna(pdh) and cur['high'] >= pdh) or \
                     (not pd.isna(pwh) and cur['high'] >= pwh) or \
                     (not pd.isna(pmh) and cur['high'] >= pmh) or \
                     (not pd.isna(pqh) and cur['high'] >= pqh) or \
                     (not pd.isna(pyh) and cur['high'] >= pyh)

        swept_low = (cur['low'] <= swing_low) or \
                    (not pd.isna(asian_low) and cur['low'] <= asian_low) or \
                    (not pd.isna(ldn_low) and cur['low'] <= ldn_low) or \
                    (not pd.isna(ny_low) and cur['low'] <= ny_low) or \
                    (not pd.isna(pdl) and cur['low'] <= pdl) or \
                    (not pd.isna(pwl) and cur['low'] <= pwl) or \
                    (not pd.isna(pml) and cur['low'] <= pml) or \
                    (not pd.isna(pql) and cur['low'] <= pql) or \
                    (not pd.isna(pyl) and cur['low'] <= pyl)

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

def run_simulation(setups, m5_gold, m5_times, m5_len,
                   be_trigger=0.8, lock1_trig=1.5, lock1_amt=1.0,
                   lock2_trig=2.4, lock2_amt=2.0, lock3_trig=3.0, lock3_amt=2.8,
                   lock4_trig=3.5, lock4_amt=3.3, lock5_trig=3.8, lock5_amt=3.5,
                   lock6_trig=4.2, lock6_amt=3.9, lock7_trig=4.6, lock7_amt=4.3,
                   lock8_trig=5.2, lock8_amt=4.9, lock9_trig=5.5, lock9_amt=5.2,
                   lock10_trig=5.6, lock10_amt=5.4, lock11_trig=5.8, lock11_amt=5.6, tp_r=5.90):
    point_val = 1.0  # Strict 0.01 lot ($1.00 per point)
    busy_until = 0
    trades = 0
    wins = 0
    bes = 0
    losses = 0
    total_pnl = 0.0
    monthly_stats = {}
    peak = 0.0
    max_dd = 0.0

    for s in setups:
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

        if lock11_trig is not None:
            l11_target = round(entry + (lock11_trig * risk), 2) if sig == "BUY" else round(entry - (lock11_trig * risk), 2)
            l11_sl = round(entry + (lock11_amt * risk), 2) if sig == "BUY" else round(entry - (lock11_amt * risk), 2)
        else:
            l11_target = 0.0
            l11_sl = 0.0

        filled = False
        fill_m5 = 0
        for k in range(m5_start, min(m5_start + 24, m5_len)):
            m_b = m5_gold[k]
            if sig == "BUY" and m_b['low'] <= entry:
                filled = True
                fill_m5 = k
                break
            elif sig == "SELL" and m_b['high'] >= entry:
                filled = True
                fill_m5 = k
                break

        if not filled:
            continue

        trades += 1
        entry_time = m5_gold[fill_m5]['time']
        entry_dt = datetime.fromtimestamp(entry_time, tz=timezone.utc)
        month_key = entry_dt.strftime("%Y-%m")

        current_sl = sl
        be_active = False
        l1_active = False
        l2_active = False
        l3_active = False
        l4_active = False
        l5_active = False
        l6_active = False
        l7_active = False
        l8_active = False
        l9_active = False
        l10_active = False
        l11_active = False
        trade_pnl = 0.0
        outcome = None
        exit_time = entry_time

        for k in range(fill_m5 + 1, min(fill_m5 + 288, m5_len)):
            b = m5_gold[k]
            exit_time = b['time']

            if sig == "BUY":
                if b['low'] <= current_sl:
                    if l11_active:
                        outcome = "WIN"
                        trade_pnl = (l11_sl - entry) * point_val
                    elif l10_active:
                        outcome = "WIN"
                        trade_pnl = (l10_sl - entry) * point_val
                    elif l9_active:
                        outcome = "WIN"
                        trade_pnl = (l9_sl - entry) * point_val
                    elif l8_active:
                        outcome = "WIN"
                        trade_pnl = (l8_sl - entry) * point_val
                    elif l7_active:
                        outcome = "WIN"
                        trade_pnl = (l7_sl - entry) * point_val
                    elif l6_active:
                        outcome = "WIN"
                        trade_pnl = (l6_sl - entry) * point_val
                    elif l5_active:
                        outcome = "WIN"
                        trade_pnl = (l5_sl - entry) * point_val
                    elif l4_active:
                        outcome = "WIN"
                        trade_pnl = (l4_sl - entry) * point_val
                    elif l3_active:
                        outcome = "WIN"
                        trade_pnl = (l3_sl - entry) * point_val
                    elif l2_active:
                        outcome = "WIN"
                        trade_pnl = (l2_sl - entry) * point_val
                    elif l1_active:
                        outcome = "WIN"
                        trade_pnl = (l1_sl - entry) * point_val
                    elif be_active:
                        outcome = "BE"
                        trade_pnl = 0.0
                    else:
                        outcome = "LOSS"
                        trade_pnl = -risk * point_val
                    break

                if b['high'] >= tp:
                    outcome = "WIN"
                    trade_pnl = (tp - entry) * point_val
                    break

                if lock11_trig and b['high'] >= l11_target:
                    l11_active = True
                    current_sl = max(current_sl, l11_sl)
                elif b['high'] >= l10_target:
                    l10_active = True
                    current_sl = max(current_sl, l10_sl)
                elif b['high'] >= l9_target:
                    l9_active = True
                    current_sl = max(current_sl, l9_sl)
                elif b['high'] >= l8_target:
                    l8_active = True
                    current_sl = max(current_sl, l8_sl)
                elif b['high'] >= l7_target:
                    l7_active = True
                    current_sl = max(current_sl, l7_sl)
                elif b['high'] >= l6_target:
                    l6_active = True
                    current_sl = max(current_sl, l6_sl)
                elif b['high'] >= l5_target:
                    l5_active = True
                    current_sl = max(current_sl, l5_sl)
                elif b['high'] >= l4_target:
                    l4_active = True
                    current_sl = max(current_sl, l4_sl)
                elif b['high'] >= l3_target:
                    l3_active = True
                    current_sl = max(current_sl, l3_sl)
                elif b['high'] >= l2_target:
                    l2_active = True
                    current_sl = max(current_sl, l2_sl)
                elif b['high'] >= l1_target:
                    l1_active = True
                    current_sl = max(current_sl, l1_sl)
                elif b['high'] >= be_target:
                    be_active = True
                    current_sl = max(current_sl, entry)

            else:
                if b['high'] >= current_sl:
                    if l11_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l11_sl) * point_val
                    elif l10_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l10_sl) * point_val
                    elif l9_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l9_sl) * point_val
                    elif l8_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l8_sl) * point_val
                    elif l7_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l7_sl) * point_val
                    elif l6_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l6_sl) * point_val
                    elif l5_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l5_sl) * point_val
                    elif l4_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l4_sl) * point_val
                    elif l3_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l3_sl) * point_val
                    elif l2_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l2_sl) * point_val
                    elif l1_active:
                        outcome = "WIN"
                        trade_pnl = (entry - l1_sl) * point_val
                    elif be_active:
                        outcome = "BE"
                        trade_pnl = 0.0
                    else:
                        outcome = "LOSS"
                        trade_pnl = -risk * point_val
                    break

                if b['low'] <= tp:
                    outcome = "WIN"
                    trade_pnl = (entry - tp) * point_val
                    break

                if lock11_trig and b['low'] <= l11_target:
                    l11_active = True
                    current_sl = min(current_sl, l11_sl)
                elif b['low'] <= l10_target:
                    l10_active = True
                    current_sl = min(current_sl, l10_sl)
                elif b['low'] <= l9_target:
                    l9_active = True
                    current_sl = min(current_sl, l9_sl)
                elif b['low'] <= l8_target:
                    l8_active = True
                    current_sl = min(current_sl, l8_sl)
                elif b['low'] <= l7_target:
                    l7_active = True
                    current_sl = min(current_sl, l7_sl)
                elif b['low'] <= l6_target:
                    l6_active = True
                    current_sl = min(current_sl, l6_sl)
                elif b['low'] <= l5_target:
                    l5_active = True
                    current_sl = min(current_sl, l5_sl)
                elif b['low'] <= l4_target:
                    l4_active = True
                    current_sl = min(current_sl, l4_sl)
                elif b['low'] <= l3_target:
                    l3_active = True
                    current_sl = min(current_sl, l3_sl)
                elif b['low'] <= l2_target:
                    l2_active = True
                    current_sl = min(current_sl, l2_sl)
                elif b['low'] <= l1_target:
                    l1_active = True
                    current_sl = min(current_sl, l1_sl)
                elif b['low'] <= be_target:
                    be_active = True
                    current_sl = min(current_sl, entry)

        if outcome is None:
            outcome = "BE"
            trade_pnl = 0.0

        if outcome == "WIN":
            wins += 1
        elif outcome == "BE":
            bes += 1
        else:
            losses += 1

        total_pnl += trade_pnl
        busy_until = exit_time

        if total_pnl > peak:
            peak = total_pnl
        dd = peak - total_pnl
        if dd > max_dd:
            max_dd = dd

        if month_key not in monthly_stats:
            monthly_stats[month_key] = {"trades": 0, "wins": 0, "bes": 0, "losses": 0, "pnl": 0.0}
        monthly_stats[month_key]["trades"] += 1
        if outcome == "WIN":
            monthly_stats[month_key]["wins"] += 1
        elif outcome == "BE":
            monthly_stats[month_key]["bes"] += 1
        else:
            monthly_stats[month_key]["losses"] += 1
        monthly_stats[month_key]["pnl"] += trade_pnl

    win_rate = (wins / trades * 100) if trades > 0 else 0
    non_loss = ((wins + bes) / trades * 100) if trades > 0 else 0
    gross_win = sum(m['pnl'] for m in monthly_stats.values() if m['pnl'] > 0)
    gross_loss = abs(sum(m['pnl'] for m in monthly_stats.values() if m['pnl'] < 0))
    pf = (gross_win / gross_loss) if gross_loss > 0 else 999.99
    pos_m = sum(1 for m in monthly_stats.values() if m['pnl'] > 0)
    tot_m = len(monthly_stats)

    return {
        "trades": trades,
        "wins": wins,
        "bes": bes,
        "losses": losses,
        "wr": win_rate,
        "non_loss": non_loss,
        "pnl": total_pnl,
        "pf": pf,
        "max_dd": max_dd,
        "pos_m": pos_m,
        "tot_m": tot_m
    }

def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    print("Fetching rates from MT5...", flush=True)
    h4_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H4, start_dt, now)
    h3_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H3, start_dt, now)
    h2_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H2, start_dt, now)
    h1_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_H1, start_dt, now)
    m30_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M30, start_dt, now)
    m20_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M20, start_dt, now)
    m15_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M15, start_dt, now)
    m12_gold = mt5.copy_rates_range(symbol_gold, mt5.TIMEFRAME_M12, start_dt, now)
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()

    df_h4 = compute_indicators(h4_gold, use_london=True, use_ny=True)
    df_h3 = compute_indicators(h3_gold, use_london=True, use_ny=True)
    df_h2 = compute_indicators(h2_gold, use_london=True, use_ny=True)
    df_h1 = compute_indicators(h1_gold, use_london=True, use_ny=True)
    df_m30 = compute_indicators(m30_gold, use_london=True, use_ny=True)
    df_m20 = compute_indicators(m20_gold, use_london=True, use_ny=True)
    df_m15 = compute_indicators(m15_gold, use_london=True, use_ny=True)
    df_m12 = compute_indicators(m12_gold, use_london=True, use_ny=True)

    m5_times = [int(r['time']) for r in m5_gold]
    m5_len = len(m5_gold)

    base_tfs = [
        ("H4", df_h4), ("H3", df_h3), ("H2", df_h2), ("H1", df_h1),
        ("M30", df_m30), ("M20", df_m20), ("M15", df_m15), ("M12", df_m12)
    ]

    print("=" * 115, flush=True)
    print(" S20.47 QUANT RESEARCH (TARGET > $24,855.94 ON STRICT LOT 0.01)", flush=True)
    print(" Benchmark S20.46: +$24,855.94 | MaxDD $12.94 | WR 87.7%", flush=True)
    print("=" * 115, flush=True)

    # Test 1: Explore Volume Climax threshold (1.15 to 1.18) & Wick (0.34 to 0.36)
    print("--- 1. Testing Volume & Wick Sensitivity ---", flush=True)
    for v in [1.15, 1.16, 1.17, 1.18]:
        for w in [0.34, 0.35, 0.36]:
            s_list = []
            for tf_label, df_tf in base_tfs:
                s_list.extend(extract_setups(df_tf, tf_label, min_vol=v, min_wick=w, retest_depth=0.121, hours=(0, 22), use_pyh=True, use_ldn=True, use_ny=True))
            comb = sorted(s_list, key=lambda x: x['time'])
            res = run_simulation(comb, m5_gold, m5_times, m5_len,
                                 be_trigger=0.8, lock1_trig=1.5, lock1_amt=1.0,
                                 lock2_trig=2.4, lock2_amt=2.0, lock3_trig=3.0, lock3_amt=2.8,
                                 lock4_trig=3.5, lock4_amt=3.3, lock5_trig=3.8, lock5_amt=3.5,
                                 lock6_trig=4.2, lock6_amt=3.9, lock7_trig=4.6, lock7_amt=4.3,
                                 lock8_trig=5.2, lock8_amt=4.9, lock9_trig=5.5, lock9_amt=5.2,
                                 lock10_trig=5.6, lock10_amt=5.4, lock11_trig=None, tp_r=5.90)
            print(f"V={v:.2f} W={w:.2f} | Trades: {res['trades']:4d} | W/BE/L: {res['wins']:4d}/{res['bes']:3d}/{res['losses']:3d} | WR: {res['wr']:4.1f}% | Net: ${res['pnl']:8.2f} | MaxDD: ${res['max_dd']:5.2f} | Mos: {res['pos_m']}/{res['tot_m']}", flush=True)

    # Test 2: Undeca-Stage Trailing & TP extension (5.90R to 6.10R)
    print("\n--- 2. Testing Trailing Extension (Undeca-Stage) ---", flush=True)
    s_list_base = []
    for tf_label, df_tf in base_tfs:
        s_list_base.extend(extract_setups(df_tf, tf_label, min_vol=1.18, min_wick=0.36, retest_depth=0.121, hours=(0, 22), use_pyh=True, use_ldn=True, use_ny=True))
    comb_base = sorted(s_list_base, key=lambda x: x['time'])

    for tp in [5.90, 5.95, 6.00, 6.05]:
        for l11_trig, l11_amt in [(None, None), (5.75, 5.55), (5.80, 5.60)]:
            res = run_simulation(comb_base, m5_gold, m5_times, m5_len,
                                 be_trigger=0.8, lock1_trig=1.5, lock1_amt=1.0,
                                 lock2_trig=2.4, lock2_amt=2.0, lock3_trig=3.0, lock3_amt=2.8,
                                 lock4_trig=3.5, lock4_amt=3.3, lock5_trig=3.8, lock5_amt=3.5,
                                 lock6_trig=4.2, lock6_amt=3.9, lock7_trig=4.6, lock7_amt=4.3,
                                 lock8_trig=5.2, lock8_amt=4.9, lock9_trig=5.5, lock9_amt=5.2,
                                 lock10_trig=5.6, lock10_amt=5.4, lock11_trig=l11_trig, lock11_amt=l11_amt, tp_r=tp)
            l11_str = f"L11={l11_trig:.2f}R->{l11_amt:.2f}R" if l11_trig else "No L11"
            print(f"TP={tp:.2f}R | {l11_str:<18} | Trades: {res['trades']:4d} | W/BE/L: {res['wins']:4d}/{res['bes']:3d}/{res['losses']:3d} | WR: {res['wr']:4.1f}% | Net: ${res['pnl']:8.2f} | MaxDD: ${res['max_dd']:5.2f}", flush=True)

if __name__ == "__main__":
    main()
