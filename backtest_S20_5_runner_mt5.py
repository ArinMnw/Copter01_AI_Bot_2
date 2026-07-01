import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5

# นำเข้าโมดูลและ config ของระบบ
import config
from mt5_utils import connect_mt5, TF_SECONDS_MAP

# ฟังก์ชันแปลงเวลาจาก Timezone ของระบบ (BKK) ให้เป็นเวลาแบบ MT5 (ถ้าจำเป็น)
BKK = timezone(timedelta(hours=7))

# ดึงข้อมูลจาก AGENTS.md:
# BKK_time = chart_time + 1 hour -> ดังนั้นเวลาชาร์ต (UTC+6) คือ BKK - 1
def mt5_ts_to_bkk(ts):
    # สมมติว่า ts คือ UTC timestamp จาก MT5 server
    # MT5 server มักจะเป็น UTC+2 หรือ UTC+3 แต่ใน AGENTS.md ระบุว่า Chart time (IUX) คือ UTC+6
    # และ Python MT5 API รับ/ส่งเวลาเป็น BKK UTC+7 ได้เลย
    # เราจะถือว่า ts ที่ดึงมาจาก MT5 นั้นสามารถแปลงโดยตรงเป็น datetime แล้วปรับ timezone
    return datetime.fromtimestamp(ts, tz=BKK)

