"""
sim_pd_precheck.py
──────────────────────────────────────────────────────────────────────
Simulate PD Zone pre-creation check บน orders ตั้งแต่ 26-05-2026
เปรียบเทียบ P&L จริง vs P&L ถ้ามี PD Zone pre-check

Logic:
- อ่าน ORDER_CREATED + POSITION_CLOSED จาก log ทุกไฟล์ (รวม old_logs)
- สำหรับแต่ละ order: ดึง HHLL ณ เวลาสร้าง order
- ตรวจ PD Zone: entry อยู่ถูกฝั่งไหม (Fib 38.2/61.8)
- ถ้า pre-check บล็อก → order นี้ไม่ควรเกิด
- แสดง diff กำไร/ขาดทุน

Skip sids: 9 (RSI Div), 10 (CRT), 13 (S13), 14 (Sweep RSI), 15 (VP)

Usage:
    python sim_pd_precheck.py
    python sim_pd_precheck.py --from 26-05-2026 --to 04-06-2026
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

print(f"Sim period: {start_dt.strftime('%d-%m-%Y')} -> {end_dt.strftime('%d-%m-%Y')}")

# ── Log files (oldest first, dedup by ticket) ─────────────────────────
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
                    "sl":         _fld(line, "sl"),
                    "tp":         _fld(line, "tp"),
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

print(f"Orders found: {len(orders)}")
print(f"Closed info:  {len(closed_info)}")

if not orders:
    print("ไม่พบ order ในช่วงเวลานี้")
    sys.exit(0)

# ── MT5 ──────────────────────────────────────────────────────────────
print("\nConnecting MT5...")
import MetaTrader5 as mt5
os.environ.setdefault("MT5_PATH", "C:/Program Files/MetaTrader 5 IC Markets (SC)/terminal64.exe")
if not mt5.initialize():
    print("MT5 init failed:", mt5.last_error())
    sys.exit(1)

from config import TF_OPTIONS, SYMBOL
import config as _cfg
import hhll_swing

HHLL_LEFT     = int(getattr(_cfg, "HHLL_LEFT",     5))
HHLL_RIGHT    = int(getattr(_cfg, "HHLL_RIGHT",    5))
HHLL_LOOKBACK = int(getattr(_cfg, "HHLL_LOOKBACK", 500))
print(f"Symbol: {SYMBOL}")

_TF_SECS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}
_N       = HHLL_LOOKBACK + HHLL_LEFT + HHLL_RIGHT + 5

def get_swing_hl_at(tf: str, end: datetime):
    """ดึง swing H/L ณ เวลา end"""
    tf_id = TF_OPTIONS.get(tf)
    if not tf_id:
        return None, None
    secs    = _TF_SECS.get(tf, 60)
    end_adj = end - timedelta(seconds=secs)
    start_r = end_adj - timedelta(seconds=secs * _N * 2)
    rates   = mt5.copy_rates_range(SYMBOL, tf_id, start_r, end_adj)
    if rates is None or len(rates) < HHLL_LEFT + HHLL_RIGHT + 10:
        return None, None
    if len(rates) > _N:
        rates = rates[-_N:]
    zz = hhll_swing._build_zz(rates, HHLL_LEFT, HHLL_RIGHT)
    if len(zz) < 5:
        return None, None
    sh_pt = sl_pt = None
    for k in range(len(zz) - 1, -1, -1):
        pt  = zz[k]
        lbl = hhll_swing._classify_pt(zz, k)
        if not lbl:
            continue
        if lbl in ("HH", "LH") and sh_pt is None:
            sh_pt = {"price": float(pt["price"]), "time": int(pt["time"])}
        if lbl in ("HL", "LL") and sl_pt is None:
            sl_pt = {"price": float(pt["price"]), "time": int(pt["time"])}
        if sh_pt and sl_pt:
            break
    return sh_pt, sl_pt

def _pdfiboplus_in_zone(order_price: float, signal: str,
                        h: float, l: float, sid: int = 0) -> bool:
    """True ถ้า entry อยู่ใน zone ที่ถูกต้อง (Fib 38.2/61.8)"""
    if h <= l:
        return True
    _range  = h - l
    fib_382 = l + _range * 0.382
    fib_618 = l + _range * 0.618
    if signal == "BUY":
        return order_price < fib_382
    elif signal == "SELL":
        return order_price > fib_618
    return True

# ── Simulate ──────────────────────────────────────────────────────────
SKIP_SIDS = {9, 10, 13, 14, 15}   # sids ที่ไม่ check PD zone

print("\nRunning simulation...")
print("=" * 70)

results = []   # (ticket, label, actual_profit, pd_blocked, reason_str)

for tk, info in sorted(orders.items(), key=lambda x: x[1]["created_ts"]):
    ci       = closed_info.get(tk)
    if not ci:
        continue   # ยังไม่ปิด หรือไม่มีข้อมูล

    actual_profit = ci["profit"]
    sid           = info["sid"]
    signal        = info["signal"]
    tf            = info["tf"]
    order_type    = info.get("order_type", "").upper()

    # skip market orders และ sids ที่ยกเว้น
    if sid in SKIP_SIDS or "MARKET" in order_type:
        continue

    try:
        entry = float(info["entry"])
    except Exception:
        continue

    # ดึง swing H/L ณ เวลา order create
    sh_pt, sl_pt = get_swing_hl_at(tf, info["created_ts"])
    if not sh_pt or not sl_pt:
        continue

    h = sh_pt["price"]
    l = sl_pt["price"]
    if h <= l:
        continue

    pd_ok = _pdfiboplus_in_zone(entry, signal, h, l, sid=sid)
    eq    = round((h + l) / 2, 2)

    ts_str = info["created_ts"].strftime("%d-%m %H:%M")

    if not pd_ok:
        # PD pre-check would block
        diff = -actual_profit  # ถ้า block: profit กลับทิศ (loss → +save, win → -miss)
        icon = "🚫" if actual_profit <= 0 else "⚠️"
        tag  = "SAVE" if actual_profit <= 0 else "MISS"
        reason = f"entry={entry:.2f} EQ={eq:.2f} H={h:.2f} L={l:.2f}"
        print(f"{icon} [{ts_str}] #{tk} {tf} {signal:<5} sid={sid:>2} | actual={actual_profit:+.2f} sim=+0.00 diff={diff:+.2f} | {tag} PD block — {reason}")
        results.append({"tk": tk, "ts": ts_str, "tf": tf, "signal": signal, "sid": sid,
                        "actual": actual_profit, "sim": 0.0, "diff": diff, "blocked": True, "tag": tag})
    else:
        # ผ่าน PD → order ยังเกิดตามปกติ
        print(f"🟢 [{ts_str}] #{tk} {tf} {signal:<5} sid={sid:>2} | actual={actual_profit:+.2f} sim={actual_profit:+.2f} diff=+0.00 | PD pass")
        results.append({"tk": tk, "ts": ts_str, "tf": tf, "signal": signal, "sid": sid,
                        "actual": actual_profit, "sim": actual_profit, "diff": 0.0, "blocked": False, "tag": "PASS"})

mt5.shutdown()

# ── Summary ───────────────────────────────────────────────────────────
print("\n" + "=" * 70)
total      = len(results)
blocked    = [r for r in results if r["blocked"]]
passed     = [r for r in results if not r["blocked"]]
saves      = [r for r in blocked if r["tag"] == "SAVE"]
misses     = [r for r in blocked if r["tag"] == "MISS"]

actual_pnl = sum(r["actual"] for r in results)
sim_pnl    = sum(r["sim"] for r in results)
diff_pnl   = sim_pnl - actual_pnl

loss_avoided  = sum(abs(r["actual"]) for r in saves)
profit_missed = sum(r["actual"] for r in misses)

print(f"\n📊 Simulation Summary ({START_STR} → {end_dt.strftime('%d-%m-%Y')})")
print(f"   Total orders (closed, PD-eligible): {total}")
print(f"   PD blocked:  {len(blocked)}  (SAVE: {len(saves)}  MISS: {len(misses)})")
print(f"   PD passed:   {len(passed)}")
print(f"\n   Actual P&L:  ${actual_pnl:.2f}")
print(f"   Sim P&L:     ${sim_pnl:.2f}")
print(f"   Difference:  ${diff_pnl:+.2f}  {'↑ ดีขึ้น' if diff_pnl > 0 else '↓ แย่ลง'}")
print(f"\n🚫 Blocked orders:")
print(f"   Loss avoided:  ${loss_avoided:.2f}")
print(f"   Profit missed: ${profit_missed:.2f}")

# Top saves / misses
if saves:
    print(f"\n   Top SAVE (loss ที่หลีกเลี่ยงได้):")
    for r in sorted(saves, key=lambda x: x["actual"])[:10]:
        print(f"   💰 [{r['ts']}] #{r['tk']} {r['tf']} {r['signal']} sid={r['sid']} actual={r['actual']:+.2f}")
if misses:
    print(f"\n   Top MISS (กำไรที่พลาด):")
    for r in sorted(misses, key=lambda x: x["actual"], reverse=True)[:10]:
        print(f"   ❌ [{r['ts']}] #{r['tk']} {r['tf']} {r['signal']} sid={r['sid']} actual={r['actual']:+.2f}")

print("\nDone.")
