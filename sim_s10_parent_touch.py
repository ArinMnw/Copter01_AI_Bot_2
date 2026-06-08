"""
sim_s10_parent_touch.py — Before/After: S10 Parent High/Low Touch Cancel
──────────────────────────────────────────────────────────────────────────
Bug: ตรวจ M1 bars ตั้งแต่ parent bar OPEN → จับ high/low ที่เกิดใน parent bar เอง
Fix: ตรวจ M1 bars หลัง parent bar CLOSE เท่านั้น

Sim: สำหรับ order ที่โดน cancel ทันที (< 30 วินาที หลัง ORDER_CREATED)
     จาก "S10 Parent High/Low Touch Cancel"
     → ดูว่าถ้า fix แล้ว order จะรอดไหม (touched หลัง parent close หรือเปล่า)
     → ถ้าไม่ touched หลัง close → ดู MT5 ว่า TP หรือ SL ถูกแตะก่อน
"""
import re, os, sys, io, glob
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import MetaTrader5 as mt5
    MT5_OK = mt5.initialize()
except Exception:
    MT5_OK = False
    mt5 = None

ROOT  = os.path.dirname(os.path.abspath(__file__))
UTC6  = timezone(timedelta(hours=6))

# ─── TF seconds ───────────────────────────────────────────────────────────────
TF_SECS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}

def htf_secs(tf_name: str) -> int:
    return TF_SECS.get(tf_name.upper(), 3600)

TF_MT5 = {}
if mt5:
    TF_MT5 = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "H12": mt5.TIMEFRAME_H12, "D1": mt5.TIMEFRAME_D1,
    }

# ─── Log files ────────────────────────────────────────────────────────────────
def _log_files():
    log_dir = os.path.join(ROOT, "logs", "old_logs")
    files = sorted(glob.glob(os.path.join(log_dir, "bot-2026-0*.log*")))
    files += [os.path.join(ROOT, "logs", "bot.log")]
    return [f for f in files if os.path.exists(f)]

# ─── Parse ────────────────────────────────────────────────────────────────────
_TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
_EV = re.compile(r"^\[[^\]]+\]\s+(\S+)")

def _ts_to_unix(ts_str: str) -> int:
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC6)
        return int(dt.timestamp())
    except Exception:
        return 0

def fld(line, key):
    m = re.search(rf"\b{key}=([^|\s]+)", line)
    return m.group(1).strip() if m else None

def parse():
    """ดึง CREATE + CANCEL pairs ที่เป็น S10 Parent High/Low Touch Cancel"""
    creates = {}   # ticket → {ts, ts_unix, signal, entry, tf, htf_tf, parent_time, parent_high, parent_low, tp, sl}
    results = []

    for path in _log_files():
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    ts_m = _TS.match(line)
                    ev_m = _EV.match(line)
                    if not ts_m or not ev_m:
                        continue
                    ts_str = ts_m.group(1)
                    ev = ev_m.group(1)
                    tk = fld(line, "ticket")
                    if not tk:
                        continue

                    if ev == "ORDER_CREATED" and "sid=10" in line and ("H1→M1" in line or "H1->M1" in line or "[H1" in line):
                        sig   = fld(line, "signal") or ""
                        entry = fld(line, "entry") or "0"
                        tf    = fld(line, "tf") or "M1"
                        tp    = fld(line, "tp") or "0"
                        sl    = fld(line, "sl") or "0"
                        # ดึง group_id เพื่อหา parent_time
                        gm = re.search(r"group_id=\S+\|(\d+)\|(\d+)\|(\d+)", line)
                        parent_time_unix = int(gm.group(2)) if gm else 0
                        # ดึง HTF tf
                        htf_m = re.search(r"\[(H\w+|M\w+)→M\d+\]", line)
                        htf_tf = htf_m.group(1) if htf_m else "H1"
                        # ดึง parent H/L จาก arm message (ถ้ามี)
                        ph = re.search(r"Parent\[H:([\d.]+)", line)
                        pl = re.search(r"L:([\d.]+)\]", line)
                        creates[tk] = {
                            "ts": ts_str, "ts_unix": _ts_to_unix(ts_str),
                            "signal": sig.upper(), "entry": float(entry),
                            "tf": tf, "htf_tf": htf_tf,
                            "parent_time": parent_time_unix,
                            "parent_high": float(ph.group(1)) if ph else 0.0,
                            "parent_low": float(pl.group(1)) if pl else 0.0,
                            "tp": float(tp), "sl": float(sl),
                        }

                    elif ev == "ORDER_CANCELED" and tk in creates:
                        cancel_ts_unix = _ts_to_unix(ts_str)
                        create_ts_unix = creates[tk]["ts_unix"]
                        delta = cancel_ts_unix - create_ts_unix
                        is_parent_touch = "S10 Parent" in line and "Touch Cancel" in line
                        if is_parent_touch and delta <= 30:  # cancel ภายใน 30 วินาที = immediate
                            results.append({
                                **creates[tk],
                                "cancel_ts": ts_str,
                                "cancel_delta": delta,
                                "cancel_line": line.strip(),
                            })
                        creates.pop(tk, None)
        except Exception:
            pass

    return results

