"""
sim_ltr_rounds.py — Simulate LIMIT_TREND_RECHECK_ROUNDS = 1 vs 2
─────────────────────────────────────────────────────────────────
Logic:
  หา orders ที่ถูกปิดโดย fill_close_round2 (XAUUSD เท่านั้น, skip sid 9/10/14/15)
  ถ้า ROUNDS=1 → ไม่มี round2 check → order ยังเปิดอยู่หลัง round2 close time
  → จำลองว่าจะโดน TP หรือ SL ก่อน (ใช้ MT5 M1 rates หลัง close_time)
  → ถ้าไม่โดนทั้งคู่ใน 48h → mark "ไม่ทราบ"

  Compare:
    Actual (ROUNDS=2) : profit ณ เวลา round2 ปิด
    Sim    (ROUNDS=1) : profit ถ้าโดน TP/SL แทน

Usage:
    python sim_ltr_rounds.py
    python sim_ltr_rounds.py --from 26-05-2026
"""

import re, sys, os, io
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE      = Path(__file__).parent
_BKK      = timezone(timedelta(hours=7))
START_STR = "26-05-2026"
END_STR   = None

for i, a in enumerate(sys.argv[1:]):
    if a == "--from" and i + 1 < len(sys.argv) - 1:
        START_STR = sys.argv[i + 2]
    if a == "--to"   and i + 1 < len(sys.argv) - 1:
        END_STR   = sys.argv[i + 2]

def _parse_dt(s):
    fmt = "%d-%m-%Y" if len(s.split("-")[0]) == 2 else "%Y-%m-%d"
    return datetime.strptime(s, fmt).replace(tzinfo=_BKK)

start_dt = _parse_dt(START_STR)
end_dt   = _parse_dt(END_STR) if END_STR else datetime.now(_BKK)
print(f"Sim period: {start_dt.strftime('%d-%m-%Y')} → {end_dt.strftime('%d-%m-%Y')}")

# ── Log files ─────────────────────────────────────────────────────────
from pathlib import Path as _Path
from log_sources import bot_log_files
LOG_FILES = [_Path(p) for p in bot_log_files(str(BASE))]
print(f"Reading {len(LOG_FILES)} log files: {[f.name for f in LOG_FILES]}")

# ── Helpers ───────────────────────────────────────────────────────────
def _fld(line, key):
    m = re.search(rf"\b{re.escape(key)}=([^\s|]+)", line)
    return m.group(1) if m else ""

