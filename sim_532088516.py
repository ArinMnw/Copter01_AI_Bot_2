"""
Simulate TREND_RECHECK for any ticket (using REAL hhll_swing module)
จำลอง: ถ้า TREND_RECHECK ทำงานได้ทันทีหลัง fill (code ใหม่ไม่มี
_swing_data.clear()) จะปิด position เมื่อไหร่?

Usage: python sim_532088516.py [1|2]
  1 = 532088516 (S3 BUY M5)
  2 = 532226511 (S1 SELL M1)
"""

import sys, os, io
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone

# Import REAL functions from hhll_swing
from hhll_swing import _build_zz, _classify_pt

BKK = timezone(timedelta(hours=7))
SYMBOL = "XAUUSD.iux"
HHLL_LEFT = 5
HHLL_RIGHT = 5
HHLL_LOOKBACK = 500

# Order presets
PRESETS = {
    "1": {
        "ticket": 532088516,
        "fill_time": datetime(2026, 5, 26, 21, 53, 29, tzinfo=BKK),
        "sl_time":   datetime(2026, 5, 26, 22, 31, 55, tzinfo=BKK),
        "entry": 4517.69, "sl": 4504.07, "tp": 4531.39,
        "signal": "BUY", "tf_mt5": mt5.TIMEFRAME_M5, "tf_name": "M5",
        "sid": "3", "pattern": "S3 DM SP BUY [C1:R_DOJI]",
    },
    "2": {
        "ticket": 532226511,
        "fill_time": datetime(2026, 5, 27, 1, 29, 15, tzinfo=BKK),
        "sl_time":   datetime(2026, 5, 27, 1, 51, 44, tzinfo=BKK),
        "entry": 4495.01, "sl": 4498.81, "tp": 4485.58,
        "signal": "SELL", "tf_mt5": mt5.TIMEFRAME_M1, "tf_name": "M1",
        "sid": "1", "pattern": "S1 SELL Pattern F 2 bar engulf",
    },
    "3": {
        "ticket": 532230121,
        "fill_time": datetime(2026, 5, 27, 1, 43, 52, tzinfo=BKK),
        "sl_time":   datetime(2026, 5, 27, 1, 51, 44, tzinfo=BKK),
        "entry": 4496.00, "sl": 4498.84, "tp": 4485.58,
        "signal": "SELL", "tf_mt5": mt5.TIMEFRAME_M1, "tf_name": "M1",
        "sid": "3", "pattern": "S3 DM SP SELL [C1:G]",
    },
}
PRESET_KEY = sys.argv[1] if len(sys.argv) > 1 else "2"
P = PRESETS[PRESET_KEY]

FILL_TIME_BKK = P["fill_time"]
SL_TIME_BKK   = P["sl_time"]
ENTRY_PRICE   = P["entry"]
SL_PRICE      = P["sl"]
TP_PRICE      = P["tp"]
SIGNAL        = P["signal"]
TF            = P["tf_mt5"]
TF_NAME       = P["tf_name"]


# ══════════════════════════════════════════════════════════════
# HHLL helpers using REAL module functions
# ══════════════════════════════════════════════════════════════

def compute_hhll_real(rates):
    """Compute HHLL using real _build_zz and _classify_pt"""
    zz = _build_zz(rates, HHLL_LEFT, HHLL_RIGHT)
    if len(zz) < 5:
        return None

    buckets = {"HH": None, "HL": None, "LH": None, "LL": None}
    structure = []

    for k in range(len(zz)):
        lbl = _classify_pt(zz, k)
        if not lbl:
            continue
        pt = {"price": zz[k]["price"], "time": zz[k]["time"], "label": lbl}
        buckets[lbl] = pt
        structure.append(lbl)

    return {
        "hh": buckets["HH"], "hl": buckets["HL"],
        "lh": buckets["LH"], "ll": buckets["LL"],
        "structure": list(reversed(structure[-6:])),
        "last_label": structure[-1] if structure else "",
    }


def get_trend(hhll_data):
    struct = hhll_data.get("structure") or []
    if not struct:
        return {"trend": "UNKNOWN", "strength": "-", "label": "? --"}

    h_labels = [s for s in struct if s in ("HH", "LH")]
    l_labels = [s for s in struct if s in ("HL", "LL")]
    if not h_labels or not l_labels:
        return {"trend": "UNKNOWN", "strength": "-", "label": "? --"}

    h0, l0 = h_labels[0], l_labels[0]
    h1 = h_labels[1] if len(h_labels) > 1 else None
    l1 = l_labels[1] if len(l_labels) > 1 else None

    if h0 == "HH" and l0 == "HL":
        s = "strong" if (h1 == "HH" and l1 == "HL") else "weak"
        return {"trend": "BULL", "strength": s, "label": f"BULL ({s})"}
    if h0 == "LH" and l0 == "LL":
        s = "strong" if (h1 == "LH" and l1 == "LL") else "weak"
        return {"trend": "BEAR", "strength": s, "label": f"BEAR ({s})"}
    return {"trend": "SIDEWAY", "strength": "-", "label": "SIDEWAY"}


