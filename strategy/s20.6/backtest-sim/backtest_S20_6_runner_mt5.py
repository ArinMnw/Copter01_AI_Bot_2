import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5

import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# นำเข้าโมดูลและ config ของระบบ
import config
from mt5_utils import connect_mt5, TF_SECONDS_MAP

# ฟังก์ชันแปลงเวลาจาก Timezone ของระบบ (BKK) ให้เป็นเวลาแบบ MT5 (ถ้าจำเป็น)
BKK = timezone(timedelta(hours=7))

# ดึงข้อมูลจาก AGENTS.md:
# BKK_time = chart_time + 1 hour -> ดังนั้นเวลาชาร์ต (UTC+6) คือ BKK - 1
def mt5_ts_to_bkk(ts):
    return datetime.fromtimestamp(ts, tz=BKK)

def run_backtest(days, tf_input, sid_target, compound_pct=0.0, start_balance=1000.0):
    if not connect_mt5():
        print("❌ ไม่สามารถเชื่อมต่อ MT5 ได้")
        sys.exit(1)

    tfs = [tf_input] if tf_input.lower() != "all" else ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]
    
    end_time = datetime.now(BKK)
    start_time = end_time - timedelta(days=days)

    print(f"🔄 เริ่มต้น Backtest กลยุทธ์ {sid_target} (FVG Retest Models)")
    print(f"📅 ช่วงเวลา: {start_time.strftime('%Y-%m-%d %H:%M')} ถึง {end_time.strftime('%Y-%m-%d %H:%M')} BKK")
    print("-" * 60)

    stats = {tf: {"trades": 0, "win": 0, "loss": 0, "pnl": 0.0, "fav_signal": {}} for tf in tfs}
    sim_trades = []
    
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    import strategy20_6

    config.S20_ENABLED = True
    config.S20_5_ENABLED = False
    config.S20_6_FVG_ENABLED = True

    symbol = config.SYMBOL
    contract_size = 100
    spread = 3.0 # จำลอง Spread 3 จุด
    commission = 0.5 # หัก Commission

    for tf in tfs:
        balance = start_balance
        mt5_tf = getattr(mt5, f"TIMEFRAME_{tf}", None)
        if not mt5_tf:
            print(f"⚠️ ไม่รู้จัก Timeframe: {tf}")
            continue

        rates = mt5.copy_rates_range(symbol, mt5_tf, start_time, end_time)
        if rates is None or len(rates) < 100:
            print(f"⚠️ ข้อมูลไม่พอสำหรับ TF {tf}")
            continue

        for i in range(100, len(rates)):
            window_rates = rates[i-50:i]
            dt_bkk = mt5_ts_to_bkk(window_rates[-1]['time'])
            
            res = strategy20_6.strategy_20_6(window_rates, tf, dt_bkk)
            
            if res and str(res.get("sid")) == str(sid_target) and res.get("signal") in ("BUY", "SELL"):
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

                hit_tp = False
                hit_sl = False
                filled = False
                pnl = 0.0
                
                # S20.6 Order is Market, so it fills immediately at entry_price
                # We factor in spread on entry for market order
                if signal == "BUY":
                    entry_price += (spread * 0.1)
                else:
                    entry_price -= (spread * 0.1)
                filled = True
                
                # The signal was generated on window_rates[-2] (which is rates[i-2]).
                # The entry happens at the open of the forming candle window_rates[-1] (which is rates[i-1]).
                # Therefore, we must start simulating the future from rates[i-1].
                for j in range(i-1, min(i+100, len(rates))):
                    future_bar = rates[j]
                    high = future_bar["high"]
                    low = future_bar["low"]
                    
                    if signal == "BUY":
                        if low <= sl:
                            hit_sl = True
                            pnl = (sl - entry_price) * contract_size * volume
                            break
                        if high >= tp:
                            hit_tp = True
                            pnl = (tp - entry_price) * contract_size * volume
                            break
                    elif signal == "SELL":
                        if high >= sl:
                            hit_sl = True
                            pnl = (entry_price - sl) * contract_size * volume
                            break
                        if low <= tp:
                            hit_tp = True
                            pnl = (entry_price - tp) * contract_size * volume
                            break
                
                stats[tf]["trades"] += 1
                stats[tf]["fav_signal"][signal] = stats[tf]["fav_signal"].get(signal, 0) + 1
                
                if hit_tp or hit_sl:
                    pnl -= commission * volume # หักคอม
                
                if hit_tp:
                    stats[tf]["win"] += 1
                    stats[tf]["pnl"] += pnl
                    balance += pnl
                    close_reason = "TP"
                elif hit_sl:
                    stats[tf]["loss"] += 1
                    stats[tf]["pnl"] += pnl
                    balance += pnl
                    close_reason = "SL"
                
                if hit_tp or hit_sl:
                    sim_trades.append({
                        "Time (BKK)": dt_bkk.strftime('%Y-%m-%d %H:%M:%S'),
                        "Close Time": mt5_ts_to_bkk(future_bar["time"]).strftime('%Y-%m-%d %H:%M:%S'),
                        "TF": tf,
                        "Type": signal,
                        "Entry": f"{entry_price:.2f}",
                        "SL": f"{sl:.2f}",
                        "TP": f"{tp:.2f}",
                        "P&L": f"{pnl:.2f}",
                        "Reason": close_reason
                    })
                else:
                    close_price = rates[min(i+99, len(rates)-1)]["close"]
                    if signal == "BUY":
                        pnl = (close_price - entry_price) * contract_size * volume
                    else:
                        pnl = (entry_price - close_price) * contract_size * volume
                    
                    pnl -= commission * volume
                        
                    if pnl > 0:
                        stats[tf]["win"] += 1
                    else:
                        stats[tf]["loss"] += 1
                    stats[tf]["pnl"] += pnl
                    balance += pnl

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
        
        print(f"| {tf} | {trades} | {win} | {loss} | {win_rate:.2f}% | {fav_sig} | {pnl:,.2f} |")
        
    total_win_rate = (total_win / total_trades * 100) if total_trades > 0 else 0
    print(f"| **Total** | **{total_trades}** | **{total_win}** | **{total_loss}** | **{total_win_rate:.2f}%** | - | **{total_pnl:,.2f}** |")

    # Save SIM trades to CSV
    if sim_trades:
        import pandas as pd
        df_sim = pd.DataFrame(sim_trades)
        out_csv = os.path.join(os.path.dirname(__file__), "..", "excel", "s20_6_sim_trades.csv")
        os.makedirs(os.path.dirname(out_csv), exist_ok=True)
        df_sim.to_csv(out_csv, index=False)
        print(f"💾 บันทึกประวัติออเดอร์จำลองไว้ที่: {out_csv}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest S20.6 Runner")
    parser.add_argument("--days", type=int, default=30, help="จำนวนย้อนหลัง (วัน)")
    
    parser.add_argument("--tf", type=str, default="all", help="Timeframe (e.g. M1, M5, H1, หรือ all)")
    parser.add_argument("--compound", type=float, default=2.0, help="Compound Risk % (0 = disable)")
    
    args = parser.parse_args()
    
    run_backtest(days=args.days, tf_input=args.tf, sid_target="20.6", compound_pct=args.compound)
    mt5.shutdown()
