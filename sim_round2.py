"""
sim_round2.py
─────────────────────────────────────────────────────────────────
Simulate "ถ้าตัด Round 2 ออก" (LIMIT_TREND_RECHECK_ROUNDS = 1)
เปรียบเทียบ P&L จริง (ปิดโดย round2) vs ถ้าถือต่อจนถึง TP/SL

Logic:
- อ่าน TREND_RECHECK | fill_close_round2 จาก log
- สำหรับแต่ละ ticket: หา entry/sl/tp จาก ORDER_CREATED
- ดึง M1 candles จาก MT5 หลังจากเวลาที่ round2 ปิด
- เช็คว่า TP หรือ SL โดนก่อน → คำนวณ P&L ที่ควรจะเป็น
- แสดง diff กับ P&L จริงที่ round2 ปิด

Usage:
    python sim_round2.py
    python sim_round2.py --from 26-05-2026
"""

import re, sys, os
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

_BKK = timezone(timedelta(hours=7))
LOG_FILE = BASE / "logs" / "bot.log"

START_STR = "2026-05-26"
for i, a in enumerate(sys.argv[1:]):
    if a == "--from" and i+1 < len(sys.argv)-1:
        START_STR = sys.argv[i+2]

start_dt = datetime.strptime(
    START_STR,
    "%d-%m-%Y" if len(START_STR.split("-")[0]) == 2 else "%Y-%m-%d"
).replace(tzinfo=_BKK)

print(f"Sim period: {start_dt.strftime('%d-%m-%Y')} -> today")
print("Loading logs...")

# ── Parse log ─────────────────────────────────────────────────────────

def _fld(line, key):
    m = re.search(rf'\b{re.escape(key)}=([^\s|]+)', line)
    return m.group(1) if m else ""

def _ts(line):
    m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', line)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_BKK)

# Collect data
round2_closes = {}   # ticket -> {ts, close_price, tf, signal}
orders        = {}   # ticket -> {entry, sl, tp, signal, tf, volume}
pos_closed    = {}   # ticket -> {profit, volume}

with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        ts = _ts(line)
        if not ts or ts < start_dt:
            continue

        if "TREND_RECHECK" in line and "fill_close_round2" in line:
            tk = _fld(line, "ticket")
            if tk:
                round2_closes[tk] = {
                    "ts":          ts,
                    "close_price": float(_fld(line, "close_price") or 0),
                    "tf":          _fld(line, "tf"),
                    "signal":      _fld(line, "signal"),
                    "why":         _fld(line, "why"),
                }

        elif "ORDER_CREATED" in line:
            tk = _fld(line, "ticket")
            if tk and tk not in orders:
                try:
                    vol_str = _fld(line, "scaled_volume") or _fld(line, "volume")
                    vol = float(vol_str) if vol_str else 0.04
                except ValueError:
                    vol = 0.04
                orders[tk] = {
                    "entry":  float(_fld(line, "entry") or 0),
                    "sl":     float(_fld(line, "sl") or 0),
                    "tp":     float(_fld(line, "tp") or 0),
                    "signal": _fld(line, "signal").upper(),
                    "tf":     _fld(line, "tf"),
                    "volume": vol,
                }

        elif "POSITION_CLOSED" in line:
            tk = _fld(line, "ticket")
            if tk:
                try:
                    profit = float(_fld(line, "profit"))
                except ValueError:
                    profit = 0.0
                vol_str = _fld(line, "volume")
                try:
                    vol = float(vol_str) if vol_str else None
                except ValueError:
                    vol = None
                pos_closed[tk] = {"profit": profit, "volume": vol}

print(f"Round2 closures: {len(round2_closes)}")
print(f"Orders found:    {len(orders)}")

# filter XAUUSD only (close_price roughly 4000-5000 range)
xau_round2 = {
    tk: v for tk, v in round2_closes.items()
    if 3500 < v["close_price"] < 6000
}
print(f"XAUUSD round2:   {len(xau_round2)}")

if not xau_round2:
    print("ไม่พบ round2 closures ใน XAUUSD")
    sys.exit(0)

# ── Connect MT5 ───────────────────────────────────────────────────────
print("\nConnecting MT5...")
import MetaTrader5 as mt5
import config as _cfg
if not _cfg.mt5_initialize(mt5):
    print("MT5 init failed:", mt5.last_error())
    sys.exit(1)

from config import TF_OPTIONS, SYMBOL
print(f"Symbol: {SYMBOL}")

# ── Sim each round2 close ─────────────────────────────────────────────

