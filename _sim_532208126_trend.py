"""
_sim_532208126_trend.py
Simulate trend_allows_signal + swing_data_ready for order 532208126
M5 S1 BUY -- fill 00:54:14 27/05/2026 @ 4498.12
"""
import sys
sys.path.insert(0, "D:/Project/Copter01_AI_Bot_2")

from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5

BKK = timezone(timedelta(hours=7))

SYMBOL    = "XAUUSD.iux"
fill_bkk  = datetime(2026, 5, 27,  1, 54, 14, tzinfo=BKK)
start_bkk = datetime(2026, 5, 26, 22,  0,  0, tzinfo=BKK)
end_bkk   = datetime(2026, 5, 27,  1, 55,  0, tzinfo=BKK)

if not mt5.initialize():
    print("MT5 init failed:", mt5.last_error())
    sys.exit(1)

rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M5, start_bkk, end_bkk)
mt5.shutdown()

if rates is None or len(rates) == 0:
    print("No rates")
    sys.exit(1)

bars = [dict(zip(rates.dtype.names, r)) for r in rates]

def chart_t(ts):
    return datetime.fromtimestamp(int(ts), tz=BKK) - timedelta(hours=1)

print(f"Fetched {len(bars)} M5 bars  "
      f"({chart_t(bars[0]['time']).strftime('%d/%m %H:%M')} - "
      f"{chart_t(bars[-1]['time']).strftime('%d/%m %H:%M')} chart)")

# bars ที่ปิดแล้วก่อน fill bar (00:50 chart = 01:50 BKK)
fill_ts = int(fill_bkk.timestamp())
fill_bar_open = (fill_ts // 300) * 300
closed = [b for b in bars if int(b["time"]) < fill_bar_open]
print(f"Closed bars before fill: {len(closed)}  "
      f"last={chart_t(closed[-1]['time']).strftime('%d/%m %H:%M') if closed else 'N/A'}")

if not closed:
    print("No closed bars")
    sys.exit(1)

# HHLL computation
import hhll_swing as hs

LEFT  = hs.HHLL_LEFT
RIGHT = hs.HHLL_RIGHT
print(f"HHLL LEFT={LEFT} RIGHT={RIGHT}")

zz = hs._build_zz(closed, LEFT, RIGHT)
print(f"Zigzag points: {len(zz)}")

labeled = []
for k in range(len(zz)):
    lbl = hs._classify_pt(zz, k)
    if lbl:
        labeled.append({"time": zz[k]["time"], "price": zz[k]["price"],
                        "dir": zz[k]["dir"], "label": lbl})

print(f"\nHHLL labels (last {min(len(labeled), 15)}):")
print(f"{'chart':^12}  {'label':^6}  {'price':>8}  dir")
print("-" * 42)
for p in labeled[-15:]:
    ct = chart_t(p["time"]).strftime("%d/%m %H:%M")
    d  = "HIGH" if p["dir"] == 1 else "LOW "
    print(f"{ct:<12}  {p['label']:^6}  {p['price']:>8.2f}  {d}")

last_label = labeled[-1]["label"] if labeled else ""
print(f"\nlast_label = {last_label!r}")

# simulate trend_allows_signal
signal = "BUY"
print(f"\n== Simulated: M5 SIDEWAY + SIDEWAY_HHLL=True, signal='{signal}' ==")
if not last_label:
    print("  swing_data_ready = FALSE  (last_label empty)")
    print("  -> fill_round1_skip  (keeps retrying forever)")
elif last_label in ("LH", "LL") and signal == "BUY":
    print(f"  swing_data_ready = TRUE")
    print(f"  trend_allows_signal -> BLOCK  (SIDEWAY/{last_label})")
    print("  -> trend recheck would CLOSE position ✅")
elif last_label in ("HH", "HL") and signal == "BUY":
    print(f"  swing_data_ready = TRUE")
    print(f"  trend_allows_signal -> ALLOW  (HHLL={last_label} bullish)")
    print("  -> trend recheck would NOT close position")
else:
    print(f"  swing_data_ready = TRUE")
    print(f"  trend_allows_signal -> ALLOW  (label={last_label})")

# last 10 M5 bars around fill
print(f"\n== M5 bars before fill (last 10 closed) ==")
print(f"{'chart':^12}  {'O':>8}  {'H':>8}  {'L':>8}  {'C':>8}  color")
print("-" * 65)
for b in closed[-10:]:
    ct  = chart_t(b["time"]).strftime("%d/%m %H:%M")
    o, h, l, c = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
    color  = "RED" if c < o else ("GRN" if c > o else "DOJI")
    marker = " <-- last before fill" if b is closed[-1] else ""
    print(f"{ct:<12}  {o:>8.2f}  {h:>8.2f}  {l:>8.2f}  {c:>8.2f}  {color}{marker}")
