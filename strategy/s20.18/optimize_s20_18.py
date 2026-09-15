# -*- coding: utf-8 -*-
"""optimize_s20_18.py — Parameter Tuning & Optimization for S20.18 (365 Days)
Sweeps key institutional parameters:
- Trend Filter: NONE, EMA50, EMA200
- Volume Ratio Threshold: 1.25, 1.40, 1.60
- Wick Rejection Pct: 0.38, 0.45, 0.50
- Risk-Reward (RR): 1.5, 1.8, 2.0, 2.2
- Breakeven Trigger: 0.35, 0.40, 0.50
- Retest Depth: 0.382, 0.50, 0.618 of wick
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

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


def evaluate_custom_bar(df, idx, tf, trend_filter="NONE", min_vol=1.35, min_wick=0.40, retest_depth=0.50, rr=1.8):
    if idx < 25 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    if pd.isna(cur['atr']) or pd.isna(cur['vol_ma20']) or pd.isna(cur['rsi']):
        return None

    atr = cur['atr']
    if atr <= 0.05 or cur['range'] < 0.45 * atr:
        return None

    # Rollover filter
    if cur['hour'] in (23, 0):
        return None

    # Volume spike
    if cur['vol_ratio'] < min_vol:
        return None

    # Trend filter
    if trend_filter == "EMA50":
        allow_buy = cur['close'] >= cur['ema_50']
        allow_sell = cur['close'] <= cur['ema_50']
    elif trend_filter == "EMA200":
        allow_buy = cur['close'] >= cur['ema_200']
        allow_sell = cur['close'] <= cur['ema_200']
    else:
        allow_buy = True
        allow_sell = True

    # 1. BUY SETUP
    swept_low = (cur['low'] <= cur['swing_low_10']) or (cur['low'] <= df.iloc[idx-5:idx]['low'].min())
    has_wick_buy = (cur['lower_wick_pct'] >= min_wick) or (cur['lower_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    rsi_ok_buy = cur['rsi'] <= 68.0

    if allow_buy and swept_low and has_wick_buy and closed_high and rsi_ok_buy:
        sl_buffer = max(0.20 * atr, 0.25)
        sl = round(cur['low'] - sl_buffer, 2)
        entry = round(cur['low'] + (retest_depth * cur['lower_wick']), 2)
        risk = entry - sl
        if risk > 0:
            tp = round(entry + (risk * rr), 2)
            return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "risk": risk}

    # 2. SELL SETUP
    swept_high = (cur['high'] >= cur['swing_high_10']) or (cur['high'] >= df.iloc[idx-5:idx]['high'].max())
    has_wick_sell = (cur['upper_wick_pct'] >= min_wick) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
    rsi_ok_sell = cur['rsi'] >= 32.0

    if allow_sell and swept_high and has_wick_sell and closed_low and rsi_ok_sell:
        sl_buffer = max(0.20 * atr, 0.25)
        sl = round(cur['high'] + sl_buffer, 2)
        entry = round(cur['high'] - (retest_depth * cur['upper_wick']), 2)
        risk = sl - entry
        if risk > 0:
            tp = round(entry - (risk * rr), 2)
            return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "risk": risk}

    return None


def simulate(rates, df, tf, trend_filter, min_vol, min_wick, retest_depth, rr, be_ratio, point_val=1.0):
    trades = 0; wins = 0; losses = 0; be = 0
    gross_profit = 0.0; gross_loss = 0.0; pnl = 0.0
    max_pnl = 0.0; max_dd = 0.0

    i = 30
    n = len(rates)
    while i < n - 5:
        res = evaluate_custom_bar(df, i, tf, trend_filter, min_vol, min_wick, retest_depth, rr)
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
        elif outcome == "LOSS":
            trades += 1; losses += 1
            diff = abs(entry - exit_p) * point_val
            gross_loss += diff; pnl -= diff
        elif outcome == "BE":
            trades += 1; be += 1

        if pnl > max_pnl: max_pnl = pnl
        dd = max_pnl - pnl
        if dd > max_dd: max_dd = dd

        i += max(1, bars_held)

    decided = wins + losses
    wr = (wins / decided * 100.0) if decided > 0 else 0.0
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
    return {
        "trades": trades, "wins": wins, "losses": losses, "be": be,
        "wr": wr, "pnl": pnl, "pf": pf, "max_dd": max_dd
    }


def main():
    if not init_mt5():
        print("MT5 Failed")
        return

    symbol = "XAUUSD.iux"
    days = 365
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    print("🚀 S20.18 Parameter Sweep Starting (M15 & M30, Lot 0.01, 365 Days)...")
    
    sweep_results = []
    
    # Test grids
    tf_list = [("M15", mt5.TIMEFRAME_M15), ("M30", mt5.TIMEFRAME_M30)]
    
    for tf_name, tf_code in tf_list:
        print(f"\n--- Loading data for {tf_name} ---")
        rates = mt5.copy_rates_range(symbol, tf_code, start_time, end_time)
        if rates is None or len(rates) < 100:
            continue
        df = strategy20_18.compute_indicators_df(rates)
        print(f"Loaded {len(rates):,} bars.")

        # Variations to test
        param_grid = [
            # Base line
            {"trend": "NONE", "vol": 1.25, "wick": 0.38, "depth": 0.50, "rr": 1.8, "be": 0.40, "desc": "Baseline"},
            # Trend Filters
            {"trend": "EMA50", "vol": 1.25, "wick": 0.38, "depth": 0.50, "rr": 1.8, "be": 0.40, "desc": "EMA50 Trend Filter"},
            {"trend": "EMA200", "vol": 1.25, "wick": 0.38, "depth": 0.50, "rr": 1.8, "be": 0.40, "desc": "EMA200 Trend Filter"},
            # Higher Volume Climax
            {"trend": "NONE", "vol": 1.45, "wick": 0.38, "depth": 0.50, "rr": 1.8, "be": 0.40, "desc": "High Vol (1.45x)"},
            {"trend": "NONE", "vol": 1.65, "wick": 0.38, "depth": 0.50, "rr": 1.8, "be": 0.40, "desc": "Very High Vol (1.65x)"},
            # Stricter Wick Rejection
            {"trend": "NONE", "vol": 1.35, "wick": 0.45, "depth": 0.50, "rr": 1.8, "be": 0.40, "desc": "Deep Wick 45%"},
            {"trend": "NONE", "vol": 1.35, "wick": 0.50, "depth": 0.50, "rr": 1.8, "be": 0.40, "desc": "Extreme Pinbar 50%"},
            # Fibo Retest Depths
            {"trend": "NONE", "vol": 1.35, "wick": 0.40, "depth": 0.382, "rr": 1.8, "be": 0.40, "desc": "Fibo Retest 38.2%"},
            {"trend": "NONE", "vol": 1.35, "wick": 0.40, "depth": 0.618, "rr": 1.8, "be": 0.40, "desc": "Fibo Retest 61.8%"},
            # Risk Reward & Breakeven Variations
            {"trend": "NONE", "vol": 1.35, "wick": 0.40, "depth": 0.50, "rr": 2.0, "be": 0.40, "desc": "RR 2.0R"},
            {"trend": "NONE", "vol": 1.35, "wick": 0.40, "depth": 0.50, "rr": 2.2, "be": 0.40, "desc": "RR 2.2R"},
            {"trend": "NONE", "vol": 1.35, "wick": 0.40, "depth": 0.50, "rr": 1.8, "be": 0.50, "desc": "BE at 50% TP"},
            # Golden Institutional Combinations
            {"trend": "EMA50", "vol": 1.40, "wick": 0.42, "depth": 0.50, "rr": 2.0, "be": 0.40, "desc": "Alpha Quant Combo A"},
            {"trend": "NONE", "vol": 1.40, "wick": 0.45, "depth": 0.50, "rr": 2.0, "be": 0.45, "desc": "Alpha Quant Combo B"},
            {"trend": "EMA200", "vol": 1.35, "wick": 0.40, "depth": 0.50, "rr": 2.2, "be": 0.40, "desc": "Alpha Quant Combo C"}
        ]

        for p in param_grid:
            res = simulate(
                rates, df, tf_name,
                trend_filter=p["trend"],
                min_vol=p["vol"],
                min_wick=p["wick"],
                retest_depth=p["depth"],
                rr=p["rr"],
                be_ratio=p["be"]
            )
            print(f"[{tf_name}] {p['desc']:24s} | Trades: {res['trades']:3d} | WR: {res['wr']:4.1f}% | Net: ${res['pnl']:+7.2f} | PF: {res['pf']:4.2f} | DD: ${res['max_dd']:5.2f}")
            sweep_results.append({
                "TF": tf_name,
                "Config": p["desc"],
                "Trend": p["trend"],
                "Vol": p["vol"],
                "Wick": p["wick"],
                "Depth": p["depth"],
                "RR": p["rr"],
                "BE": p["be"],
                "Trades": res["trades"],
                "WinRate%": round(res["wr"], 1),
                "NetProfit($)": round(res["pnl"], 2),
                "ProfitFactor": round(res["pf"], 2),
                "MaxDD($)": round(res["max_dd"], 2)
            })

    mt5.shutdown()
    
    if sweep_results:
        res_df = pd.DataFrame(sweep_results)
        csv_out = os.path.join(current_dir, "S20_18_optimization_results.csv")
        res_df.to_csv(csv_out, index=False)
        print(f"\n✅ Optimization complete! Saved to {csv_out}")
        
        # Sort and show top 5 for each TF
        print("\n=======================================================")
        print("🏆 TOP CONFIGURATIONS BY NET PROFIT (M15)")
        print("=======================================================")
        top_m15 = res_df[res_df['TF'] == 'M15'].sort_values(by="NetProfit($)", ascending=False).head(5)
        print(top_m15[["Config", "Trades", "WinRate%", "NetProfit($)", "ProfitFactor", "MaxDD($)"]].to_string(index=False))

        print("\n=======================================================")
        print("🏆 TOP CONFIGURATIONS BY NET PROFIT (M30)")
        print("=======================================================")
        top_m30 = res_df[res_df['TF'] == 'M30'].sort_values(by="NetProfit($)", ascending=False).head(5)
        print(top_m30[["Config", "Trades", "WinRate%", "NetProfit($)", "ProfitFactor", "MaxDD($)"]].to_string(index=False))


if __name__ == "__main__":
    main()
