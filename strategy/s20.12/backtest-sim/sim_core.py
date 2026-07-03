"""
sim_core.py — S20.12 simulation engine

ไฟล์กลางที่ backtest_S20_12_runner_mt5.py และ supervisor_s20_12.py ใช้ร่วมกัน
ไม่มี MT5 init/shutdown และไม่มี config mutation ที่ top-level
"""

import os
import sys
from datetime import datetime, timedelta

import pandas as pd

_script_dir   = os.path.dirname(os.path.abspath(__file__))
_strategy_dir = os.path.dirname(_script_dir)
_root_dir     = os.path.dirname(os.path.dirname(_strategy_dir))

for _p in (_strategy_dir, _root_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import MetaTrader5 as mt5
import config
from config import mt5_ts_to_bkk
from strategy20_12 import strategy_20_12

_OUT_CSV = os.path.join(_script_dir, "..", "excel", "s20_12_sim_trades.csv")


def run_sim(symbol: str, start_dt_bkk: datetime, end_dt_bkk=None,
            tf: str = "all", compound: float = 2.0) -> pd.DataFrame:
    """
    รัน S20.12 simulation และบันทึก s20_12_sim_trades.csv

    ข้อกำหนด: MT5 ต้อง initialize ไว้แล้วก่อนเรียก (ไม่เรียก init/shutdown ภายใน)

    Returns:
        pd.DataFrame ของ SIM trades ที่บันทึก (empty DataFrame ถ้าไม่มี trade)
    """
    info = mt5.symbol_info(symbol)
    if not info:
        print(f"Symbol {symbol} not found")
        return pd.DataFrame()

    spread        = info.spread * info.point
    contract_size = info.trade_contract_size if info.trade_contract_size > 0 else 100.0

    all_tfs = {
        "M1":  mt5.TIMEFRAME_M1,
        "M5":  mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1":  mt5.TIMEFRAME_H1,
        "H4":  mt5.TIMEFRAME_H4,
        "H12": mt5.TIMEFRAME_H12,
        "D1":  mt5.TIMEFRAME_D1,
    }
    if tf == "all":
        tfs = all_tfs
    else:
        keys = [k.strip() for k in tf.strip("[]").split(",")]
        tfs  = {k: all_tfs[k] for k in keys if k in all_tfs}
        if not tfs:
            raise ValueError(f"ไม่รู้จัก tf: {tf!r}. ใช้ได้: {list(all_tfs)}")

    if end_dt_bkk is not None:
        end_time     = end_dt_bkk + timedelta(hours=1)
        end_time_bkk = end_dt_bkk
    else:
        end_time     = datetime.now() + timedelta(hours=1)
        end_time_bkk = datetime.now()

    start_time     = start_dt_bkk + timedelta(hours=1)
    start_time_bkk = start_dt_bkk
    days_label     = (f"{start_dt_bkk.strftime('%d-%m-%Y %H:%M')} ถึง "
                      f"{end_dt_bkk.strftime('%d-%m-%Y %H:%M') if end_dt_bkk else 'ปัจจุบัน'}")
    risk_pct = compound / 100.0

    print(f"\n--- Running Backtest S20.12 for {days_label} ---")

    candidates = []

    for tf_name, tf_code in tfs.items():
        lookback_days_needed = {
            "M1": 1, "M5": 1, "M15": 2, "M30": 3,
            "H1": 5, "H4": 20, "H12": 60, "D1": 120
        }.get(tf_name, 5)

        fetch_start = start_time - timedelta(days=lookback_days_needed)
        rates = mt5.copy_rates_range(symbol, tf_code, fetch_start, end_time)
        if rates is None or len(rates) < 50:
            continue

        # ไม่ skip ไปรอ trade ก่อนหน้าปิดอีกต่อไป — เช็ค signal ทุกแท่ง เพื่อจำลองว่า live bot
        # ยิงออเดอร์ซ้ำได้หลายไม้พร้อมกันต่อ TF เดียวกัน (เช่น sweep ต่อเนื่องหลายแท่งติด)
        # ไม่ใช่แค่ทีละไม้ต่อ TF แบบเดิม — เก็บแค่ raw shape ก่อน ยังไม่คิด lot/compounding
        # (คิดทีหลังตอน event-driven balance simulation รวมทุก TF ตามลำดับเวลาจริง)
        # หมายเหตุ: เริ่ม loop ที่ 20 (ขั้นต่ำที่ strategy เองต้องการ) ไม่ใช่ 100 — TF ใหญ่ (H1/H4)
        # ตอนใช้ --start ช่วงแคบๆ อาจได้ rates รวมทั้งก้อนไม่ถึง 100 แท่ง ทำให้ range(100, len(rates))
        # ว่างเปล่าและไม่มีทาง detect signal ได้เลยแม้แต่ตัวเดียว (เจอเคสจริง: H4/H1 = 0 เสมอ)
        for i in range(20, len(rates)):
            # หมายเหตุ: ห้ามกรองจากเวลาแท่งอ้างอิง (rates[i]) แล้ว continue ตรงนี้ — TF ใหญ่
            # (H1/H4) แท่งอ้างอิงอาจปิดไปนานแล้วก่อน start_time_bkk แต่ order จริงเพิ่งเปิดใน
            # ช่วงที่ขอ (เจอเคสจริง: H4 แท่งอ้างอิงปิด 14:00 แต่ order เปิดจริง 18:13 ซึ่งอยู่ใน
            # ช่วง --start ที่ขอ) ต้องกรองด้วย open_dt (เวลาเปิดจริง) ทีหลังแทน ดูด้านล่าง
            if i % 5000 == 0:
                print(f"  [{tf_name}] Processing bar {i}/{len(rates)}...")

            # ATR ใช้ Wilder's RMA (calc_atr) ที่ผลลัพธ์ขึ้นกับขนาด window ทั้งก้อน (ไม่ใช่แค่
            # 14 แท่งสุดท้าย) — ต้องใช้ lookback เท่ากับที่ live scanner ใช้จริง (TF_LOOKBACK+6)
            # ไม่งั้น ATR จะเพี้ยนจาก live ทำให้ SL/TP (ที่คำนวณจาก atr) ต่างกันได้ทั้งที่
            # entry ตรงกัน (เจอจาก ticket 555402265 — entry/sl ตรง แต่ tp ต่างกันมาก)
            live_lookback = config.TF_LOOKBACK.get(tf_name, 200) + 6
            window_rates  = rates[max(0, i - live_lookback):i + 1]
            res = strategy_20_12(window_rates, tf_name)

            if not (res and res.get("signal") in ("BUY", "SELL")):
                continue

            sig     = res["signal"]
            entry   = res["entry"]
            sl      = res["sl"]
            tp      = res["tp"]
            pattern = res["pattern"]
            sl_dist = abs(entry - sl) or 1.0

            # เข้า order ทันทีแบบ market (ไม่รอ limit fill): pattern confirm ตอนแท่ง i ปิด
            # (c_curr=rates[-1]=window[i] หลังตัด lag แล้ว) → ถือว่าเปิด order ทันที ที่ entry
            # ที่ strategy คำนวณไว้ แล้วไล่หา SL/TP จากแท่งถัดไป (i+1) เป็นต้นไป
            trade_result  = None
            close_bar_idx = None
            for j in range(i + 1, min(i + 2000, len(rates))):
                c = rates[j]
                if sig == "BUY":
                    # BUY SL: MT5 ใช้ BID ≤ SL → bar low (bid) ≤ sl ✓
                    if c['low'] <= sl:
                        trade_result  = "LOSS"
                        exec_price    = sl - spread
                        pnl_per_lot   = -(entry - exec_price) * contract_size
                        close_bar_idx = j
                        break
                    # BUY TP: MT5 ใช้ BID ≥ TP → bar high (bid) ≥ tp ✓
                    elif c['high'] >= tp:
                        trade_result  = "WIN"
                        exec_price    = tp - spread
                        pnl_per_lot   = (exec_price - entry) * contract_size
                        close_bar_idx = j
                        break
                else:  # SELL
                    # SELL SL: MT5 ใช้ ASK ≥ SL → bar high (bid) + spread ≥ sl
                    # ถ้าไม่บวก spread backtest จะ miss SL ที่ MT5 trigger ได้แล้ว
                    # (bid_high อยู่ระหว่าง sl-spread กับ sl แต่ ask ข้าม sl แล้ว)
                    if c['high'] + spread >= sl:
                        trade_result  = "LOSS"
                        exec_price    = sl + spread
                        pnl_per_lot   = -(exec_price - entry) * contract_size
                        close_bar_idx = j
                        break
                    # SELL TP: MT5 ใช้ BID ≤ TP → bar low (bid) ≤ tp ✓
                    elif c['low'] <= tp:
                        trade_result  = "WIN"
                        exec_price    = tp + spread
                        pnl_per_lot   = (entry - exec_price) * contract_size
                        close_bar_idx = j
                        break

            if not trade_result:
                continue

            # rates[i]['time'] คือเวลา "เปิด" ของแท่งสัญญาณ แต่ order จริงถูกสร้าง
            # ตอนแท่งนั้น "ปิด" (=เวลาเปิดของแท่งถัดไป) ต้องใช้ rates[i+1] ไม่งั้น
            # เวลาที่โชว์จะช้ากว่าจริงไป 1 ความยาวแท่งเสมอ (เทียบ ORDER_CREATED จริง)
            open_dt = mt5_ts_to_bkk(rates[i + 1]['time'])
            # กรองด้วยเวลาเปิดจริง (ไม่ใช่เวลาแท่งอ้างอิง) — TF ใหญ่แท่งอ้างอิงอาจปิด
            # ก่อน start_time_bkk นานแล้ว แต่ order เปิดจริงอยู่ในช่วงที่ขอได้
            _open_naive = open_dt.replace(tzinfo=None)
            if _open_naive < start_time_bkk or _open_naive > end_time_bkk:
                continue

            close_dt = mt5_ts_to_bkk(rates[close_bar_idx]['time'])
            candidates.append({
                "open_dt":     open_dt,
                "close_dt":    close_dt,
                "tf":          tf_name,
                "sig":         sig,
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     pattern,
                "sl_dist":     sl_dist,
                "pnl_per_lot": pnl_per_lot,
                "reason":      "TP" if trade_result == "WIN" else "SL",
            })

    # ── Event-driven portfolio balance simulation ──────────────────────
    # รวมทุก TF มาเรียงตามเวลาเปิดจริง แล้วเดิน balance ทีละ event (open/close)
    # ตามลำดับเวลาจริง ไม่ใช่ตามลำดับที่ตรวจเจอ signal หรือประมวลผลทีละ TF จบก่อน
    # (เดิม balance กระโดดไม่ stack ต่อเนื่อง เพราะ trade ที่เปิดคาบเกี่ยวกันข้าม TF/ข้ามไม้
    # ถูกอัปเดตผิดลำดับเวลา) เริ่มต้นด้วย balance = $1000 เสมอ
    balance = 1000.0
    candidates.sort(key=lambda c: c["open_dt"])
    open_positions = []

    def _close_due(now_dt):
        nonlocal balance
        due = sorted([c for c in open_positions if c["close_dt"] <= now_dt],
                     key=lambda c: c["close_dt"])
        for c in due:
            actual_pnl        = c["pnl_per_lot"] * c["lot"]
            balance           += actual_pnl
            c["actual_pnl"]   = actual_pnl
            c["balance_after"] = balance
            open_positions.remove(c)

    for cand in candidates:
        _close_due(cand["open_dt"])
        risk_amt    = balance * risk_pct
        cand["lot"] = max(0.01, round(risk_amt / (cand["sl_dist"] * contract_size), 2))
        open_positions.append(cand)

    # ปิดไม้ที่เหลือค้างอยู่ทั้งหมดตามลำดับเวลาปิดจริง
    for c in sorted(list(open_positions), key=lambda c: c["close_dt"]):
        actual_pnl        = c["pnl_per_lot"] * c["lot"]
        balance           += actual_pnl
        c["actual_pnl"]   = actual_pnl
        c["balance_after"] = balance
        open_positions.remove(c)

    # ── พิมพ์ตาราง per-TF ──
    results = []
    for tf_name in tfs:
        tf_cands = [c for c in candidates if c["tf"] == tf_name]
        tr  = len(tf_cands)
        w   = sum(1 for c in tf_cands if c["reason"] == "TP")
        wr  = (w / tr * 100.0) if tr > 0 else 0.0
        net = sum(c["actual_pnl"] for c in tf_cands)
        pat_count    = {}
        for c in tf_cands:
            pat_count[c["pattern"]] = pat_count.get(c["pattern"], 0) + 1
        most_pattern = max(pat_count, key=pat_count.get) if pat_count else "-"
        results.append((tf_name, tr, w, tr - w, wr, most_pattern, net))

    print(f"\n| กรอบเวลา (Timeframe) | จำนวนการเข้าเทรดทั้งหมด (Trades) | เคสที่ชนะ (Win) | เคสที่แพ้ (Loss) | อัตราแพ้ชนะ (Win Rate %) | แนวราคา/ระดับสัญญาณเทคนิคอลที่เข้าบ่อยที่สุด | ผลรวมกำไรขาดทุนสุทธิ (Net P&L ($)) |")
    print(f"|---|---|---|---|---|---|---|")
    total_trades = total_wins = total_losses = 0
    total_net = 0.0
    for tf_name, tr, w, l, wr, pat, net in results:
        print(f"| **{tf_name}** | {tr} | {w} | {l} | {wr:.1f}% | {pat} | {net:,.2f} |")
        total_trades += tr; total_wins += w; total_losses += l; total_net += net
    total_wr = (total_wins / total_trades * 100.0) if total_trades > 0 else 0.0
    print(f"| **สรุปรวมทุก TF** | {total_trades} | {total_wins} | {total_losses} | {total_wr:.1f}% | - | {total_net:,.2f} |")
    print(f"💰 Balance เริ่มต้น: $1,000.00 | Balance สุดท้าย: ${balance:,.2f}")

    if not candidates:
        return pd.DataFrame()

    sim_trades = [{
        "Time (BKK)": c["open_dt"].strftime('%Y-%m-%d %H:%M:%S'),
        "Close Time": c["close_dt"].strftime('%Y-%m-%d %H:%M:%S'),
        "TF":      c["tf"],
        "Type":    c["sig"],
        "Entry":   f"{c['entry']:.2f}",
        "SL":      f"{c['sl']:.2f}",
        "TP":      f"{c['tp']:.2f}",
        "Lot":     f"{c['lot']:.2f}",
        "P&L":     f"{c['actual_pnl']:.2f}",
        "Balance": f"{c['balance_after']:.2f}",
        "Reason":  c["reason"],
    } for c in candidates]

    df_sim = pd.DataFrame(sim_trades)
    df_sim["Time (BKK)"] = pd.to_datetime(df_sim["Time (BKK)"])
    df_sim = df_sim.sort_values("Time (BKK)").reset_index(drop=True)
    os.makedirs(os.path.dirname(_OUT_CSV), exist_ok=True)
    df_sim.to_csv(_OUT_CSV, index=False)
    print(f"💾 บันทึกประวัติออเดอร์จำลองไว้ที่: {_OUT_CSV}")
    return df_sim
