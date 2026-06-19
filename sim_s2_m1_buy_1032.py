"""
sim_s2_m1_buy_1032.py — backtest แบบ replay จริง สำหรับ S2 M1 FVG BUY ที่ถูก
sweep_high_block_buy block ตอน 10:32 18-Jun-2026

ใช้ฟังก์ชันจริงจาก strategy1.py / strategy2.py / strategy3.py
+ ข้อมูล M1 จริงจาก MT5 (ไม่ใช่ข้อมูลสมมติ)

ไม่แตะไฟล์เดิม — standalone script, อ่านอย่างเดียว (read-only กับ MT5)
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone

import config
from strategy1 import strategy_1
from strategy2 import strategy_2, detect_fvg
from strategy3 import strategy_3
from mt5_utils import find_swing_tp

SYMBOL = "XAUUSD.iux"
TZ_OFFSET = config.TZ_OFFSET       # 7
SERVER_TZ = config.MT5_SERVER_TZ   # 1
BKK_MINUS_QUERY_OFFSET = TZ_OFFSET - SERVER_TZ  # 6h: bkk = server_epoch_as_utc + 6h

assert mt5.initialize(), "MT5 connect failed"


def bkk_to_query_dt(bkk_dt: datetime) -> datetime:
    """แปลง BKK datetime (naive) -> tz-aware UTC datetime สำหรับส่งให้ copy_rates_range
    ต้องใส่ tzinfo=utc ชัดเจน (ห้ามส่ง naive — wrapper จะตีความผ่าน local mktime() ผิดเพี้ยน)"""
    return (bkk_dt - timedelta(hours=BKK_MINUS_QUERY_OFFSET)).replace(tzinfo=timezone.utc)


def server_ts_to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc) + timedelta(hours=BKK_MINUS_QUERY_OFFSET)


# ── ดึง M1 rates จริง BKK 09:00–12:30 18-Jun-2026 ──────────────────────────
q_start = bkk_to_query_dt(datetime(2026, 6, 18, 9, 0))
q_end   = bkk_to_query_dt(datetime(2026, 6, 18, 12, 30))
raw = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, q_start, q_end)
assert raw is not None and len(raw) > 0, "no rates returned"

bars = []
for r in raw:
    bkk_t = server_ts_to_bkk(r["time"])
    bars.append({
        "time": int(r["time"]), "bkk": bkk_t,
        "open": float(r["open"]), "high": float(r["high"]),
        "low": float(r["low"]), "close": float(r["close"]),
        "tick_volume": r["tick_volume"],
        "real_volume": r["real_volume"], "spread": r["spread"],
    })

print(f"Loaded {len(bars)} M1 bars, {bars[0]['bkk'].strftime('%H:%M')} -> {bars[-1]['bkk'].strftime('%H:%M')}")

# cross-check กับ log: bar ปิด 10:30 ควรเป็น O:4314.68 H:4318.18 L:4313.84 C:4317.52
chk = next((b for b in bars if b["bkk"].strftime("%H:%M") == "10:30"), None)
if chk:
    print(f"cross-check 10:30 bar: O:{chk['open']} H:{chk['high']} L:{chk['low']} C:{chk['close']}  "
          f"(ค่าจาก log: O:4314.68 H:4318.18 L:4313.84 C:4317.52)")
print()


# ── helper: copy ของ _has_swing_in_lookback / _find_recent_signal_confirmation จาก scanner.py ──

def has_swing_in_lookback(rates, signal, lookback_bars=8):
    if rates is None or len(rates) < 3:
        return False
    signal = str(signal or "").upper()
    check = rates[-(lookback_bars + 2):]
    for i in range(1, len(check) - 1):
        if signal == "BUY":
            if check[i]["low"] <= check[i-1]["low"] and check[i]["low"] <= check[i+1]["low"]:
                return True
        elif signal == "SELL":
            if check[i]["high"] >= check[i-1]["high"] and check[i]["high"] >= check[i+1]["high"]:
                return True
    return False


def find_recent_signal_confirmation(rates, signal, tf_secs, lookback_bars):
    lookback_bars = max(0, int(lookback_bars or 0))
    if lookback_bars <= 0 or rates is None or len(rates) < 4:
        return None
    signal = str(signal or "").upper()
    matches = []
    checkers = ((1, strategy_1), (2, strategy_2), (3, strategy_3))
    for bars_back in range(1, lookback_bars + 1):
        end_idx = len(rates) - bars_back
        if end_idx < 3:
            break
        sliced = rates[:end_idx]
        confirm_bar_time = int(sliced[-1]["time"])
        detect_time = confirm_bar_time + int(tf_secs or 0)
        for sid, checker in checkers:
            try:
                result = checker(sliced)
            except Exception:
                continue
            if sid == 2:
                if str(result.get("signal", "")).upper() != "FVG_DETECTED":
                    continue
                fvg = result.get("fvg") or {}
                if str(fvg.get("signal", "")).upper() != signal:
                    continue
            else:
                if str(result.get("signal", "")).upper() != signal:
                    continue
            matches.append({"sid": sid, "bars_back": bars_back, "detect_time": detect_time})
    if not matches:
        return None
    matches.sort(key=lambda item: (item["detect_time"], -item["sid"]), reverse=True)
    return matches[0]


# ── replay: เดินทีละ bar, จำลอง scan cycle ของ scanner.py สำหรับ S2 M1 BUY ──
TF_SECS = 60
lookback_fallback_start = None  # _key_s2 timer (ใน prod เก็บ dict ข้าม tf/sid/signal — ที่นี่ track ตัวเดียวเพราะ sim เฉพาะ M1 BUY)

print("=" * 78)
print("REPLAY S2 M1 FVG BUY ตั้งแต่ sweep_high หาย (10:32) เป็นต้นไป")
print("=" * 78)

order_placed = False
order_info = None

for i in range(30, len(bars)):
    cur_bkk = bars[i]["bkk"]
    if cur_bkk.strftime("%H:%M") < "10:32":
        continue
    if order_placed:
        break

    rates_slice = bars[:i+1]  # รวม bar ที่ปิดล่าสุด = [0]

    r2 = strategy_2(rates_slice, tf="M1")
    if r2.get("signal") != "FVG_DETECTED":
        continue

    fvg = r2["fvg"]
    if fvg["signal"] != "BUY":
        continue

    # sweep_high gate: จาก sim ก่อนหน้า (sim_sweep_fix.py) sweep_high M1 ไม่ active ในช่วงนี้แล้ว (fix applied) -> PASS
    print(f"[{cur_bkk.strftime('%H:%M')}] FVG_DETECTED BUY | entry(98%)={fvg['entry']} sl={fvg['sl']} "
          f"gap=[{fvg['gap_bot']:.2f},{fvg['gap_top']:.2f}] pattern={fvg['pattern']}")

    # ── S2 confirm-lookback gate (M1-only, parallel_tfs ถือว่า=1) ──
    confirm = find_recent_signal_confirmation(rates_slice, "BUY", TF_SECS, 8)
    if not confirm:
        if lookback_fallback_start is None:
            lookback_fallback_start = bars[i]["time"]
        bars_waited = (bars[i]["time"] - lookback_fallback_start) // TF_SECS
        if bars_waited >= 4 and has_swing_in_lookback(rates_slice, "BUY", 8):
            print(f"    -> confirm: ไม่เจอ S1/S2/S3 ตรงๆ แต่ fallback ผ่าน (waited={bars_waited} bars, swing in lookback=True)")
            confirm = {"sid": 0, "swing_fallback": True}
        else:
            print(f"    -> confirm: ยังไม่ผ่าน (waited={bars_waited} bars, need>=4 + swing in lookback) -> WAIT, ยังไม่ตั้ง order")
            continue
    else:
        print(f"    -> confirm: เจอ sid={confirm['sid']} ({confirm['bars_back']} bars back) -> ผ่าน")

    # ── คำนวณ final_entry ตามสูตร scanner.py (ไม่มี parallel TF อื่นมาซ้อน) ──
    gap_bot, gap_top = fvg["gap_bot"], fvg["gap_top"]
    gap_size = gap_top - gap_bot
    final_entry = round(gap_bot + gap_size * 0.98, 2)
    sl = fvg["sl"]

    tp = find_swing_tp(rates_slice, "BUY", final_entry, sl, tf="") or round(final_entry + abs(final_entry - sl), 2)

    print(f"[{cur_bkk.strftime('%H:%M')}] >>> ORDER (sim) S2 M1 BUY LIMIT  entry={final_entry}  sl={sl}  tp={tp}")
    order_placed = True
    order_info = {"entry": final_entry, "sl": sl, "tp": tp, "placed_at": cur_bkk, "placed_idx": i}

if not order_placed:
    print("\n*** ไม่มี order ถูกตั้งเลยในช่วงข้อมูลที่ดึงมา (09:00-12:30) ***")
    mt5.shutdown()
    sys.exit(0)

# ── simulate fill + SL/TP จาก bar ถัดไป ──────────────────────────────────
print()
print("=" * 78)
print("SIMULATE FILL / SL / TP")
print("=" * 78)

entry, sl, tp = order_info["entry"], order_info["sl"], order_info["tp"]
filled = False
fill_bkk = None
result = None
result_price = None

for b in bars[order_info["placed_idx"]+1:]:
    if not filled:
        if b["low"] <= entry <= b["high"]:
            filled = True
            fill_bkk = b["bkk"]
            print(f"[{b['bkk'].strftime('%H:%M')}] FILLED at {entry} (bar L:{b['low']} H:{b['high']})")
        continue
    # หลัง fill แล้ว เช็ค SL/TP (ลำดับ: ดู low ก่อนถ้า SL ต่ำกว่า entry)
    if b["low"] <= sl:
        result = "SL HIT"
        result_price = sl
        print(f"[{b['bkk'].strftime('%H:%M')}] SL HIT at {sl} (bar L:{b['low']})")
        break
    if b["high"] >= tp:
        result = "TP HIT"
        result_price = tp
        print(f"[{b['bkk'].strftime('%H:%M')}] TP HIT at {tp} (bar H:{b['high']})")
        break

if not filled:
    print("ORDER ไม่ FILL เลยในช่วงข้อมูลที่มี (ราคาไม่ย้อนมาแตะ entry)")
elif result is None:
    last_close = bars[-1]["close"]
    pnl_pt = last_close - entry
    print(f"ยังไม่ปิด (ข้อมูลหมด) — close ล่าสุด {last_close} -> unrealized {pnl_pt:+.2f} pt")
else:
    pnl_pt = (result_price - entry) if result == "TP HIT" else (result_price - entry)
    print()
    print(f"สรุป: entry={entry} -> {result} @ {result_price}  => P&L = {pnl_pt:+.2f} pt (XAUUSD, ต่อ 1.0 lot = ${pnl_pt*100:+.2f}, ต่อ 0.01 lot = ${pnl_pt:+.2f})")

mt5.shutdown()
