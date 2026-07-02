import argparse
import sys, os
import copy
from datetime import datetime, timedelta, timezone

script_dir = os.path.dirname(os.path.abspath(__file__))
strategy_dir = os.path.dirname(script_dir) # s20.12 folder
root_dir = os.path.dirname(os.path.dirname(strategy_dir)) # project root

sys.path.insert(0, strategy_dir)
sys.path.insert(0, root_dir)

from strategy20_12 import strategy_20_12
import MetaTrader5 as mt5
from mt5_utils import connect_mt5
import config
from config import mt5_ts_to_bkk
config.S20_12_ENABLED = True
for tf in config.S20_12_TF_ENABLED:
    config.S20_12_TF_ENABLED[tf] = True

def parse_args():
    parser = argparse.ArgumentParser(description="Backtest S20.12 Candle Strength")
    parser.add_argument("--tf", type=str, default="all", help="Timeframe (e.g. M1, M5, all)")
    parser.add_argument("--symbol", type=str, default="", help="Symbol (default: profile SYMBOL)")
    parser.add_argument("--days", type=int, default=0, help="Days to backtest (0 = run multiple)")
    parser.add_argument("--compound", type=float, default=2.0, help="Risk percentage for compounding (default 2)")
    parser.add_argument("--start", type=str, default=None, help="Start time dd-MM-yyyy HH:mm (BKK) — วิ่งจากเวลานี้จนถึงปัจจุบัน (override --days)")
    return parser.parse_args()

