"""
_diag_s14_m15.py — ตรวจ S14 order 532198427 (M15 BUY 27/05 00:30 chart)
logic ใหม่: local_low ล่าสุด + RSI แท่งแดงย้อนหลัง 3 แท่ง
"""
import sys
sys.path.insert(0, "D:/Project/Copter01_AI_Bot_2")

from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5
import config
from strategy9 import _calc_rsi_values

BKK    = timezone(timedelta(hours=7))
SYMBOL = config.SYMBOL

# sweep bar = 00:30 chart = 01:30 BKK  (M15)
# fetch ย้อนหลัง ~18h สำหรับ RSI warmup (69 bars × 15min)
start_bkk = datetime(2026, 5, 26,  8, 0, tzinfo=BKK)   # chart 07:00
end_bkk   = datetime(2026, 5, 27,  1, 50, tzinfo=BKK)   # chart 00:50

if not config.mt5_initialize(mt5):
    print("MT5 init failed:", mt5.last_error())
    sys.exit(1)

rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M15, start_bkk, end_bkk)
mt5.shutdown()

if rates is None or len(rates) == 0:
    print("No rates")
    sys.exit(1)

bars = [dict(zip(rates.dtype.names, r)) for r in rates]

def chart_t(ts):
    return datetime.fromtimestamp(int(ts), tz=BKK) - timedelta(hours=1)

def is_red(b):   return float(b["close"]) < float(b["open"])
def is_green(b): return float(b["close"]) > float(b["open"])

# หา sweep bar = M15 bar เปิด 00:30 chart = ts 01:30 BKK
target_ts = int(datetime(2026, 5, 27, 1, 15, tzinfo=BKK).timestamp())  # 00:15 chart
sweep_global_idx = None
for i, b in enumerate(bars):
    if int(b["time"]) == target_ts:
        sweep_global_idx = i
        break

if sweep_global_idx is None:
    print("Sweep bar not found. Available near 00:30:")
    for i, b in enumerate(bars):
        ct = chart_t(b["time"])
        if ct.hour == 0 and 15 <= ct.minute <= 45:
            print(f"  idx={i} chart={ct.strftime('%H:%M')} ts={int(b['time'])}")
    sys.exit(1)

# window = bars ถึง sweep bar
window = bars[:sweep_global_idx + 1]
reject_idx = len(window) - 1

# RSI
rsi_vals = _calc_rsi_values(window, period=14, applied_price="close")

def pivot_rsi_buy(w, rsi, idx):
    # NEW logic: ค้นหาแท่งแดงย้อนหลัง max 3 แท่ง
    for j in range(idx, max(idx - 3, -1), -1):
        if j >= 0 and float(w[j]["close"]) < float(w[j]["open"]):
            return rsi[j], j
    return rsi[idx], idx

# ── NEW logic: local low 3-bar pivot (any color) ──
def find_local_lows(w):
    idxs = []
    n = len(w) - 1
    for i in range(1, n - 1):
        cl = float(w[i]["low"])
        pl = float(w[i-1]["low"])
        nl = float(w[i+1]["low"])
        if cl < pl and cl < nl:
            idxs.append(i)
    return idxs

local_low_idxs = find_local_lows(window)
valid_lows = [i for i in local_low_idxs if reject_idx - i >= 2]

print(f"\n== M15 bars (last 20 before sweep) ==")
print(f"{'idx':>4}  {'chart':^12}  {'O':>8}  {'H':>8}  {'L':>8}  {'C':>8}  color")
print("-" * 72)
start_show = max(0, sweep_global_idx - 19)
for i in range(start_show, sweep_global_idx + 1):
    b = window[i]
    ct = chart_t(b["time"]).strftime("%d/%m %H:%M")
    color = "RED  " if is_red(b) else ("GREEN" if is_green(b) else "DOJI ")
    marker = " <-- SWEEP" if i == sweep_global_idx else ""
    ll_mark = " [local_low]" if i in valid_lows else ""
    print(f"{i:>4}  {ct:<12}  {b['open']:>8.2f}  {b['high']:>8.2f}  {b['low']:>8.2f}  {b['close']:>8.2f}  {color}{marker}{ll_mark}")

