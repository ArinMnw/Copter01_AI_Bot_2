"""
debug_hhll.py
─────────────────────────────────────────────────────────────────────────
ตรวจสอบว่า Python hhll_swing คิด swing ตรงกับ HHLLStrategy.mq5 บน chart ไหม
แสดง ALL classified ZZ points บน M1 ในช่วงที่ระบุ

Timezone rule (project):
  MT5 raw timestamp → fromtimestamp(tz=BKK) ได้เวลา +1h เกิน
  display ที่ถูก = fromtimestamp(tz=BKK) - 1h
  ดังนั้น input --start/--end ต้องบวก +1h ก่อน filter

Usage:
    python debug_hhll.py                  # 3 ชม. ล่าสุด (BKK)
    python debug_hhll.py --start 11:00    # เริ่ม 11:00 BKK วันนี้
    python debug_hhll.py --start 11:00 --end 12:00
    python debug_hhll.py --tf M5
"""

import sys, os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

_BKK = timezone(timedelta(hours=7))

# ── Parse args ────────────────────────────────────────────────────────
TF      = "M1"
start_h = None
end_h   = None

args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == "--tf" and i+1 < len(args):
        TF = args[i+1].upper(); i += 2
    elif args[i] == "--start" and i+1 < len(args):
        start_h = args[i+1]; i += 2
    elif args[i] == "--end" and i+1 < len(args):
        end_h = args[i+1]; i += 2
    else:
        i += 1

# now_bkk = เวลา BKK จริงๆ (fromtimestamp - 1h)
now_raw  = datetime.now(_BKK)                         # raw (เกิน 1h)
now_bkk  = now_raw - timedelta(hours=1)               # BKK จริง

def _parse_hm(s: str) -> tuple[int, int]:
    parts = s.split(":")
    return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0

if start_h:
    h, m = _parse_hm(start_h)
    # user บอก BKK จริง → ต้องบวก +1h เพื่อ match raw timestamp
    t_start_raw = now_raw.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(hours=1)
    t_start_bkk = now_raw.replace(hour=h, minute=m, second=0, microsecond=0)  # สำหรับแสดงผล
else:
    t_start_raw = now_raw - timedelta(hours=3)
    t_start_bkk = now_bkk - timedelta(hours=3)

if end_h:
    h, m = _parse_hm(end_h)
    t_end_raw = now_raw.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(hours=1)
    t_end_bkk = now_raw.replace(hour=h, minute=m, second=0, microsecond=0)
else:
    t_end_raw = now_raw
    t_end_bkk = now_bkk

print(f"TF: {TF}  |  Window: {t_start_bkk.strftime('%H:%M')} - {t_end_bkk.strftime('%H:%M')} BKK  ({now_bkk.strftime('%d-%m-%Y')})")
print(f"(Raw filter: {t_start_raw.strftime('%H:%M')} - {t_end_raw.strftime('%H:%M')} fromtimestamp)")
print()

# ── MT5 ───────────────────────────────────────────────────────────────
print("Connecting MT5...")
import MetaTrader5 as mt5
import config as _cfg
if not _cfg.mt5_initialize(mt5):
    print("MT5 init failed:", mt5.last_error()); sys.exit(1)

from config import TF_OPTIONS, SYMBOL

HHLL_LEFT     = int(getattr(_cfg, "HHLL_LEFT",     5))
HHLL_RIGHT    = int(getattr(_cfg, "HHLL_RIGHT",    5))
HHLL_LOOKBACK = int(getattr(_cfg, "HHLL_LOOKBACK", 500))
N = HHLL_LOOKBACK + HHLL_LEFT + HHLL_RIGHT + 5

tf_id = TF_OPTIONS.get(TF)
if not tf_id:
    print(f"TF {TF} ไม่พบใน TF_OPTIONS"); sys.exit(1)

print(f"Symbol: {SYMBOL}  |  LEFT={HHLL_LEFT}  RIGHT={HHLL_RIGHT}  LOOKBACK={HHLL_LOOKBACK}  N={N}")
print()

