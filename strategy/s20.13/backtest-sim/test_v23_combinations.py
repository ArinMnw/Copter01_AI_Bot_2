import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
import itertools

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_22 import compute_indicators_df, evaluate_bar

def test_combos(days=700, symbol="XAUUSD.iux", compound=1.5):
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    if not mt5.initialize(path=path): return
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start_time, end_time)
    
    df_master = compute_indicators_df(rates)
    df_master['upper_wick'] = df_master['high'] - np.maximum(df_master['open'], df_master['close'])
    df_master['lower_wick'] = np.minimum(df_master['open'], df_master['close']) - df_master['low']
    df_master['upper_wick_pct'] = df_master['upper_wick'] / (df_master['range'] + 0.0001)
    df_master['lower_wick_pct'] = df_master['lower_wick'] / (df_master['range'] + 0.0001)
    df_master['dist_ema50'] = df_master['close'] - df_master['ema_50']
    df_master['dist_ema200'] = df_master['close'] - df_master['ema_200']
    df_master['hour'] = df_master['time_dt'].dt.hour

    # Let's pre-evaluate all signals from v22 first to save time!
    signals_data = []
    for i in range(100, len(rates) - 10):
        res = evaluate_bar(df_master, i, tf="H1")
        if res and res.get("signal") in ["BUY", "SELL"]:
            signals_data.append((i, res["signal"], res["entry"], res["sl"], res["tp"], df_master.iloc[i]))
            
    print(f"Total base signals found: {len(signals_data)}")

    # Candidate rules for SELL:
    sell_candidates = [
        ("di_diff < 1.0 and body_pct > 0.85", lambda cur: cur['di_diff'] < 1.0 and cur['body_pct'] > 0.85),
        ("body_pct > 0.70 and atr_pct < 0.30", lambda cur: cur['body_pct'] > 0.70 and cur['atr_pct'] < 0.30),
        ("rsi_7 > 47.0 and atr_pct < 0.30", lambda cur: cur['rsi_7'] > 47.0 and cur['atr_pct'] < 0.30),
        ("adx > 40.0 and atr_pct < 0.35", lambda cur: cur['adx'] > 40.0 and cur['atr_pct'] < 0.35),
        ("rsi < 52.0 and z_score > 0.0", lambda cur: cur['rsi'] < 52.0 and cur['z_score'] > 0.0),
        ("rsi_7 < 55.0 and body_pct > 0.90", lambda cur: cur['rsi_7'] < 55.0 and cur['body_pct'] > 0.90),
        ("atr_pct < 0.40 and hour == 16", lambda cur: cur['atr_pct'] < 0.40 and cur['hour'] == 16),
        ("rsi < 45.0 and body_pct > 0.85", lambda cur: cur['rsi'] < 45.0 and cur['body_pct'] > 0.85),
        ("z_score < -0.50 and body_pct > 0.85", lambda cur: cur['z_score'] < -0.50 and cur['body_pct'] > 0.85),
        ("di_diff < -3.0 and body_pct > 0.85", lambda cur: cur['di_diff'] < -3.0 and cur['body_pct'] > 0.85),
    ]
    
    # Candidate rule for BUY:
    buy_rule = lambda cur: cur['rsi'] < 40.0 and cur['adx'] > 42.0

    best_pnl = 0.0
    best_combo = None
    best_stats = None

    # Try subsets of sell candidates (from size 2 to 6)
    for r_size in range(2, 7):
        for combo in itertools.combinations(range(len(sell_candidates)), r_size):
            wins, losses, be, trades, pnl = 0, 0, 0, 0, 0.0
            sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
            sniper_count = 0
            
            for i, signal, entry, sl, tp, cur in signals_data:
                if signal == "SELL":
                    blocked = False
                    for idx in combo:
                        if sell_candidates[idx][1](cur):
                            blocked = True; break
                    if blocked: continue
                elif signal == "BUY":
                    if buy_rule(cur): continue
                    
                if signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
                if signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
                
                dt_str = datetime.fromtimestamp(rates[i]['time']).strftime('%Y-%m-%d %H:%M')
                if '2026-07-16' in dt_str or '2026-07-17' in dt_str:
                    if signal == "BUY": sniper_count += 1
                
                future_rates = rates[i+1:]
                be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
                be_act = False
                closed = False
                
                for f_bar in future_rates:
                    if signal == "BUY":
                        if f_bar['low'] <= sl:
                            if be_act: be += 1
                            else:
                                losses += 1; pnl -= ((entry - sl) * 10 * compound)
                                sl_buy_count += 1; last_buy_loss = entry
                            trades += 1; closed = True; break
                        elif f_bar['high'] >= tp:
                            wins += 1; trades += 1; sl_buy_count = 0
                            pnl += ((tp - entry) * 10 * compound)
                            closed = True; break
                        if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                    elif signal == "SELL":
                        if f_bar['high'] >= sl:
                            if be_act: be += 1
                            else:
                                losses += 1; pnl -= ((sl - entry) * 10 * compound)
                                sl_sell_count += 1; last_sell_loss = entry
                            trades += 1; closed = True; break
                        elif f_bar['low'] <= tp:
                            wins += 1; trades += 1; sl_sell_count = 0
                            pnl += ((entry - tp) * 10 * compound)
                            closed = True; break
                        if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
                        
            win_rate_wl = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            
            if sniper_count >= 3 and win_rate_wl >= 80.0 and wins >= 55:
                if pnl > best_pnl:
                    best_pnl = pnl
                    best_combo = [sell_candidates[idx][0] for idx in combo]
                    best_stats = (wins, losses, be, trades, win_rate_wl, pnl)
                    
    print("\n================== BEST V23 COMBINATION RESULT ==================")
    if best_stats:
        wins, losses, be, trades, win_rate_wl, pnl = best_stats
        print(f"Wins: {wins} | Losses: {losses} | BE: {be} | Total: {trades}")
        print(f"Win/Loss Rate: {win_rate_wl:.2f}% (Target: >80%)")
        print(f"Net P&L ($): ${pnl:,.2f} (Target: >$150k)")
        print("\nSelected SELL Rules:")
        for r in best_combo: print(f" - {r}")
    else:
        print("No combo found meeting all criteria (Sniper >=3, WR >=80%, Wins >=55)")
        
    mt5.shutdown()

if __name__ == "__main__":
    test_combos()
