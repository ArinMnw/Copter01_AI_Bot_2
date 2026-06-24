import argparse
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
import pandas as pd
import config
from strategy20_7 import strategy_20_7

# อิงจาก AGENTS.md: เวลา MT5 Server IUX คือ UTC+6, BKK คือ UTC+7 (ห่างกัน 1 ชม.)
# ต้อง +1 ชม เพื่อแปลงชาร์ตเป็น BKK
def to_bkk(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=7)

def main():
    parser = argparse.ArgumentParser(description="Backtest S20.7 Ultimate 1 Entry")
    parser.add_argument("--days", type=int, default=30, help="Days to backtest")
    parser.add_argument("--tf", type=str, default="all", help="Timeframe: M1, M5, M15, M30, H1, H4, H12, D1, all")
    args = parser.add_argument_group()
    args = parser.parse_args()

    if not mt5.initialize():
        print("initialize() failed")
        mt5.shutdown()
        quit()

    symbol = config.SYMBOL
    if args.tf == "all":
        tfs = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]
    else:
        tfs = [args.tf]

    mt5_tfs = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "H12": mt5.TIMEFRAME_H12,
        "D1": mt5.TIMEFRAME_D1
    }

    # เปิดใช้งานเพื่อทำการ Test เสมือนเปิดบอท
    config.S20_7_ENABLED = True
    lot_size = config.AUTO_VOLUME # 0.01

    results = []

    print(f"--- Starting Backtest for S20.7 on {symbol} for {args.days} days ---")
    
    total_trades_all = 0
    total_wins_all = 0
    total_losses_all = 0
    total_pnl_all = 0.0

    for tf in tfs:
        mt5_tf = mt5_tfs[tf]
        # ดึงแท่งเทียนโดยใช้คณิตศาสตร์คร่าวๆ (1 วัน = X แท่ง)
        bars_per_day = {"M1": 1440, "M5": 288, "M15": 96, "M30": 48, "H1": 24, "H4": 6, "H12": 2, "D1": 1}
        num_bars = bars_per_day[tf] * args.days + 50 # buffer
        
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, num_bars)
        if rates is None or len(rates) < 20:
            continue

        # แปลงเป็น dict format ที่บอทใช้
        formatted_rates = []
        for r in rates:
            formatted_rates.append({
                "time": r['time'],
                "open": r['open'],
                "high": r['high'],
                "low": r['low'],
                "close": r['close'],
                "tick_volume": r['tick_volume']
            })

        trades = 0
        wins = 0
        losses = 0
        pnl = 0.0
        
        entry_prices = []

        # สแกนทีละแท่ง (Walk-forward จำลอง)
        for i in range(20, len(formatted_rates)):
            slice_rates = formatted_rates[i-20:i]
            # เรียกใช้งาน strategy_20_7
            res = strategy_20_7(slice_rates, tf=tf, dt_bkk=to_bkk(slice_rates[-1]['time']))
            
            if res.get("signal") in ("BUY", "SELL"):
                # เจอสัญญานแล้ว จำลองการตั้ง Pending Order ที่ปลายไส้ และรอราคาชน
                sig = res["signal"]
                entry = res["entry"]
                sl = res["sl"]
                tp = res["tp"]
                
                # มองไปอนาคต (แท่ง i ถึงจบ) เพื่อดูว่าราคาชน Entry ไหม
                # จากนั้นดูว่าชน TP หรือ SL ก่อน
                triggered = False
                trade_result = None
                
                for j in range(i, len(formatted_rates)):
                    future_bar = formatted_rates[j]
                    
                    if not triggered:
                        if sig == "BUY" and future_bar['low'] <= entry:
                            triggered = True
                            entry_prices.append(entry)
                        elif sig == "SELL" and future_bar['high'] >= entry:
                            triggered = True
                            entry_prices.append(entry)
                    
                    if triggered:
                        if sig == "BUY":
                            if future_bar['low'] <= sl:
                                trade_result = "LOSS"
                                break
                            if future_bar['high'] >= tp:
                                trade_result = "WIN"
                                break
                        else:
                            if future_bar['high'] >= sl:
                                trade_result = "LOSS"
                                break
                            if future_bar['low'] <= tp:
                                trade_result = "WIN"
                                break
                                
                if trade_result == "WIN":
                    wins += 1
                    trades += 1
                    # คำนวณ PnL (Gold 100 pt = $1 สำหรับ 0.01 lot)
                    pts = abs(tp - entry)
                    pnl += (pts * lot_size)
                elif trade_result == "LOSS":
                    losses += 1
                    trades += 1
                    pts = abs(entry - sl)
                    pnl -= (pts * lot_size)

        win_rate = (wins / trades * 100) if trades > 0 else 0
        most_freq_level = "-"
        if entry_prices:
            # หาราคาที่เกิดบ่อยสุดแบบกลุ่ม (bin)
            most_freq_level = f"{round(sum(entry_prices)/len(entry_prices), 2)} (Avg)"

        results.append({
            "TF": tf,
            "Trades": trades,
            "Win": wins,
            "Loss": losses,
            "WR": f"{win_rate:.1f}%",
            "Level": most_freq_level,
            "PnL": f"${pnl:.2f}"
        })
        
        total_trades_all += trades
        total_wins_all += wins
        total_losses_all += losses
        total_pnl_all += pnl

    mt5.shutdown()

    print(f"| กรอบเวลา (Timeframe) | จำนวนการเข้าเทรดทั้งหมด (Trades) | เคสที่ชนะ (Win) | เคสที่แพ้ (Loss) | อัตราแพ้ชนะ (Win Rate %) | แนวราคา/ระดับสัญญาณเทคนิคอลที่เข้าบ่อยที่สุด | ผลรวมกำไรขาดทุนสุทธิ (Net P&L ($)) |")
    print(f"|---|---|---|---|---|---|---|")
    for r in results:
        print(f"| **{r['TF']}** | {r['Trades']} | {r['Win']} | {r['Loss']} | {r['WR']} | {r['Level']} | {r['PnL']} |")
    
    overall_wr = (total_wins_all / total_trades_all * 100) if total_trades_all > 0 else 0
    print(f"| **สรุปรวมทุก TF** | {total_trades_all} | {total_wins_all} | {total_losses_all} | {overall_wr:.1f}% | - | ${total_pnl_all:.2f} |")


if __name__ == "__main__":
    main()
