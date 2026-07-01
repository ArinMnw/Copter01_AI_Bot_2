"""debug_sweep_detail.py — ดู M1 bars หลัง HH@11:34 และ M5 HTF confirmation"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from datetime import datetime, timedelta, timezone
_BKK = timezone(timedelta(hours=7))

import MetaTrader5 as mt5
import config as _cfg
if not _cfg.mt5_initialize(mt5):
    print("MT5 init failed:", mt5.last_error()); sys.exit(1)
from config import TF_OPTIONS, SYMBOL

ref_price = 4483.69   # HH@11:34 price
# raw time = real BKK + 1h  → 11:34 real = 12:34 raw
start_raw = datetime(2026,6,4,12,34,0, tzinfo=_BKK)
end_raw   = datetime(2026,6,4,13,5,0,  tzinfo=_BKK)   # 12:05 real

print(f"M1 bars หลัง HH@11:34 (ref_price={ref_price}):")
print(f"{'Time':>6}  {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8}  {'Color':<6}  Note")
print("-"*70)
tf_id = TF_OPTIONS["M1"]
rates = mt5.copy_rates_range(SYMBOL, tf_id, start_raw, end_raw)
for r in rates:
    t    = datetime.fromtimestamp(r["time"], _BKK) - timedelta(hours=1)
    clr  = "GREEN" if r["close"] > r["open"] else "RED  "
    note = ""
    if r["close"] > ref_price:
        note += "★ close > HH"
    print(f"  {t.strftime('%H:%M')}  {r['open']:>8.2f} {r['high']:>8.2f} {r['low']:>8.2f} {r['close']:>8.2f}  {clr}  {note}")

print()
print(f"M5 bars (HTF check — high > {ref_price} AND red):")
print(f"{'Time':>6}  {'High':>8} {'Close':>8}  {'Color':<6}  Note")
print("-"*70)
tf5_id = TF_OPTIONS["M5"]
rates5 = mt5.copy_rates_range(SYMBOL, tf5_id, start_raw - timedelta(hours=2), end_raw)
for r in rates5:
    t   = datetime.fromtimestamp(r["time"], _BKK) - timedelta(hours=1)
    clr = "GREEN" if r["close"] > r["open"] else "RED  "
    note = ""
    if r["high"] > ref_price and r["close"] < r["open"]:
        note = "★ HTF CONFIRM (high > HH AND red)"
    elif r["high"] > ref_price:
        note = "  high > HH but not red"
    print(f"  {t.strftime('%H:%M')}  {r['high']:>8.2f} {r['close']:>8.2f}  {clr}  {note}")

mt5.shutdown()
print("\nDone.")
