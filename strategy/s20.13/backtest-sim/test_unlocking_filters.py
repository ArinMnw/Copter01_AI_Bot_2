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

def test_unlocks(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    filters_to_test = [
        ("Baseline v23", None),
        ("Remove BUY Low Volatility Drift (atr_pct <= 0.41 & adx < 50)", "BUY Low Volatility Drift Block"),
        ("Remove BUY Trend/Z Block (z > 0 & adx > 30)", "BUY Trend/Z Block"),
        ("Remove SELL Momentum Conflict Block (rsi7 > 50.5 & body 0.35-0.615)", "SELL Momentum Conflict Block"),
        ("Remove SELL Low ADX Above EMA50 Block", "SELL Low ADX Above EMA50 Block"),
        ("Remove SELL Short-Term Oversold Bullish DI Block", "SELL Short-Term Oversold Bullish DI Block"),
        ("Remove BUY Trend Exhaustion Block (adx > 52)", "BUY Trend Exhaustion Block"),
        ("Remove SELL Low Volatility Upper BB Block", "SELL Low Volatility Upper BB Block"),
        ("Remove SELL Low Volume Trap Block", "SELL Low Volume Trap Block"),
        ("Remove SELL Trend/Z Block", "SELL Trend/Z Block"),
    ]

    print("================== TESTING UNLOCKING INDIVIDUAL FILTERS ==================")
    
    for name, ignore_reason in filters_to_test:
        wins, losses, be, trades, pnl = 0, 0, 0, 0, 0.0
        sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
        all_trades_log = []
        
        for i in range(100, len(rates) - 10):
            res = evaluate_bar(df_master, i, tf="H1")
            
            signal = None
            if res:
                if res.get("signal") in ["BUY", "SELL"]:
                    signal = res["signal"]; entry = res["entry"]; sl = res["sl"]; tp = res["tp"]
                elif ignore_reason and res.get("signal") == "WAIT" and res.get("reason", "").startswith(ignore_reason):
                    cur = df_master.iloc[i]
                    recent_3 = df_master.iloc[i-2:i+1]
                    active_mode = getattr(config, "S20_13_ACTIVE_MODE", 2.6)
                    target_tf_buy = getattr(config, "S20_13_TARGET_TF_BUY", "H12")
                    target_tf_sell = getattr(config, "S20_13_TARGET_TF_SELL", "D1")
                    
                    if res["reason"].startswith("BUY"):
                        signal = "BUY"
                        entry = cur['close']
                        sweep_bottom = min(recent_3['low'].min(), cur['low'])
                        sl = sweep_bottom - config.SL_BUFFER(cur['atr'])
                        fuel_multiplier = get_fuel_multiplier("H1", target_tf_buy)
                        fuel = cur['atr'] * active_mode * fuel_multiplier
                        tp = sweep_bottom + fuel
                    elif res["reason"].startswith("SELL"):
                        signal = "SELL"
                        entry = cur['close']
                        sweep_top = max(recent_3['high'].max(), cur['high'])
                        sl = sweep_top + config.SL_BUFFER(cur['atr'])
                        fuel_multiplier = get_fuel_multiplier("H1", target_tf_sell)
                        fuel = cur['atr'] * active_mode * fuel_multiplier
                        tp = sweep_top - fuel
            
            if signal in ["BUY", "SELL"]:
                if signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
                if signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
                
                dt_str = datetime.fromtimestamp(rates[i]['time']).strftime('%Y-%m-%d %H:%M:%S')
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
                if closed:
                    all_trades_log.append({"time": dt_str, "type": signal, "pnl": pnl})

        win_rate_wl = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        df_log = pd.DataFrame(all_trades_log)
        sniper_count = 0
        if len(df_log) > 0:
            sniper_count = len(df_log[(df_log['time'].str.contains('2026-07-16|2026-07-17')) & (df_log['type'] == 'BUY')])
            
        print(f"{name:<60} | Wins: {wins:3d} | Losses: {losses:2d} | WR: {win_rate_wl:6.2f}% | PnL: ${pnl:11,.2f} | Snipers: {sniper_count}/3")

    mt5.shutdown()

if __name__ == "__main__":
    test_unlocks()
