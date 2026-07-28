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

def check_pnl_diff(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    def eval_v24(df, idx, tf="H1", unlock_mode=4):
        res = evaluate_bar(df, idx, tf)
        if not res: return res
        cur = df.iloc[idx]; recent_3 = df.iloc[idx-2:idx+1]
        active_mode = getattr(config, "S20_13_ACTIVE_MODE", 2.6)
        target_tf_buy = getattr(config, "S20_13_TARGET_TF_BUY", "H12")
        target_tf_sell = getattr(config, "S20_13_TARGET_TF_SELL", "D1")
        sig = res.get("signal"); reason = res.get("reason", "")
        
        if sig == "WAIT" and unlock_mode > 0:
            if "BUY Low Volatility Drift Block" in reason:
                if cur['di_diff'] > 0.0 and cur['rsi_7'] > 52.0 and cur['dist_ema50'] > 5.0:
                    sweep_bottom = min(recent_3['low'].min(), cur['low'])
                    sl = sweep_bottom - config.SL_BUFFER(cur['atr'])
                    fuel = cur['atr'] * active_mode * get_fuel_multiplier("H1", target_tf_buy)
                    return {"signal": "BUY", "entry": cur['close'], "sl": sl, "tp": sweep_bottom + fuel, "reason": "Unlocked Drift"}
            elif "BUY Trend/Z Block" in reason and unlock_mode >= 2:
                if cur['rsi'] > 55.0 and cur['vol_ratio'] > 1.20 and cur['di_diff'] > 5.0:
                    sweep_bottom = min(recent_3['low'].min(), cur['low'])
                    sl = sweep_bottom - config.SL_BUFFER(cur['atr'])
                    fuel = cur['atr'] * active_mode * get_fuel_multiplier("H1", target_tf_buy)
                    return {"signal": "BUY", "entry": cur['close'], "sl": sl, "tp": sweep_bottom + fuel, "reason": "Unlocked Trend/Z"}
        if sig == "SELL":
            if cur['dist_ema50'] > 5.0 and cur['upper_wick_pct'] < 0.22 and cur['body_pct'] < 0.50: return {"signal": "WAIT"}
            if cur['hour'] == 5 and cur['vol_ratio'] < 1.10: return {"signal": "WAIT"}
            if cur['rsi_7'] > 64.0 and cur['z_score'] > 0.75: return {"signal": "WAIT"}
        return res

    for mode in [0, 4]:
        wins, losses, be, pnl = 0, 0, 0, 0.0
        sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
        trades_log = []
        for i in range(100, len(rates) - 10):
            res = eval_v24(df_master, i, tf="H1", unlock_mode=mode) if mode > 0 else evaluate_bar(df_master, i, tf="H1")
            if res and res.get("signal") in ["BUY", "SELL"]:
                signal = res["signal"]; entry = res["entry"]; sl = res["sl"]; tp = res["tp"]
                if signal == "BUY" and sl_buy_count >= 1 and abs(entry - last_buy_loss) <= 5.0: continue
                if signal == "SELL" and sl_sell_count >= 1 and abs(entry - last_sell_loss) <= 5.0: continue
                dt_str = datetime.fromtimestamp(rates[i]['time']).strftime('%Y-%m-%d %H:%M:%S')
                future_rates = rates[i+1:]
                be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
                be_act = False; closed_type = None; t_pnl = 0.0
                for f_bar in future_rates:
                    if signal == "BUY":
                        if f_bar['low'] <= sl:
                            closed_type = "BE" if be_act else "LOSS"; t_pnl = 0 if be_act else -((entry - sl)*10*compound)
                            if not be_act: sl_buy_count += 1; last_buy_loss = entry
                            break
                        elif f_bar['high'] >= tp:
                            closed_type = "WIN"; t_pnl = ((tp - entry)*10*compound); sl_buy_count = 0; break
                        if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
                    elif signal == "SELL":
                        if f_bar['high'] >= sl:
                            closed_type = "BE" if be_act else "LOSS"; t_pnl = 0 if be_act else -((sl - entry)*10*compound)
                            if not be_act: sl_sell_count += 1; last_sell_loss = entry
                            break
                        elif f_bar['low'] <= tp:
                            closed_type = "WIN"; t_pnl = ((entry - tp)*10*compound); sl_sell_count = 0; break
                        if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
                if closed_type:
                    if closed_type == "WIN": wins += 1; pnl += t_pnl
                    elif closed_type == "LOSS": losses += 1; pnl += t_pnl
                    elif closed_type == "BE": be += 1
                    trades_log.append({"time": dt_str, "type": signal, "outcome": closed_type, "pnl": t_pnl, "reason": res.get("reason", "")})
        print(f"Mode {mode} -> Wins: {wins} | Losses: {losses} | BE: {be} | PnL: ${pnl:,.2f}")
        if mode == 4:
            df_log = pd.DataFrame(trades_log)
            print("\nUnlocked Trades in Mode 4:")
            print(df_log[df_log['reason'].str.contains("Unlocked")].to_string())

    mt5.shutdown()

if __name__ == "__main__":
    check_pnl_diff()
