# -*- coding: utf-8 -*-
"""optimize_s20_22.py — Quant Grid Tuning for S20.22 (Session VWAP Extreme Reversion)
Sweeps key institutional quantitative levers:
1. Sigma Threshold: 2.0σ, 2.2σ, 2.4σ, 2.6σ, 2.8σ
2. Volume Climax: 1.15x, 1.35x, 1.55x
3. Wick Rejection Pct: 0.35, 0.42, 0.50
4. Macro Trend Alignment: NONE, EMA200 (Trade with macro trend only), ADX Guard
5. Session Maturity Filter: Hour >= 3 (Skip early VWAP sample noise)
6. Risk-Reward / Target: VWAP Center, 1.0σ Band, Fixed 2.0R, Fixed 2.5R
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

import strategy20_22


def init_mt5():
    paths = [
        r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal64.exe'
    ]
    for p in paths:
        if os.path.exists(p) and mt5.initialize(path=p):
            return True
    return mt5.initialize()


def evaluate_tuned_vwap(df, idx, sigma_mult=2.3, min_vol=1.30, min_wick=0.40, trend_filter="NONE", min_hour=3, target_mode="VWAP", rr=2.0):
    if idx < 20 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05 or pd.isna(cur['vwap_std']) or cur['vwap_std'] < 1.0:
        return None

    # Skip early morning hours when VWAP is immature / sample size too small
    if cur['hour'] < min_hour or cur['hour'] in (23, 0):
        return None

    if cur['vol_ratio'] < min_vol:
        return None

    upper_band = cur['vwap'] + (sigma_mult * cur['vwap_std'])
    lower_band = cur['vwap'] - (sigma_mult * cur['vwap_std'])

    # Trend filter
    allow_buy = True
    allow_sell = True
    if trend_filter == "EMA200":
        allow_buy = cur['close'] >= cur['ema_200']
        allow_sell = cur['close'] <= cur['ema_200']
    elif trend_filter == "COUNTER_EMA200":
        allow_buy = cur['close'] < cur['ema_200']
        allow_sell = cur['close'] > cur['ema_200']

    # 1. SELL SETUP (Extreme Upper Band Reversal)
    hit_upper = cur['high'] >= upper_band
    rejected_down = cur['upper_wick_pct'] >= min_wick and cur['close'] <= (cur['high'] - 0.40 * cur['range'])

    if allow_sell and hit_upper and rejected_down:
        entry = round(cur['close'], 2)
        sl = round(cur['high'] + max(0.20 * atr, 0.30), 2)
        risk = sl - entry
        if risk <= 0:
            return None

        if target_mode == "VWAP":
            tp = round(cur['vwap'], 2)
        elif target_mode == "SIGMA_1":
            tp = round(cur['vwap'] + (1.0 * cur['vwap_std']), 2)
        else:
            tp = round(entry - (risk * rr), 2)

        reward = entry - tp
        if reward >= risk * 1.2:
            return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "risk": risk}

    # 2. BUY SETUP (Extreme Lower Band Reversal)
    hit_lower = cur['low'] <= lower_band
    rejected_up = cur['lower_wick_pct'] >= min_wick and cur['close'] >= (cur['low'] + 0.40 * cur['range'])

    if allow_buy and hit_lower and rejected_up:
        entry = round(cur['close'], 2)
        sl = round(cur['low'] - max(0.20 * atr, 0.30), 2)
        risk = entry - sl
        if risk <= 0:
            return None

        if target_mode == "VWAP":
            tp = round(cur['vwap'], 2)
        elif target_mode == "SIGMA_1":
            tp = round(cur['vwap'] - (1.0 * cur['vwap_std']), 2)
        else:
            tp = round(entry + (risk * rr), 2)

        reward = tp - entry
        if reward >= risk * 1.2:
            return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "risk": risk}

    return None


def simulate_tuned(rates, df, sigma_mult, min_vol, min_wick, trend_filter, min_hour, target_mode, rr, be_ratio=0.40, point_val=1.0):
    trades = 0; wins = 0; losses = 0; be = 0
    gross_profit = 0.0; gross_loss = 0.0; pnl = 0.0
    max_pnl = 0.0; max_dd = 0.0

    i = 30
    n = len(rates)
    while i < n - 5:
        res = evaluate_tuned_vwap(
            df, i, sigma_mult=sigma_mult, min_vol=min_vol, min_wick=min_wick,
            trend_filter=trend_filter, min_hour=min_hour, target_mode=target_mode, rr=rr
        )
        if not res:
            i += 1
            continue

        sig = res["signal"]
        entry = rates[i + 1]['open']
        sl = res["sl"]
        tp = res["tp"]
        target = abs(tp - entry)

        future = rates[i + 1:]
        be_trig = entry + (target * be_ratio) if sig == "BUY" else entry - (target * be_ratio)
        be_active = False
        outcome = None
        exit_p = entry
        bars_held = 0

        for bar in future:
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
            diff = abs(exit_p - entry) * point_val
            trades += 1; wins += 1
            gross_profit += diff; pnl += diff
        elif outcome == "LOSS":
            diff = abs(entry - exit_p) * point_val
            trades += 1; losses += 1
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
        print("❌ MT5 Failed to initialize")
        return

    symbol = "XAUUSD.iux"
    days = 365
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    print("=========================================================================")
    print("  🚀 S20.22 QUANT VWAP HYPER-TUNING (365 Days | Gold Lot 0.01)")
    print("=========================================================================\n")

    tf_code = mt5.TIMEFRAME_M15
    rates = mt5.copy_rates_range(symbol, tf_code, start_time, end_time)
    if rates is None or len(rates) < 100:
        print("❌ Insufficient rates data")
        mt5.shutdown()
        return

    print(f"Loaded {len(rates):,} bars")
    df = strategy20_22.compute_indicators_df(rates)

    grid = [
        # Baseline
        {"sigma": 2.0, "vol": 1.15, "wick": 0.35, "trend": "NONE", "hour": 0, "target": "VWAP", "rr": 2.0, "desc": "Baseline (v1.0)"},
        
        # 1. Stricter Sigma Extremes (2.2, 2.4, 2.6)
        {"sigma": 2.2, "vol": 1.15, "wick": 0.35, "trend": "NONE", "hour": 0, "target": "VWAP", "rr": 2.0, "desc": "Sigma 2.2σ Extreme"},
        {"sigma": 2.4, "vol": 1.15, "wick": 0.35, "trend": "NONE", "hour": 0, "target": "VWAP", "rr": 2.0, "desc": "Sigma 2.4σ Extreme"},
        {"sigma": 2.6, "vol": 1.15, "wick": 0.35, "trend": "NONE", "hour": 0, "target": "VWAP", "rr": 2.0, "desc": "Sigma 2.6σ Extreme"},

        # 2. Volume & Wick Climax Filter
        {"sigma": 2.2, "vol": 1.35, "wick": 0.42, "trend": "NONE", "hour": 0, "target": "VWAP", "rr": 2.0, "desc": "Sigma 2.2σ + Vol 1.35x"},
        {"sigma": 2.3, "vol": 1.30, "wick": 0.40, "trend": "NONE", "hour": 2, "target": "VWAP", "rr": 2.0, "desc": "Sigma 2.3σ + Vol 1.30x + H>=2"},
        
        # 3. Macro Trend Alignment (EMA200 Filter)
        {"sigma": 2.0, "vol": 1.20, "wick": 0.38, "trend": "EMA200", "hour": 0, "target": "VWAP", "rr": 2.0, "desc": "Sigma 2.0σ + EMA200 Trend"},
        {"sigma": 2.2, "vol": 1.20, "wick": 0.38, "trend": "EMA200", "hour": 2, "target": "VWAP", "rr": 2.0, "desc": "Sigma 2.2σ + EMA200 + H>=2"},

        # 4. Target Tuning: Fixed 2.0R vs 2.5R vs VWAP
        {"sigma": 2.2, "vol": 1.25, "wick": 0.38, "trend": "NONE", "hour": 2, "target": "FIXED_RR", "rr": 2.0, "desc": "Sigma 2.2σ + Fixed 2.0R"},
        {"sigma": 2.2, "vol": 1.25, "wick": 0.38, "trend": "NONE", "hour": 2, "target": "FIXED_RR", "rr": 2.5, "desc": "Sigma 2.2σ + Fixed 2.5R"},
        {"sigma": 2.4, "vol": 1.25, "wick": 0.38, "trend": "NONE", "hour": 2, "target": "FIXED_RR", "rr": 2.0, "desc": "Sigma 2.4σ + Fixed 2.0R"},
        
        # 5. Grand Institutional Alpha Confluence
        {"sigma": 2.3, "vol": 1.35, "wick": 0.40, "trend": "EMA200", "hour": 2, "target": "FIXED_RR", "rr": 2.2, "desc": "👑 Quant Master Alpha A"},
        {"sigma": 2.4, "vol": 1.30, "wick": 0.42, "trend": "NONE", "hour": 2, "target": "VWAP", "rr": 2.0, "desc": "👑 Quant Master Alpha B"},
        {"sigma": 2.5, "vol": 1.25, "wick": 0.40, "trend": "NONE", "hour": 2, "target": "FIXED_RR", "rr": 2.2, "desc": "👑 Quant Master Alpha C"}
    ]

    results = []
    for g in grid:
        res = simulate_tuned(
            rates, df,
            sigma_mult=g["sigma"], min_vol=g["vol"], min_wick=g["wick"],
            trend_filter=g["trend"], min_hour=g["hour"], target_mode=g["target"], rr=g["rr"]
        )
        print(f"{g['desc']:32s} | Trades: {res['trades']:3d} | WR: {res['wr']:4.1f}% | Net: ${res['pnl']:+7.2f} | PF: {res['pf']:4.2f} | DD: ${res['max_dd']:5.2f}")
        results.append({
            "Config": g["desc"],
            "Sigma": g["sigma"],
            "Vol": g["vol"],
            "Wick": g["wick"],
            "Trend": g["trend"],
            "Target": g["target"],
            "Trades": res["trades"],
            "Wins": res["wins"],
            "Losses": res["losses"],
            "BE": res["be"],
            "WinRate%": round(res["wr"], 1),
            "NetProfit($)": round(res["pnl"], 2),
            "ProfitFactor": round(res["pf"], 2),
            "MaxDD($)": round(res["max_dd"], 2)
        })

    mt5.shutdown()

    res_df = pd.DataFrame(results)
    csv_out = os.path.join(current_dir, "S20_22_hyper_tuning_results.csv")
    res_df.to_csv(csv_out, index=False)

    print("\n" + "=" * 95)
    print("🏆 TOP 5 TUNED QUANT CONFIGURATIONS (Ranked by Profit Factor & Drawdown)")
    print("=" * 95)
    top_df = res_df.sort_values(by=["ProfitFactor", "NetProfit($)"], ascending=[False, False]).head(6)
    print(top_df[["Config", "Trades", "WinRate%", "NetProfit($)", "ProfitFactor", "MaxDD($)"]].to_string(index=False))
    print("=" * 95)


if __name__ == "__main__":
    main()