def _ts(line):
    m = re.match(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", line)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_BKK)

# ── Parse: หา fill_close_round2 tickets ──────────────────────────────
# Step1: รวบ ticket ที่โดน fill_close_round2
round2_close = {}   # ticket → {ts, why}
# Step2: หา POSITION_CLOSED details
pos_closed = {}     # ticket → {profit, open_price, close_price, sl, tp, side, sid, tf, symbol, ts}

SKIP_SIDS = {"9", "10", "14", "15"}

for log_file in LOG_FILES:
    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            ts = _ts(line)
            if not ts or ts < start_dt or ts > end_dt:
                continue

            # หา round2 close events
            if "TREND_RECHECK | fill_close_round2 |" in line:
                tk = _fld(line, "ticket")
                if tk and tk.isdigit() and tk not in round2_close:
                    round2_close[tk] = {"ts": ts, "why": _fld(line, "why")}

            # หา POSITION_CLOSED
            elif "] POSITION_CLOSED |" in line and tk not in pos_closed if (tk := _fld(line, "ticket")) else False:
                pass

for log_file in LOG_FILES:
    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            ts = _ts(line)
            if not ts or ts < start_dt or ts > end_dt:
                continue
            if "] POSITION_CLOSED |" not in line:
                continue
            tk = _fld(line, "ticket")
            if not tk or not tk.isdigit() or tk in pos_closed:
                continue
            sid = _fld(line, "sid")
            sym = _fld(line, "symbol")
            try:
                profit = float(_fld(line, "profit"))
                op     = float(_fld(line, "open_price"))
                cp     = float(_fld(line, "close_price"))
                sl     = float(_fld(line, "sl"))
                tp_val = float(_fld(line, "tp"))
            except (ValueError, TypeError):
                continue
            pos_closed[tk] = {
                "profit":      profit,
                "open_price":  op,
                "close_price": cp,
                "sl":          sl,
                "tp":          tp_val,
                "side":        _fld(line, "side"),
                "sid":         sid,
                "tf":          _fld(line, "tf"),
                "symbol":      sym,
                "ts":          ts,
            }

print(f"fill_close_round2 events : {len(round2_close)}")
print(f"POSITION_CLOSED records  : {len(pos_closed)}")

# ── กรอง: XAUUSD, ไม่ skip sid ───────────────────────────────────────
eligible = {}
for tk, r2 in round2_close.items():
    pc = pos_closed.get(tk)
    if not pc:
        continue
    if pc["symbol"] and "XAU" not in pc["symbol"].upper():
        continue    # skip non-XAUUSD
    if pc["sid"] in SKIP_SIDS:
        continue
    if pc["sl"] <= 0 or pc["tp"] <= 0:
        continue
    eligible[tk] = {**pc, "round2_ts": r2["ts"], "why": r2["why"]}

print(f"Eligible (XAUUSD, not skip): {len(eligible)}")

# ── MT5 ──────────────────────────────────────────────────────────────
print("\nConnecting MT5...")
import MetaTrader5 as mt5
import config as _cfg
if not _cfg.mt5_initialize(mt5):
    print("MT5 init failed:", mt5.last_error()); sys.exit(1)

from config import TF_OPTIONS, SYMBOL
MT5_TF_M1 = TF_OPTIONS.get("M1")
LOTS_PER_UNIT = 0.01   # 1 lot = 100 oz, 0.01 lot = 1 oz → $1/pt for XAUUSD standard

def _sim_outcome(tk, d):
    """จำลองว่าถ้า round2 ไม่ปิด → โดน TP หรือ SL (หรือไม่ทราบ)
    คืน (tag, sim_profit) โดย:
      tag = "TP" | "SL" | "UNKNOWN"
      sim_profit = profit ถ้า ROUNDS=1 (ใช้ open_price ของจริง)
    """
    close_ts   = d["round2_ts"]
    actual_cp  = d["close_price"]
    op         = d["open_price"]
    sl         = d["sl"]
    tp         = d["tp"]
    side       = d["side"].upper()

    # fetch M1 rates หลัง round2 close ไป 48h
    t_from = close_ts
    t_to   = close_ts + timedelta(hours=48)
    rates  = mt5.copy_rates_range(SYMBOL, MT5_TF_M1, t_from, t_to)
    if rates is None or len(rates) == 0:
        return "UNKNOWN", 0.0

    # ตรวจทีละแท่ง: โดน SL หรือ TP ก่อน
    for bar in rates:
        h = float(bar["high"])
        l = float(bar["low"])
        if side == "BUY":
            if l <= sl:
                return "SL", d["profit"] * sl / actual_cp if actual_cp else 0.0
            if h >= tp:
                return "TP", d["profit"] * tp / actual_cp if actual_cp else 0.0
        else:  # SELL
            if h >= sl:
                return "SL", d["profit"] * sl / actual_cp if actual_cp else 0.0
            if l <= tp:
                return "TP", d["profit"] * tp / actual_cp if actual_cp else 0.0

    return "UNKNOWN", 0.0

def _calc_sim_profit(d, outcome_tag):
    """คำนวณ sim profit จาก actual profit + TP/SL ratio"""
    op  = d["open_price"]
    sl  = d["sl"]
    tp  = d["tp"]
    act = d["profit"]
    side = d["side"].upper()
    # ใช้ ratio ระยะทาง เทียบกับ actual close price
    actual_cp = d["close_price"]
    if actual_cp == 0 or op == 0:
        return 0.0
    # profit per point ≈ act / (actual_cp - op) [SELL: op - actual_cp]
    if side == "BUY":
        pt_val = act / (actual_cp - op) if abs(actual_cp - op) > 0.001 else 0
        if outcome_tag == "TP":
            return pt_val * (tp - op)
        elif outcome_tag == "SL":
            return pt_val * (sl - op)
    else:
        pt_val = act / (op - actual_cp) if abs(op - actual_cp) > 0.001 else 0
        if outcome_tag == "TP":
            return pt_val * (op - tp)
        elif outcome_tag == "SL":
            return pt_val * (op - sl)
    return 0.0

# ── Simulate ──────────────────────────────────────────────────────────
print("Running simulation...")
print("=" * 80)

results = []
for tk, d in sorted(eligible.items(), key=lambda x: x[1]["round2_ts"]):
    outcome_tag, _ = _sim_outcome(tk, d)
    sim_profit     = _calc_sim_profit(d, outcome_tag) if outcome_tag != "UNKNOWN" else 0.0
    actual_profit  = d["profit"]
    diff           = sim_profit - actual_profit

    ts_str = d["round2_ts"].strftime("%d-%m %H:%M")
    icon   = "🎯" if outcome_tag == "TP" else ("🛑" if outcome_tag == "SL" else "❓")
    trend  = "↑" if diff > 0 else ("↓" if diff < 0 else "=")
    print(f"{icon} [{ts_str}] #{tk} {d['tf']:<6} {d['side']:<5} sid={d['sid']:>2} | "
          f"actual={actual_profit:>+7.2f} sim={sim_profit:>+7.2f} diff={diff:>+7.2f} {trend} | "
          f"{outcome_tag} (why={d['why']})")

    results.append({
        "tk": tk, "ts": ts_str, "tf": d["tf"], "side": d["side"],
        "sid": d["sid"], "actual": actual_profit, "sim": sim_profit,
        "diff": diff, "outcome": outcome_tag, "why": d["why"],
    })

mt5.shutdown()

# ── Summary ───────────────────────────────────────────────────────────
print("\n" + "=" * 80)
total     = len(results)
tp_list   = [r for r in results if r["outcome"] == "TP"]
sl_list   = [r for r in results if r["outcome"] == "SL"]
unk_list  = [r for r in results if r["outcome"] == "UNKNOWN"]

# คำนวณเฉพาะที่รู้ outcome (TP หรือ SL)
known    = [r for r in results if r["outcome"] != "UNKNOWN"]
actual_k = sum(r["actual"] for r in known)
sim_k    = sum(r["sim"]    for r in known)
diff_k   = sim_k - actual_k

# รวมทั้งหมด (UNKNOWN ใช้ actual ไม่เปลี่ยน)
actual_all = sum(r["actual"] for r in results)
sim_all    = sum(r["sim"] if r["outcome"] != "UNKNOWN" else r["actual"] for r in results)
diff_all   = sim_all - actual_all

print(f"\n📊 Simulation: LIMIT_TREND_RECHECK_ROUNDS 2→1 — {START_STR} → {end_dt.strftime('%d-%m-%Y')}")
print(f"   Orders closed by round2  : {total}")
print(f"   → TP ก่อน (ROUNDS=1 ดีกว่า?)  : {len(tp_list)}")
print(f"   → SL ก่อน (ROUNDS=1 แย่กว่า?) : {len(sl_list)}")
print(f"   → ไม่ทราบ (>48h)              : {len(unk_list)}")

print(f"\n   ── Known outcomes ({len(known)} orders) ──")
print(f"   Actual P&L (ROUNDS=2) : ${actual_k:>+9.2f}")
print(f"   Sim P&L    (ROUNDS=1) : ${sim_k:>+9.2f}")
print(f"   Diff                  : ${diff_k:>+9.2f}  {'↑ ROUNDS=1 ดีกว่า' if diff_k > 0 else '↓ ROUNDS=2 ดีกว่า'}")

print(f"\n   ── All orders (UNKNOWN ใช้ actual) ──")
print(f"   Actual P&L (ROUNDS=2) : ${actual_all:>+9.2f}")
print(f"   Sim P&L    (ROUNDS=1) : ${sim_all:>+9.2f}")
print(f"   Diff                  : ${diff_all:>+9.2f}  {'↑ ROUNDS=1 ดีกว่า' if diff_all > 0 else '↓ ROUNDS=2 ดีกว่า'}")

# TF breakdown
print(f"\n   📋 แยกตาม TF:")
tf_stats: dict = {}
for r in known:
    tf_stats.setdefault(r["tf"], {"n": 0, "actual": 0.0, "sim": 0.0, "tp": 0, "sl": 0})
    tf_stats[r["tf"]]["n"] += 1
    tf_stats[r["tf"]]["actual"] += r["actual"]
    tf_stats[r["tf"]]["sim"]    += r["sim"]
    if r["outcome"] == "TP": tf_stats[r["tf"]]["tp"] += 1
    else:                     tf_stats[r["tf"]]["sl"] += 1
for tf_k, v in sorted(tf_stats.items()):
    net = v["sim"] - v["actual"]
    print(f"   {tf_k:<6} n={v['n']:>3} | TP={v['tp']:>2} SL={v['sl']:>2} | actual={v['actual']:>+8.2f} sim={v['sim']:>+8.2f} net={net:>+8.2f}")

# Top movers
better = sorted([r for r in known if r["diff"] > 0], key=lambda x: -x["diff"])[:8]
worse  = sorted([r for r in known if r["diff"] < 0], key=lambda x: x["diff"])[:8]
if better:
    print(f"\n   🟢 Top ดีขึ้นถ้า ROUNDS=1 (TP ก่อน):")
    for r in better:
        print(f"      [{r['ts']}] #{r['tk']} {r['tf']} {r['side']} sid={r['sid']} actual={r['actual']:+.2f} sim={r['sim']:+.2f} diff={r['diff']:+.2f}")
if worse:
    print(f"\n   🔴 Top แย่ลงถ้า ROUNDS=1 (SL ก่อน):")
    for r in worse:
        print(f"      [{r['ts']}] #{r['tk']} {r['tf']} {r['side']} sid={r['sid']} actual={r['actual']:+.2f} sim={r['sim']:+.2f} diff={r['diff']:+.2f}")

print("\nDone.")
