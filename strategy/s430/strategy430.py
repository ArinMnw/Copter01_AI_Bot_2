# -*- coding: utf-8 -*-
"""S430 - Triple EMA Stochastic RSI Strategy: พอร์ตจาก Pine v5 "Triple EMA
Stochastic RSI Strategy with Fixed Stop/Take Profit and Pyramiding" (ผู้ใช้ส่ง
โค้ดมาให้ตรงๆ) — trend filter จาก 3 เส้น EMA (แยกความยาวกันคนละเส้น ไม่ใช่
multi-timeframe) + entry จาก Stochastic-of-RSI (K ตัด D พร้อมอยู่ในโซน limit)
+ SL/TP ตายตัวจาก ATR multiplier (ไม่ใช่ RR ratio)

ตัวแปรชื่อใน Pine ต้นฉบับสับสน (ema50_length default=350, ema14_length
default=110, ema8_length default=14 — ชื่อไม่ตรงกับค่า default เลย) ในพอร์ตนี้
เปลี่ยนชื่อให้ตรงบทบาทจริงเป็น EMA_LEN_SLOW/MID/FAST (350/110/14 ตามลำดับ)

Stochastic ของ Pine: k = sma(ta.stoch(rsi1, rsi1, rsi1, lengthStoch), smoothK)
โดย ta.stoch(source, high, low, length) = 100*(source - lowest(low,length)) /
(highest(high,length) - lowest(low,length)) — ที่นี่ source=high=low=rsi1 ทั้ง
สามพารามิเตอร์ เท่ากับเป็น "stochastic ของ RSI เอง" (StochRSI %K แบบ raw ก่อน
smooth), แล้ว d = sma(k, smoothD)

ข้อแตกต่างจาก Pine ต้นฉบับ ที่ต้อง "ปรับให้เข้ากับ backtest engine ของโปรเจกต์"
(ตาม convention เดียวกับ S420-S429 ทุกตัวในโปรเจกต์นี้):
  1) Pine เปิด pyramiding=10 + default_qty_type=percent_of_equity 100% (เข้าไม้
     ซ้อนได้ถึง 10 ไม้พร้อมกัน แต่ละไม้เต็ม equity) — ไม่ตรงกับ convention 1
     สัญญาณ/ไม้ต่อรอบของ engine โปรเจกต์นี้ เลยตีความใหม่เป็น "เข้าไม้เดียว รอ
     TP/SL ก่อนถึงจะเข้าไม้ใหม่ได้" (ไม่ pyramid) เหมือน S420/S422/S427 ทุกตัว
  2) ATR ของโปรเจกต์นี้ (`_atr()`/`_atr_series()` ใน strategy119/ที่นี่) คือ
     ค่าเฉลี่ยเลขคณิตธรรมดาของ True Range ย้อนหลัง N แท่ง (SMA) ไม่ใช่ Wilder's
     RMA แบบ ta.atr() ของ Pine จริง — เป็นการลดความซับซ้อนที่ใช้ตรงกันทั้งโปรเจกต์
     อยู่แล้ว (ดู docstring `_atr()` ใน strategy119.py) ไม่ใช่จุดสนใจหลักของ
     กลยุทธ์นี้
  3) trade_direction default ของ Pine = "Long Only" — พอร์ตนี้ตรงตาม default
     ผ่าน ALLOW_BUY=True/ALLOW_SELL=False ใน DEFAULT_CFG (เปลี่ยนได้)
  4) entry ใน backtest ใช้ order_type="market" fill ที่ราคาเปิดของแท่งถัดไป
     (เหมือน S422/S427) ไม่ใช่ fill ทันทีที่ close ของแท่งสัญญาณ — SL/TP ยังคง
     คำนวณจาก close ของแท่งสัญญาณ (ตรงกับที่ Pine เขียน `close - mult*atr` ณ
     แท่งที่เงื่อนไขเป็นจริง)
"""

from __future__ import annotations

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from strategy119 import _bars, _wait

DEFAULT_CFG = {
    "EMA_LEN_SLOW": 350, "EMA_LEN_MID": 110, "EMA_LEN_FAST": 14,
    "RSI_LEN": 160, "STOCH_LEN": 90, "SMOOTH_K": 14, "SMOOTH_D": 4,
    "LONG_STOCH_LIMIT": 35.0, "SHORT_STOCH_LIMIT": 85.0,
    "ATR_PERIOD": 75, "ATR_SL_MULT": 7.0, "ATR_TP_MULT": 4.0,
    "ALLOW_BUY": True, "ALLOW_SELL": False,  # trade_direction="Long Only" (default ของ Pine)
    "BE_RR": 0.5,
    "CANCEL_BARS": 3,
}


def _ema_series(values, period):
    alpha = 2.0 / (period + 1)
    out = np.empty(len(values), dtype=float)
    prev = None
    for i, v in enumerate(values):
        prev = v if prev is None else prev + alpha * (v - prev)
        out[i] = prev
    return out


