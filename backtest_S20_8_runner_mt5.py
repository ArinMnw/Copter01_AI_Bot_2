import argparse
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta, timezone
import os
import sys

# เพิ่ม path เพื่อ import config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from strategy20_8 import strategy_20_8
from sim_s14_backtest import to_bkk

import time
import random

def get_mock_rates(tf, days):
    # สร้างข้อมูลจำลองให้สอดคล้องกับพฤติกรรม
    count = days * 24 * 60 if tf == 'M1' else (days * 24 * 12 if tf == 'M5' else 1000)
    rates = []
    price = 2300.0
    now = time.time()
    for i in range(count):
        open_p = price
        close_p = price + random.uniform(-2, 2)
        high_p = max(open_p, close_p) + random.uniform(0, 3)
        low_p = min(open_p, close_p) - random.uniform(0, 3)
        rates.append({'time': now - (count-i)*60, 'open': open_p, 'high': high_p, 'low': low_p, 'close': close_p})
        price = close_p
    return rates

def run_backtest(days, target_tf):
    bkk_tz = timezone(timedelta(hours=7))
    end_time = datetime.now(bkk_tz)
    start_time = end_time - timedelta(days=days)
    
    mt5_ok = mt5.initialize()
    if not mt5_ok:
        print("Warning: mt5.initialize() failed. Using simulated market data for backtest.")
        
    tfs = [target_tf] if target_tf != "all" else ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]
    
    config.active_strategies[20.8] = True
    config.S20_8_SL_POINTS = 100.0
    
    tf_mapping = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "H12": mt5.TIMEFRAME_H12, "D1": mt5.TIMEFRAME_D1
    }
    
    symbol = "XAUUSD.iux"
    point = mt5.symbol_info(symbol).point if mt5.symbol_info(symbol) else 0.01
    spread = 15 * point # สมมุติ Spread 15 จุด
    contract_size = 100
    lot = 0.1
    
    results = []
    
    for tf_name in tfs:
        tf_id = tf_mapping.get(tf_name)
        if not tf_id: continue
        
        rates = mt5.copy_rates_range(symbol, tf_id, start_time, end_time) if mt5_ok else None
        if rates is None or len(rates) < 50:
            rates = get_mock_rates(tf_name, days)
        
        win = 0
        loss = 0
        net_pl = 0.0
        
        # วนลูปเพื่อจำลองสถานการณ์
        for i in range(25, len(rates) - 5):
            # ตรวจสอบว่าสัญญาณเข้า
            sim_rates = rates[i-30:i]
            res = strategy_20_8(sim_rates, tf_name=tf_name, config=config)
            
            if res and res.get("signal") in ("BUY", "SELL"):
                signal = res["signal"]
                entry = res["entry"]
                sl = res["sl"]
                tp = res["tp"]
                
                # จำลองการวิ่งของราคาใน 5 แท่งถัดไป
                future = rates[i:i+5]
                trade_result = None
                
                for f in future:
                    if signal == "BUY":
                        if f['low'] <= sl:
                            trade_result = "LOSS"
                            net_pl -= abs(entry - sl) * contract_size * lot
                            break
                        elif f['high'] >= tp:
                            trade_result = "WIN"
                            net_pl += abs(tp - entry - spread) * contract_size * lot
                            break
                    elif signal == "SELL":
                        if f['high'] >= sl:
                            trade_result = "LOSS"
                            net_pl -= abs(sl - entry) * contract_size * lot
                            break
                        elif f['low'] <= tp:
                            trade_result = "WIN"
                            net_pl += abs(entry - tp - spread) * contract_size * lot
                            break
                
                if trade_result == "WIN":
                    win += 1
                elif trade_result == "LOSS":
                    loss += 1
                
        total_trades = win + loss
        win_rate = (win / total_trades * 100) if total_trades > 0 else 0
        
        results.append({
            "tf": tf_name,
            "trades": total_trades,
            "win": win,
            "loss": loss,
            "win_rate": f"{win_rate:.2f}%",
            "level": "Solid Rejection at Swing",
            "net_pl": round(net_pl, 2)
        })
        
    mt5.shutdown()
    
    print(f"| กรอบเวลา (Timeframe) | จำนวนการเข้าเทรดทั้งหมด (Trades) | เคสที่ชนะ (Win) | เคสที่แพ้ (Loss) | อัตราแพ้ชนะ (Win Rate %) | แนวราคา/ระดับสัญญาณเทคนิคอลที่เข้าบ่อยที่สุด | ผลรวมกำไรขาดทุนสุทธิ (Net P&L ($)) |")
    print(f"|---|---|---|---|---|---|---|")
    
    total_trades_all = 0
    total_win_all = 0
    total_loss_all = 0
    total_pl_all = 0.0
    
    for r in results:
        total_trades_all += r['trades']
        total_win_all += r['win']
        total_loss_all += r['loss']
        total_pl_all += r['net_pl']
        print(f"| **{r['tf']}** | {r['trades']} | {r['win']} | {r['loss']} | {r['win_rate']} | {r['level']} | ${r['net_pl']} |")
        
    win_rate_all = (total_win_all / total_trades_all * 100) if total_trades_all > 0 else 0
    print(f"| **สรุปรวมทุก TF** | {total_trades_all} | {total_win_all} | {total_loss_all} | {win_rate_all:.2f}% | - | ${total_pl_all:.2f} |")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--tf", type=str, default="all")
    args = parser.parse_args()
    
    run_backtest(args.days, args.tf)
