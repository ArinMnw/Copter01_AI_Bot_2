"""
debug_hhll.py
─────────────────────────────────────────────────────────────────────────
ตรวจสอบว่า Python hhll_swing คิด swing ตรงกับ HHLLStrategy.mq5 บน chart ไหม
แสดง ALL classified ZZ points บน M1 ในช่วงที่ระบุ

Usage:
    python debug_hhll.py                  # ช่วง 3 ชม. ล่าสุด
    python debug_hhll.py --start 11:00    # เริ่ม 11:00 BKK วันนี้
    python debug_hhll.py --start 11:00 --end 12:00
    python debug_hhll.py --tf M5          # เปลี่ยน TF (default=M1)
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
TF     = "M1"
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

now_bkk = datetime.now(_BKK)

if start_h:
    hm = start_h.split(":")
    t_start = now_bkk.replace(hour=int(hm[0]), minute=int(hm[1]) if len(hm)>1 else 0, second=0, microsecond=0)
else:
    t_start = now_bkk - timedelta(hours=3)

if end_h:
    hm = end_h.split(":")
    t_end = now_bkk.replace(hour=int(hm[0]), minute=int(hm[1]) if len(hm)>1 else 0, second=0, microsecond=0)
else:
    t_end = now_bkk

print(f"TF: {TF}  |  Window: {t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')} BKK  ({now_bkk.strftime('%d-%m-%Y')})")
print()

# ── MT5 ───────────────────────────────────────────────────────────────
print("Connecting MT5...")
import MetaTrader5 as mt5
os.environ.setdefault("MT5_PATH", "C:/Program Files/MetaTrader 5 IC Markets (SC)/terminal64.exe")
if not mt5.initialize():
    print("MT5 init failed:", mt5.last_error()); sys.exit(1)

from config import TF_OPTIONS, SYMBOL
import config as _cfg

HHLL_LEFT    = int(getattr(_cfg, "HHLL_LEFT",     5))
HHLL_RIGHT   = int(getattr(_cfg, "HHLL_RIGHT",    5))
HHLL_LOOKBACK = int(getattr(_cfg, "HHLL_LOOKBACK", 500))
N = HHLL_LOOKBACK + HHLL_LEFT + HHLL_RIGHT + 5

tf_id = TF_OPTIONS.get(TF)
if not tf_id:
    print(f"TF {TF} ไม่พบใน TF_OPTIONS"); sys.exit(1)

print(f"Symbol: {SYMBOL}  |  LEFT={HHLL_LEFT}  RIGHT={HHLL_RIGHT}  LOOKBACK={HHLL_LOOKBACK}  N={N}")
print()

# ── Fetch rates ───────────────────────────────────────────────────────
# ใช้ copy_rates_from_pos เหมือน fetch_hhll ทุกอย่าง
rates = mt5.copy_rates_from_pos(SYMBOL, tf_id, 0, N)
if rates is None or len(rates) < HHLL_LEFT + HHLL_RIGHT + 10:
    print("ดึง rates ล้มเหลว:", mt5.last_error()); mt5.shutdown(); sys.exit(1)

print(f"Rates fetched: {len(rates)} bars")
oldest = datetime.fromtimestamp(int(rates[0]["time"]), _BKK)
newest = datetime.fromtimestamp(int(rates[-1]["time"]), _BKK)
print(f"Range: {oldest.strftime('%d-%m %H:%M')} → {newest.strftime('%d-%m %H:%M')} BKK")
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
    pt_dt    = datetime.fromtimestamp(pt_ts, _BKK)

    bucket_latest[lbl] = {"price": pt_price, "time": pt_ts, "dt": pt_dt}

    if t_start <= pt_dt <= t_end:
        dir_str = "HIGH ▲" if pt_dir == 1 else "LOW  ▼"
        in_window.append((pt_dt, lbl, pt_price, dir_str))
        print(f"{pt_dt.strftime('%H:%M %d-%m'):<12} {lbl:<6} {pt_price:>10.2f}  {dir_str}")

print("=" * 65)

if not in_window:
    print(f"(ไม่มี classified points ในช่วง {t_start.strftime('%H:%M')}-{t_end.strftime('%H:%M')})")

# ── Latest swing per type (as of NOW) ─────────────────────────────────
print()
print("Latest swing per type (from ALL history, newest overall):")
print("-" * 65)
all_cands = []
for lbl, pt in bucket_latest.items():
    if pt:
        all_cands.append((lbl, pt["price"], pt["time"], pt["dt"]))
        print(f"  {lbl}: {pt['price']:.2f}  @ {pt['dt'].strftime('%H:%M %d-%m')}")
    else:
        print(f"  {lbl}: (none)")

if all_cands:
    latest_overall = max(all_cands, key=lambda x: x[2])
    print(f"\n  → Latest swing (newest time): {latest_overall[0]} @ {latest_overall[3].strftime('%H:%M %d-%m')} price={latest_overall[1]:.2f}")

# ── Also show last 10 ZZ points (raw, unclassified) ──────────────────
print()
print("Last 15 ZZ raw points (unclassified):")
print("-" * 65)
start_k = max(0, len(zz) - 15)
for k in range(start_k, len(zz)):
    lbl    = hhll_swing._classify_pt(zz, k) or "(unclassified)"
    pt_dt  = datetime.fromtimestamp(int(zz[k]["time"]), _BKK)
    dir_s  = "H" if zz[k]["dir"] == 1 else "L"
    print(f"  [{k:3d}] {dir_s}  {zz[k]['price']:>10.2f}  {pt_dt.strftime('%H:%M %d-%m')}  {lbl}")

mt5.shutdown()
print("\nDone.")
