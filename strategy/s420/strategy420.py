# -*- coding: utf-8 -*-
"""S420 - ZigZag PA Strategy: port ตรงตัวจาก Pine v3 "[STRATEGY][RS]ZigZag PA
Strategy V4.1" (@RichardSwing/JayRogers-derived) มาเป็น detect_s420() ตาม
convention ของโปรเจกต์นี้ (sim_strategy_backtest.py) เพื่อให้ backtest แล้ว
export CSV รายไม้ออกมาไล่เทียบกับ TradingView ได้ทีละไม้

Logic เดียวกับ mql5/ZigZagPA_Lib.mqh + mql5/ZigZagPA_EA.mq5 ที่ทำไปก่อนหน้า
(ตรวจสอบตัวเลขแล้วว่าตรงกับ Pine ทุกจุด: สูตร zigzag แบบ bar-color-flip,
17 harmonic pattern, Fib Entry Window/TP/SL จากขา C-D ล่าสุด) — พอร์ตมาเป็น
Python รอบนี้เพื่อใช้กับ backtest engine ของโปรเจกต์แทน MT5 Strategy Tester
โดยตรง จะได้ debug ทีละไม้ง่ายกว่า (ไม่ต้องพึ่งภาพหน้าจอ/timezone offset)

ข้อแตกต่างจาก Pine ต้นฉบับ ที่ต้อง "ปรับให้เข้ากับ backtest engine ของโปรเจกต์":
  1) Alt Timeframe ยัง aggregate จากแท่ง base-TF (M15 เป็นต้น) เป็นแท่ง
     สังเคราะห์ 60 นาที (ตาม tf="60" ของ Pine) เหมือน MQL5 EA — bucket ตัด
     ทิ้งถ้ายังไม่ครบ (non-repaint)
  2) TP_RATE default เปลี่ยนจาก 0.618 (Pine target01) เป็น 1.618 (เทียบเท่า
     Pine target02_tp_rate) เพราะ engine ของโปรเจกต์นี้บังคับ RR>=1.5 ทุกไม้
     (validate_signal ใน sim_strategy_backtest.py) — TP 0.618 เดิมให้ RR
     ~0.81 เท่านั้น จะโดน engine reject ทุกไม้ ปรับ TP_RATE ได้ผ่าน cfg ถ้า
     อยากลอง rate อื่น (EW_RATE/SL_RATE ยังคงค่า default ของ Pine ไว้เหมือนเดิม)
  3) Exit เป็นแบบ SL/TP นิ่ง (fixed ตอนเข้าไม้ ใช้จนกว่าจะโดน) ตาม engine
     ของโปรเจกต์ — ไม่มี dynamic re-anchoring ตาม pivot ใหม่แบบ Pine/MQL5 EA
     (feature นั้นเป็น quirk เฉพาะของ Pine ที่ engine นี้ไม่รองรับ)
  4) ไม่รองรับ Target1/Target2 คู่ขนาน (โครงสร้าง engine นี้คือ 1 สัญญาณ/ไม้
     ต่อรอบ) — ถ้าจะเทียบ Target2 (EW/TP/SL rate อื่น) ให้รัน backtest แยก
     รอบด้วย --cfg-json คนละชุด
"""

from __future__ import annotations

import os
import sys

# strategy119/strategy197 อยู่ที่ root ของโปรเจกต์ ไม่ใช่ในโฟลเดอร์นี้ (strategy/s420/)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from strategy119 import _bars
from strategy197 import _wait

TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60}

DEFAULT_CFG = {
    "USE_HA": False,
    "USE_ALT_TF": True,
    "ALT_TF_MINUTES": 60,
    "EW_RATE": 0.236,
    # TP_RATE = 0.618 (ค่า Pine ต้นฉบับจริง — ตรงกับ backtest_s420.py's
    # PINE_TARGET1_CFG) — เดิมตั้งเป็น 1.618 เพื่อเลี่ยง RR>=1.5 floor filter
    # ที่ detect_s420() เคยมี (ถอดออกไปแล้ว 2026-08-22 ตอนแก้บั๊ก S421) แต่ลืม
    # เปลี่ยน TP_RATE กลับ ทำให้ live ตั้ง TP ไกลกว่าที่ backtest คำนวณไว้มาก
    # (entry/SL ตรงกันเป๊ะ แต่ TP ต่างกันหลายสิบจุด) ราคาไม่ทันถึง TP ไกลๆ
    # ย้อนกลับมาโดน SL แทน — เจอจาก --compare 7 วัน: backtest ทำนาย +1,063
    # แต่ live จริงขาดทุน -6,248 ในช่วงเดียวกัน ดู [[project-s420-zigzagpa-status]]
    "TP_RATE": 0.618,
    "SL_RATE": -0.236,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "BE_RR": 0.10,
    "CANCEL_BARS": 3,
}