def trend_allows(signal, trend_info, last_label=""):
    t = trend_info.get("trend", "UNKNOWN")
    s = trend_info.get("strength", "-")
    if t == "BULL":
        if signal == "BUY":
            return True, f"BULL({s}) -> BUY ok"
        return False, f"BULL({s}) -> SELL blocked"
    if t == "BEAR":
        if signal == "SELL":
            return True, f"BEAR({s}) -> SELL ok"
        return False, f"BEAR({s}) -> BUY blocked"
    if t == "SIDEWAY":
        if last_label in ("LH", "LL") and signal == "BUY":
            return False, f"SW/{last_label} -> BUY blocked"
        if last_label in ("HH", "HL") and signal == "SELL":
            return False, f"SW/{last_label} -> SELL blocked"
        if last_label:
            return True, f"SW/{last_label} -> {signal} ok"
        return True, f"SW -> {signal} ok (no label)"
    return True, f"{t} -> {signal} ok"


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════

def main():
    if not mt5.initialize():
        print(f"MT5 init failed: {mt5.last_error()}")
        return

    tf_min_map = {mt5.TIMEFRAME_M1: 1, mt5.TIMEFRAME_M5: 5, mt5.TIMEFRAME_M15: 15,
                  mt5.TIMEFRAME_M30: 30, mt5.TIMEFRAME_H1: 60, mt5.TIMEFRAME_H4: 240}
    tf_min = tf_min_map.get(TF, 5)

    start = FILL_TIME_BKK - timedelta(minutes=tf_min * (HHLL_LOOKBACK + 20))
    end   = SL_TIME_BKK + timedelta(minutes=30)

    rates = mt5.copy_rates_range(SYMBOL, TF, start, end)
    if rates is None or len(rates) == 0:
        print(f"No rates: {mt5.last_error()}")
        mt5.shutdown()
        return

    print(f"Fetched {len(rates)} {TF_NAME} candles")
    print(f"Range: {datetime.fromtimestamp(rates[0]['time'], tz=BKK)} -> "
          f"{datetime.fromtimestamp(rates[-1]['time'], tz=BKK)}")
    print()

    fill_ts = int(FILL_TIME_BKK.timestamp())
    sl_ts   = int(SL_TIME_BKK.timestamp())

    fill_idx = None
    for i, r in enumerate(rates):
        if int(r["time"]) >= fill_ts - (tf_min * 60):
            fill_idx = i
            break

    if fill_idx is None:
        print("Cannot find fill candle")
        mt5.shutdown()
        return

    print("=" * 100)
    print(f"TICKET: {P['ticket']}  |  {P['pattern']}")
    print(f"ORDER: S{P['sid']} {SIGNAL} {TF_NAME}  |  Entry: {ENTRY_PRICE}  |  SL: {SL_PRICE}  |  TP: {TP_PRICE}")
    print(f"Fill: {FILL_TIME_BKK.strftime('%H:%M:%S')}  |  SL hit: {SL_TIME_BKK.strftime('%H:%M:%S')}")
    print("=" * 100)
    print()

    hdr = f"{SIGNAL}?"
    print(f"{'Time':>8s} | {'Close':>9s} | {'P/L':>8s} | {'Trend':>15s} | {'last':>5s} | {hdr:>5s} | Detail")
    print("-" * 90)

    close_time = None
    close_reason = None
    mult = -1 if SIGNAL == "SELL" else 1

    for i in range(fill_idx, len(rates)):
        bar_time = int(rates[i]["time"])
        bar_bkk = datetime.fromtimestamp(bar_time, tz=BKK)
        if bar_time > sl_ts + 600:
            break

        hhll = compute_hhll_real(rates[:i+1])
        if hhll is None:
            print(f"{bar_bkk.strftime('%H:%M'):>8s} | {float(rates[i]['close']):>9.2f} | {'?':>8s} | {'NO DATA':>15s} | {'':>5s} | {'?':>5s} |")
            continue

        trend = get_trend(hhll)
        ll = hhll.get("last_label", "")
        ok, detail = trend_allows(SIGNAL, trend, ll)

        cp = float(rates[i]["close"])
        pl = (cp - ENTRY_PRICE) * 100 * mult
        st = "OK" if ok else "XX"

        lo, hi = float(rates[i]["low"]), float(rates[i]["high"])
        note = ""
        if SIGNAL == "BUY" and lo <= SL_PRICE:
            note = " << SL"
        elif SIGNAL == "SELL" and hi >= SL_PRICE:
            note = " << SL"
        elif SIGNAL == "BUY" and hi >= TP_PRICE:
            note = " << TP"
        elif SIGNAL == "SELL" and lo <= TP_PRICE:
            note = " << TP"

        print(f"{bar_bkk.strftime('%H:%M'):>8s} | {cp:>9.2f} | {pl:>+7.0f}pt | {trend['label']:>15s} | {ll:>5s} | {st:>5s} | {detail}{note}")

        if not ok and close_time is None:
            close_time = bar_bkk
            close_reason = detail
            close_pl_pt = pl
            close_cp = cp

    print()
    actual_pl = (SL_PRICE - ENTRY_PRICE) * 100 * mult
    print("=" * 100)
    if close_time:
        saved = close_pl_pt - actual_pl
        print(f"  TREND_RECHECK close at: {close_time.strftime('%H:%M')} BKK")
        print(f"  Reason: {close_reason}")
        print(f"  Close ~{close_cp:.2f}  |  P/L: {close_pl_pt:+.0f} pt")
        print()
        print(f"  vs actual SL hit: {SL_TIME_BKK.strftime('%H:%M')} -> {SL_PRICE:.2f} ({actual_pl:+.0f} pt)")
        print(f"  Saved: {saved:+.0f} pt")
    else:
        print(f"  TREND_RECHECK never blocked {SIGNAL}")
        print(f"  Position still SL Hit ({actual_pl:+.0f} pt)")
    print("=" * 100)

    mt5.shutdown()

if __name__ == "__main__":
    main()
