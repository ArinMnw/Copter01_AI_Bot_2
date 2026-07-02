import argparse
import sys
import copy
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STRATEGY_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.abspath(os.path.join(STRATEGY_DIR, "..", ".."))
for _path in (REPO_ROOT, STRATEGY_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import config
from strategy20_8 import strategy_20_8

def run_backtest_for_days(days, symbol, tfs, tf_mapping, contract_size, lot_size, BKK):
    total_trades_all = 0
    total_win_all = 0
    total_loss_all = 0
    total_pnl_all = 0.0
    
    # Costs
    commission_per_lot = 7.0
    spread_slippage_points = 20.0
    cost_per_trade = (commission_per_lot * lot_size) + (spread_slippage_points * contract_size * lot_size * getattr(config, "S20_8_POINTS_MULTIPLIER", 0.01))
    
    results = []
    
    class SimConfig:
        def __getattr__(self, name):
            return getattr(config, name)
            
    sim_config = SimConfig()
    sim_config.S20_8_ENABLED = True
    sim_config.S20_8_POINTS_MULTIPLIER = 0.01

    for tf_name in tfs:
        mt5_tf = tf_mapping.get(tf_name)
        if mt5_tf is None: continue
        
        bars_needed = days * 1440 if tf_name == "M1" else days * 288 if tf_name == "M5" else days * 96 if tf_name == "M15" else days * 48 if tf_name == "M30" else days * 24
        
        rates_raw = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, bars_needed)
        if rates_raw is None or len(rates_raw) == 0:
            continue
            
        tf_trades = 0
        tf_win = 0
        tf_loss = 0
        
        in_position = False
        pos_type = None
        pos_entry = 0.0
        pos_sl = 0.0
        pos_tp = 0.0
        current_trade_lot = 0.01
        
        # Compounding Variables
        initial_balance = 1000.0
        current_balance = initial_balance
        peak_balance = initial_balance
        max_drawdown = 0.0
        
        for i in range(15, len(rates_raw)):
            current_rates = [{"time": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "tick_volume": r[5]} for r in rates_raw[i-15:i+1]]
            curr_bar = current_rates[-1]
            
            if in_position:
                curr_high = float(curr_bar["high"])
                curr_low = float(curr_bar["low"])
                trade_pnl = 0.0
                closed = False
                
                cost_per_trade = (commission_per_lot * current_trade_lot) + (spread_slippage_points * contract_size * current_trade_lot * getattr(config, "S20_8_POINTS_MULTIPLIER", 0.01))
                
                if pos_type == "BUY":
                    if curr_low <= pos_sl:
                        loss_amt = (pos_entry - pos_sl) * contract_size * current_trade_lot
                        trade_pnl = -loss_amt - cost_per_trade
                        tf_loss += 1
                        closed = True
                    elif curr_high >= pos_tp:
                        win_amt = (pos_tp - pos_entry) * contract_size * current_trade_lot
                        trade_pnl = win_amt - cost_per_trade
                        tf_win += 1
                        closed = True
                        
                elif pos_type == "SELL":
                    if curr_high >= pos_sl:
                        loss_amt = (pos_sl - pos_entry) * contract_size * current_trade_lot
                        trade_pnl = -loss_amt - cost_per_trade
                        tf_loss += 1
                        closed = True
                    elif curr_low <= pos_tp:
                        win_amt = (pos_entry - pos_tp) * contract_size * current_trade_lot
                        trade_pnl = win_amt - cost_per_trade
                        tf_win += 1
                        closed = True
                        
                if closed:
                    in_position = False
                    current_balance += trade_pnl
                    if current_balance > peak_balance:
                        peak_balance = current_balance
                    drawdown = peak_balance - current_balance
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
                        
                continue 

            result = strategy_20_8(current_rates, tf=tf_name, config=sim_config)
            if result.get("signal") in ("BUY", "SELL"):
                sl_dist = abs(result["entry"] - result["sl"])
                if sl_dist > 0:
                    risk_pct = 2.0 # Risk 2% of balance
                    risk_usd = current_balance * (risk_pct / 100.0)
                    calculated_lot = risk_usd / (sl_dist * contract_size)
                    current_trade_lot = max(0.01, min(round(calculated_lot, 2), 50.0))
                else:
                    current_trade_lot = 0.01
                    
                in_position = True
                pos_type = result["signal"]
                pos_entry = result["entry"]
                pos_sl = result["sl"]
                pos_tp = result["tp"]
                tf_trades += 1
                
        win_rate = (tf_win / tf_trades * 100) if tf_trades > 0 else 0.0
        final_pnl = current_balance - initial_balance
        results.append((days, tf_name, tf_trades, tf_win, tf_loss, win_rate, final_pnl, max_drawdown))
        
        total_trades_all += tf_trades
        total_win_all += tf_win
        total_loss_all += tf_loss
        total_pnl_all += final_pnl
        
    return results

def main():
    if not config.mt5_initialize(mt5):
        print("initialize() failed, error code =", mt5.last_error())
        return

    symbol = config.SYMBOL
    contract_size = 100.0  
    lot_size = 0.01

    BKK = timezone(timedelta(hours=7))
    tf_mapping = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "H12": mt5.TIMEFRAME_H12,
        "D1": mt5.TIMEFRAME_D1,
    }
    
    tfs = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]
    periods = [30, 60, 90, 120, 180]
    
    all_results = []
    for days in periods:
        res = run_backtest_for_days(days, symbol, tfs, tf_mapping, contract_size, lot_size, BKK)
        all_results.extend(res)
        
    mt5.shutdown()
    
    print("=========================================================================================================")
    print(f"| Days | กรอบเวลา | Trades | Win | Loss | Win Rate % | Net P&L ($) | Max Drawdown ($) |")
    print("=========================================================================================================")
    for r in all_results:
        days, tf_name, trades, win, loss, wr, pnl, mdd = r
        print(f"| {days:<4} | {tf_name:<8} | {trades:<6} | {win:<3} | {loss:<4} | {wr:>10.2f}% | $ {pnl:>10.2f} | $ {mdd:>13.2f} |")
    print("=========================================================================================================")

if __name__ == "__main__":
    main()
