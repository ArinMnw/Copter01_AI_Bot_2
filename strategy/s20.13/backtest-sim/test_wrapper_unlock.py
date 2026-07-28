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

def test_wrapper_unlock(days=700, symbol="XAUUSD.iux", compound=1.5):
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

    def eval_v24(df, idx, tf="H1", unlock_mode=1):
        res = evaluate_bar(df, idx, tf)
        if not res: return res
        
        cur = df.iloc[idx]
        recent_3 = df.iloc[idx-2:idx+1]
        active_mode = getattr(config, "S20_13_ACTIVE_MODE", 2.6)
        target_tf_buy = getattr(config, "S20_13_TARGET_TF_BUY", "H12")
        target_tf_sell = getattr(config, "S20_13_TARGET_TF_SELL", "D1")
        
        sig = res.get("signal")
        reason = res.get("reason", "")
        
        # 1) Try unlocking high-probability BUY setups blocked by v18/v20 filters:
        if sig == "WAIT" and unlock_mode > 0:
            if "BUY Low Volatility Drift Block" in reason:
                if cur['di_diff'] > 0.0 and cur['rsi_7'] > 52.0 and cur['dist_ema50'] > 5.0:
                    sweep_bottom = min(recent_3['low'].min(), cur['low'])
                    sl = sweep_bottom - config.SL_BUFFER(cur['atr'])
                    fuel = cur['atr'] * active_mode * get_fuel_multiplier("H1", target_tf_buy)
                    return {"signal": "BUY", "entry": cur['close'], "sl": sl, "tp": sweep_bottom + fuel, "reason": "v24 Unlocked Low Volatility Bullish Drift"}
            elif "BUY Trend/Z Block" in reason and unlock_mode >= 2:
                if cur['rsi'] > 55.0 and cur['vol_ratio'] > 1.20 and cur['di_diff'] > 5.0:
                    sweep_bottom = min(recent_3['low'].min(), cur['low'])
                    sl = sweep_bottom - config.SL_BUFFER(cur['atr'])
                    fuel = cur['atr'] * active_mode * get_fuel_multiplier("H1", target_tf_buy)
                    return {"signal": "BUY", "entry": cur['close'], "sl": sl, "tp": sweep_bottom + fuel, "reason": "v24 Unlocked Trend/Z Bullish Climb"}
            elif "BUY Trend Exhaustion Block" in reason and unlock_mode >= 3:
                if cur['vol_ratio'] > 1.50 and cur['rsi_7'] > 60.0:
                    sweep_bottom = min(recent_3['low'].min(), cur['low'])
                    sl = sweep_bottom - config.SL_BUFFER(cur['atr'])
                    fuel = cur['atr'] * active_mode * get_fuel_multiplier("H1", target_tf_buy)
                    return {"signal": "BUY", "entry": cur['close'], "sl": sl, "tp": sweep_bottom + fuel, "reason": "v24 Unlocked Strong Momentum Breakout"}
            elif "BUY Extreme Low Volume Breakout Block" in reason and unlock_mode >= 4:
                if cur['rsi_7'] > 58.0 and cur['di_diff'] > 8.0:
                    sweep_bottom = min(recent_3['low'].min(), cur['low'])
                    sl = sweep_bottom - config.SL_BUFFER(cur['atr'])
                    fuel = cur['atr'] * active_mode * get_fuel_multiplier("H1", target_tf_buy)
                    return {"signal": "BUY", "entry": cur['close'], "sl": sl, "tp": sweep_bottom + fuel, "reason": "v24 Unlocked Quiet Bull Breakout"}
                    
        # 2) Precision SELL loss block:
        if sig == "SELL":
            if cur['dist_ema50'] > 5.0 and cur['upper_wick_pct'] < 0.22 and cur['body_pct'] < 0.50:
                return {"signal": "WAIT", "reason": "v24 SELL Weak Wick Block"}
            if cur['hour'] == 5 and cur['vol_ratio'] < 1.10:
                return {"signal": "WAIT", "reason": "v24 SELL Asian Low Volume Trap"}
            if cur['rsi_7'] > 64.0 and cur['z_score'] > 0.75:
                return {"signal": "WAIT", "reason": "v24 SELL High RSI Momentum Trap"}
                
        return res

    for mode in [0, 1, 2, 3, 4]:
        wins, losses, be, trades, pnl = 0, 0, 0, 0, 0.0
        sl_buy_count, sl_sell_count, last_buy_loss, last_sell_loss = 0, 0, 0.0, 0.0
        all_trades_log = []
        for i in range(100, len(rates) - 10):
            res = eval_v24(df_master, i, tf="H1", unlock_mode=mode) if mode > 0 else evaluate_bar(df_master, i, tf="H1")
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
        print(f"Mode {mode} | Wins: {wins:3d} | Losses: {losses:2d} | BE: {be:2d} | WR: {win_rate_wl:6.2f}% | PnL: ${pnl:11,.2f} | Snipers: {snipers}/3")

    mt5.shutdown()

if __name__ == "__main__":
    test_wrapper_unlock()