def sim_outcome(signal, entry, sl, tp, close_ts, volume, lookforward_h=48):
    """
    จาก close_ts เดินไปข้างหน้า 48 ชม. ใช้ M1 candles
    คืน ('TP'|'SL'|'TIMEOUT'|None, price, pnl_sim, pnl_round2)
    """
    tf_id = TF_OPTIONS.get("M1")
    if not tf_id:
        return None, 0, 0, 0

    end_ts = close_ts + timedelta(hours=lookforward_h)
    rates  = mt5.copy_rates_range(SYMBOL, tf_id, close_ts, end_ts)
    if rates is None or len(rates) == 0:
        return "TIMEOUT", 0, 0, 0

    # ดู candle แรกหลัง close_ts (skip candle ที่กำลัง form)
    for r in rates:
        hi = float(r["high"])
        lo = float(r["low"])
        if signal == "BUY":
            if lo <= sl:
                hit_price = sl
                outcome   = "SL"
                pnl_sim   = (sl - entry) * volume * 100
                return outcome, hit_price, pnl_sim
            if hi >= tp:
                hit_price = tp
                outcome   = "TP"
                pnl_sim   = (tp - entry) * volume * 100
                return outcome, hit_price, pnl_sim
        else:  # SELL
            if hi >= sl:
                hit_price = sl
                outcome   = "SL"
                pnl_sim   = (entry - sl) * volume * 100
                return outcome, hit_price, pnl_sim
            if lo <= tp:
                hit_price = tp
                outcome   = "TP"
                pnl_sim   = (entry - tp) * volume * 100
                return outcome, hit_price, pnl_sim

    return "TIMEOUT", float(rates[-1]["close"]), 0


print("\nRunning simulation (Round 2 removed)...")
print("=" * 75)

actual_total = 0.0
sim_total    = 0.0
rows         = []

for tk, r2 in sorted(xau_round2.items(), key=lambda x: x[1]["ts"]):
    o  = orders.get(tk)
    pc = pos_closed.get(tk)
    if not o:
        print(f"  [skip] #{tk} ไม่พบ ORDER_CREATED")
        continue

    entry   = o["entry"]
    sl      = o["sl"]
    tp      = o["tp"]
    signal  = r2["signal"] or o["signal"]
    vol     = pc["volume"] if (pc and pc["volume"]) else o["volume"]
    r2_px   = r2["close_price"]
    r2_ts   = r2["ts"]
    why     = r2["why"]

    # P&L จริง (closed by round2)
    if pc:
        actual_pnl = pc["profit"]
    else:
        # คำนวณจาก close_price
        if signal == "BUY":
            actual_pnl = (r2_px - entry) * vol * 100
        else:
            actual_pnl = (entry - r2_px) * vol * 100

    # P&L ถ้าถือต่อ (sim)
    outcome, hit_px, sim_pnl = sim_outcome(signal, entry, sl, tp, r2_ts, vol)

    diff = sim_pnl - actual_pnl
    actual_total += actual_pnl
    sim_total    += sim_pnl

    icon = "✅" if diff > 0 else ("❌" if diff < 0 else "─")
    outcome_str = f"{outcome}@{hit_px:.2f}" if hit_px else outcome or "?"

    row_str = (
        f"{icon} [{r2_ts.strftime('%d-%m %H:%M')}] #{tk} {r2['tf']} {signal:4s} | "
        f"entry={entry} sl={sl} tp={tp} vol={vol:.2f} | "
        f"round2={actual_pnl:+.2f} ({r2_px:.2f}) | "
        f"sim={sim_pnl:+.2f} ({outcome_str}) | "
        f"diff={diff:+.2f} | {why}"
    )
    print(row_str)
    rows.append({
        "tk": tk, "ts": r2_ts, "signal": signal, "tf": r2["tf"],
        "actual": actual_pnl, "sim": sim_pnl, "diff": diff,
        "outcome": outcome, "why": why,
    })

# ── Summary ───────────────────────────────────────────────────────────
print("\n" + "=" * 75)
diff_total = sim_total - actual_total
better = sum(1 for r in rows if r["diff"] > 0)
worse  = sum(1 for r in rows if r["diff"] < 0)
same   = sum(1 for r in rows if r["diff"] == 0)

print(f"\n[Round 1 only vs Round 1+2]  ({start_dt.strftime('%d-%m-%Y')} -> today)")
print(f"  Round2 closures:  {len(rows)}")
print(f"  ถ้าถือต่อดีกว่า:  {better} orders")
print(f"  ถ้าถือต่อแย่กว่า: {worse} orders")
print(f"  เท่าเดิม:         {same} orders")
print(f"\n  Actual P&L (round2 closed): ${actual_total:+.2f}")
print(f"  Sim P&L   (hold to TP/SL):  ${sim_total:+.2f}")
print(f"  Difference:                  ${diff_total:+.2f}  "
      f"{'-> ตัด round2 ดีกว่า!' if diff_total > 0 else '-> เก็บ round2 ดีกว่า' if diff_total < 0 else '-> เท่ากัน'}")

# TP/SL breakdown
tp_hits = [r for r in rows if r["outcome"] == "TP"]
sl_hits = [r for r in rows if r["outcome"] == "SL"]
to_hits = [r for r in rows if r["outcome"] == "TIMEOUT"]
print(f"\n  ถ้าไม่มี round2:")
print(f"    TP โดน:     {len(tp_hits)} orders  (${sum(r['sim'] for r in tp_hits):+.2f})")
print(f"    SL โดน:     {len(sl_hits)} orders  (${sum(r['sim'] for r in sl_hits):+.2f})")
print(f"    Timeout:    {len(to_hits)} orders")

mt5.shutdown()
print("\nDone.")
