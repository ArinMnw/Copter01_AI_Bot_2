"""Debug: dump HHLL zigzag + structure at fill time of 532226511
using the REAL hhll_swing module functions"""

import sys, os, io
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import MetaTrader5 as mt5
import config
from datetime import datetime, timedelta, timezone

# Import REAL functions from hhll_swing
from hhll_swing import _build_zz, _classify_pt, _is_ph, _is_pl

BKK = timezone(timedelta(hours=7))
SYMBOL = config.SYMBOL
TF = mt5.TIMEFRAME_M1
HHLL_LEFT = 5
HHLL_RIGHT = 5
HHLL_LOOKBACK = 500


def main():
    if not config.mt5_initialize(mt5):
        print(f"MT5 init failed: {mt5.last_error()}")
        return

    fill_time = datetime(2026, 5, 27, 1, 29, 15, tzinfo=BKK)
    start = fill_time - timedelta(minutes=HHLL_LOOKBACK + 20)
    end   = fill_time + timedelta(minutes=5)

    rates = mt5.copy_rates_range(SYMBOL, TF, start, end)
    if rates is None or len(rates) == 0:
        print(f"No rates: {mt5.last_error()}")
        mt5.shutdown()
        return

    print(f"Fetched {len(rates)} M1 candles")
    fill_ts = int(fill_time.timestamp())

    # Use rates up to fill time
    fill_idx = None
    for i, r in enumerate(rates):
        if int(r["time"]) >= fill_ts - 60:
            fill_idx = i
            break

    rates_at_fill = rates[:fill_idx + 1]
    print(f"Using {len(rates_at_fill)} candles up to fill")
    print()

    zz = _build_zz(rates_at_fill, HHLL_LEFT, HHLL_RIGHT)
    print(f"Zigzag points: {len(zz)}")
    print()

    # Classify all and collect structure
    structure_full = []
    for k in range(len(zz)):
        lbl = _classify_pt(zz, k)
        if lbl:
            structure_full.append((k, lbl, zz[k]))

    # Show last 20 zigzag points
    print("=" * 105)
    print("Last 25 Zigzag points (newest first) with REAL classification:")
    print("=" * 105)
    print(f"{'#':>3s} | {'Dir':>4s} | {'Price':>9s} | {'Time BKK':>20s} | {'Label':>5s}")
    print("-" * 55)

    start_k = max(0, len(zz) - 25)
    for k in range(len(zz) - 1, start_k - 1, -1):
        pt = zz[k]
        t_bkk = datetime.fromtimestamp(pt["time"], tz=BKK)
        lbl = _classify_pt(zz, k)
        d_str = "H" if pt["dir"] == 1 else "L"
        marker = f" <<< {lbl}" if lbl else ""
        print(f"{k:>3d} | {d_str:>4s} | {pt['price']:>9.2f} | {t_bkk.strftime('%Y-%m-%d %H:%M'):>20s} |{marker}")

    # Structure newest first
    print()
    print("=" * 105)
    print("Structure list (newest first) - last_label comes from [0]:")
    print("=" * 105)
    structure_full.reverse()
    for i, (k, lbl, pt) in enumerate(structure_full[:15]):
        t_bkk = datetime.fromtimestamp(pt["time"], tz=BKK)
        d_str = "H" if pt["dir"] == 1 else "L"
        print(f"  [{i}] {lbl:>3s}  {pt['price']:>9.2f}  {t_bkk.strftime('%H:%M %d-%b')}  (zigzag #{k}, pivot {d_str})")

    last_label = structure_full[0][1] if structure_full else "?"
    print()
    print(f"=> last_label = {last_label}")

    # H/L labels for trend
    h_labels = [s[1] for s in structure_full if s[1] in ("HH", "LH")]
    l_labels = [s[1] for s in structure_full if s[1] in ("HL", "LL")]
    print(f"=> H-labels: {h_labels[:5]}")
    print(f"=> L-labels: {l_labels[:5]}")
    if h_labels and l_labels:
        h0, l0 = h_labels[0], l_labels[0]
        if h0 == "HH" and l0 == "HL":
            trend = "BULL"
        elif h0 == "LH" and l0 == "LL":
            trend = "BEAR"
        else:
            trend = f"SIDEWAY (h0={h0}, l0={l0})"
        print(f"=> Trend: {trend}")

    # Show SELL allowed?
    print()
    print("=" * 105)
    if last_label in ("HH", "HL"):
        print(f"SIDEWAY/{last_label} -> SELL **BLOCKED** XX")
        print("=> TREND_RECHECK would CLOSE position immediately!")
    elif last_label in ("LH", "LL"):
        print(f"SIDEWAY/{last_label} -> SELL allowed OK")
        print("=> TREND_RECHECK would PASS, position stays open")
    print("=" * 105)

    # Pivot lows around 01:09-01:15
    print()
    print("Pivot LOWs from 01:00 to 01:29:")
    t_0100 = datetime(2026, 5, 27, 1, 0, tzinfo=BKK)
    ts_0100 = int(t_0100.timestamp())
    for i, r in enumerate(rates_at_fill):
        rt = int(r["time"])
        if ts_0100 <= rt <= fill_ts:
            is_l = _is_pl(rates_at_fill, i, HHLL_LEFT, HHLL_RIGHT)
            if is_l:
                t_bkk = datetime.fromtimestamp(rt, tz=BKK)
                in_zz = any(z["time"] == rt and z["dir"] == -1 for z in zz)
                # classify if in zz
                zz_idx = next((k for k, z in enumerate(zz) if z["time"] == rt and z["dir"] == -1), None)
                cls = _classify_pt(zz, zz_idx) if zz_idx is not None else "N/A"
                print(f"  PL at {t_bkk.strftime('%H:%M')} low={float(r['low']):.2f}  in_zigzag={in_zz}  classify={cls}")

    mt5.shutdown()

if __name__ == "__main__":
    main()
