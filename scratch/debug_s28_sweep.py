"""Debug script to understand Asian range sweep frequency and characteristics"""
import MetaTrader5 as mt5
import config
from strategy28 import S28_DEFAULTS, calc_atr, detect_sweep, _cfg
from sim_s28_backtest import to_bkk, fetch_bars, _build_daily_asian_ranges, _calc_atr_series
from datetime import timedelta

PYTHON = r"C:\Users\Copter\AppData\Local\Programs\Python\Python313\python.exe"

if not mt5.initialize():
    print(f"MT5 init failed: {mt5.last_error()}")
    exit()

symbol = config.SYMBOL
bars = fetch_bars(symbol, "M5", 30, extra_bars=1500)
print(f"Total M5 bars: {len(bars)}")

cfg = dict(S28_DEFAULTS)
cfg["SWEEP_MIN_ATR"] = 0.01  # very relaxed
cfg["BODY_REVERSAL_PCT"] = 0.1
cfg["MAX_TRADES_PER_DAY"] = 999

# Build Asian ranges
daily_ranges = _build_daily_asian_ranges(bars, cfg)
print(f"\nAsian ranges found: {len(daily_ranges)} days")
for day, r in sorted(daily_ranges.items()):
    rng = r["high"] - r["low"]
    print(f"  {day}: H={r['high']:.2f} L={r['low']:.2f} range={rng:.2f}")

# Check ATR
atr_series = _calc_atr_series(bars, 14)

# Count potential sweeps
sweep_count = 0
sweep_details = []
trade_start_h = int(_cfg(cfg, "TRADE_START_H"))
trade_end_h = int(_cfg(cfg, "TRADE_END_H"))

for j in range(50, len(bars)):
    bar = bars[j]
    dt = to_bkk(int(bar["time"]))
    if dt is None:
        continue
    
    # Only in trade window
    h = dt.hour
    if not (trade_start_h <= h < trade_end_h):
        continue
    
    day_key = dt.strftime("%Y-%m-%d")
    ar = daily_ranges.get(day_key)
    if ar is None:
        continue
    
    atr = atr_series[j]
    if atr <= 0:
        continue
    
    asian_high = ar["high"]
    asian_low = ar["low"]
    
    bh = float(bar["high"])
    bl = float(bar["low"])
    bo = float(bar["open"])
    bc = float(bar["close"])
    
    # Check if any wick touches Asian H/L
    wick_above = bh - asian_high
    wick_below = asian_low - bl
    
    if wick_above > 0 or wick_below > 0:
        sweep = detect_sweep(asian_high, asian_low, bar, atr, cfg)
        if sweep:
            sweep_count += 1
            direction, extreme = sweep
            sweep_details.append({
                "time": dt.strftime("%Y-%m-%d %H:%M"),
                "dir": direction,
                "extreme": extreme,
                "bar_o": bo, "bar_h": bh, "bar_l": bl, "bar_c": bc,
                "asian_h": asian_high, "asian_l": asian_low,
                "wick_above": max(0, wick_above),
                "wick_below": max(0, wick_below),
                "atr": atr,
            })

print(f"\nTotal sweep signals detected (relaxed): {sweep_count}")
for d in sweep_details[:20]:
    print(f"  {d['time']} {d['dir']} | bar O={d['bar_o']:.2f} H={d['bar_h']:.2f} L={d['bar_l']:.2f} C={d['bar_c']:.2f}")
    print(f"    asian H={d['asian_h']:.2f} L={d['asian_l']:.2f} | wick_above={d['wick_above']:.2f} wick_below={d['wick_below']:.2f} ATR={d['atr']:.2f}")

# Also check how many bars cross Asian H/L boundaries (without sweep requirement)
cross_count = 0
for j in range(50, len(bars)):
    bar = bars[j]
    dt = to_bkk(int(bar["time"]))
    if dt is None:
        continue
    h = dt.hour
    if not (trade_start_h <= h < trade_end_h):
        continue
    day_key = dt.strftime("%Y-%m-%d")
    ar = daily_ranges.get(day_key)
    if ar is None:
        continue
    bh = float(bar["high"])
    bl = float(bar["low"])
    if bh > ar["high"] or bl < ar["low"]:
        cross_count += 1

print(f"\nBars crossing Asian H/L (trade window): {cross_count}")
print(f"Sweep-to-cross ratio: {sweep_count/cross_count*100:.1f}%" if cross_count > 0 else "N/A")

mt5.shutdown()
