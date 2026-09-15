# -*- coding: utf-8 -*-
"""tune_s20_18_advanced.py — Advanced Tuning for S20.18 to achieve Profit Factor > 2.0 & WinRate > 50%
Tests:
1. Session Timing: Trade only High-Liquidity Sessions (London 08:00-12:00 & NY 13:00-18:00 server time)
2. Retest Depth: 0.382 (Fibo)
3. Volume Climax: 1.25x, 1.35x, 1.50x
4. Risk-Reward Ratio: 1.8R, 2.0R, 2.2R, 2.4R
5. Early Breakeven Lock: 35% vs 40% vs 45% of target
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if current_dir not in sys.path:
    sys.path.append(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

import strategy20_18


def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()


def evaluate_adv_bar(df, idx, session_mode="ALL", min_vol=1.25, min_wick=0.38, retest_depth=0.382, rr=1.8):
    if idx < 25 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05 or cur['range'] < 0.45 * atr or cur['hour'] in (23, 0):
        return None

    hour = cur['hour']
    if session_mode == "LONDON_NY":
        # London (8-11 server) & NY (13-18 server)
        if not ((8 <= hour <= 11) or (13 <= hour <= 18)):
            return None
    elif session_mode == "LONDON_ONLY":
        if not (8 <= hour <= 12):
            return None
    elif session_mode == "NY_ONLY":
        if not (13 <= hour <= 18):
            return None

    if cur['vol_ratio'] < min_vol:
        return None

    # 1. BUY
    swept_low = (cur['low'] <= cur['swing_low_10']) or (cur['low'] <= df.iloc[idx-5:idx]['low'].min())
    has_wick_buy = (cur['lower_wick_pct'] >= min_wick) or (cur['lower_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    if swept_low and has_wick_buy and closed_high and cur['rsi'] <= 68.0:
        sl_buf = max(0.20 * atr, 0.25)
        sl = round(cur['low'] - sl_buf, 2)
        entry = round(cur['low'] + (retest_depth * cur['lower_wick']), 2)
        risk = entry - sl
        if risk > 0:
            tp = round(entry + (risk * rr), 2)
            return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "risk": risk}

    # 2. SELL
    swept_high = (cur['high'] >= cur['swing_high_10']) or (cur['high'] >= df.iloc[idx-5:idx]['high'].max())
    has_wick_sell = (cur['upper_wick_pct'] >= min_wick) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
    if swept_high and has_wick_sell and closed_low and cur['rsi'] >= 32.0:
        sl_buf = max(0.20 * atr, 0.25)
        sl = round(cur['high'] + sl_buf, 2)
        entry = round(cur['high'] - (retest_depth * cur['upper_wick']), 2)
        risk = sl - entry
        if risk > 0:
            tp = round(entry - (risk * rr), 2)
            return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "risk": risk}

    return None


def simulate(rates, df, session_mode, min_vol, min_wick, retest_depth, rr, be_ratio, point_val=1.0):
    trades = 0; wins = 0; losses = 0; be = 0
    gross_profit = 0.0; gross_loss = 0.0; pnl = 0.0
    max_pnl = 0.0; max_dd = 0.0
    monthly_pnl = {}

    i = 30
    n = len(rates)
    while i < n - 5:
        res = evaluate_adv_bar(
            df, i, session_mode=session_mode, min_vol=min_vol, min_wick=min_wick,
            retest_depth=retest_depth, rr=rr
        )
        if not res:
            i += 1
            continue

        sig = res["signal"]
        entry = res["entry"]
        sl = res["sl"]
        tp = res["tp"]

        future = rates[i + 1:]
        filled = False
        fill_idx = 0
        for f_idx, f_bar in enumerate(future[:5]):
            if sig == "BUY" and f_bar['low'] <= entry:
                filled = True
                fill_idx = f_idx
                break
            elif sig == "SELL" and f_bar['high'] >= entry:
                filled = True
                fill_idx = f_idx
                break

        if not filled:
            i += 1
            continue

        active = future[fill_idx:]
        entry_time = datetime.fromtimestamp(future[fill_idx]['time'], tz=datetime.now().astimezone().tzinfo)
        month_key = entry_time.strftime("%Y-%m")

        be_trig = entry + ((tp - entry) * be_ratio) if sig == "BUY" else entry - ((entry - tp) * be_ratio)
        be_active = False
        outcome = None
        exit_p = entry
        bars_held = 0

        for bar in active:
            bars_held += 1
            if sig == "BUY":
                if bar['low'] <= sl:
                    outcome = "BE" if be_active else "LOSS"
                    exit_p = sl
                    break
                if bar['high'] >= tp:
                    outcome = "WIN"
                    exit_p = tp
                    break
                if not be_active and bar['high'] >= be_trig:
                    be_active = True
                    sl = entry
            elif sig == "SELL":
                if bar['high'] >= sl:
                    outcome = "BE" if be_active else "LOSS"
                    exit_p = sl
                    break
                if bar['low'] <= tp:
                    outcome = "WIN"
                    exit_p = tp
                    break
                if not be_active and bar['low'] <= be_trig:
                    be_active = True
                    sl = entry

        if outcome == "WIN":
            trades += 1; wins += 1
            diff = abs(exit_p - entry) * point_val
            gross_profit += diff; pnl += diff
            monthly_pnl[month_key] = monthly_pnl.get(month_key, 0.0) + diff
        elif outcome == "LOSS":
            trades += 1; losses += 1
            diff = abs(entry - exit_p) * point_val
            gross_loss += diff; pnl -= diff
            monthly_pnl[month_key] = monthly_pnl.get(month_key, 0.0) - diff
        elif outcome == "BE":
            trades += 1; be += 1

        if pnl > max_pnl: max_pnl = pnl
        dd = max_pnl - pnl
        if dd > max_dd: max_dd = dd

        i += max(1, bars_held)

    decided = wins + losses
    wr = (wins / decided * 100.0) if decided > 0 else 0.0
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
    
    # Check winning months
    pos_months = sum(1 for v in monthly_pnl.values() if v > 0)
    tot_months = len(monthly_pnl)
    monthly_winrate = (pos_months / tot_months * 100.0) if tot_months > 0 else 0.0

    return {
        "trades": trades, "wins": wins, "losses": losses, "be": be,
        "wr": wr, "pnl": pnl, "pf": pf, "max_dd": max_dd,
        "monthly_wr": monthly_winrate, "pos_months": pos_months, "tot_months": tot_months
    }


def main():
    if not init_mt5():
        print("❌ MT5 initialize failed")
        return

    symbol = "XAUUSD.iux"
    days = 365
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    print("=========================================================================")
    print("  🔥 S20.18 ADVANCED HYPER-OPTIMIZATION: CRACKING PROFIT FACTOR > 1.8")
    print("=========================================================================\n")

    for tf_name in ["M30", "M15"]:
        tf_code = mt5.TIMEFRAME_M30 if tf_name == "M30" else mt5.TIMEFRAME_M15
        rates = mt5.copy_rates_range(symbol, tf_code, start_time, end_time)
        if rates is None: continue
        df = strategy20_18.compute_indicators_df(rates)

        print(f"\n--- Testing Timeframe: {tf_name} ({len(rates):,} bars) ---")

        test_variations = [
            # Baseline
            {"session": "ALL", "vol": 1.25, "wick": 0.38, "depth": 0.382, "rr": 1.8, "be": 0.40, "desc": "Baseline (Fibo 38.2%)"},
            
            # Session Targeting (London + NY only)
            {"session": "LONDON_NY", "vol": 1.25, "wick": 0.38, "depth": 0.382, "rr": 1.8, "be": 0.40, "desc": "London+NY Killzones Only"},
            {"session": "NY_ONLY", "vol": 1.25, "wick": 0.38, "depth": 0.382, "rr": 1.8, "be": 0.40, "desc": "NY Session Only"},

            # Higher Volume Climax
            {"session": "LONDON_NY", "vol": 1.35, "wick": 0.38, "depth": 0.382, "rr": 1.8, "be": 0.40, "desc": "London+NY + Vol 1.35x"},
            {"session": "LONDON_NY", "vol": 1.45, "wick": 0.40, "depth": 0.382, "rr": 1.8, "be": 0.40, "desc": "London+NY + Vol 1.45x"},

            # Higher Risk-Reward
            {"session": "LONDON_NY", "vol": 1.30, "wick": 0.38, "depth": 0.382, "rr": 2.0, "be": 0.40, "desc": "London+NY + RR 2.0R"},
            {"session": "LONDON_NY", "vol": 1.30, "wick": 0.38, "depth": 0.382, "rr": 2.2, "be": 0.40, "desc": "London+NY + RR 2.2R"},
            {"session": "ALL", "vol": 1.30, "wick": 0.40, "depth": 0.382, "rr": 2.0, "be": 0.35, "desc": "All Sessions + RR 2.0R + Fast BE 35%"},

            # The Grand Champion Combos
            {"session": "LONDON_NY", "vol": 1.35, "wick": 0.40, "depth": 0.382, "rr": 2.0, "be": 0.35, "desc": "👑 Institutional Alpha A"},
            {"session": "LONDON_NY", "vol": 1.40, "wick": 0.42, "depth": 0.382, "rr": 2.2, "be": 0.35, "desc": "👑 Institutional Alpha B"},
            {"session": "ALL", "vol": 1.35, "wick": 0.40, "depth": 0.382, "rr": 2.0, "be": 0.38, "desc": "👑 All-Day Steady Alpha C"}
        ]

        results = []
        for t in test_variations:
            res = simulate(
                rates, df,
                session_mode=t["session"], min_vol=t["vol"], min_wick=t["wick"],
                retest_depth=t["depth"], rr=t["rr"], be_ratio=t["be"]
            )
            print(f"[{tf_name}] {t['desc']:30s} | Trades: {res['trades']:3d} | WR: {res['wr']:4.1f}% | Net: ${res['pnl']:+7.2f} | PF: {res['pf']:4.2f} | DD: ${res['max_dd']:5.2f} | WinMonths: {res['pos_months']}/{res['tot_months']} ({res['monthly_wr']:.0f}%)")
            results.append({
                "TF": tf_name,
                "Config": t["desc"],
                "Trades": res["trades"],
                "WinRate%": round(res["wr"], 1),
                "NetProfit($)": round(res["pnl"], 2),
                "ProfitFactor": round(res["pf"], 2),
                "MaxDD($)": round(res["max_dd"], 2),
                "MonthlyWinRate%": round(res["monthly_wr"], 1)
            })

        print("\n" + "=" * 95)
        print(f"🏆 TOP CONFIGURATIONS FOR {tf_name} (Ranked by Profit Factor)")
        print("=" * 95)
        top_df = pd.DataFrame(results).sort_values(by="ProfitFactor", ascending=False).head(5)
        print(top_df.to_string(index=False))

    mt5.shutdown()


if __name__ == "__main__":
    main()
