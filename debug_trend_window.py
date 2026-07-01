"""
debug_trend_window.py — ดู M1 trend structure ทุกนาทีในช่วงที่ระบุ
Usage: python debug_trend_window.py --start 11:00 --end 12:30 --tf M1
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from datetime import datetime, timedelta, timezone
from pathlib import Path
BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

_BKK = timezone(timedelta(hours=7))

def _to_real(raw): return raw - timedelta(hours=1)
def _to_raw(real): return real + timedelta(hours=1)
def _ts_real(ts):  return datetime.fromtimestamp(ts, _BKK) - timedelta(hours=1)

now_raw  = datetime.now(_BKK)
now_real = _to_real(now_raw)

TF = "M1"; start_h = "11:00"; end_h = "12:30"; step_m = 1
args = sys.argv[1:]; i = 0
while i < len(args):
    if   args[i]=="--tf"    and i+1<len(args): TF      = args[i+1].upper(); i+=2
    elif args[i]=="--start" and i+1<len(args): start_h = args[i+1]; i+=2
    elif args[i]=="--end"   and i+1<len(args): end_h   = args[i+1]; i+=2
    else: i+=1

def _hm(s): p=s.split(":"); return int(p[0]), int(p[1]) if len(p)>1 else 0

h,m = _hm(start_h)
t_start = now_real.replace(hour=h, minute=m, second=0, microsecond=0)
h,m = _hm(end_h)
t_end   = now_real.replace(hour=h, minute=m, second=0, microsecond=0)

print(f"Trend check — TF={TF}  {start_h}-{end_h} BKK  ({now_real.strftime('%d-%m-%Y')})")
print()

import MetaTrader5 as mt5
import config as _cfg
if not _cfg.mt5_initialize(mt5):
    print("MT5 init failed:", mt5.last_error()); sys.exit(1)

from config import TF_OPTIONS, SYMBOL
import hhll_swing

LEFT  = int(getattr(_cfg,"HHLL_LEFT",5))
RIGHT = int(getattr(_cfg,"HHLL_RIGHT",5))
LBK   = int(getattr(_cfg,"HHLL_LOOKBACK",500))
N     = LBK + LEFT + RIGHT + 5
secs  = {"M1":60,"M5":300,"M15":900,"M30":1800,"H1":3600}.get(TF,60)
tf_id = TF_OPTIONS.get(TF)

def get_trend_at(real_end: datetime):
    raw_end  = _to_raw(real_end)
    end_adj  = raw_end - timedelta(seconds=secs)
    start_r  = end_adj - timedelta(seconds=secs*N*2)
    rates = mt5.copy_rates_range(SYMBOL, tf_id, start_r, end_adj)
    if rates is None or len(rates) < LEFT+RIGHT+10: return None, None, None
    if len(rates) > N: rates = rates[-N:]
    zz = hhll_swing._build_zz(rates, LEFT, RIGHT)
    if len(zz) < 5: return None, None, None

    buckets = {"HH":None,"HL":None,"LH":None,"LL":None}
    for k in range(len(zz)):
        lbl = hhll_swing._classify_pt(zz, k)
        if lbl:
            buckets[lbl] = {"price":float(zz[k]["price"]),"time":int(zz[k]["time"])}

    # newest high-type vs newest low-type
    h_types = [(lbl, buckets[lbl]) for lbl in ("HH","LH") if buckets[lbl]]
    l_types = [(lbl, buckets[lbl]) for lbl in ("HL","LL") if buckets[lbl]]

    h1 = max(h_types, key=lambda x: x[1]["time"]) if h_types else None
    l1 = max(l_types, key=lambda x: x[1]["time"]) if l_types else None

    if not h1 or not l1: return "UNKNOWN", None, None

    h_lbl = h1[0]; l_lbl = l1[0]
    h_str = f"{h_lbl} {h1[1]['price']:.2f}@{_ts_real(h1[1]['time']).strftime('%H:%M')}"
    l_str = f"{l_lbl} {l1[1]['price']:.2f}@{_ts_real(l1[1]['time']).strftime('%H:%M')}"

    if h_lbl=="HH" and l_lbl=="HL": trend = "BULL"
    elif h_lbl=="LH" and l_lbl=="LL": trend = "BEAR"
    else: trend = "SIDEWAY"

    return trend, h_str, l_str

print(f"{'Time':>6}  {'Trend':<8}  {'Latest High':<22}  {'Latest Low':<22}")
print("-"*70)

prev_trend = None
cur = t_start
while cur <= t_end:
    trend, h_str, l_str = get_trend_at(cur)
    if trend is None:
        cur += timedelta(minutes=step_m); continue

    icon = {"BULL":"🟢","BEAR":"🔴","SIDEWAY":"⚪","UNKNOWN":"❓"}.get(trend,"?")
    changed = " ◀ CHANGE" if (prev_trend and prev_trend != trend) else ""
    print(f"{cur.strftime('%H:%M'):>6}  {icon}{trend:<7}  {h_str:<22}  {l_str:<22}{changed}")
    prev_trend = trend
    cur += timedelta(minutes=step_m)

mt5.shutdown()
print("\nDone.")
