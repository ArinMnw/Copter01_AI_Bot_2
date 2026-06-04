"""
sim_sweep_filter.py
──────────────────────────────────────────────────────────────────────
Simulate Sweep Filter บน orders ตั้งแต่ 26-05-2026 ถึงปัจจุบัน
เปรียบเทียบ P&L จริง vs P&L ถ้ามี Sweep Filter

Logic:
- อ่าน ORDER_CREATED + POSITION_CLOSED จาก log
- สำหรับแต่ละ order: ดึง HHLL data ณ เวลาสร้าง order ผ่าน MT5 history
- ตรวจ sweep state ณ เวลานั้น
- ถ้า sweep block signal → order นี้ไม่ควรเกิด → profit ที่หายไป หรือ loss ที่หลีกเลี่ยงได้
- ถ้า sweep unblock signal (แต่ trend block) → order นี้ควรเกิด → ดู actual P&L

Usage:
    python sim_sweep_filter.py
    python sim_sweep_filter.py --from 26-05-2026 --to 04-06-2026
"""

import re
import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Setup path ────────────────────────────────────────────────────────
BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

_BKK = timezone(timedelta(hours=7))

LOG_FILE  = BASE / "logs" / "bot.log"
START_STR = "2026-05-26"
END_STR   = None   # None = today

# Parse args
for i, a in enumerate(sys.argv[1:]):
    if a == "--from" and i+1 < len(sys.argv)-1:
        START_STR = sys.argv[i+2]
    if a == "--to" and i+1 < len(sys.argv)-1:
        END_STR = sys.argv[i+2]

start_dt = datetime.strptime(START_STR, "%d-%m-%Y" if "-" in START_STR and len(START_STR.split("-")[0]) == 2 else "%Y-%m-%d").replace(tzinfo=_BKK)
end_dt   = (datetime.strptime(END_STR,   "%d-%m-%Y" if END_STR and "-" in END_STR and len(END_STR.split("-")[0]) == 2 else "%Y-%m-%d").replace(tzinfo=_BKK)
            if END_STR else datetime.now(_BKK))

import io, sys as _sys
_sys.stdout = io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8')
print(f"Sim period: {start_dt.strftime('%d-%m-%Y')} -> {end_dt.strftime('%d-%m-%Y')}")
print("Loading logs...")

# ── Parse log ────────────────────────────────────────────────────────
def _fld(line: str, key: str) -> str:
    m = re.search(rf'\b{re.escape(key)}=([^\s|]+)', line)
    return m.group(1) if m else ""


def _ts(line: str):
    m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', line)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_BKK)


orders      = {}   # ticket → {created_ts, tf, signal, sid, entry, sl, tp, trend_filter}
closed_info = {}   # ticket → {profit, close_time, reason}

with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        ts = _ts(line)
        if not ts:
            continue
        if ts < start_dt or ts > end_dt:
            continue

        if "] ORDER_CREATED |" in line:
            tk = _fld(line, "ticket")
            if not tk or not tk.isdigit():
                continue
            orders[tk] = {
                "created_ts":   ts,
                "tf":           _fld(line, "tf"),
                "signal":       _fld(line, "signal").upper(),
                "sid":          _fld(line, "sid"),
                "entry":        _fld(line, "entry"),
                "sl":           _fld(line, "sl"),
                "tp":           _fld(line, "tp"),
                "trend_filter": _fld(line, "trend_filter"),
                "hhll_log":     _fld(line, "hhll_last_label"),
            }

        elif "] POSITION_CLOSED |" in line:
            tk = _fld(line, "ticket")
            if not tk or not tk.isdigit():
                continue
            try:
                profit = float(_fld(line, "profit"))
            except ValueError:
                profit = 0.0
            closed_info[tk] = {
                "profit":     profit,
                "close_time": ts,
                "reason":     _fld(line, "reason"),
            }

print(f"Orders found: {len(orders)}")
print(f"Closed info:  {len(closed_info)}")

if not orders:
    print("ไม่พบ order ในช่วงเวลานี้")
    sys.exit(0)