print(f"\n== local lows (distance>=2): {len(valid_lows)} ==")
for i in valid_lows[-8:]:
    b = window[i]
    color = "RED  " if is_red(b) else "GREEN"
    rsi_v, rsi_src = pivot_rsi_buy(window, rsi_vals, i)
    rsi_ct = chart_t(window[rsi_src]["time"]).strftime("%H:%M")
    print(f"  idx={i:>3}  chart={chart_t(b['time']).strftime('%d/%m %H:%M')}  L={float(b['low']):.2f}  {color}  RSI_red={rsi_v:.2f}@{rsi_ct}")

if not valid_lows:
    print("[!] no valid local low")
    sys.exit(0)

# NEW: เลือกล่าสุด
ref_idx = max(valid_lows)
ref_bar = window[ref_idx]
ref_low = float(ref_bar["low"])
ref_color = "RED  " if is_red(ref_bar) else "GREEN"
ref_rsi, ref_rsi_src = pivot_rsi_buy(window, rsi_vals, ref_idx)
ref_rsi_ct = chart_t(window[ref_rsi_src]["time"]).strftime("%d/%m %H:%M")

sweep_bar = window[-1]
sweep_low = float(sweep_bar["low"])
sweep_c   = float(sweep_bar["close"])
sweep_o   = float(sweep_bar["open"])
sweep_rsi, sweep_rsi_src = pivot_rsi_buy(window, rsi_vals, reject_idx)
sweep_rsi_ct = chart_t(window[sweep_rsi_src]["time"]).strftime("%d/%m %H:%M")
sweep_color = "RED  " if is_red(sweep_bar) else "GREEN"

print(f"\n== ref bar (NEW: latest local low) ==")
print(f"  chart={chart_t(ref_bar['time']).strftime('%d/%m %H:%M')}  L={ref_low:.2f}  {ref_color}  dist={reject_idx - ref_idx}")
print(f"  RSI_red = {ref_rsi:.4f}  (from {ref_rsi_ct})")

print(f"\n== sweep bar ==")
print(f"  chart={chart_t(sweep_bar['time']).strftime('%d/%m %H:%M')}  O={sweep_o:.2f}  L={sweep_low:.2f}  C={sweep_c:.2f}  {sweep_color}")
print(f"  RSI_red = {sweep_rsi:.4f}  (from {sweep_rsi_ct})")

ok_dist  = reject_idx - ref_idx >= 2
ok_low   = sweep_low < ref_low
ok_rsi   = sweep_rsi > ref_rsi
ok_rsi50 = sweep_rsi < 50.0
ok_sweep  = sweep_o > ref_low and sweep_c >= ref_low
ok_engulf = sweep_c < ref_low

print(f"\n== S14 BUY conditions ==")
print(f"  distance >= 2  : {'OK' if ok_dist else 'FAIL'} ({reject_idx - ref_idx})")
print(f"  low < ref_low  : {'OK' if ok_low else 'FAIL'} ({sweep_low:.2f} < {ref_low:.2f})")
print(f"  RSI_red div    : {'OK' if ok_rsi else 'FAIL'} ({sweep_rsi:.2f} > {ref_rsi:.2f})")
print(f"  RSI_red < 50   : {'OK' if ok_rsi50 else 'FAIL'} ({sweep_rsi:.2f})")
print(f"  Sweep pattern  : {'OK' if ok_sweep else 'FAIL'} (O={sweep_o:.2f}>ref, C={sweep_c:.2f}>=ref)")
print(f"  Engulf pattern : {'OK' if ok_engulf else 'FAIL'} (C={sweep_c:.2f}<ref={ref_low:.2f})")

sig = "BUY Sweep" if (ok_dist and ok_low and ok_rsi and ok_rsi50 and ok_sweep) else \
      ("BUY Engulf" if (ok_dist and ok_low and ok_rsi and ok_rsi50 and ok_engulf) else "WAIT")
print(f"\n  -> {sig}")