def main():
    args = parse_args()
    
    if not connect_mt5():
        print("MT5 initialize failed")
        return

    args.symbol = config.profile_symbol(args.symbol or config.SYMBOL, mt5, set_runtime=True)
    mt5.symbol_select(args.symbol, True)
    info = mt5.symbol_info(args.symbol)
    if not info:
        print(f"Symbol {args.symbol} not found")
        return
        
    point = info.point
    spread = info.spread * point
    
    tfs = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "H12": mt5.TIMEFRAME_H12,
        "D1": mt5.TIMEFRAME_D1,
    }
    
    if args.tf != "all":
        tfs = {args.tf: tfs[args.tf]}
        
    start_dt_bkk = None
    if args.start:
        start_dt_bkk = datetime.strptime(args.start, "%d-%m-%Y %H:%M")
        days_list = ["custom"]  # sentinel, วิ่งรอบเดียวจาก --start ถึงปัจจุบัน
    elif args.days > 0:
        days_list = [args.days]
    else:
        days_list = [30, 60, 90, 120, 180]

    for days in days_list:
        sim_trades = []
        candidates = []  # raw trade shapes ทุก TF รวมกัน — ยังไม่คิด lot/compounding

        # datetime.now() = เวลา BKK จาก OS clock แต่ mt5.copy_rates_range ต้องการค่าที่ต่างจาก
        # BKK อยู่ +1h เป๊ะ (ยืนยันด้วย copy_rates_from_pos ground-truth) — ไม่ใช่ TZ_OFFSET(-7h)
        # ตามที่ backtest_auto_trade.py ใช้ เพราะ context ฐานเวลาเริ่มต้นต่างกัน
        end_time = datetime.now() + timedelta(hours=1)
        if start_dt_bkk is not None:
            start_time = start_dt_bkk + timedelta(hours=1)
            start_time_bkk = start_dt_bkk  # ใช้เทียบกับ mt5_ts_to_bkk() ในลูป (convention เดียวกับ BKK จริง)
            days_label = f"{args.start} ถึงปัจจุบัน"
        else:
            start_time = end_time - timedelta(days=days)
            start_time_bkk = datetime.now() - timedelta(days=days)
            days_label = f"{days} days"

        risk_pct = args.compound / 100.0
        contract_size = info.trade_contract_size if info.trade_contract_size > 0 else 100.0

        print(f"\n--- Running Backtest S20.12 for {days_label} ---")

        for tf_name, tf_code in tfs.items():
            lookback_days_needed = {
                "M1": 1, "M5": 1, "M15": 2, "M30": 3,
                "H1": 5, "H4": 20, "H12": 60, "D1": 120
            }.get(tf_name, 5)
            
            fetch_start = start_time - timedelta(days=lookback_days_needed)
            rates = mt5.copy_rates_range(args.symbol, tf_code, fetch_start, end_time)
            if rates is None or len(rates) < 50:
                continue
                
            # ไม่ skip ไปรอ trade ก่อนหน้าปิดอีกต่อไป — เช็ค signal ทุกแท่ง เพื่อจำลองว่า live bot
            # ยิงออเดอร์ซ้ำได้หลายไม้พร้อมกันต่อ TF เดียวกัน (เช่น sweep ต่อเนื่องหลายแท่งติด)
            # ไม่ใช่แค่ทีละไม้ต่อ TF แบบเดิม — เก็บแค่ raw shape ก่อน ยังไม่คิด lot/compounding
            # (คิดทีหลังตอน event-driven balance simulation รวมทุก TF ตามลำดับเวลาจริง)
            for i in range(100, len(rates)):
                # ใช้ mt5_ts_to_bkk() เทียบกับ start_time_bkk ตรงๆ (BKK จริงทั้งคู่) แทนการเทียบ
                # raw epoch-as-UTC กับ start_time ที่ปรับ +1h แล้ว (คนละ convention กัน ต่างได้ถึง
                # ~7 ชม. — ทำให้ --start ช่วงสั้นๆ กรองข้อมูลออกหมดจนไม่เจอไม้เลย)
                c_time_bkk = mt5_ts_to_bkk(rates[i]['time'])
                if c_time_bkk.replace(tzinfo=None) < start_time_bkk:
                    continue

                if i % 5000 == 0:
                    print(f"  [{tf_name}] Processing bar {i}/{len(rates)}...")

                # ATR ใช้ Wilder's RMA (calc_atr) ที่ผลลัพธ์ขึ้นกับขนาด window ทั้งก้อน (ไม่ใช่แค่
                # 14 แท่งสุดท้าย) — ต้องใช้ lookback เท่ากับที่ live scanner ใช้จริง (TF_LOOKBACK+6)
                # ไม่งั้น ATR จะเพี้ยนจาก live ทำให้ SL/TP (ที่คำนวณจาก atr) ต่างกันได้ทั้งที่
                # entry ตรงกัน (เจอจาก ticket 555402265 — entry/sl ตรง แต่ tp ต่างกันมาก)
                live_lookback = config.TF_LOOKBACK.get(tf_name, 200) + 6
                window_rates = rates[max(0, i-live_lookback):i+1]
                res = strategy_20_12(window_rates, tf_name)

                if res and res.get("signal") in ("BUY", "SELL"):
                    sig = res["signal"]
                    entry = res["entry"]
                    sl = res["sl"]
                    tp = res["tp"]
                    pattern = res["pattern"]

                    trade_result = None
                    sl_dist = abs(entry - sl)
                    if sl_dist == 0: sl_dist = 1.0

                    # เข้า order ทันทีแบบ market (ไม่รอ limit fill): pattern confirm ตอนแท่ง i ปิด
                    # (c_curr=rates[-1]=window[i] หลังตัด lag แล้ว) → ถือว่าเปิด order ทันที ที่ entry
                    # ที่ strategy คำนวณไว้ แล้วไล่หา SL/TP จากแท่งถัดไป (i+1) เป็นต้นไป
                    close_bar_idx = None
                    for j in range(i + 1, min(i + 2000, len(rates))):
                        c = rates[j]
                        if sig == "BUY":
                            if c['low'] <= sl:
                                trade_result = "LOSS"
                                exec_price = sl - spread
                                pnl_per_lot = -(entry - exec_price) * contract_size
                                close_bar_idx = j
                                break
                            elif c['high'] >= tp:
                                trade_result = "WIN"
                                exec_price = tp - spread
                                pnl_per_lot = (exec_price - entry) * contract_size
                                close_bar_idx = j
                                break
                        else:  # SELL
                            if c['high'] >= sl:
                                trade_result = "LOSS"
                                exec_price = sl + spread
                                pnl_per_lot = -(exec_price - entry) * contract_size
                                close_bar_idx = j
                                break
                            elif c['low'] <= tp:
                                trade_result = "WIN"
                                exec_price = tp + spread
                                pnl_per_lot = (entry - exec_price) * contract_size
                                close_bar_idx = j
                                break

                    if trade_result:
                        # rates[i]['time'] คือเวลา "เปิด" ของแท่งสัญญาณ แต่ order จริงถูกสร้าง
                        # ตอนแท่งนั้น "ปิด" (=เวลาเปิดของแท่งถัดไป) ต้องใช้ rates[i+1] ไม่งั้น
                        # เวลาที่โชว์จะช้ากว่าจริงไป 1 ความยาวแท่งเสมอ (เทียบ ORDER_CREATED จริง)
                        open_dt = mt5_ts_to_bkk(rates[i+1]['time'])
                        close_dt = mt5_ts_to_bkk(rates[close_bar_idx]['time'])
                        candidates.append({
                            "open_dt": open_dt,
                            "close_dt": close_dt,
                            "tf": tf_name,
                            "sig": sig,
                            "entry": entry,
                            "sl": sl,
                            "tp": tp,
                            "pattern": pattern,
                            "sl_dist": sl_dist,
                            "pnl_per_lot": pnl_per_lot,
                            "reason": "TP" if trade_result == "WIN" else "SL",
                        })

        # ── Event-driven portfolio balance simulation ──────────────────────
        # รวมทุก TF มาเรียงตามเวลาเปิดจริง แล้วเดิน balance ทีละ event (open/close)
        # ตามลำดับเวลาจริง ไม่ใช่ตามลำดับที่ตรวจเจอ signal หรือประมวลผลทีละ TF จบก่อน
        # (เดิม balance กระโดดไม่ stack ต่อเนื่อง เพราะ trade ที่เปิดคาบเกี่ยวกันข้าม TF/ข้ามไม้
        # ถูกอัปเดตผิดลำดับเวลา) เริ่มต้นด้วย balance = $1000 เสมอ
        balance = 1000.0
        candidates.sort(key=lambda c: c["open_dt"])
        open_positions = []  # trade ที่เปิดอยู่ ยังไม่ปิด (list of candidate dict)

        def _close_due(now_dt):
            nonlocal balance
            due = [c for c in open_positions if c["close_dt"] <= now_dt]
            due.sort(key=lambda c: c["close_dt"])
            for c in due:
                actual_pnl = c["pnl_per_lot"] * c["lot"]
                balance += actual_pnl
                c["actual_pnl"] = actual_pnl
                c["balance_after"] = balance
                open_positions.remove(c)

        for cand in candidates:
            _close_due(cand["open_dt"])
            risk_amt = balance * risk_pct
            lot = max(0.01, round(risk_amt / (cand["sl_dist"] * contract_size), 2))
            cand["lot"] = lot
            open_positions.append(cand)

        # ปิดไม้ที่เหลือค้างอยู่ทั้งหมดตามลำดับเวลาปิดจริง
        open_positions.sort(key=lambda c: c["close_dt"])
        for c in list(open_positions):
            actual_pnl = c["pnl_per_lot"] * c["lot"]
            balance += actual_pnl
            c["actual_pnl"] = actual_pnl
            c["balance_after"] = balance
            open_positions.remove(c)

        for c in candidates:
            sim_trades.append({
                "Time (BKK)": c["open_dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "Close Time": c["close_dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "TF": c["tf"],
                "Type": c["sig"],
                "Entry": f"{c['entry']:.2f}",
                "SL": f"{c['sl']:.2f}",
                "TP": f"{c['tp']:.2f}",
                "Lot": f"{c['lot']:.2f}",
                "P&L": f"{c['actual_pnl']:.2f}",
                "Balance": f"{c['balance_after']:.2f}",
                "Reason": c["reason"],
            })

        # ── สรุปตาราง per-TF จาก candidates ที่คิด lot จริงแล้ว ──
        results = []
        for tf_name in tfs:
            tf_cands = [c for c in candidates if c["tf"] == tf_name]
            tr = len(tf_cands)
            w = sum(1 for c in tf_cands if c["reason"] == "TP")
            l = tr - w
            wr = (w / tr * 100.0) if tr > 0 else 0.0
            net = sum(c["actual_pnl"] for c in tf_cands)
            pat_count = {}
            for c in tf_cands:
                pat_count[c["pattern"]] = pat_count.get(c["pattern"], 0) + 1
            most_pattern = max(pat_count, key=pat_count.get) if pat_count else "-"
            results.append((tf_name, tr, w, l, wr, most_pattern, net))

        print(f"\n| กรอบเวลา (Timeframe) | จำนวนการเข้าเทรดทั้งหมด (Trades) | เคสที่ชนะ (Win) | เคสที่แพ้ (Loss) | อัตราแพ้ชนะ (Win Rate %) | แนวราคา/ระดับสัญญาณเทคนิคอลที่เข้าบ่อยที่สุด | ผลรวมกำไรขาดทุนสุทธิ (Net P&L ($)) |")
        print(f"|---|---|---|---|---|---|---|")

        total_trades = 0
        total_wins = 0
        total_losses = 0
        total_net = 0.0

        for r in results:
            tf_name, tr, w, l, wr, pat, net = r
            print(f"| **{tf_name}** | {tr} | {w} | {l} | {wr:.1f}% | {pat} | {net:,.2f} |")
            total_trades += tr
            total_wins += w
            total_losses += l
            total_net += net

        total_wr = (total_wins / total_trades * 100.0) if total_trades > 0 else 0.0
        print(f"| **สรุปรวมทุก TF** | {total_trades} | {total_wins} | {total_losses} | {total_wr:.1f}% | - | {total_net:,.2f} |")
        print(f"💰 Balance เริ่มต้น: $1,000.00 | Balance สุดท้าย: ${balance:,.2f}")

        # Save SIM trades to CSV
        if sim_trades:
            import pandas as pd
            df_sim = pd.DataFrame(sim_trades)
            df_sim["Time (BKK)"] = pd.to_datetime(df_sim["Time (BKK)"])
            df_sim = df_sim.sort_values("Time (BKK)").reset_index(drop=True)
            out_csv = os.path.join(os.path.dirname(__file__), "..", "excel", "s20_12_sim_trades.csv")
            os.makedirs(os.path.dirname(out_csv), exist_ok=True)
            df_sim.to_csv(out_csv, index=False)
            print(f"💾 บันทึกประวัติออเดอร์จำลองไว้ที่: {out_csv}")

    mt5.shutdown()

if __name__ == "__main__":
    main()
