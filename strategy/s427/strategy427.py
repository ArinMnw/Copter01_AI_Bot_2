# -*- coding: utf-8 -*-
"""S427 - Open Close Cross Strategy R5.1 (พอร์ตจาก Pine v3 @JayRogers,
revised by JustUncleL) — คำนวณ SMMA (Smoothed MA, len=8 default) ของราคา Close
กับราคา Open บน "Alternate Resolution" (TF ปัจจุบัน x multiplier, default 3)
แล้วดู crossover ระหว่างสองเส้นนี้: closeSeries ตัดขึ้นเหนือ openSeries = BUY,
ตัดลงใต้ = SELL — reversal-only (pyramiding=0, ไม่มี SL/TP default เหมือน
ต้นฉบับ Pine ที่ slPoints/tpPoints=0)

⚠️⚠️ โปรเจกต์นี้เคยพอร์ต OCC Strategy ตัวนี้มาก่อนแล้วเป็น MQL5 EA
(`mql5/OCC_Strategy_EA.mq5` + `mql5/OCC_MA_Lib.mqh`) และ**ยืนยันแล้วว่าต้นฉบับ
Pine repaint** — ใช้ `security(tickerid, stratRes, ..., lookahead=barmerge.
lookahead_on)` ดึงค่า Alt-TF โดยไม่กัน repaint (ต้องตั้ง delayOffset>=1 เอง
ถึงจะไม่ repaint แต่ default=0) แปลว่าตัวเลข backtest ที่เห็นจาก TradingView
(เช่น PF สูงลิ่ว win rate 70%+) ใช้ข้อมูลแท่ง Alt-TF ที่ "ยังไม่ปิด" ซึ่งเป็น
การมองอนาคต — ห้ามไล่ตามตัวเลข TV เป๊ะๆ (ดู feedback_pine_security_repaint_
pattern ในความจำ, ยืนยันซ้ำกับ S420 มาแล้ว) ไฟล์นี้พอร์ตแบบ **non-repaint**
เท่านั้น (เหมือน MQL5 EA ที่ทำไว้ก่อนหน้า) — ใช้เฉพาะแท่ง Alt-TF ที่ปิด
สมบูรณ์แล้วเท่านั้นในการคำนวณสัญญาณ

⚠️ ต่างจาก MQL5 EA ตรงที่ Alt-TF ที่นี่ aggregate จากแท่งของ TF หลักที่กำลัง
backtest อยู่เอง (ไม่ใช่ดึงจาก M1 เสมอแบบ EA) เพราะ M1 history ใน MT5 มีแค่
~205 วัน ไม่พอสำหรับหน้าต่าง backtest ยาวๆ บน H1/M30 — ผลคือ epoch-alignment
ของ Alt-TF อาจต่างจาก MQL5 EA/TradingView เล็กน้อยในบาง TF (ยอมรับเป็น known
approximation เหมือนความต่างของ broker data ที่เจอมาตลอดในโปรเจกต์นี้)

⚠️ พอร์ตแค่ MA type "SMMA" (default ของ Pine/ค่าที่ผู้ใช้ใช้จริง) เท่านั้น —
Pine รองรับ 12 แบบ (SMA/EMA/DEMA/TEMA/WMA/VWMA/SMMA/HullMA/LSMA/ALMA/SSMA/TMA)
แต่ไม่พอร์ตครบเพราะไม่มีความจำเป็นสำหรับ config ที่ใช้เทียบตอนนี้"""

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
    "USE_ALT_RES": True,
    "ALT_MULT": 3,
    "MA_LEN": 8,
    "ATR_PERIOD": 14,
    "SL_ATR_MULT": 2.0,     # safety net เท่านั้น (ต้นฉบับไม่มี SL/TP default)
    "TP_RR": 1.5,
    "USE_ATR_STOP": False,  # default ปิด — ตรงต้นฉบับ (slPoints/tpPoints=0)
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "BE_RR": None,
    "CANCEL_BARS": None,
}


def _smma(values, length):
    """Smoothed MA (Wilder RMA) — seed ด้วย SMA ของ length แรก คืน list ยาว
    เท่า values โดยตำแหน่งก่อน seed = None"""
    n = len(values)
    out = [None] * n
    if n < length:
        return out
    seed = sum(values[:length]) / length
    out[length - 1] = seed
    prev = seed
    for i in range(length, n):
        prev = (prev * (length - 1) + values[i]) / length
        out[i] = prev
    return out