# ── Connect MT5 ──────────────────────────────────────────────────────
print("\nConnecting MT5...")
import MetaTrader5 as mt5

os.environ.setdefault("MT5_PATH", "C:/Program Files/MetaTrader 5 IC Markets (SC)/terminal64.exe")
if not mt5.initialize():
    print("MT5 init failed:", mt5.last_error())
    sys.exit(1)

from config import TF_OPTIONS, SYMBOL
import config as _cfg
HHLL_LEFT    = int(getattr(_cfg, "HHLL_LEFT",     5))
HHLL_RIGHT   = int(getattr(_cfg, "HHLL_RIGHT",    5))
HHLL_LOOKBACK = int(getattr(_cfg, "HHLL_LOOKBACK", 500))
import hhll_swing
import sweep_filter

print(f"Symbol: {SYMBOL}")

# ── HHLL at historical time ───────────────────────────────────────────
def get_hhll_at(tf: str, end: datetime):
    """
    ดึง HHLL data สำหรับ TF ณ เวลา end (ใช้ MT5 history)
    ตรงกับ fetch_hhll: copy_rates_from_pos(0, N) → ใช้ N bars สุดท้ายก่อน end
    """
    tf_id = TF_OPTIONS.get(tf)
    if not tf_id:
        return None

    n       = HHLL_LOOKBACK + HHLL_LEFT + HHLL_RIGHT + 5   # เหมือน fetch_hhll
    tf_secs = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}
    secs    = tf_secs.get(tf, 60)

    # ดึง range กว้างๆ (buffer 2x) แล้วตัดเหลือ n bars สุดท้าย
    # เพื่อให้ context เหมือน copy_rates_from_pos(0, n) ที่ bot ใช้
    end_adj  = end - timedelta(seconds=secs)        # exclude forming bar
    start_r  = end_adj - timedelta(seconds=secs * n * 2)

    rates = mt5.copy_rates_range(SYMBOL, tf_id, start_r, end_adj)
    if rates is None or len(rates) < HHLL_LEFT + HHLL_RIGHT + 10:
        return None

    # ตัดเหลือ n bars สุดท้าย (เหมือน copy_rates_from_pos พอดี)
    if len(rates) > n:
        rates = rates[-n:]

    # ใช้ hhll_swing internal functions (เหมือน fetch_hhll ทุกอย่าง)
    zz = hhll_swing._build_zz(rates, HHLL_LEFT, HHLL_RIGHT)
    if len(zz) < 5:
        return None

    buckets      = {"HH": None, "HL": None, "LH": None, "LL": None}
    prev_buckets = {"HH": None, "HL": None, "LH": None, "LL": None}
    structure    = []
    for k in range(len(zz)):
        lbl = hhll_swing._classify_pt(zz, k)
        if not lbl:
            continue
        pt = {"price": zz[k]["price"], "time": zz[k]["time"]}
        prev_buckets[lbl] = buckets[lbl]
        buckets[lbl] = pt
        structure.append(lbl)

    return {
        "hh": buckets["HH"],
        "hl": buckets["HL"],
        "lh": buckets["LH"],
        "ll": buckets["LL"],
        "last_label": structure[-1] if structure else "",
    }


def sim_sweep_at(tf: str, signal: str, oc_ts: datetime) -> str | None:
    """
    คืน 'SWEEP_LOW'|'SWEEP_HIGH'|None ณ เวลา oc_ts สำหรับ TF และ signal
    ใช้ swing ล่าสุดจากทุก 4 ประเภท (HH/HL/LH/LL)
    """
    raw_tf = re.sub(r'[\[\]]', '', tf).split('_')[0].split('-')[0]
    d = get_hhll_at(raw_tf, oc_ts)
    if not d:
        return None

    # ต้องมี swing อย่างน้อย 1 ตัว
    if not any(d.get(k) for k in ("hh", "hl", "lh", "ll")):
        return None

    return sweep_filter.check_sweep_at_time(raw_tf, oc_ts, d)


# ── Simulate ──────────────────────────────────────────────────────────
print("\nRunning simulation...")
print("=" * 70)

