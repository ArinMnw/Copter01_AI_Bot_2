"""
sim_ptc.py — Simulate PENDING_TREND_CHECK (1 round) impact on P&L
─────────────────────────────────────────────────────────────────
Logic:
  สำหรับแต่ละ limit order ที่ fill แล้วปิด (skip sid 9/10/14/15):
    1. ดึง HHLL ณ เวลาที่ order สร้าง
    2. คำนวณ trend (BULL/BEAR/SIDEWAY) จาก structure
    3. ถ้า trend ไม่อนุญาต signal → pending trend check จะยกเลิก order ก่อน fill
       → P&L = 0  (ประหยัด loss / พลาด win)
    4. เปรียบเทียบ Actual P&L vs Sim P&L

Usage:
    python sim_ptc.py
    python sim_ptc.py --from 26-05-2026 --to 04-06-2026
"""

import re, sys, os, io
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE     = Path(__file__).parent
_BKK     = timezone(timedelta(hours=7))
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

# ── Parse logs ────────────────────────────────────────────────────────
orders      = {}   # ticket → info
closed_info = {}   # ticket → {profit, reason}

for log_file in LOG_FILES:
    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            ts = _ts(line)
            if not ts or ts < start_dt or ts > end_dt:
                continue

            if "] ORDER_CREATED |" in line:
                tk = _fld(line, "ticket")
                if not tk or not tk.isdigit() or tk in orders:
                    continue
                try:
                    sid = int(_fld(line, "sid"))
                except Exception:
                    sid = 0
                orders[tk] = {
                    "created_ts": ts,
                    "tf":         _fld(line, "tf"),
                    "signal":     _fld(line, "signal").upper(),
                    "sid":        sid,
                    "entry":      _fld(line, "entry"),
                    "order_type": _fld(line, "order_type"),
                }

            elif "] POSITION_CLOSED |" in line:
                tk = _fld(line, "ticket")
                if not tk or not tk.isdigit():
                    continue
                try:
                    profit = float(_fld(line, "profit"))
                except ValueError:
                    profit = 0.0
                if tk not in closed_info:
                    closed_info[tk] = {
                        "profit": profit,
                        "reason": _fld(line, "reason"),
                    }

print(f"Orders found:  {len(orders)}")
print(f"Closed orders: {len(closed_info)}")

# ── MT5 + config ──────────────────────────────────────────────────────
print("\nConnecting MT5...")
import MetaTrader5 as mt5
import config as _cfg
if not _cfg.mt5_initialize(mt5):
    print("MT5 init failed:", mt5.last_error()); sys.exit(1)

from config import TF_OPTIONS, SYMBOL, TREND_FILTER_PER_TF
import hhll_swing

HHLL_LEFT     = int(getattr(_cfg, "HHLL_LEFT",     5))
HHLL_RIGHT    = int(getattr(_cfg, "HHLL_RIGHT",    5))
HHLL_LOOKBACK = int(getattr(_cfg, "HHLL_LOOKBACK", 500))
_N = HHLL_LOOKBACK + HHLL_LEFT + HHLL_RIGHT + 5
_TF_SECS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}
_PER_TF  = getattr(_cfg, "TREND_FILTER_PER_TF", {}) or {}

print(f"Symbol: {SYMBOL}")
print(f"TREND_FILTER_PER_TF: {_PER_TF}")

# ── Trend computation from historical rates ───────────────────────────
def _get_trend_at(tf: str, end: datetime):
    """คืน 'BULL' | 'BEAR' | 'SIDEWAY' | 'UNKNOWN' ณ เวลา end"""
    tf_id = TF_OPTIONS.get(tf)
    if not tf_id:
        return "UNKNOWN"
    secs    = _TF_SECS.get(tf, 60)
    end_adj = end - timedelta(seconds=secs)        # ตัด bar ปัจจุบันออก
    start_r = end_adj - timedelta(seconds=secs * _N * 2)
    rates   = mt5.copy_rates_range(SYMBOL, tf_id, start_r, end_adj)
    if rates is None or len(rates) < HHLL_LEFT + HHLL_RIGHT + 10:
        return "UNKNOWN"
    if len(rates) > _N:
        rates = rates[-_N:]

    zz = hhll_swing._build_zz(rates, HHLL_LEFT, HHLL_RIGHT)
    if len(zz) < 4:
        return "UNKNOWN"

    # classify ทุก point แล้วเรียงใหม่ newest-first
    labeled = []
    for k in range(len(zz)):
        lbl = hhll_swing._classify_pt(zz, k)
        if lbl:
            labeled.append(lbl)
    if not labeled:
        return "UNKNOWN"
    struct = list(reversed(labeled))

    h_labels = [s for s in struct if s in ("HH", "LH")]
    l_labels = [s for s in struct if s in ("HL", "LL")]
    if not h_labels or not l_labels:
        return "UNKNOWN"

    h0 = h_labels[0]
    l0 = l_labels[0]
    if h0 == "HH" and l0 == "HL":
        return "BULL"
    elif h0 == "LH" and l0 == "LL":
        return "BEAR"
    else:
        return "SIDEWAY"


def _trend_allows(tf: str, signal: str, trend: str) -> bool:
    """เช็คว่า trend อนุญาต signal ไหม (basic mode)"""
    # ถ้า TF นี้ไม่ได้เปิด trend filter → ผ่านเสมอ
    if not _PER_TF.get(tf, False):
        return True
    if trend == "BULL":
        return signal == "BUY"
    elif trend == "BEAR":
        return signal == "SELL"
    else:   # SIDEWAY / UNKNOWN → ผ่านทั้งคู่
        return True