def _aggregate_alt(bars, base_minutes, mult):
    """รวมแท่งของ TF หลักเป็นแท่ง Alt-TF (ขนาด base_minutes*mult นาที) โดยแบ่ง
    bucket ตาม raw epoch time (สม่ำเสมอ ไม่มี gap-tolerance เพราะเป็นการรวม
    แท่งภายใน TF เดียวกัน ไม่ข้ามวันเหมือน daily bucket) ตัด bucket ที่ไม่ครบ
    mult แท่งทิ้ง (รวมทั้ง bucket แรกสุดถ้าเริ่มไม่ตรง boundary และ bucket
    สุดท้ายถ้ายังไม่ปิด)"""
    alt_seconds = base_minutes * mult * 60
    buckets = {}
    order = []
    counts = {}
    for bar in bars:
        bucket_start = (bar["time"] // alt_seconds) * alt_seconds
        if bucket_start not in buckets:
            buckets[bucket_start] = {
                "time": bucket_start, "open": bar["open"], "high": bar["high"],
                "low": bar["low"], "close": bar["close"],
            }
            order.append(bucket_start)
            counts[bucket_start] = 1
        else:
            b = buckets[bucket_start]
            b["high"] = max(b["high"], bar["high"])
            b["low"] = min(b["low"], bar["low"])
            b["close"] = bar["close"]
            counts[bucket_start] += 1
    return [buckets[t] for t in order if counts[t] >= mult]


def _cross_series(alt_bars, ma_len):
    """คืน list ยาวเท่า alt_bars ของ 1 (xlong เพิ่งเกิดที่แท่งนี้), -1 (xshort),
    0 (ไม่มี cross) — คำนวณจาก SMMA(close) ตัดกับ SMMA(open) ของแท่ง Alt-TF"""
    closes = [b["close"] for b in alt_bars]
    opens = [b["open"] for b in alt_bars]
    close_ma = _smma(closes, ma_len)
    open_ma = _smma(opens, ma_len)
    n = len(alt_bars)
    out = [0] * n
    for i in range(1, n):
        c0, o0, c1, o1 = close_ma[i - 1], open_ma[i - 1], close_ma[i], open_ma[i]
        if c0 is None or o0 is None or c1 is None or o1 is None:
            continue
        if c0 <= o0 and c1 > o1:
            out[i] = 1
        elif c0 >= o0 and c1 < o1:
            out[i] = -1
    return out


def compute_state(rates, tf="", cfg=None):
    """คืน (state, None) หรือ (None, เหตุผล). state = {"event","side"} —
    side="BUY"/"SELL"/None (None = ยังไม่เคย cross เลยตั้งแต่เริ่มมีข้อมูล)"""
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

    mult = max(1, int(c["ALT_MULT"])) if bool(c["USE_ALT_RES"]) else 1
    ma_len = max(1, int(c["MA_LEN"]))
    alt_bars = _aggregate_alt(bars, base_minutes, mult)
    if len(alt_bars) < ma_len + 1:
        return None, "Not enough complete alt-TF bars"

    crosses = _cross_series(alt_bars, ma_len)
    side = None
    for value in crosses:
        if value == 1:
            side = "BUY"
        elif value == -1:
            side = "SELL"

    return {"event": bars[-1], "side": side}, None


def detect_s427(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S427 Open Close Cross Strategy — ดู docstring บนสุดของไฟล์นี้ (⚠️
    non-repaint เท่านั้น ต้นฉบับ Pine repaint ยืนยันแล้วในโปรเจกต์นี้)"""
    del dt_bkk, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    state, err = compute_state(rates, tf, c)
    if state is None:
        return _wait(err)

    signal = state["side"]
    if signal is None:
        return _wait("No cross yet")
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

    entry = round(state["event"]["close"], 2)
    sl = tp = None
    atr_str = "n/a"
    if bool(c["USE_ATR_STOP"]):
        atr = _atr(bars, atr_period)
        if atr <= 0.0:
            return _wait("ATR is zero")
        atr_str = f"{atr:.2f}"
        risk = atr * sl_mult
        sl = round(entry - risk, 2) if signal == "BUY" else round(entry + risk, 2)
        tp = round(entry + risk * tp_rr, 2) if signal == "BUY" else round(entry - risk * tp_rr, 2)

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S427 {signal} Open Close Cross",
        "reason": f"OCC SMMA{c['MA_LEN']} altTFx{c['ALT_MULT']} ATR={atr_str}",
        "be_rr": c["BE_RR"],
        "cancel_bars": c["CANCEL_BARS"],
    }