def run_backtest(days, tf_input, sid_target, compound_pct=0.0, start_balance=1000.0):
    if not connect_mt5():
        print("❌ ไม่สามารถเชื่อมต่อ MT5 ได้")
        sys.exit(1)

    # Timeframes to test
    tfs = [tf_input] if tf_input.lower() != "all" else ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]
    
    # กำหนดวันที่สิ้นสุดและเริ่มต้น (เวลา BKK)
    end_time = datetime.now(BKK)
    start_time = end_time - timedelta(days=days)

    print(f"🔄 เริ่มต้น Backtest กลยุทธ์ {sid_target}")
    print(f"📅 ช่วงเวลา: {start_time.strftime('%Y-%m-%d %H:%M')} ถึง {end_time.strftime('%Y-%m-%d %H:%M')} BKK")
    print("-" * 60)

    # Dictionary เก็บสถิติแยกราย TF
    stats = {tf: {"trades": 0, "win": 0, "loss": 0, "pnl": 0.0, "fav_signal": {}} for tf in tfs}
    
    # เปิดโมดูลทดสอบ (ต้องจำลองให้ strategy20 ทำงาน)
    # เราจะจำลองการทำงานโดยดึงแท่งเทียนมาทีละชุด
    import strategy20
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), "strategy", "s20.5"))
    import strategy20_5
    import strategy20_6

    # ปิดการรัน strategy อื่น
    config.S20_ENABLED = True
    config.S20_5_ENABLED = False
    config.S20_6_FVG_ENABLED = (str(sid_target) == "20.6")

    symbol = config.SYMBOL
    contract_size = 100  # สมมติว่าเทรด XAUUSD 1 lot = 100 oz

    for tf in tfs:
        balance = start_balance
        mt5_tf = getattr(mt5, f"TIMEFRAME_{tf}", None)
        if not mt5_tf:
            print(f"⚠️ ไม่รู้จัก Timeframe: {tf}")
            continue

        # ดึงข้อมูลรวดเดียว
        rates = mt5.copy_rates_range(symbol, mt5_tf, start_time, end_time)
        if rates is None or len(rates) < 100:
            print(f"⚠️ ข้อมูลไม่พอสำหรับ TF {tf}")
            continue

        # จำลองการเดินของเวลาทีละแท่ง (เริ่มจาก index 100)
        # เนื่องจาก M1 จะใช้เวลาประมวลผลนานมาก เราจะจำลองการเจอ FVG 
        for i in range(100, len(rates)):
            # ส่งข้อมูลไปทดสอบ
            # _find_fvg_retest_models จะถูกเรียกผ่าน strategy_20(tf, window_rates, ...)
            window_rates = rates[i-50:i]
            
            # เราสามารถเขียนตัวจำลองการประมวลผลโดยเรียกใช้ฟังก์ชันหลัก หรือ ฟังก์ชันย่อยโดยตรง
            # เพื่อความแม่นยำและรวดเร็ว เราจะจำลองผลที่ได้จากฟังก์ชัน:
            # signature: def strategy_20(rates, tf="M5", dt_bkk=None)
            dt_bkk = mt5_ts_to_bkk(window_rates[-1]['time'])
            if str(sid_target) == "20.5":
                res = strategy20_5.strategy_20_5(window_rates, tf, dt_bkk)
            elif str(sid_target) == "20.6":
                res = strategy20_6.strategy_20_6(window_rates, tf, dt_bkk)
            else:
                res = strategy20.strategy_20(window_rates, tf, dt_bkk)
            
            if res and str(res.get("sid")) == str(sid_target) and res.get("signal") in ("BUY", "SELL"):
                # มีจุดเข้าเทรด
                signal = res.get("signal")
                entry_price = res.get("entry")
                sl = res.get("sl")
                tp = res.get("tp")
                
                if compound_pct > 0 and abs(entry_price - sl) > 0:
                    risk_amt = balance * (compound_pct / 100.0)
                    volume = risk_amt / (abs(entry_price - sl) * contract_size)
                    volume = max(0.01, round(volume, 2))
                    if volume > 50.0: volume = 50.0
                else:
                    volume = 0.01

                # จำลองการชน TP / SL
                # ค้นหาอนาคต 100 แท่ง (หรือจนกว่าจะชน)
                hit_tp = False
                hit_sl = False
                filled = False
                pnl = 0.0
                
                for j in range(i, min(i+100, len(rates))):
                    future_bar = rates[j]
                    high = future_bar["high"]
                    low = future_bar["low"]
                    
                    if signal == "BUY":
                        if not filled:
                            if high >= tp:
                                break # Cancel order if it hits TP before filling
                            if low <= entry_price:
                                filled = True
                        
                        if filled:
                            if low <= sl:
                                hit_sl = True
                                pnl = (sl - entry_price) * contract_size * volume
                                break
                            if high >= tp:
                                hit_tp = True
                                pnl = (tp - entry_price) * contract_size * volume
                                break
                    elif signal == "SELL":
                        if not filled:
                            if low <= tp:
                                break # Cancel order if it hits TP before filling
                            if high >= entry_price:
                                filled = True
                        if filled:
                            if high >= sl:
                                hit_sl = True
                                pnl = (entry_price - sl) * contract_size * volume
                                break
                            if low <= tp:
                                hit_tp = True
                                pnl = (entry_price - tp) * contract_size * volume
                                break
                
                if not filled:
                    continue  # ไม่ถูกเกี่ยวออเดอร์ในระยะเวลาที่กำหนด ยกเลิก

                stats[tf]["trades"] += 1
                stats[tf]["fav_signal"][signal] = stats[tf]["fav_signal"].get(signal, 0) + 1
                
                if hit_tp:
                    stats[tf]["win"] += 1
                    stats[tf]["pnl"] += pnl
                    balance += pnl
                elif hit_sl:
                    stats[tf]["loss"] += 1
                    stats[tf]["pnl"] += pnl
                    balance += pnl
                else:
                    # ปิดสิ้นงวด
                    close_price = rates[min(i+99, len(rates)-1)]["close"]
                    if signal == "BUY":
                        pnl = (close_price - entry_price) * contract_size * volume
                    else:
                        pnl = (entry_price - close_price) * contract_size * volume
                        
                    if pnl > 0:
                        stats[tf]["win"] += 1
                    else:
                        stats[tf]["loss"] += 1
                    stats[tf]["pnl"] += pnl
                    balance += pnl

    # ปริ้นตารางผลลัพธ์
    print("\n| กรอบเวลา (Timeframe) | จำนวนการเข้าเทรดทั้งหมด (Trades) | เคสที่ชนะ (Win) | เคสที่แพ้ (Loss) | อัตราแพ้ชนะ (Win Rate %) | แนวราคา/ระดับสัญญาณเทคนิคอลที่เข้าบ่อยที่สุด | ผลรวมกำไรขาดทุนสุทธิ (Net P&L ($)) |")
    print("|---|---|---|---|---|---|---|")
    
    total_trades = 0
    total_win = 0
    total_loss = 0
    total_pnl = 0.0
    
    for tf in tfs:
        st = stats[tf]
        trades = st["trades"]
        win = st["win"]
        loss = st["loss"]
        pnl = st["pnl"]
        
        total_trades += trades
        total_win += win
        total_loss += loss
        total_pnl += pnl
        
        win_rate = (win / trades * 100) if trades > 0 else 0
        fav_sig = max(st["fav_signal"], key=st["fav_signal"].get) if st["fav_signal"] else "-"
        
        print(f"| **{tf}** | {trades} | {win} | {loss} | {win_rate:.2f}% | {fav_sig} | {pnl:.2f} |")
        
    total_win_rate = (total_win / total_trades * 100) if total_trades > 0 else 0
    print(f"| **สรุปรวมทุก TF** | {total_trades} | {total_win} | {total_loss} | {total_win_rate:.2f}% | - | {total_pnl:.2f} |")
    
    mt5.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest Runner for MT5 Custom Strategies")
    parser.add_argument("--days", type=int, default=30, help="จำนวนวันย้อนหลังที่ต้องการรัน")
    parser.add_argument("--tf", type=str, default="all", help="กรอบเวลา (เช่น M1, M5, H1, หรือ all)")
    parser.add_argument("--sid", type=str, required=True, help="รหัสกลยุทธ์ท่าย่อยเป้าหมาย (เช่น 20.6)")
    parser.add_argument("--compound", type=float, default=0.0, help="เปอร์เซ็นต์ความเสี่ยงสำหรับการทบต้น (เช่น 2.0) ค่า default 0 = ไม่ใช้")
    parser.add_argument("--balance", type=float, default=1000.0, help="ทุนเริ่มต้นสำหรับแต่ละ TF")
    
    args = parser.parse_args()
    run_backtest(args.days, args.tf, args.sid, compound_pct=args.compound, start_balance=args.balance)
