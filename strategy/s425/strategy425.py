# -*- coding: utf-8 -*-
"""S425 - D1 Candle Color Reversal (ไอเดียของพี่ ไม่ได้พอร์ตจาก Pine ต้นฉบับไหน) —
ดูสีของแท่ง D1 ล่าสุดที่ปิดสมบูรณ์แล้ว (non-repaint): close > open = เขียว =
ถือ BUY, close < open = แดง = ถือ SELL, สีเดิมถือต่อ สีเปลี่ยนสลับทิศทันที
(reversal ล้วนๆ ไม่มี SL/TP เหมือน S424) มีไม้ได้แค่ 1 ไม้ต่อครั้ง

ใช้ daily-bucket + rollover-offset เดียวกับ strategy424.py (rollover จริงที่
raw epoch hour=23 = true BKK 05:00 — ยืนยันด้วยข้อมูลจริงเทียบ TradingView ตอน
พอร์ต S424 แล้ว ใช้ค่าเดียวกันตรงนี้เพื่อความสอดคล้อง)

⚠️ 2026-08-13: เคยลองเปลี่ยนเป็น "ดูสีแท่งแรกของวัน" (แท่งแรกบน TF ที่ใช้อยู่
เท่านั้น ตัดสินไวขึ้นมาก เช่น M1 ตัดสินได้ตั้งแต่นาทีแรก) แต่ backtest ยืนยันแล้ว
ว่า**แย่กว่าเดิมทุก TF** (ติดลบหมด PF 0.32-0.66) เพราะแท่งเดียวมี noise สูงเกิน
ไปที่จะทำนายทิศทางทั้งวันได้แม่น — พี่เลือกกลับมาใช้ D1 เต็มวันเป็นหลักแล้ว (บวก
ทุก TF ตอน validate) ไฟล์นี้จึงกลับไปเป็นเวอร์ชัน D1 เต็มวันเหมือนเดิม"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_S424_DIR = os.path.join(_ROOT, "strategy", "s424")
for _p in (_ROOT, _S424_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from strategy119 import _atr, _bars, _wait
from strategy424 import _aggregate_daily

TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60}

DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SL_ATR_MULT": 2.0,     # safety net เท่านั้น (ต้นฉบับไอเดียไม่มี SL/TP เหมือน S424)
    "TP_RR": 1.5,
    "USE_ATR_STOP": False,  # default ปิด — ตรงไอเดียเดิม (reversal-only)
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "BE_RR": None,
    "CANCEL_BARS": None,
}


def compute_state(rates, tf="", cfg=None):
    """คืน (state, None) หรือ (None, เหตุผล). state = {"event","buying",
    "day_open","day_close"} — buying=True (เขียว/BUY) หรือ False (แดง/SELL)
    ของแท่ง D1 ล่าสุดที่ปิดสมบูรณ์แล้ว (ต้องการแค่ 1 daily bucket ไม่ใช่ 2 แบบ S424
    เพราะเทียบ close-vs-open ของแท่งเดียวกัน ไม่ใช่เทียบข้ามวัน)"""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    base_minutes = TF_MINUTES.get(str(tf).upper())
    if base_minutes is None:
        return None, f"Unsupported tf {tf}"

    if rates is None or len(rates) < 30:
        return None, "Not enough data"
    try:
        bars = _bars(rates)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return None, f"Invalid rates: {exc}"

    daily = _aggregate_daily(bars, base_minutes)
    if len(daily) < 1:
        return None, "Not enough complete daily bars (need 1)"

    last_day = daily[-1]
    day_open, day_close = last_day["open"], last_day["close"]
    if day_close > day_open:
        buying = True
    elif day_close < day_open:
        buying = False
    else:
        return None, "D1 close == open (doji) — no clear color"

    return {"event": bars[-1], "buying": buying, "day_open": day_open, "day_close": day_close}, None


def detect_s425(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S425 D1 Candle Color Reversal — ดู docstring บนสุดของไฟล์นี้"""
    del dt_bkk, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    state, err = compute_state(rates, tf, c)
    if state is None:
        return _wait(err)

    signal = "BUY" if state["buying"] else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")

    try:
        bars = _bars(rates)
        atr_period = int(c["ATR_PERIOD"])
        sl_mult = float(c["SL_ATR_MULT"])
        tp_rr = max(1.5, float(c["TP_RR"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid cfg/rates: {exc}")

    atr = _atr(bars, atr_period)
    if atr <= 0.0:
        return _wait("ATR is zero")

    entry = round(state["event"]["close"], 2)
    risk = atr * sl_mult
    sl = round(entry - risk, 2) if signal == "BUY" else round(entry + risk, 2)
    tp = round(entry + risk * tp_rr, 2) if signal == "BUY" else round(entry - risk * tp_rr, 2)

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S425 {signal} D1 Candle Color",
        "reason": f"D1 open={state['day_open']:.2f} close={state['day_close']:.2f} ATR={atr:.2f}",
        "be_rr": c["BE_RR"],
        "cancel_bars": c["CANCEL_BARS"],
    }