def _rma_series(values, length):
    """Wilder RMA แบบ Pine ta.rma()/ta.rsi() ภายใน — seed ด้วย SMA ของ
    `length` ค่าแรก จากนั้น prev*(length-1)/length + value/length ทุกจุดถัดไป
    (ต่างจาก _ema_series ตรงการ seed — ใช้เฉพาะสำหรับ RSI ให้ตรง Pine)"""
    n = len(values)
    out = np.full(n, np.nan, dtype=float)
    if n < length:
        return out
    seed = float(np.mean(values[:length]))
    out[length - 1] = seed
    prev = seed
    for i in range(length, n):
        prev = (prev * (length - 1) + values[i]) / length
        out[i] = prev
    return out


def _rsi_series(closes, length):
    n = len(closes)
    diffs = np.diff(closes, prepend=closes[0])
    gains = np.where(diffs > 0.0, diffs, 0.0)
    losses = np.where(diffs < 0.0, -diffs, 0.0)
    gains[0] = losses[0] = 0.0
    up = _rma_series(gains, length)
    down = _rma_series(losses, length)
    out = np.full(n, np.nan, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = up / down
        rsi = 100.0 - 100.0 / (1.0 + rs)
    valid = ~np.isnan(up) & ~np.isnan(down)
    out[valid] = rsi[valid]
    out[valid & (down == 0.0) & (up == 0.0)] = 50.0  # flat price ต่อเนื่อง — เลี่ยง 0/0=nan
    out[valid & (down == 0.0) & (up != 0.0)] = 100.0
    return out


def _rolling_min_max(values, length):
    """rolling min/max แบบ O(n) ด้วย monotonic deque (สำคัญเมื่อ length=90 กับ
    ข้อมูลเป็นแสนแท่ง — วิธี slice+min/max ต่อแท่งจะช้าเกินไปมาก)."""
    n = len(values)
    roll_min = np.full(n, np.nan, dtype=float)
    roll_max = np.full(n, np.nan, dtype=float)
    min_dq, max_dq = [], []  # เก็บ index, ค่าเรียงจากน้อย/มากไปมาก (monotonic)
    for i in range(n):
        v = values[i]
        lo = i - length + 1
        while min_dq and min_dq[0] < lo:
            min_dq.pop(0)
        while max_dq and max_dq[0] < lo:
            max_dq.pop(0)
        if not np.isnan(v):
            while min_dq and values[min_dq[-1]] >= v:
                min_dq.pop()
            min_dq.append(i)
            while max_dq and values[max_dq[-1]] <= v:
                max_dq.pop()
            max_dq.append(i)
        if i >= length - 1 and min_dq and max_dq:
            roll_min[i] = values[min_dq[0]]
            roll_max[i] = values[max_dq[0]]
    return roll_min, roll_max


def _sma_series(values, period):
    """rolling mean แบบ O(n) (cumsum) — รองรับ NaN นำหน้า (ช่วง warmup)."""
    n = len(values)
    out = np.full(n, np.nan, dtype=float)
    filled = np.nan_to_num(values, nan=0.0)
    csum = np.cumsum(filled)
    valid = ~np.isnan(values)
    csum_valid = np.cumsum(valid.astype(float))
    for i in range(n):
        lo = max(0, i - period + 1)
        if csum_valid[i] - (csum_valid[lo - 1] if lo > 0 else 0.0) < period:
            continue  # ยังไม่มีค่า valid ครบ period ในหน้าต่างนี้
        total = csum[i] - (csum[lo - 1] if lo > 0 else 0.0)
        out[i] = total / period
    return out


def _atr_series(bars, period):
    """ค่าเฉลี่ย True Range ย้อนหลัง `period` แท่งแบบ SMA (ตรงกับ `_atr()` ของ
    strategy119.py — ดู docstring หัวไฟล์ข้อ 2 สำหรับความต่างจาก Pine ta.atr)."""
    n = len(bars)
    highs = np.array([b["high"] for b in bars], dtype=float)
    lows = np.array([b["low"] for b in bars], dtype=float)
    closes = np.array([b["close"] for b in bars], dtype=float)
    prev_close = np.concatenate(([closes[0]], closes[:-1]))
    tr = np.maximum(highs - lows, np.maximum(np.abs(highs - prev_close), np.abs(lows - prev_close)))
    out = np.full(n, np.nan, dtype=float)
    csum = np.cumsum(tr)
    for i in range(period, n):
        out[i] = (csum[i] - csum[i - period]) / period
    return out


def compute_series(rates, cfg=None):
    """คำนวณทุก series ที่ต้องใช้ทั้งช่วงราคาในครั้งเดียว (ไม่ recompute ทุกแท่ง
    แบบ S420) คืน (dict, None) หรือ (None, เหตุผล)."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        ema_slow_p = int(c["EMA_LEN_SLOW"])
        ema_mid_p = int(c["EMA_LEN_MID"])
        ema_fast_p = int(c["EMA_LEN_FAST"])
        rsi_len = int(c["RSI_LEN"])
        stoch_len = int(c["STOCH_LEN"])
        smooth_k = int(c["SMOOTH_K"])
        smooth_d = int(c["SMOOTH_D"])
        atr_period = int(c["ATR_PERIOD"])
        if min(ema_slow_p, ema_mid_p, ema_fast_p, rsi_len, stoch_len, smooth_k, smooth_d, atr_period) < 1:
            return None, "Invalid cfg periods"
    except (KeyError, TypeError, ValueError) as exc:
        return None, f"Invalid cfg: {exc}"

    try:
        bars = _bars(rates)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return None, f"Invalid rates: {exc}"

    warmup = max(ema_slow_p, ema_mid_p, ema_fast_p, atr_period) + rsi_len + stoch_len + smooth_k + smooth_d + 5
    if len(bars) < warmup:
        return None, "Not enough data"

    closes = np.array([bar["close"] for bar in bars], dtype=float)
    ema_slow = _ema_series(closes, ema_slow_p)
    ema_mid = _ema_series(closes, ema_mid_p)
    ema_fast = _ema_series(closes, ema_fast_p)

    rsi = _rsi_series(closes, rsi_len)
    roll_min, roll_max = _rolling_min_max(rsi, stoch_len)
    span = roll_max - roll_min
    with np.errstate(divide="ignore", invalid="ignore"):
        raw_stoch = np.where(span > 0.0, 100.0 * (rsi - roll_min) / span, np.nan)
    k = _sma_series(raw_stoch, smooth_k)
    d = _sma_series(k, smooth_d)
    atr = _atr_series(bars, atr_period)

    return {
        "bars": bars, "close": closes,
        "ema_slow": ema_slow, "ema_mid": ema_mid, "ema_fast": ema_fast,
        "k": k, "d": d, "atr": atr,
    }, None


def compute_state(rates, cfg=None):
    """คืน state ของบาร์สุดท้าย (ใช้ทั้งใน detect_s430() one-shot และเป็นข้อมูล
    debug — backtest_s430.py ดึง series ตรงๆ ไม่เรียกฟังก์ชันนี้ซ้ำทุกบาร์)."""
    series, err = compute_series(rates, cfg)
    if series is None:
        return None, err
    close, ema_slow, ema_mid, ema_fast = series["close"], series["ema_slow"], series["ema_mid"], series["ema_fast"]
    k, d = series["k"], series["d"]
    if np.isnan(k[-1]) or np.isnan(d[-1]) or np.isnan(k[-2]) or np.isnan(d[-2]):
        return None, "StochRSI ยัง warm-up ไม่ครบ"

    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    long_limit, short_limit = float(c["LONG_STOCH_LIMIT"]), float(c["SHORT_STOCH_LIMIT"])

    trend_long = close[-1] > ema_slow[-1] and close[-1] > ema_mid[-1] and close[-1] > ema_fast[-1]
    trend_short = close[-1] < ema_slow[-1] and close[-1] < ema_mid[-1] and close[-1] < ema_fast[-1]
    cross_up = k[-2] <= d[-2] and k[-1] > d[-1]
    cross_down = k[-2] >= d[-2] and k[-1] < d[-1]

    signal_long = trend_long and cross_up and k[-1] < long_limit
    signal_short = trend_short and cross_down and k[-1] > short_limit

    return {
        "event": series["bars"][-1], "close": float(close[-1]),
        "ema_slow": float(ema_slow[-1]), "ema_mid": float(ema_mid[-1]), "ema_fast": float(ema_fast[-1]),
        "k": float(k[-1]), "d": float(d[-1]), "atr": float(series["atr"][-1]),
        "signal_long": signal_long, "signal_short": signal_short,
        "bars": series["bars"],
    }, None


def detect_s430(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S430 Triple EMA Stochastic RSI — ดู docstring บนสุดของไฟล์นี้สำหรับ
    รายละเอียดที่ปรับให้เข้ากับ engine กลาง."""
    del dt_bkk, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    state, err = compute_state(rates, c)
    if state is None:
        return _wait(err)

    if not (state["signal_long"] or state["signal_short"]):
        return _wait(f"No signal (k={state['k']:.2f} d={state['d']:.2f} "
                      f"close={state['close']:.2f} ema_slow={state['ema_slow']:.2f})")

    signal = "BUY" if state["signal_long"] else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")

    atr = state["atr"]
    if not atr or atr <= 0.0:
        return _wait("ATR is zero")

    sl_mult, tp_mult = float(c["ATR_SL_MULT"]), float(c["ATR_TP_MULT"])
    entry = round(state["close"], 2)
    sl = round(entry - sl_mult * atr, 2) if signal == "BUY" else round(entry + sl_mult * atr, 2)
    tp = round(entry + tp_mult * atr, 2) if signal == "BUY" else round(entry - tp_mult * atr, 2)

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S430 {signal} Triple EMA StochRSI",
        "reason": (f"k={state['k']:.2f} d={state['d']:.2f} close={entry:.2f} "
                   f"ema_slow={state['ema_slow']:.2f} ema_mid={state['ema_mid']:.2f} "
                   f"ema_fast={state['ema_fast']:.2f} ATR={atr:.2f}"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
