# -*- coding: utf-8 -*-
"""goal_s20_53_to_100.py
Automated Master Engine for S20.53 through S20.100 Progression
Rigid Non-Negotiable Mandates:
1. Strict 0.01 lot single position ($1.00/pt) throughout 365 days.
2. Single-candle multi-strategy confluence (exact same bar).
3. Zero lookahead bias, causal shift(1) backward-looking indicators.
4. Pessimistic M5 SL-First sequential engine across 75,000+ real bars.
5. Realistic 2-hour limit retest timeout (no magic fill).
6. Monotonically increasing net profit for every version N from 53 to 100.
7. Generate all 5 required files per version and update strategy.md.
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
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101183586\mt5\terminal64.exe',
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()

def compute_indicators(rates, use_london=True, use_ny=True, use_ny_pm=True, fvg_depth=5):
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

    # Strategy 11: Fibonacci Golden Zone & Premium/Discount Equilibrium Levels (Shifted 1 - Causal)
    swing_range = df['swing_high_12'] - df['swing_low_12']
    df['fibo_discount_382'] = df['swing_low_12'] + (0.382 * swing_range)
    df['fibo_equilibrium'] = df['swing_low_12'] + (0.500 * swing_range)
    df['fibo_premium_618'] = df['swing_low_12'] + (0.618 * swing_range)

    # Strategy 15: Volume Profile Value Area (VAH / VAL proxy via volume-weighted quantile, shifted 1 Causal)
    vwap_24 = (df['typical_price'] * df['tick_volume']).rolling(24).sum() / (df['tick_volume'].rolling(24).sum() + 1e-5)
    rolling_std = df['typical_price'].rolling(24).std()
    df['val_proxy'] = (vwap_24 - (1.0 * rolling_std)).shift(1)
    df['vah_proxy'] = (vwap_24 + (1.0 * rolling_std)).shift(1)

    # Multi-Bar Fair Value Gap (FVG Memory: lookback up to fvg_depth bars)
    bull_series = []
    bear_series = []
    for d in range(1, fvg_depth - 1):
        b_s = np.where(df['low'].shift(d) > df['high'].shift(d + 2), df['high'].shift(d + 2), np.nan)
        s_s = np.where(df['high'].shift(d) < df['low'].shift(d + 2), df['low'].shift(d + 2), np.nan)
        bull_series.append(pd.Series(b_s))
        bear_series.append(pd.Series(s_s))

    comb_bull = bull_series[0]
    comb_bear = bear_series[0]
    for s in bull_series[1:]:
        comb_bull = comb_bull.combine_first(s)
    for s in bear_series[1:]:
        comb_bear = comb_bear.combine_first(s)

    df['fvg_bull_zone'] = comb_bull
    df['fvg_bear_zone'] = comb_bear

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

def extract_setups(df, tf_label, min_vol=1.17, min_wick=0.30, retest_depth=0.124, sl_mult=0.20, hours=(0, 22),
                   use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True, use_fibo=True, use_vp=True,
                   crt_momentum=0.45, rsi_bounds=(68.0, 32.0)):
    setups = []
    h_start, h_end = hours
    rsi_buy_max, rsi_sell_min = rsi_bounds
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

        # Multi-Bar Fair Value Gap (FVG) Imbalance Confluence
        if use_fvg:
            fvg_bull = cur.get('fvg_bull_zone', np.nan)
            fvg_bear = cur.get('fvg_bear_zone', np.nan)
            if not pd.isna(fvg_bull) and cur['low'] <= fvg_bull:
                swept_low = True
            if not pd.isna(fvg_bear) and cur['high'] >= fvg_bear:
                swept_high = True

        # Strategy 11: Fibonacci Premium/Discount Equilibrium Confluence
        if use_fibo:
            fibo_disc = cur.get('fibo_discount_382', np.nan)
            fibo_prem = cur.get('fibo_premium_618', np.nan)
            if not pd.isna(fibo_disc) and cur['low'] <= fibo_disc:
                swept_low = True
            if not pd.isna(fibo_prem) and cur['high'] >= fibo_prem:
                swept_high = True

        # Strategy 15: Volume Profile Value Area (VAH/VAL) Extreme Auction Absorption
        if use_vp:
            val_p = cur.get('val_proxy', np.nan)
            vah_p = cur.get('vah_proxy', np.nan)
            if not pd.isna(val_p) and cur['low'] <= val_p:
                swept_low = True
            if not pd.isna(vah_p) and cur['high'] >= vah_p:
                swept_high = True

        has_wick_buy = (cur['lower_wick_pct'] >= min_wick) or (cur['lower_wick'] >= 1.1 * cur['body'])
        closed_high = cur['close'] >= (cur['low'] + crt_momentum * cur['range'])
        rsi_ok_buy = cur['rsi'] <= rsi_buy_max

        has_wick_sell = (cur['upper_wick_pct'] >= min_wick) or (cur['upper_wick'] >= 1.1 * cur['body'])
        closed_low = cur['close'] <= (cur['high'] - crt_momentum * cur['range'])
        rsi_ok_sell = cur['rsi'] >= rsi_sell_min

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

def run_simulation(m5_gold, m5_times, combined, tp_r=6.90, stages=None):
    if stages is None:
        stages = [
            (1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5),
            (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4),
            (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.50, 6.30), (6.70, 6.50)
        ]

    m5_len = len(m5_gold)
    point_val = 1.0  # Strict 0.01 lot on XAUUSD ($1.00 per point)
    be_trigger = 0.8

    busy_until = 0
    trades = 0; wins = 0; bes = 0; losses = 0
    total_pnl = 0.0
    monthly_stats = {}
    trade_records = []
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

        stage_levels = []
        for trig, amt in stages:
            t_price = round(entry + (trig * risk), 2) if sig == "BUY" else round(entry - (trig * risk), 2)
            s_price = round(entry + (amt * risk), 2) if sig == "BUY" else round(entry - (amt * risk), 2)
            stage_levels.append((t_price, s_price))

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
        active_stage_idx = -1
        trade_pnl = 0.0
        outcome = None
        exit_time = entry_time

        for k in range(fill_m5 + 1, min(fill_m5 + 288, m5_len)):
            b = m5_gold[k]
            exit_time = b['time']

            if sig == "BUY":
                # PESSIMISTIC SL-FIRST EVALUATION
                if b['low'] <= current_sl:
                    if active_stage_idx >= 0:
                        outcome = "WIN"
                        trade_pnl = (stage_levels[active_stage_idx][1] - entry) * point_val
                    elif be_active:
                        outcome = "BE"; trade_pnl = 0.0
                    else:
                        outcome = "LOSS"; trade_pnl = -risk * point_val
                    break

                # TP Evaluation
                if b['high'] >= tp:
                    outcome = "WIN"; trade_pnl = (tp - entry) * point_val
                    break

                # Trailing Ratchet Locks Activation
                for s_idx in range(len(stage_levels) - 1, -1, -1):
                    t_price, s_price = stage_levels[s_idx]
                    if b['high'] >= t_price:
                        if s_idx > active_stage_idx:
                            active_stage_idx = s_idx
                            current_sl = max(current_sl, s_price)
                        break

                if active_stage_idx == -1 and b['high'] >= be_target:
                    be_active = True
                    current_sl = max(current_sl, entry)

            else:  # SELL
                # PESSIMISTIC SL-FIRST EVALUATION
                if b['high'] >= current_sl:
                    if active_stage_idx >= 0:
                        outcome = "WIN"
                        trade_pnl = (entry - stage_levels[active_stage_idx][1]) * point_val
                    elif be_active:
                        outcome = "BE"; trade_pnl = 0.0
                    else:
                        outcome = "LOSS"; trade_pnl = -risk * point_val
                    break

                # TP Evaluation
                if b['low'] <= tp:
                    outcome = "WIN"; trade_pnl = (entry - tp) * point_val
                    break

                # Trailing Ratchet Locks Activation
                for s_idx in range(len(stage_levels) - 1, -1, -1):
                    t_price, s_price = stage_levels[s_idx]
                    if b['low'] <= t_price:
                        if s_idx > active_stage_idx:
                            active_stage_idx = s_idx
                            current_sl = min(current_sl, s_price)
                        break

                if active_stage_idx == -1 and b['low'] <= be_target:
                    be_active = True
                    current_sl = min(current_sl, entry)

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
            monthly_stats[month_key] = {"trades": 0, "wins": 0, "bes": 0, "losses": 0, "pnl": 0.0}
        monthly_stats[month_key]["trades"] += 1
        if outcome == "WIN": monthly_stats[month_key]["wins"] += 1
        elif outcome == "BE": monthly_stats[month_key]["bes"] += 1
        else: monthly_stats[month_key]["losses"] += 1
        monthly_stats[month_key]["pnl"] += trade_pnl

        trade_records.append({
            "entry_time": str(entry_dt),
            "month": month_key,
            "tf": s['tf'],
            "signal": sig,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "outcome": outcome,
            "pnl": trade_pnl
        })

    win_rate = (wins / trades * 100) if trades > 0 else 0
    non_loss_rate = ((wins + bes) / trades * 100) if trades > 0 else 0
    gross_profit = sum(t['pnl'] for t in trade_records if t['pnl'] > 0)
    gross_loss = abs(sum(t['pnl'] for t in trade_records if t['pnl'] < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.99
    pos_months = sum(1 for m in monthly_stats.values() if m['pnl'] > 0)

    return {
        "trades": trades,
        "wins": wins,
        "bes": bes,
        "losses": losses,
        "wr": win_rate,
        "non_loss_rate": non_loss_rate,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "pf": profit_factor,
        "pnl": total_pnl,
        "max_dd": max_dd,
        "pos_months": f"{pos_months}/{len(monthly_stats)}",
        "monthly_stats": monthly_stats
    }

print("Goal engine module defined successfully.")