# ─── Simulate fix ─────────────────────────────────────────────────────────────
def sim_fix(order):
    """ตรวจ M1 ตั้งแต่ parent bar CLOSE ว่า H/L ถูกแตะไหม"""
    if not MT5_OK or not mt5:
        return "NO_MT5"
    sig        = order["signal"]
    parent_t   = order["parent_time"]
    htf_tf     = order["htf_tf"]
    p_close    = parent_t + htf_secs(htf_tf)  # parent bar close timestamp
    entry      = order["entry"]
    tp         = order["tp"]
    sl         = order["sl"]
    p_high     = order["parent_high"]
    p_low      = order["parent_low"]
    cancel_unix = _ts_to_unix(order["cancel_ts"])

    # ดึง M1 bars หลัง parent close ไปถึง 48h หลัง cancel
    end_unix = cancel_unix + 48 * 3600
    from_dt  = datetime.fromtimestamp(p_close, tz=timezone.utc)
    to_dt    = datetime.fromtimestamp(end_unix, tz=timezone.utc)
    rates = mt5.copy_rates_range("XAUUSD.iux", mt5.TIMEFRAME_M1, from_dt, to_dt)
    if rates is None or len(rates) == 0:
        return "NO_DATA"

    # 1. ตรวจว่า fix แล้ว parent touch cancel จะยังยิงไหม
    touched_after_close = None
    for r in rates:
        if int(r["time"]) < p_close:
            continue
        if sig == "BUY"  and float(r["high"]) >= p_high:
            touched_after_close = r; break
        if sig == "SELL" and float(r["low"])  <= p_low:
            touched_after_close = r; break

    if touched_after_close:
        t_dt = datetime.fromtimestamp(int(touched_after_close["time"]), UTC6)
        return f"STILL_CANCEL @ {t_dt.strftime('%H:%M %d-%b')}"

    # 2. ถ้าไม่ cancel → ดูว่า TP หรือ SL ถูกแตะก่อน
    if tp <= 0 or sl <= 0:
        return "NO_TP_SL"

    for r in rates:
        if int(r["time"]) < p_close:
            continue
        high, low = float(r["high"]), float(r["low"])
        t_dt = datetime.fromtimestamp(int(r["time"]), UTC6)
        if sig == "BUY":
            if low  <= sl: return f"SL @ {t_dt.strftime('%H:%M %d-%b')}"
            if high >= tp: return f"TP @ {t_dt.strftime('%H:%M %d-%b')}"
        else:  # SELL
            if high >= sl: return f"SL @ {t_dt.strftime('%H:%M %d-%b')}"
            if low  <= tp: return f"TP @ {t_dt.strftime('%H:%M %d-%b')}"

    return "OPEN>48h"

# ─── Main ─────────────────────────────────────────────────────────────────────
print("Parsing logs for S10 Parent Touch Cancel (immediate, H1→M1)...")
orders = parse()
print(f"Found {len(orders)} orders\n")

if not orders:
    print("ไม่พบ order ที่ตรงเงื่อนไข")
    sys.exit(0)

tp_count = sl_count = still_cancel = open_count = nodata = 0

print(f"{'Date':>12} {'Sig':>4} {'Entry':>8} {'HTF':>4} {'Delta':>5}  Fix Result")
print("-" * 70)
for o in orders:
    result = sim_fix(o)
    ts_short = o["ts"][5:16]
    line = (f"{ts_short:>12} {o['signal']:>4} {o['entry']:>8.2f} "
            f"{o['htf_tf']:>4} {o['cancel_delta']:>4}s  {result}")
    print(line)
    if   "TP"           in result: tp_count    += 1
    elif "SL"           in result: sl_count    += 1
    elif "STILL_CANCEL" in result: still_cancel += 1
    elif "OPEN"         in result: open_count  += 1
    else:                          nodata       += 1

n = len(orders)
print(f"\n{'='*70}")
print(f"📊 S10 Parent Touch Cancel Fix — {n} orders")
print(f"   ก่อน fix: ทั้งหมด cancel ทันที (0 วินาที~30 วินาที)")
print(f"   หลัง fix:")
print(f"   ✅ TP  : {tp_count:>3} ({tp_count/n*100:.0f}%) — จะ fill แล้วได้กำไร")
print(f"   ❌ SL  : {sl_count:>3} ({sl_count/n*100:.0f}%) — จะ fill แล้วโดน SL")
print(f"   🔄 STILL_CANCEL: {still_cancel:>3} ({still_cancel/n*100:.0f}%) — ยังโดน cancel หลัง parent close")
print(f"   ⏳ OPEN: {open_count:>3} ({open_count/n*100:.0f}%) — ไม่ทราบผล (ยังเปิดอยู่)")
print(f"   ❓ NO_DATA: {nodata:>3}")

if MT5_OK and mt5:
    mt5.shutdown()
print("\nDone.")
