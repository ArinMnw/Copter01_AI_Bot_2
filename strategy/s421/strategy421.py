# -*- coding: utf-8 -*-
"""S421 - ZigZag PA Strategy: port ตรงตัวจาก Pine v3 "[STRATEGY][RS]ZigZag PA
Strategy V4" (เวอร์ชัน "เก่ากว่า" V4.1 ที่พอร์ตไปแล้วเป็น S420 — ตรวจสอบทีละ
บรรทัดแล้วว่า zigzag/17 pattern เหมือน V4.1 ทุกจุดเป๊ะ ต่างกันแค่ default Fib
rate ของ Entry Window/TP/SL เท่านั้น) เก็บเป็นไฟล์แยกต่างหากตามที่พี่เลือก
(ไม่ผสมกับ S420 เพื่อให้ config/CSV ของสองเวอร์ชันไม่ปนกัน)

logic หลักทั้งหมด (zigzag bar-color-flip, 17 harmonic pattern, alt-tf
aggregation แบบ non-repaint, gap-handling fix) ใช้ร่วมกับ strategy420.py
ตรงๆ ไม่ก็อปโค้ดซ้ำ — เพราะพิสูจน์แล้วว่าเหมือนกัน 100%, มีแค่ default rate
ที่ต่าง:

    | rate     | S420 (V4.1) | S421 (V4)  |
    |----------|-------------|------------|
    | EW_RATE  | 0.236       | 0.382      |
    | TP_RATE  | 0.618       | 0.618      |
    | SL_RATE  | -0.236      | -0.618     |
"""

from __future__ import annotations

import os
import sys

# strategy197 อยู่ที่ root, strategy420 อยู่ใน strategy/s420/ — คนละโฟลเดอร์กับไฟล์นี้ (strategy/s421/)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_S420_DIR = os.path.join(_ROOT, "strategy", "s420")
for _p in (_ROOT, _S420_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from strategy197 import _wait
from strategy420 import _last_fib, compute_zigzag_state

DEFAULT_CFG = {
    "USE_HA": False,
    "USE_ALT_TF": True,
    "ALT_TF_MINUTES": 60,
    "EW_RATE": 0.382,
    # TP_RATE = 0.618 (ค่า Pine ต้นฉบับจริง — ตรงกับ backtest_s421.py's
    # PINE_V4_CFG) — เดิมตั้งเป็น 1.618 เพื่อเลี่ยง RR>=1.5 floor filter ที่
    # detect_s421() เคยมี (ถอดออกไปแล้ว 2026-08-22) แต่ลืมเปลี่ยน TP_RATE กลับ
    # ทำให้ live ตั้ง TP ไกลกว่าที่ backtest คำนวณไว้มาก (เจอบั๊กเดียวกันกับ
    # S420 ผ่าน --compare 7 วัน ดู strategy/s420/strategy420.py)
    "TP_RATE": 0.618,
    "SL_RATE": -0.618,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "BE_RR": 0.10,
    "CANCEL_BARS": 3,
}


def detect_s421(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S421 ZigZag PA (Pine V4 rate เก่า) — logic เดียวกับ detect_s420() ทุก
    จุด ต่างแค่ default EW/SL rate (ดู docstring บนสุดของไฟล์นี้)

    order_type="limit" เสมอ (entry=fib_ew พอดี) — เปลี่ยนจาก market ตาม
    backtest_s421.py ที่ยืนยันแล้วว่า limit ที่ fib_ew ดีกว่า market ทุก TF/
    ช่วงเวลาที่ทดสอบ (เหมือน S420 เป๊ะ ดู strategy/s420/strategy420.py)."""
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
    # RR>=1.5 floor ถอดออก 2026-08-22 — ดูเหตุผลเต็มใน strategy420.py's
    # detect_s420() (จุดเดียวกันเป๊ะ) กรณี S421 คือตัวที่เจอปัญหาจริง: filter
    # นี้กรอง pattern match ทิ้งเกือบ 100% (0/360 ผ่านทั้งเดือน) ทำให้ไม่เทรด
    # เลยทั้งเดือนทั้งที่ backtest_s421.py (ซึ่งหลบ filter นี้อยู่แล้ว) เจอ
    # สัญญาณเพียบในช่วงเวลาเดียวกัน

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S421 {signal} {pattern_name}",
        "reason": (f"{pattern_name} X={x:.2f} A={a:.2f} B={b:.2f} C={cc:.2f} D={d:.2f} "
                   f"EW={fib_ew:.2f}"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
