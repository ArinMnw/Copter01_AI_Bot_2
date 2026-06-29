import sys
import copy
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from strategy20_8 import strategy_20_8

def run_backtest(days_list):
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        return

    symbol = config.SYMBOL
    contract_size = 100.0  
    lot_size = 0.01
    
    # Realistic Calculation Constants
    spread_pts = 15.0
    slippage_pts = 5.0
    commission_usd = 7.0 * lot_size # $7 per lot -> $0.07 for 0.01 lot

    tfs = ["M1", "M5", "M15", "M30"] # Focus on Sniper TFs
    
    tf_mapping = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30
    }

    class SimConfig:
        def __getattr__(self, name):
            return getattr(config, name)
            
    sim_config = SimConfig()
    sim_config.S20_8_ENABLED = True
    sim_config.S20_8_POINTS_MULTIPLIER = 0.01

    print("=========================================================================================================")
    print(f"| Days | กรอบเวลา | Trades | Win | Loss | Win Rate % | Net P&L ($) | Max Drawdown ($) |")
    print("=========================================================================================================")

    for days in days_list:
        for tf_name in tfs:
            mt5_tf = tf_mapping.get(tf_name)
            
            if tf_name == "M1": bars_needed = days * 1440
            elif tf_name == "M5": bars_needed = days * 288
            elif tf_name == "M15": bars_needed = days * 96
            elif tf_name == "M30": bars_needed = days * 48
            
            rates_raw = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, bars_needed)
            if rates_raw is None or len(rates_raw) == 0:
                continue

            tf_trades = 0
            tf_win = 0
            tf_loss = 0
            tf_pnl = 0.0
            
            peak_pnl = 0.0
            max_drawdown = 0.0
            
            in_position = False
            pos_type = None
            pos_entry = 0.0
            pos_sl = 0.0
            pos_tp = 0.0
            
            for i in range(15, len(rates_raw)):
                current_rates = [{"time": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4]} for r in rates_raw[i-15:i+1]]
                curr_bar = current_rates[-1]
                
                if in_position:
                    curr_high = float(curr_bar["high"])
                    curr_low = float(curr_bar["low"])
                    
                    if pos_type == "BUY":
                        if curr_low <= pos_sl:
                            # Apply slippage on Stop Loss
                            actual_sl = pos_sl - (slippage_pts * sim_config.S20_8_POINTS_MULTIPLIER)
                            loss_amt = (pos_entry - actual_sl) * contract_size * lot_size
                            tf_pnl -= loss_amt
                            tf_pnl -= commission_usd
                            tf_loss += 1
                            in_position = False
                        elif curr_high >= pos_tp:
                            # Limit orders generally get filled exactly, but spread matters
                            win_amt = (pos_tp - pos_entry) * contract_size * lot_size
                            tf_pnl += win_amt
                            tf_pnl -= commission_usd
                            tf_win += 1
                            in_position = False
                            
                    elif pos_type == "SELL":
                        if curr_high >= pos_sl:
                            actual_sl = pos_sl + (slippage_pts * sim_config.S20_8_POINTS_MULTIPLIER)
                            loss_amt = (actual_sl - pos_entry) * contract_size * lot_size
                            tf_pnl -= loss_amt
                            tf_pnl -= commission_usd
                            tf_loss += 1
                            in_position = False
                        elif curr_low <= pos_tp:
                            win_amt = (pos_entry - pos_tp) * contract_size * lot_size
                            tf_pnl += win_amt
                            tf_pnl -= commission_usd
                            tf_win += 1
                            in_position = False
                            
                    if tf_pnl > peak_pnl:
                        peak_pnl = tf_pnl
                    dd = peak_pnl - tf_pnl
                    if dd > max_drawdown:
                        max_drawdown = dd
                        
                    continue 

                result = strategy_20_8(current_rates, tf=tf_name, config=sim_config)
                if result.get("signal") in ("BUY", "SELL"):
                    in_position = True
                    pos_type = result["signal"]
                    
                    # Apply Spread on Entry
                    if pos_type == "BUY":
                        pos_entry = result["entry"] + (spread_pts * sim_config.S20_8_POINTS_MULTIPLIER)
                    else:
                        pos_entry = result["entry"] - (spread_pts * sim_config.S20_8_POINTS_MULTIPLIER)
                        
                    pos_sl = result["sl"]
                    pos_tp = result["tp"]
                    tf_trades += 1
                    
            win_rate = (tf_win / tf_trades * 100) if tf_trades > 0 else 0.0
            
            print(f"| {days:<4} | {tf_name:<8} | {tf_trades:<6} | {tf_win:<3} | {tf_loss:<4} | {win_rate:>10.2f}% | ${tf_pnl:>9.2f} | ${max_drawdown:>14.2f} |")

    mt5.shutdown()
    print("=========================================================================================================")

if __name__ == "__main__":
    run_backtest([30, 60, 90, 120, 180])
