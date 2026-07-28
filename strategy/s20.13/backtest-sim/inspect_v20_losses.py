import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_20 import compute_indicators_df, evaluate_bar

def inspect_losses(days=365, symbol="XAUUSD.iux"):
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    if not mt5.initialize(path=path):
        print("MT5 init failed")
        return
        
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start_time, end_time)
    print(f"Loaded {len(rates)} H1 bars for {days} days")
    
    df_master = compute_indicators_df(rates)
    
    # Calculate additional features for analysis
    df_master['upper_wick'] = df_master['high'] - np.maximum(df_master['open'], df_master['close'])
    df_master['lower_wick'] = np.minimum(df_master['open'], df_master['close']) - df_master['low']
    df_master['upper_wick_pct'] = df_master['upper_wick'] / (df_master['range'] + 0.0001)
    df_master['lower_wick_pct'] = df_master['lower_wick'] / (df_master['range'] + 0.0001)
    df_master['dist_ema50'] = df_master['close'] - df_master['ema_50']
    df_master['dist_ema200'] = df_master['close'] - df_master['ema_200']
    df_master['hour'] = df_master['time_dt'].dt.hour
    
    sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
    
    trades_list = []
    
    for i in range(100, len(rates) - 10):
        res = evaluate_bar(df_master, i, tf="H1")
        if res and res.get("signal") in ["BUY", "SELL"]:
            signal = res["signal"]; entry = res["entry"]; sl = res["sl"]; tp = res["tp"]
            if signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
            if signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
            
            future_rates = rates[i+1:]
            be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
            be_act = False
            outcome = "OPEN"
            pnl = 0.0
            
            for f_bar in future_rates:
                if signal == "BUY":
                    if f_bar['low'] <= sl:
                        if be_act: outcome = "BE"
                        else:
                            outcome = "LOSS"
                            sl_buy_count += 1; last_buy_loss = entry
                        break
                    elif f_bar['high'] >= tp:
                        outcome = "WIN"; sl_buy_count = 0; break
                    if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                elif signal == "SELL":
                    if f_bar['high'] >= sl:
                        if be_act: outcome = "BE"
                        else:
                            outcome = "LOSS"
                            sl_sell_count += 1; last_sell_loss = entry
                        break
                    elif f_bar['low'] <= tp:
                        outcome = "WIN"; sl_sell_count = 0; break
                    if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
                    
            cur = df_master.iloc[i]
            trades_list.append({
                "idx": i,
                "time": cur['time_dt'].strftime('%Y-%m-%d %H:%M'),
                "signal": signal,
                "outcome": outcome,
                "rsi": round(cur['rsi'], 2),
                "rsi_7": round(cur['rsi_7'], 2),
                "adx": round(cur['adx'], 2),
                "di_diff": round(cur['di_diff'], 2),
                "vol_ratio": round(cur['vol_ratio'], 2),
                "z_score": round(cur['z_score'], 2),
                "body_pct": round(cur['body_pct'], 2),
                "atr_pct": round(cur['atr_pct'], 2),
                "dist_ema50": round(cur['dist_ema50'], 2),
                "dist_ema200": round(cur['dist_ema200'], 2),
                "upper_wick_pct": round(cur['upper_wick_pct'], 2),
                "lower_wick_pct": round(cur['lower_wick_pct'], 2),
                "hour": cur['hour']
            })
            
    df_trades = pd.DataFrame(trades_list)
    df_losses = df_trades[df_trades['outcome'] == 'LOSS']
    df_wins = df_trades[df_trades['outcome'] == 'WIN']
    
    print(f"Total Trades: {len(df_trades)} | Wins: {len(df_wins)} | Losses: {len(df_losses)}")
    print("\n--- ALL 20 LOSSES IN V20 ---")
    for idx, row in df_losses.iterrows():
        print(f"{row['time']} | {row['signal']} | RSI:{row['rsi']} RSI7:{row['rsi_7']} ADX:{row['adx']} DI_df:{row['di_diff']} VolR:{row['vol_ratio']} Z:{row['z_score']} Body%:{row['body_pct']} ATR%:{row['atr_pct']} dEMA50:{row['dist_ema50']} uWick%:{row['upper_wick_pct']} lWick%:{row['lower_wick_pct']} Hr:{row['hour']}")
        
    df_trades.to_csv('v20_all_trades_features.csv', index=False)
    print("\nSaved all trades with features to v20_all_trades_features.csv")
    mt5.shutdown()

if __name__ == "__main__":
    inspect_losses()
