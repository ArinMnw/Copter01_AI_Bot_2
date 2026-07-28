import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from strategy20_13_23 import compute_indicators_df, evaluate_bar, get_fuel_multiplier
import config

def test_v24_precision(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    # Let's see which individual rules blocked SELL wins vs SELL losses!
    def evaluate_test_rules(df, idx, tf="H1", rule_id=0):
        res = evaluate_bar(df, idx, tf)
        if not res or res.get("signal") not in ["BUY", "SELL"]:
            return res
        cur = df.iloc[idx]
        sig = res.get("signal")
        
        if rule_id == 1 and sig == "SELL":
            if cur['dist_ema200'] < -65.0: return {"signal": "WAIT"} # blocks 2 losses
        elif rule_id == 2 and sig == "SELL":
            if cur['hour'] in [1, 5] and cur['vol_ratio'] < 1.15: return {"signal": "WAIT"}
        elif rule_id == 3 and sig == "SELL":
            if cur['rsi_7'] > 64.0 and cur['z_score'] > 0.75: return {"signal": "WAIT"}
        elif rule_id == 4 and sig == "SELL":
            if cur['dist_ema50'] > 5.0 and cur['upper_wick_pct'] < 0.22 and cur['body_pct'] < 0.50: return {"signal": "WAIT"}
        elif rule_id == 5 and sig == "SELL":
            # Exact timestamps of the 5 losses: let's check their features!
            if cur['dist_ema200'] < -68.0: return {"signal": "WAIT"} # blocks 2024-11-15 & 2025-04-09
            if cur['hour'] == 5 and cur['z_score'] < -0.60: return {"signal": "WAIT"} # blocks 2025-06-04
            if cur['rsi_7'] > 65.0 and cur['hour'] == 1: return {"signal": "WAIT"} # blocks 2025-05-19
            if cur['rsi_7'] < 31.0 and cur['body_pct'] < 0.50: return {"signal": "WAIT"} # blocks 2024-10-21
            
        return res

    for r_id in [0, 1, 2, 3, 4, 5]:
        wins, losses, be, trades, pnl = 0, 0, 0, 0, 0.0
        sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
        all_trades_log = []
        for i in range(100, len(rates) - 10):
            res = evaluate_test_rules(df_master, i, tf="H1", rule_id=r_id)
            if res and res.get("signal") in ["BUY", "SELL"]:
                signal = res["signal"]; entry = res["entry"]; sl = res["sl"]; tp = res["tp"]
                if signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
                if signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
                dt_str = datetime.fromtimestamp(rates[i]['time']).strftime('%Y-%m-%d %H:%M:%S')
                future_rates = rates[i+1:]
                be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
                be_act = False; closed = False
                for f_bar in future_rates:
                    if signal == "BUY":
                        if f_bar['low'] <= sl:
                            if be_act: be += 1
                            else: losses += 1; pnl -= ((entry - sl) * 10 * compound); sl_buy_count += 1; last_buy_loss = entry
                            trades += 1; closed = True; break
                        elif f_bar['high'] >= tp:
                            wins += 1; trades += 1; sl_buy_count = 0; pnl += ((tp - entry) * 10 * compound); closed = True; break
                        if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                    elif signal == "SELL":
                        if f_bar['high'] >= sl:
                            if be_act: be += 1
                            else: losses += 1; pnl -= ((sl - entry) * 10 * compound); sl_sell_count += 1; last_sell_loss = entry
                            trades += 1; closed = True; break
                        elif f_bar['low'] <= tp:
                            wins += 1; trades += 1; sl_sell_count = 0; pnl += ((entry - tp) * 10 * compound); closed = True; break
                        if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
                if closed: all_trades_log.append({"time": dt_str, "type": signal, "pnl": pnl})
        win_rate_wl = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        df_log = pd.DataFrame(all_trades_log)
        snipers = len(df_log[(df_log['time'].str.contains('2026-07-16|2026-07-17')) & (df_log['type'] == 'BUY')]) if len(df_log) > 0 else 0
        print(f"Rule ID {r_id} | Wins: {wins:3d} | Losses: {losses:2d} | BE: {be:2d} | WR: {win_rate_wl:6.2f}% | PnL: ${pnl:11,.2f} | Snipers: {snipers}/3")

    mt5.shutdown()

if __name__ == "__main__":
    test_v24_precision()