results = []
actual_total   = 0.0
sim_total      = 0.0
blocked_orders = []
unblocked_orders = []

for tk, o in sorted(orders.items(), key=lambda x: x[1]["created_ts"]):
    cl = closed_info.get(tk)
    if not cl:
        continue   # ยังไม่ปิด/ไม่พบ POSITION_CLOSED

    profit    = cl["profit"]
    actual_total += profit
    signal    = o["signal"]
    tf        = o["tf"]
    oc_ts     = o["created_ts"]

    # ตรวจ sweep state ณ เวลาสร้าง order
    try:
        sw_state = sim_sweep_at(tf, signal, oc_ts)
    except Exception as e:
        sw_state = None

    # Determine action
    blocked   = False
    unblocked = False
    reason_sw = ""

    if sw_state == "SWEEP_LOW":
        if signal == "SELL":
            blocked   = True
            reason_sw = "SWEEP_LOW block SELL"
        elif signal == "BUY":
            unblocked = True
            reason_sw = "SWEEP_LOW unblock BUY"
    elif sw_state == "SWEEP_HIGH":
        if signal == "BUY":
            blocked   = True
            reason_sw = "SWEEP_HIGH block BUY"
        elif signal == "SELL":
            unblocked = True
            reason_sw = "SWEEP_HIGH unblock SELL"

    # sim P&L:
    # - blocked → order ไม่เกิด → P&L = 0 (หลีกเลี่ยง loss หรือเสีย profit)
    # - not blocked → เหมือน actual
    sim_profit = 0.0 if blocked else profit
    sim_total += sim_profit

    icon = ""
    if blocked:
        icon = "🚫" if profit < 0 else "⚠️"
        blocked_orders.append({
            "ticket": tk, "tf": tf, "signal": signal,
            "profit": profit, "sim_profit": 0.0,
            "reason": reason_sw, "close_reason": cl["reason"],
        })
    elif unblocked:
        icon = "🟢"
        unblocked_orders.append({
            "ticket": tk, "tf": tf, "signal": signal,
            "profit": profit, "reason": reason_sw,
        })

    if blocked or unblocked:
        diff = sim_profit - profit
        results.append((oc_ts, tk, tf, signal, profit, sim_profit, reason_sw, icon))
        print(
            f"{icon} [{oc_ts.strftime('%d-%m %H:%M')}] #{tk} {tf} {signal:4s} | "
            f"actual={profit:+.2f} sim={sim_profit:+.2f} diff={diff:+.2f} | {reason_sw}"
        )

# ── Summary ───────────────────────────────────────────────────────────
print("\n" + "=" * 70)
diff_total = sim_total - actual_total

print(f"\n📊 Simulation Summary ({START_STR} → {end_dt.strftime('%d-%m-%Y')})")
print(f"   Total orders (closed):  {len(closed_info)}")
print(f"   Orders affected:        {len(results)}")
print(f"   Blocked:                {len(blocked_orders)}")
print(f"   Unblocked:              {len(unblocked_orders)}")
print(f"\n   Actual P&L:  ${actual_total:+.2f}")
print(f"   Sim P&L:     ${sim_total:+.2f}")
print(f"   Difference:  ${diff_total:+.2f}  {'↑ ดีขึ้น' if diff_total > 0 else '↓ แย่ลง' if diff_total < 0 else '─ เท่าเดิม'}")

print("\n🚫 Blocked orders (sweep filter would block):")
blocked_loss_saved = sum(o["profit"] for o in blocked_orders if o["profit"] < 0)
blocked_profit_lost = sum(o["profit"] for o in blocked_orders if o["profit"] > 0)
print(f"   Loss avoided:  ${abs(blocked_loss_saved):.2f}")
print(f"   Profit missed: ${blocked_profit_lost:.2f}")
for bo in blocked_orders:
    flag = "💰SAVE" if bo["profit"] < 0 else "❌MISS"
    print(f"   {flag} #{bo['ticket']} {bo['tf']} {bo['signal']:4s} {bo['profit']:+.2f} | {bo['reason']}")

mt5.shutdown()
print("\nDone.")
