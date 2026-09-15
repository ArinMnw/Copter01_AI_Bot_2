# -*- coding: utf-8 -*-
"""S426 - Pivot Reversal Stop-Breakout (พอร์ตจาก Pine v4 "Monthly Returns in
PineScript Strategies") — ใช้ pivothigh/pivotlow (leftBars=2, rightBars=1) หา
จุด swing high/low ล่าสุดที่ยืนยันแล้ว (non-repaint, ต้องรอ rightBars แท่ง
ถัดไปปิดก่อนถึงจะยืนยัน pivot ได้) แล้ว "แขวน" stop order ไว้:
  - pivot high ใหม่ยืนยัน -> แขวน BUY STOP ที่ hprice+tick, ยกเลิกเองเมื่อราคา
    breakout ผ่าน (high > hprice) แล้วเปลี่ยนไปรอ pivot ใหม่
  - pivot low ใหม่ยืนยัน -> แขวน SELL STOP ที่ lprice-tick เช่นกัน (ทิศตรงข้าม)
มีได้ไม้เดียวต่อครั้ง — ถ้า trigger ทิศตรงข้ามกับไม้ที่ถืออยู่ = reversal
(ปิดไม้เดิมที่ราคา trigger ใหม่ แล้วเปิดไม้ใหม่ทันที) เหมือน S424/S425

⚠️ ต้นฉบับ Pine "ไม่มี SL/TP" (เป็น reversal-only ผ่าน stop order สลับทิศ) —
ตรงนี้เพิ่ม ATR SL/TP เป็น safety net เท่านั้น ปิดโดย default (USE_ATR_STOP=False)
ส่วน monthly/yearly P&L table ใน Pine เป็น visualization ล้วนๆ ไม่มีผลต่อ
trading logic เลย จึงไม่พอร์ตส่วนนั้น

⚠️ นี่เป็น STOP order ตัวแรกของโปรเจกต์ (ต่างจาก S420/S421 ที่เป็น limit และ
S422-S425 ที่เป็น market) — demo_portfolio.py ยังไม่มี _place_stop_order()
รองรับ mt5.ORDER_TYPE_BUY_STOP/SELL_STOP ตอนนี้ detect_s426() คืน
order_type="stop" ไว้ก่อนสำหรับอนาคต แต่ยังใช้ไม่ได้กับ live demo จนกว่าจะเพิ่ม
infrastructure ส่วนนั้น (งานนี้ทำแค่ backtest ตามที่พี่ขอ)"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT,):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from strategy119 import _atr, _bars, _wait

TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60}

DEFAULT_CFG = {
    "LEFT_BARS": 2,
    "RIGHT_BARS": 1,
    "MINTICK": 0.01,         # gold ปกติ 2 ตำแหน่งทศนิยม
    "ATR_PERIOD": 14,
    "SL_ATR_MULT": 2.0,      # safety net เท่านั้น (ต้นฉบับไม่มี SL/TP)
    "TP_RR": 1.5,
    "USE_ATR_STOP": False,   # default ปิด — ตรงไอเดียเดิม (reversal-only)
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "BE_RR": None,
    "CANCEL_BARS": None,
}


def _pivot_at(bars, idx, left_bars, right_bars, kind):
    """คืนราคาถ้า bar[idx] เป็น pivot high/low ที่ยืนยันแล้ว (strict สูง/ต่ำกว่า
    เพื่อนบ้านทั้งซ้าย-ขวา) ไม่งั้นคืน None ต้องการ idx+right_bars ไม่เกิน
    ความยาว bars (ไม่มองอนาคตเกินกว่าที่ปิดแล้วจริง)"""
    n = len(bars)
    if idx - left_bars < 0 or idx + right_bars >= n:
        return None
    key = "high" if kind == "high" else "low"
    center = bars[idx][key]
    if kind == "high":
        for j in range(idx - left_bars, idx):
            if bars[j]["high"] >= center:
                return None
        for j in range(idx + 1, idx + right_bars + 1):
            if bars[j]["high"] >= center:
                return None
    else:
        for j in range(idx - left_bars, idx):
            if bars[j]["low"] <= center:
                return None
        for j in range(idx + 1, idx + right_bars + 1):
            if bars[j]["low"] <= center:
                return None
    return center


def _pivot_state_series(bars, left_bars, right_bars):
    """คืน (long_stop, short_stop) — list ความยาวเท่า bars ของราคา stop order
    ที่ "แขวนอยู่" ณ ตอนปิดแท่งนั้น (None = ไม่มีไม้แขวน) ตรงตามสูตร Pine:
    hprice/lprice เก็บ pivot ล่าสุด, le/se เป็น true จนกว่าราคาจะ breakout ผ่าน"""
    n = len(bars)
    hprice = 0.0
    lprice = 0.0
    le = False
    se = False
    long_stop = [None] * n
    short_stop = [None] * n
    for i in range(n):
        candidate = i - right_bars
        swh = _pivot_at(bars, candidate, left_bars, right_bars, "high") if candidate >= 0 else None
        swl = _pivot_at(bars, candidate, left_bars, right_bars, "low") if candidate >= 0 else None
        if swh is not None:
            hprice = swh
        if swl is not None:
            lprice = swl

        high_i = bars[i]["high"]
        low_i = bars[i]["low"]
        if swh is not None:
            le = True
        elif le and high_i > hprice:
            le = False
        if swl is not None:
            se = True
        elif se and low_i < lprice:
            se = False

        long_stop[i] = hprice if le else None
        short_stop[i] = lprice if se else None
    return long_stop, short_stop


def compute_state(rates, tf="", cfg=None):
    """คืน (state, None) หรือ (None, เหตุผล). state = {"event","long_stop",
    "short_stop"} — ราคา stop order ที่แขวนอยู่ ณ แท่งล่าสุดที่ปิดสมบูรณ์แล้ว"""
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

    left_bars = int(c["LEFT_BARS"])
    right_bars = int(c["RIGHT_BARS"])
    long_stop, short_stop = _pivot_state_series(bars, left_bars, right_bars)

    return {
        "event": bars[-1],
        "long_stop": long_stop[-1],
        "short_stop": short_stop[-1],
    }, None


def detect_s426(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S426 Pivot Reversal Stop-Breakout — ดู docstring บนสุดของไฟล์นี้ คืน
    order_type="stop" (ยังไม่รองรับ live demo จนกว่าจะเพิ่ม _place_stop_order)"""
    del dt_bkk, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    state, err = compute_state(rates, tf, c)
    if state is None:
        return _wait(err)

    long_stop = state["long_stop"]
    short_stop = state["short_stop"]
    if long_stop is None and short_stop is None:
        return _wait("No armed pivot stop")

    # ถ้าแขวนทั้งสองทิศพร้อมกัน (เพิ่งยืนยัน pivot ใหม่ทั้งคู่ในรอบใกล้กัน)
    # เลือกทิศที่ pivot เพิ่งยืนยันหลังสุด ไม่ได้ ใช้ long ก่อนเป็น tie-break
    if long_stop is not None and (short_stop is None or True):
        signal = "BUY"
        stop_price = round(long_stop + float(c["MINTICK"]), 2)
    else:
        signal = "SELL"
        stop_price = round(short_stop - float(c["MINTICK"]), 2)

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

    sl = tp = None
    atr_str = "n/a"
    if bool(c["USE_ATR_STOP"]):
        atr = _atr(bars, atr_period)
        if atr <= 0.0:
            return _wait("ATR is zero")
        atr_str = f"{atr:.2f}"
        risk = atr * sl_mult
        sl = round(stop_price - risk, 2) if signal == "BUY" else round(stop_price + risk, 2)
        tp = round(stop_price + risk * tp_rr, 2) if signal == "BUY" else round(stop_price - risk * tp_rr, 2)

    return {
        "signal": signal,
        "entry": stop_price,
        "sl": sl,
        "tp": tp,
        "order_type": "stop",
        "pattern": f"S426 {signal} Pivot Reversal Stop",
        "reason": f"pivot hprice/lprice breakout ATR={atr_str}",
        "be_rr": c["BE_RR"],
        "cancel_bars": c["CANCEL_BARS"],
    }
