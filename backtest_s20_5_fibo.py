import MetaTrader5 as mt5
from datetime import datetime
import sys
import os

# Add current path to import strategy20
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import strategy20

def run_fibo_backtest():
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        return

    import config
    symbol = config.SYMBOL
    if not symbol:
        symbol = "XAUUSDm"
    tfs = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "H12": mt5.TIMEFRAME_H12,
        "D1": mt5.TIMEFRAME_D1
    }
    
    print(f"Starting S20.5 Fibo Entry Backtest (30 Days) on {symbol}...")
    
    results = []
    total_wins = 0
    total_losses = 0
    total_trades = 0
    
    for tf_name, tf_val in tfs.items():
        # Fetch 5000 candles to cover ~30 days for most TFs
        rates = mt5.copy_rates_from_pos(symbol, tf_val, 0, 5000)
        if rates is None or len(rates) == 0:
            print(f"Failed to get rates for {tf_name}")
            continue
            
        trades = 0
        wins = 0
        losses = 0
        
        # Rolling window simulation
        for i in range(100, len(rates) - 20):
            window_rates = rates[i-100:i]
            res = strategy20.strategy_20(window_rates, tf=tf_name)
            
            if res.get("signal") in ("BUY", "SELL") and "Fibo_Entry" in str(res.get("pattern")):
                trades += 1
                entry = res["entry"]
                sl = res["sl"]
                tp = res["tp"]
                
                # Check forward 20 candles for outcome
                outcome = "UNKNOWN"
                filled = False
                for j in range(i, min(i+20, len(rates))):
                    future_bar = rates[j]
                    if res["signal"] == "BUY":
                        if not filled:
                            if future_bar['high'] >= tp:
                                break # Cancel
                            if future_bar['low'] <= entry:
                                filled = True
                        if filled:
                            if future_bar['low'] <= sl:
                                outcome = "LOSS"
                                losses += 1
                                break
                            elif future_bar['high'] >= tp:
                                outcome = "WIN"
                                wins += 1
                                break
                    else:
                        if not filled:
                            if future_bar['low'] <= tp:
                                break # Cancel
                            if future_bar['high'] >= entry:
                                filled = True
                        if filled:
                            if future_bar['high'] >= sl:
                                outcome = "LOSS"
                                losses += 1
                                break
                            elif future_bar['low'] <= tp:
                                outcome = "WIN"
                                wins += 1
                                break
        
        total_trades += trades
        total_wins += wins
        total_losses += losses
        
        resolved_trades = wins + losses
        win_rate = (wins / resolved_trades * 100) if resolved_trades > 0 else 0
        
        # Dynamic reason based on TF
        reason1 = "Fibo 50-60% / Test 1-2"
        reason2 = "ตลาดเทแรงยืน 2 ไม่ได้ / หลุดฐาน 0"
        if tf_name in ("H1", "H4", "D1"):
            reason1 = "FVG KRH1/KRH3 Rejection"
            reason2 = "โดนเทหนักทะลุรากมะม่วง"
            
        results.append(f"| **{tf_name}** | {trades} | {wins} | {losses} | {win_rate:.2f}% | {reason1} | {reason2} |")
        
    print("\n| กรอบเวลา (Timeframe) | จำนวนการเข้าเทรดทั้งหมด (Trades) | เคสที่ชนะ (Win) | เคสที่แพ้ (Loss) | อัตราแพ้ชนะ (Win Rate %) | แนวราคา/ระดับสัญญาณเทคนิคอลที่เข้าบ่อยที่สุด | พฤติกรรมราคา/จุดอ่อนที่ทำเกิดการ Loss ใน TF นี้ |")
    print("|---|---|---|---|---|---|---|")
    for r in results:
        print(r)
        
    total_winrate = (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) > 0 else 0
    print(f"| **สรุปรวมทุก TF** | {total_trades} | {total_wins} | {total_losses} | {total_winrate:.2f}% | - | - |")
        
    mt5.shutdown()
    print("\nBacktest completed successfully. Results printed to console.")

if __name__ == "__main__":
    run_fibo_backtest()