# ── Fetch rates (เหมือน fetch_hhll ทุกอย่าง) ──────────────────────────
rates = mt5.copy_rates_from_pos(SYMBOL, tf_id, 0, N)
if rates is None or len(rates) < HHLL_LEFT + HHLL_RIGHT + 10:
    print("ดึง rates ล้มเหลว:", mt5.last_error()); mt5.shutdown(); sys.exit(1)

def _bkk(ts: int) -> datetime:
    """แปลง MT5 timestamp → BKK จริง (fromtimestamp - 1h)"""
    return datetime.fromtimestamp(ts, _BKK) - timedelta(hours=1)

print(f"Rates fetched: {len(rates)} bars")
oldest_bkk = _bkk(int(rates[0]["time"]))
newest_bkk = _bkk(int(rates[-1]["time"]))
print(f"Range: {oldest_bkk.strftime('%d-%m %H:%M')} → {newest_bkk.strftime('%d-%m %H:%M')} BKK")
print(f"Now  : {now_bkk.strftime('%H:%M')} BKK")
print()

# ── Build Zigzag ──────────────────────────────────────────────────────
import hhll_swing

zz = hhll_swing._build_zz(rates, HHLL_LEFT, HHLL_RIGHT)
print(f"Zigzag points: {len(zz)}")
print()

# ── Classify ALL points ───────────────────────────────────────────────
print("=" * 65)
print(f"{'Time (BKK)':<12} {'Label':<6} {'Price':>10}  {'Dir'}")
print("-" * 65)

in_window = []
bucket_latest = {"HH": None, "HL": None, "LH": None, "LL": None}

for k in range(len(zz)):
    lbl = hhll_swing._classify_pt(zz, k)
    if not lbl:
        continue

    pt_ts    = int(zz[k]["time"])
    pt_price = float(zz[k]["price"])
    pt_dir   = zz[k]["dir"]
    pt_dt    = _bkk(pt_ts)              # BKK จริง
    pt_raw   = datetime.fromtimestamp(pt_ts, _BKK)  # raw (สำหรับ filter)

    bucket_latest[lbl] = {"price": pt_price, "time": pt_ts, "dt": pt_dt}

    # filter ด้วย raw (เพราะ t_start_raw/t_end_raw เป็น raw)
    if t_start_raw <= pt_raw <= t_end_raw:
        dir_str = "HIGH ▲" if pt_dir == 1 else "LOW  ▼"
        in_window.append((pt_dt, lbl, pt_price, dir_str))
        print(f"{pt_dt.strftime('%H:%M %d-%m'):<12} {lbl:<6} {pt_price:>10.2f}  {dir_str}")

print("=" * 65)

if not in_window:
    print(f"(ไม่มี classified points ในช่วงนี้)")

# ── Latest swing per type ─────────────────────────────────────────────
print()
print("Latest swing per type (newest overall):")
print("-" * 65)
all_cands = []
for lbl, pt in bucket_latest.items():
    if pt:
        all_cands.append((lbl, pt["price"], pt["time"], pt["dt"]))
        print(f"  {lbl}: {pt['price']:.2f}  @ {pt['dt'].strftime('%H:%M %d-%m')} BKK")
    else:
        print(f"  {lbl}: (none)")

if all_cands:
    latest = max(all_cands, key=lambda x: x[2])
    print(f"\n  → Latest: {latest[0]} @ {latest[3].strftime('%H:%M %d-%m')} price={latest[1]:.2f}")

# ── Last 15 ZZ raw points ─────────────────────────────────────────────
print()
print("Last 15 ZZ raw points:")
print("-" * 65)
start_k = max(0, len(zz) - 15)
for k in range(start_k, len(zz)):
    lbl   = hhll_swing._classify_pt(zz, k) or "(unclassified)"
    pt_dt = _bkk(int(zz[k]["time"]))
    dir_s = "H" if zz[k]["dir"] == 1 else "L"
    print(f"  [{k:3d}] {dir_s}  {zz[k]['price']:>10.2f}  {pt_dt.strftime('%H:%M %d-%m')}  {lbl}")

mt5.shutdown()
print("\nDone.")