def _aggregate_alt_tf(hist, base_minutes, alt_minutes):
    """รวมแท่ง base-TF เป็นแท่งสังเคราะห์ alt_minutes นาที (bucket ตาม epoch)
    ตัดทิ้งทุก bucket ที่แท่ง base ไม่ครบ (ไม่ใช่แค่ bucket สุดท้าย) — bucket ที่ไม่ครบ
    (เช่น broker มี gap ข้อมูลกลางชั่วโมง) จะได้ close ที่ไม่ใช่ close จริงของช่วงนั้น
    เอามาตัดสินสี/ทิศทางแบบเชื่อถือได้ไม่ได้ ดีกว่าตัดทิ้งไปเลยแล้วปฏิบัติเหมือน gap
    (ยืนยันจากเคสจริง: บั๊กนี้ทำให้ pivot ผูกกับแท่งผิดไปหลายชั่วโมงเมื่อ bucket
    กลางทางไม่ครบระหว่างเจอ gap รายวันของ broker)"""
    if alt_minutes <= base_minutes:
        return list(hist)
    bucket_seconds = alt_minutes * 60
    bars_per_bucket = max(1, alt_minutes // base_minutes)
    buckets, order, counts = {}, [], {}
    for bar in hist:
        bucket_start = (bar["time"] // bucket_seconds) * bucket_seconds
        if bucket_start not in buckets:
            buckets[bucket_start] = {
                "time": bucket_start, "open": bar["open"], "high": bar["high"],
                "low": bar["low"], "close": bar["close"], "tick_volume": bar["tick_volume"],
            }
            order.append(bucket_start)
            counts[bucket_start] = 1
        else:
            slot = buckets[bucket_start]
            slot["high"] = max(slot["high"], bar["high"])
            slot["low"] = min(slot["low"], bar["low"])
            slot["close"] = bar["close"]
            slot["tick_volume"] += bar["tick_volume"]
            counts[bucket_start] += 1

    return [buckets[t] for t in order if counts[t] >= bars_per_bucket]


def _heikin_ashi(bars):
    """แปลง OHLC ดิบเป็น Heikin Ashi (สูตรมาตรฐาน)."""
    out = []
    ha_open_prev = ha_close_prev = None
    for bar in bars:
        ha_close = (bar["open"] + bar["high"] + bar["low"] + bar["close"]) / 4.0
        ha_open = (bar["open"] + bar["close"]) / 2.0 if ha_open_prev is None else (ha_open_prev + ha_close_prev) / 2.0
        ha_high = max(bar["high"], ha_open, ha_close)
        ha_low = min(bar["low"], ha_open, ha_close)
        out.append({"time": bar["time"], "open": ha_open, "high": ha_high, "low": ha_low,
                     "close": ha_close, "tick_volume": bar["tick_volume"]})
        ha_open_prev, ha_close_prev = ha_open, ha_close
    return out


def _compute_zigzag(bars):
    """ZigZag แบบ bar-color-flip ของ Pine — คืน list[(index, value)] เก่า->ใหม่
    ยอด(highest 2)/ก้น(lowest 2) เฉพาะตอนสีแท่งกลับด้านและทิศทางก่อนหน้าไม่ตรง.

    ถ้าแท่ง H1 หายไปทั้งแท่ง (bucket ว่างเปล่า เช่น broker ไม่มีข้อมูลช่วงนั้นเลย)
    bars[i-1] กับ bars[i] จะไม่ใช่แท่งติดกันจริง — ต้อง reset การเทียบ (ข้าม
    การตัดสินกลับสี/ทิศทางสำหรับคู่นี้ไปเลย) แทนที่จะเทียบข้ามช่องว่างแบบผิดๆ
    ซึ่งอาจสร้าง/บัง pivot ที่ไม่ควรมี/ควรมีได้"""
    pivots = []
    direction = 0
    expected_gap = None
    for i in range(1, len(bars)):
        actual_gap = bars[i]["time"] - bars[i-1]["time"]
        if expected_gap is None:
            expected_gap = actual_gap
        elif actual_gap > expected_gap * 1.5:
            # แท่งหายไปทั้งแท่งระหว่างกลาง — ไม่ถือว่า i-1 กับ i ติดกันจริง
            direction = 0  # ไม่รู้ทิศทางที่แท้จริงอีกต่อไป รอ flip ใหม่หลัง gap
            continue

        prev_up = bars[i-1]["close"] >= bars[i-1]["open"]
        prev_down = bars[i-1]["close"] <= bars[i-1]["open"]
        cur_up = bars[i]["close"] >= bars[i]["open"]
        cur_down = bars[i]["close"] <= bars[i]["open"]

        if prev_up and cur_down and direction != -1:
            pivots.append((i, max(bars[i-1]["high"], bars[i]["high"])))
        elif prev_down and cur_up and direction != 1:
            pivots.append((i, min(bars[i-1]["low"], bars[i]["low"])))

        if prev_up and cur_down:
            direction = -1
        elif prev_down and cur_up:
            direction = 1
    return pivots


def _ratios(x, a, b, c, d):
    denom_xa, denom_ab, denom_bc = abs(x - a), abs(a - b), abs(b - c)
    if denom_xa == 0.0 or denom_ab == 0.0 or denom_bc == 0.0:
        return None
    return (abs(b - a) / denom_xa, abs(a - d) / denom_xa,
            abs(b - c) / denom_ab, abs(c - d) / denom_bc)


def _dir_ok(mode, d, c):
    return d < c if mode == 1 else d > c


def _is_abcd(mode, _xab, _xad, abc, bcd, d, c):
    return 0.382 <= abc <= 0.886 and 1.13 <= bcd <= 2.618 and _dir_ok(mode, d, c)


def _is_bat(mode, xab, xad, abc, bcd, d, c):
    return (0.382 <= xab <= 0.5 and 0.382 <= abc <= 0.886 and 1.618 <= bcd <= 2.618
            and xad <= 0.618 and xad <= 1.000 and _dir_ok(mode, d, c))


def _is_antibat(mode, xab, xad, abc, bcd, d, c):
    return (0.500 <= xab <= 0.886 and 1.000 <= abc <= 2.618 and 1.618 <= bcd <= 2.618
            and 0.886 <= xad <= 1.000 and _dir_ok(mode, d, c))


def _is_altbat(mode, xab, xad, abc, bcd, d, c):
    return (xab <= 0.382 and 0.382 <= abc <= 0.886 and 2.0 <= bcd <= 3.618
            and xad <= 1.13 and _dir_ok(mode, d, c))


def _is_butterfly(mode, xab, xad, abc, bcd, d, c):
    return (xab <= 0.786 and 0.382 <= abc <= 0.886 and 1.618 <= bcd <= 2.618
            and 1.27 <= xad <= 1.618 and _dir_ok(mode, d, c))


def _is_antibutterfly(mode, xab, xad, abc, bcd, d, c):
    return (0.236 <= xab <= 0.886 and 1.130 <= abc <= 2.618 and 1.000 <= bcd <= 1.382
            and 0.500 <= xad <= 0.886 and _dir_ok(mode, d, c))


def _is_gartley(mode, xab, xad, abc, bcd, d, c):
    return (0.5 <= xab <= 0.618 and 0.382 <= abc <= 0.886 and 1.13 <= bcd <= 2.618
            and 0.75 <= xad <= 0.875 and _dir_ok(mode, d, c))


def _is_antigartley(mode, xab, xad, abc, bcd, d, c):
    return (0.500 <= xab <= 0.886 and 1.000 <= abc <= 2.618 and 1.500 <= bcd <= 5.000
            and 1.000 <= xad <= 5.000 and _dir_ok(mode, d, c))


def _is_crab(mode, xab, xad, abc, bcd, d, c):
    return (0.500 <= xab <= 0.875 and 0.382 <= abc <= 0.886 and 2.000 <= bcd <= 5.000
            and 1.382 <= xad <= 5.000 and _dir_ok(mode, d, c))


def _is_anticrab(mode, xab, xad, abc, bcd, d, c):
    return (0.250 <= xab <= 0.500 and 1.130 <= abc <= 2.618 and 1.618 <= bcd <= 2.618
            and 0.500 <= xad <= 0.750 and _dir_ok(mode, d, c))


def _is_shark(mode, xab, xad, abc, bcd, d, c):
    return (0.500 <= xab <= 0.875 and 1.130 <= abc <= 1.618 and 1.270 <= bcd <= 2.240
            and 0.886 <= xad <= 1.130 and _dir_ok(mode, d, c))


def _is_antishark(mode, xab, xad, abc, bcd, d, c):
    return (0.382 <= xab <= 0.875 and 0.500 <= abc <= 1.000 and 1.250 <= bcd <= 2.618
            and 0.500 <= xad <= 1.250 and _dir_ok(mode, d, c))


def _is_5o(mode, xab, xad, abc, bcd, d, c):
    return (1.13 <= xab <= 1.618 and 1.618 <= abc <= 2.24 and 0.5 <= bcd <= 0.625
            and 0.0 <= xad <= 0.236 and _dir_ok(mode, d, c))


def _is_wolf(mode, xab, xad, abc, bcd, d, c):
    return (1.27 <= xab <= 1.618 and 0 <= abc <= 5 and 1.27 <= bcd <= 1.618
            and 0.0 <= xad <= 5 and _dir_ok(mode, d, c))


def _is_hns(mode, xab, xad, abc, bcd, d, c):
    return (2.0 <= xab <= 10 and 0.90 <= abc <= 1.1 and 0.236 <= bcd <= 0.88
            and 0.90 <= xad <= 1.1 and _dir_ok(mode, d, c))


def _is_contria(mode, xab, xad, abc, bcd, d, c):
    return (0.382 <= xab <= 0.618 and 0.382 <= abc <= 0.618 and 0.382 <= bcd <= 0.618
            and 0.236 <= xad <= 0.764 and _dir_ok(mode, d, c))


def _is_exptria(mode, xab, xad, abc, bcd, d, c):
    return (1.236 <= xab <= 1.618 and 1.000 <= abc <= 1.618 and 1.236 <= bcd <= 2.000
            and 2.000 <= xad <= 2.236 and _dir_ok(mode, d, c))


_PATTERN_CHECKS = (
    ("ABCD", _is_abcd), ("Bat", _is_bat), ("AltBat", _is_altbat),
    ("Butterfly", _is_butterfly), ("Gartley", _is_gartley), ("Crab", _is_crab),
    ("Shark", _is_shark), ("5-O", _is_5o), ("Wolf Wave", _is_wolf),
    ("Head and Shoulders", _is_hns), ("Contracting Triangle", _is_contria),
    ("Expanding Triangle", _is_exptria),
    ("Anti Bat", _is_antibat), ("Anti Butterfly", _is_antibutterfly),
    ("Anti Gartley", _is_antigartley), ("Anti Crab", _is_anticrab),
    ("Anti Shark", _is_antishark),
)


def _matched_pattern(mode, xab, xad, abc, bcd, d, c):
    for name, fn in _PATTERN_CHECKS:
        if fn(mode, xab, xad, abc, bcd, d, c):
            return name
    return None


def _last_fib(rate, d, c):
    fib_range = abs(d - c)
    return d - fib_range * rate if d > c else d + fib_range * rate


def compute_zigzag_state(rates, tf="", cfg=None):
    """คำนวณ pivot/pattern/Fib state ปัจจุบัน (ไม่ตัดสินใจเปิดไม้) — ใช้ร่วมกัน
    ทั้งใน detect_s420() (โหมด one-shot ของ engine กลาง) และใน
    backtest_s420.py (โหมด stateful ต่อเนื่องทุกบาร์ เหมือน Pine/MQL5 EA จริง
    ที่ต้องเช็ค TP/SL/pattern ใหม่ทุกบาร์ ไม่ใช่แค่ตอนเปิดไม้ครั้งเดียว)

    คืน dict {event, x,a,b,c,d, bull_name, bear_name, fib_ew, fib_tp, fib_sl}
    หรือ (None, เหตุผล) ถ้าข้อมูล/config ไม่พอ."""
    c_cfg = dict(DEFAULT_CFG)
    if cfg:
        c_cfg.update(cfg)
    try:
        use_ha = bool(c_cfg["USE_HA"])
        use_alt_tf = bool(c_cfg["USE_ALT_TF"])
        alt_tf_minutes = max(1, int(c_cfg["ALT_TF_MINUTES"]))
        ew_rate = float(c_cfg["EW_RATE"])
        tp_rate = float(c_cfg["TP_RATE"])
        sl_rate = float(c_cfg["SL_RATE"])
    except (KeyError, TypeError, ValueError) as exc:
        return None, f"Invalid config: {exc}"

    base_minutes = TF_MINUTES.get(str(tf).upper())
    if base_minutes is None:
        return None, f"Unsupported tf {tf}"

    if rates is None or len(rates) < 30:
        return None, "Not enough data"
    try:
        bars = _bars(rates)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return None, f"Invalid rates: {exc}"

    event = bars[-1]
    hist = bars[:-1]

    alt_minutes = alt_tf_minutes if use_alt_tf else base_minutes
    calc_bars = _aggregate_alt_tf(hist, base_minutes, alt_minutes)
    if use_ha:
        calc_bars = _heikin_ashi(calc_bars)
    if len(calc_bars) < 10:
        return None, "Not enough aggregated bars for zigzag"

    pivots = _compute_zigzag(calc_bars)
    if len(pivots) < 5:
        return None, "Not enough zigzag pivots (need 5)"

    x, a, b, cc, d = (val for _, val in pivots[-5:])
    ratios = _ratios(x, a, b, cc, d)
    if ratios is None:
        return None, "Degenerate pivot ratios (zero denominator)"
    xab, xad, abc, bcd = ratios

    bull_name = _matched_pattern(1, xab, xad, abc, bcd, d, cc)
    bear_name = _matched_pattern(-1, xab, xad, abc, bcd, d, cc)

    return {
        "event": event, "x": x, "a": a, "b": b, "c": cc, "d": d,
        "bull_name": bull_name, "bear_name": bear_name,
        "fib_ew": _last_fib(ew_rate, d, cc),
        "fib_tp": _last_fib(tp_rate, d, cc),
        "fib_sl": _last_fib(sl_rate, d, cc),
    }, None


def detect_s420(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S420 ZigZag PA — bar-color-flip zigzag + 17 harmonic pattern บนขา
    X-A-B-C-D ล่าสุด + Fib Entry Window/TP/SL จากขา C-D (ดู docstring บนสุด
    ของไฟล์นี้สำหรับรายละเอียดที่ปรับให้เข้ากับ engine ของโปรเจกต์).

    order_type="limit" เสมอ (entry=fib_ew พอดี ไม่ใช่ close ปัจจุบัน) — เปลี่ยน
    จาก market เป็น limit ตาม backtest_s420.py ที่ยืนยันแล้วว่า limit ที่ fib_ew
    ให้ P&L/WinRate/PF ดีกว่า market ทุก TF/ช่วงเวลาที่ทดสอบ (ดู
    strategy/s420/backtest_s420.py) เงื่อนไขจึงเปลี่ยนจาก "close ต้องอยู่ในโซน
    EW แล้ว" (market) เป็น "pattern match ก็พอ" (limit — รอราคาย้อนมาแตะ fib_ew
    เอง)."""
    del dt_bkk, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    state, err = compute_zigzag_state(rates, tf, c)
    if state is None:
        return _wait(err)

    x, a, b, cc, d = state["x"], state["a"], state["b"], state["c"], state["d"]
    bull_name, bear_name = state["bull_name"], state["bear_name"]
    fib_ew, tp_rate, sl_rate = state["fib_ew"], float(c["TP_RATE"]), float(c["SL_RATE"])

    side, pattern_name = 0, None
    if bull_name:
        side, pattern_name = 1, bull_name
    elif bear_name:
        side, pattern_name = -1, bear_name

    if side == 0:
        return _wait(f"No pattern match (bull={bull_name} bear={bear_name} EW={fib_ew:.2f})")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")

    entry = round(fib_ew, 2)
    sl = round(_last_fib(sl_rate, d, cc), 2)
    tp = round(_last_fib(tp_rate, d, cc), 2)

    risk = side * (entry - sl)
    reward = side * (tp - entry)
    if risk <= 0.0 or reward <= 0.0:
        return _wait(f"Invalid risk/reward geometry (risk={risk:.2f} reward={reward:.2f})")
    # RR>=1.5 floor (เดิมมีไว้ผ่าน validate_signal ของ sim_strategy_backtest.py
    # engine กลาง) ถอดออก 2026-08-22: demo_portfolio.py (live จริง) เรียก
    # detect_s420() ตรงๆ ไม่ผ่าน engine กลางเลย ไม่จำเป็นต้องมี floor นี้ —
    # backtest_s420.py ก็หลบ filter นี้มาตลอดอยู่แล้ว (เรียก compute_zigzag_state
    # ตรงๆ ไม่เรียก detect_s420) ตัวเลขกำไรทั้งหมดที่ตัดสินใจ deploy live ไม่เคย
    # ผ่าน filter นี้เลย — เจอจาก S421 ที่ RR floor กรองสัญญาณทิ้งเกือบ 100%
    # (0/360 pattern match ผ่านทั้งเดือน) ทำให้ S421 ไม่เทรดเลยทั้งที่ backtest
    # เจอสัญญาณเพียบ ดู [[project-s420-zigzagpa-status]] ในความจำ

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S420 {signal} {pattern_name}",
        "reason": (f"{pattern_name} X={x:.2f} A={a:.2f} B={b:.2f} C={cc:.2f} D={d:.2f} "
                   f"EW={fib_ew:.2f}"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