# ── Simulate ──────────────────────────────────────────────────────────
SKIP_SIDS = {9, 10, 14, 15}
print("\nRunning simulation...")
print("=" * 75)

results = []

for tk, info in sorted(orders.items(), key=lambda x: x[1]["created_ts"]):
    ci = closed_info.get(tk)
    if not ci:
        continue   # ยังไม่ปิด

    actual_profit = ci["profit"]
    sid           = info["sid"]
    signal        = info["signal"]
    tf            = info["tf"]
    order_type    = info.get("order_type", "").upper()

    # skip market orders และ sids ยกเว้น
    if sid in SKIP_SIDS or "MARKET" in order_type:
        continue
    if signal not in ("BUY", "SELL"):
        continue

    ts_str = info["created_ts"].strftime("%d-%m %H:%M")

    # ดึง trend ณ เวลาสร้าง order
    trend = _get_trend_at(tf, info["created_ts"])
    allowed = _trend_allows(tf, signal, trend)

    if not allowed:
        # PTC would cancel → P&L = 0
        diff = -actual_profit
        tag  = "SAVE" if actual_profit < 0 else "MISS"
        icon = "🚫" if actual_profit < 0 else "⚠️"
        print(f"{icon} [{ts_str}] #{tk} {tf} {signal:<5} sid={sid:>2} | trend={trend:<8} | actual={actual_profit:+.2f} sim=+0.00 diff={diff:+.2f} | {tag}")
        results.append({"tk": tk, "ts": ts_str, "tf": tf, "signal": signal, "sid": sid,
                        "actual": actual_profit, "sim": 0.0, "diff": diff,
                        "blocked": True, "tag": tag, "trend": trend})
    else:
        # ผ่าน → order ปกติ
        print(f"🟢 [{ts_str}] #{tk} {tf} {signal:<5} sid={sid:>2} | trend={trend:<8} | actual={actual_profit:+.2f} diff=+0.00 | PASS")
        results.append({"tk": tk, "ts": ts_str, "tf": tf, "signal": signal, "sid": sid,
                        "actual": actual_profit, "sim": actual_profit, "diff": 0.0,
                        "blocked": False, "tag": "PASS", "trend": trend})

mt5.shutdown()

# ── Summary ───────────────────────────────────────────────────────────
print("\n" + "=" * 75)
total   = len(results)
blocked = [r for r in results if r["blocked"]]
passed  = [r for r in results if not r["blocked"]]
saves   = [r for r in blocked if r["tag"] == "SAVE"]
misses  = [r for r in blocked if r["tag"] == "MISS"]

actual_pnl = sum(r["actual"] for r in results)
sim_pnl    = sum(r["sim"]    for r in results)
diff_pnl   = sim_pnl - actual_pnl

loss_avoided  = sum(abs(r["actual"]) for r in saves)
profit_missed = sum(r["actual"]      for r in misses)

print(f"\n📊 Simulation: PENDING_TREND_CHECK (1R) — {START_STR} → {end_dt.strftime('%d-%m-%Y')}")
print(f"   Total eligible orders : {total}")
print(f"   PTC blocked           : {len(blocked)}  (SAVE: {len(saves)}  MISS: {len(misses)})")
print(f"   PTC passed            : {len(passed)}")
print(f"\n   Actual P&L : ${actual_pnl:>10.2f}")
print(f"   Sim P&L    : ${sim_pnl:>10.2f}")
print(f"   Diff       : ${diff_pnl:>+10.2f}  {'↑ ดีขึ้น' if diff_pnl > 0 else '↓ แย่ลง'}")
print(f"\n🚫 Blocked detail:")
print(f"   Loss avoided  : ${loss_avoided:>8.2f}  ({len(saves)} orders)")
print(f"   Profit missed : ${profit_missed:>8.2f}  ({len(misses)} orders)")

# แยกตาม TF
print(f"\n📋 แยกตาม TF (blocked only):")
tf_stats: dict = {}
for r in blocked:
    tf_stats.setdefault(r["tf"], {"save": 0, "miss": 0, "save_amt": 0.0, "miss_amt": 0.0})
    if r["tag"] == "SAVE":
        tf_stats[r["tf"]]["save"] += 1
        tf_stats[r["tf"]]["save_amt"] += abs(r["actual"])
    else:
        tf_stats[r["tf"]]["miss"] += 1
        tf_stats[r["tf"]]["miss_amt"] += r["actual"]
for tf_k, v in sorted(tf_stats.items()):
    net = v["save_amt"] - v["miss_amt"]
    print(f"   {tf_k:<5} SAVE {v['save']:>3} (${v['save_amt']:>7.2f})  MISS {v['miss']:>3} (${v['miss_amt']:>7.2f})  net={net:>+8.2f}")

# Top saves / misses
if saves:
    print(f"\n   Top SAVE:")
    for r in sorted(saves, key=lambda x: x["actual"])[:10]:
        print(f"   💰 [{r['ts']}] #{r['tk']} {r['tf']} {r['signal']} sid={r['sid']} trend={r['trend']} actual={r['actual']:+.2f}")
if misses:
    print(f"\n   Top MISS:")
    for r in sorted(misses, key=lambda x: x["actual"], reverse=True)[:10]:
        print(f"   ❌ [{r['ts']}] #{r['tk']} {r['tf']} {r['signal']} sid={r['sid']} trend={r['trend']} actual={r['actual']:+.2f}")

print("\nDone.")
