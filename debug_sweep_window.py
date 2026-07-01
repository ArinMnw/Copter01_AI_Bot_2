"""
debug_sweep_window.py — เช็ค Sweep Filter state ทุกนาทีในช่วงที่ระบุ (BKK real)
Usage:
    python debug_sweep_window.py --start 11:00 --end 12:00 --tf M1
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from datetime import datetime, timedelta, timezone
from pathlib import Path
BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

_BKK = timezone(timedelta(hours=7))

# ── timezone helpers ──────────────────────────────────────────────────
# MT5 raw ts → fromtimestamp(_BKK) ได้เวลา +1h เกิน
# display real BKK = fromtimestamp(_BKK) - 1h
# query raw       = real BKK + 1h
def _to_real(raw: datetime) -> datetime:   return raw - timedelta(hours=1)
def _to_raw(real: datetime) -> datetime:   return real + timedelta(hours=1)
def _ts_to_real(ts: int)    -> datetime:
    return datetime.fromtimestamp(ts, _BKK) - timedelta(hours=1)

now_raw  = datetime.now(_BKK)
now_real = _to_real(now_raw)   # BKK จริง

# ── Args ──────────────────────────────────────────────────────────────
TF = "M1"; start_h = "11:00"; end_h = "12:00"; step_m = 1
args = sys.argv[1:]; i = 0
while i < len(args):
    if   args[i]=="--tf"    and i+1<len(args): TF      = args[i+1].upper(); i+=2
    elif args[i]=="--start" and i+1<len(args): start_h = args[i+1]; i+=2
    elif args[i]=="--end"   and i+1<len(args): end_h   = args[i+1]; i+=2
    elif args[i]=="--step"  and i+1<len(args): step_m  = int(args[i+1]); i+=2
    else: i+=1

def _hm(s):
    p = s.split(":"); return int(p[0]), int(p[1]) if len(p)>1 else 0

h,m = _hm(start_h)
t_start = now_real.replace(hour=h, minute=m, second=0, microsecond=0)
h,m = _hm(end_h)
t_end   = now_real.replace(hour=h, minute=m, second=0, microsecond=0)

print(f"Sweep Filter check — TF={TF}  {start_h}-{end_h} BKK  ({now_real.strftime('%d-%m-%Y')})")
print(f"(Now: {now_real.strftime('%H:%M')} BKK)")
print()

# ── MT5 ───────────────────────────────────────────────────────────────
import MetaTrader5 as mt5
import config as _cfg
if not _cfg.mt5_initialize(mt5):
    print("MT5 init failed:", mt5.last_error()); sys.exit(1)

from config import TF_OPTIONS, SYMBOL
import hhll_swing, sweep_filter

LEFT  = int(getattr(_cfg, "HHLL_LEFT",     5))
RIGHT = int(getattr(_cfg, "HHLL_RIGHT",    5))
LBK   = int(getattr(_cfg, "HHLL_LOOKBACK", 500))
N     = LBK + LEFT + RIGHT + 5
secs  = {"M1":60,"M5":300,"M15":900,"M30":1800,"H1":3600,"H4":14400}.get(TF,60)
tf_id = TF_OPTIONS.get(TF)

def get_hhll(real_end: datetime) -> dict | None:
    """ดึง HHLL ณ เวลา real_end (BKK จริง)"""
    raw_end  = _to_raw(real_end)
    end_adj  = raw_end - timedelta(seconds=secs)    # exclude forming bar
    start_r  = end_adj - timedelta(seconds=secs*N*2)
    rates = mt5.copy_rates_range(SYMBOL, tf_id, start_r, end_adj)
    if rates is None or len(rates) < LEFT+RIGHT+10:
        return None
    if len(rates) > N:
        rates = rates[-N:]
    zz = hhll_swing._build_zz(rates, LEFT, RIGHT)
    if len(zz) < 5:
        return None
    buckets = {"HH":None,"HL":None,"LH":None,"LL":None}
    for k in range(len(zz)):
        lbl = hhll_swing._classify_pt(zz, k)
        if lbl:
            buckets[lbl] = {"price": float(zz[k]["price"]), "time": int(zz[k]["time"])}
    return {"hh":buckets["HH"],"hl":buckets["HL"],"lh":buckets["LH"],"ll":buckets["LL"]}

# helper: คำนวณ trend จาก hhll dict
def _get_trend(d):
    hh = d.get("hh"); hl = d.get("hl")
    lh = d.get("lh"); ll = d.get("ll")
    def newest(a, b):
        if not a and not b: return None
        if not a: return b
        if not b: return a
        return a if a["time"] >= b["time"] else b
    h1 = newest(hh, lh)
    l1 = newest(hl, ll)
    if not h1 or not l1: return "UNKNOWN", ""
    h_lbl = "HH" if (hh and (not lh or hh["time"] >= lh["time"])) else "LH"
    l_lbl = "HL" if (hl and (not ll or hl["time"] >= ll["time"])) else "LL"
    if h_lbl == "HH" and l_lbl == "HL": return "BULL", h_lbl
    if h_lbl == "LH" and l_lbl == "LL": return "BEAR", h_lbl
    return "SIDEWAY", h_lbl

def _get_last_label(d):
    """หา last_label = swing ล่าสุดทุกประเภท"""
    cands = []
    for lbl in ("HH","HL","LH","LL"):
        pt = d.get(lbl.lower())
        if pt and pt.get("time"):
            cands.append((lbl, int(pt["time"])))
    if not cands: return ""
    return max(cands, key=lambda x: x[1])[0]

# ── ตรวจทุก step_m นาที ───────────────────────────────────────────────
print(f"{'Time':>6}  {'Latest Swing':<22}  {'Trend':<8}  {'Sweep State':<16}  Effect")
print("-" * 82)

prev_state = None
cur = t_start
while cur <= t_end:
    d = get_hhll(cur)
    state_str  = "⬜ None"
    effect_str = ""
    swing_str  = "(no data)"
    trend_str  = ""

    if d:
        cands = []
        for lbl in ("HH","HL","LH","LL"):
            pt = d.get(lbl.lower())
            if pt and pt.get("time"):
                disp = _ts_to_real(pt["time"])
                cands.append((lbl, pt["price"], pt["time"], disp))
        if cands:
            latest = max(cands, key=lambda x: x[2])
            swing_str = f"{latest[0]} {latest[1]:.2f} @{latest[3].strftime('%H:%M')}"

        # ── simulate reset (trend + last_label เหมือน live bot) ──────────
        trend, _ = _get_trend(d)
        last_lbl  = _get_last_label(d)
        reset     = sweep_filter.update_trend_and_check_reset(TF, trend, last_lbl)
        trend_icon = {"BULL":"🟢","BEAR":"🔴","SIDEWAY":"⚪","UNKNOWN":"❓"}.get(trend,"?")
        trend_str = f"{trend_icon}{trend[:4]}"
        if reset:
            trend_str += "↺"   # แสดงว่า reset เกิด

        sw = sweep_filter.check_sweep_at_time(TF, _to_raw(cur), d)
        # อ่าน trigger bar จาก _sweep_at (เขียนโดย _activate, raw +1h)
        trigger_raw_str = sweep_filter._sweep_at.get(TF, "")
        try:
            yr = cur.year
            trig_dt   = datetime.strptime(f"{trigger_raw_str} {yr}", "%H:%M %d-%b %Y").replace(tzinfo=_BKK)
            trig_real = (trig_dt - timedelta(hours=1)).strftime("%H:%M")
        except Exception:
            trig_real = trigger_raw_str
        if sw == "SWEEP_HIGH":
            state_str  = "🔴 SWEEP_HIGH"
            effect_str = f"block BUY  [trigger bar: {trig_real}]"
        elif sw == "SWEEP_LOW":
            state_str  = "🟢 SWEEP_LOW"
            effect_str = f"block SELL [trigger bar: {trig_real}]"
        else:
            state_str  = "⬜ None"
            effect_str = ""

    # แสดงทุกนาทีถ้า step=1 หรือแค่ตอนเปลี่ยน state
    changed = (state_str != prev_state)
    marker  = " ◀ CHANGE" if changed and prev_state is not None else ""
    print(f"{cur.strftime('%H:%M'):>6}  {swing_str:<22}  {trend_str:<10}  {state_str:<16}  {effect_str}{marker}")
    prev_state = state_str
    cur += timedelta(minutes=step_m)

mt5.shutdown()
print("\nDone.")
