import argparse
import sys
import copy
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone

import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from strategy20_8 import strategy_20_8

def main():
    parser = argparse.ArgumentParser(description="Backtest S20.8 Strategy via MT5")
    parser.add_argument("--days", type=int, default=30, help="จำนวนวันย้อนหลัง (Days)")
    parser.add_argument("--tf", type=str, default="all", help="Timeframe (e.g. M1, M5, M15, M30, H1, H4, H12, D1 หรือ all)")
    args = parser.parse_args()
    
    if args.tf.lower() == "all":
        tfs = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]
    else:
        tfs = [args.tf.upper()]

    if not mt5.initialize():
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

    print("=========================================================================================")
    print(f"| กรอบเวลา | จำนวนการเข้าเทรดทั้งหมด (Trades) | เคสที่ชนะ (Win) | เคสที่แพ้ (Loss) | อัตราแพ้ชนะ (Win Rate %) | แนวราคา/ระดับสัญญาณเทคนิคอลที่เข้าบ่อยที่สุด | ผลรวมกำไรขาดทุนสุทธิ (Net P&L ($)) |")
    print("=========================================================================================")
    
    total_trades = 0
    total_win = 0
    total_loss = 0
    total_pnl = 0.0
    
    for tf_name in tfs:
        mt5_tf = tf_mapping.get(tf_name)
        if mt5_tf is None:
            continue
            
        if tf_name == "M1": bars_needed = args.days * 1440
        elif tf_name == "M5": bars_needed = args.days * 288
        elif tf_name == "M15": bars_needed = args.days * 96
        elif tf_name == "M30": bars_needed = args.days * 48
        elif tf_name == "H1": bars_needed = args.days * 24
        elif tf_name == "H4": bars_needed = args.days * 6
        elif tf_name == "H12": bars_needed = args.days * 2
        elif tf_name == "D1": bars_needed = args.days
        else: bars_needed = args.days * 1440
        
        rates_raw = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, bars_needed)
        if rates_raw is None or len(rates_raw) == 0:
            print(f"| {tf_name:<8} | 0 | 0 | 0 | 0.00% | N/A | $0.00 |")
            continue
            
        class SimConfig:
            def __getattr__(self, name):
                return getattr(config, name)
                
        sim_config = SimConfig()
        sim_config.S20_8_ENABLED = True
        sim_config.S20_8_SL_POINTS = 100.0
        sim_config.S20_8_TP_POINTS = 700.0
        sim_config.S20_8_ENTRY_BUFFER_POINTS = 300.0
        sim_config.S20_8_POINTS_MULTIPLIER = 0.01
        
        tf_trades = 0
        tf_win = 0
        tf_loss = 0
        tf_pnl = 0.0
        
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
                        loss_amt = (pos_entry - pos_sl) * contract_size * lot_size
                        tf_pnl -= loss_amt
                        tf_loss += 1
                        in_position = False
                    elif curr_high >= pos_tp:
                        win_amt = (pos_tp - pos_entry) * contract_size * lot_size
                        tf_pnl += win_amt
                        tf_win += 1
                        in_position = False
                        
                elif pos_type == "SELL":
                    if curr_high >= pos_sl:
                        loss_amt = (pos_sl - pos_entry) * contract_size * lot_size
                        tf_pnl -= loss_amt
                        tf_loss += 1
                        in_position = False
                    elif curr_low <= pos_tp:
                        win_amt = (pos_entry - pos_tp) * contract_size * lot_size
                        tf_pnl += win_amt
                        tf_win += 1
                        in_position = False
                        
                continue 

            result = strategy_20_8(current_rates, tf=tf_name, config=sim_config)
            if result.get("signal") in ("BUY", "SELL"):
                # --- Quant Engine Intercept ---
                # import quant_engine
                # last_candle_time = curr_bar["time"]
                # time_bkk = datetime.fromtimestamp(last_candle_time, tz=BKK)
                # curr_price = float(curr_bar["close"])
                
                # quant_res = quant_engine.evaluate_signal(tf_name, 20.8, result, current_rates, curr_price, time_bkk)
                # if quant_res.get("status") == "REJECTED":
                #     continue
                    
                # if quant_res.get("adjusted_sl"):
                #     result["sl"] = quant_res["adjusted_sl"]
                # if quant_res.get("adjusted_tp"):
                #     result["tp"] = quant_res["adjusted_tp"]
                # ------------------------------
                
                in_position = True
                pos_type = result["signal"]
                pos_entry = result["entry"]
                pos_sl = result["sl"]
                pos_tp = result["tp"]
                tf_trades += 1
                
        win_rate = (tf_win / tf_trades * 100) if tf_trades > 0 else 0.0
        
        print(f"| {tf_name:<8} | {tf_trades:<32} | {tf_win:<15} | {tf_loss:<16} | {win_rate:>20.2f}% | Small 2L/2H Rejection | ${tf_pnl:>22.2f} |")
        
        total_trades += tf_trades
        total_win += tf_win
        total_loss += tf_loss
        total_pnl += tf_pnl

    mt5.shutdown()
    
    total_win_rate = (total_win / total_trades * 100) if total_trades > 0 else 0.0
    print("=========================================================================================")
    print(f"| สรุปรวมทุก TF | {total_trades:<32} | {total_win:<15} | {total_loss:<16} | {total_win_rate:>20.2f}% | Small 2L/2H Rejection | ${total_pnl:>22.2f} |")
    print("=========================================================================================")

if __name__ == "__main__":
    main()
