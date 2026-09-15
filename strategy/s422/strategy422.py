# -*- coding: utf-8 -*-
"""S422 - FTSMA (Fourier Transform SMA) Strategy: port จาก Pine v4 "FTSMA"
(ต้นฉบับ © 03.freeman, MPL-2.0) — ใช้ discrete Fourier transform หาแอมพลิจูด
ของ sinusoid ความถี่ต่ำ (harmonic ที่ 1/2/3 ของหน้าต่าง lookback N) แล้วบวกกับ
close มาเป็น "ราคาสังเคราะห์" 3 เส้น (slow/med/fast) ก่อนนำไปทำ MA อีกชั้น
เข้าไม้เมื่อ FASTMA ตัด MEDMA พร้อม close อยู่ฝั่งเดียวกับ SLOWMA

สูตร Fourier ของ Pine (ReX/ImX/ReX_/ImX_/x/sx) เรียก sx(i,k) เสมอที่ i=0 (bar
ปัจจุบัน) เท่านั้นในทั้งสคริปต์ (ไม่เคยเรียก x(i,N) หรือ sx(i!=0,k) เลย) — พิสูจน์
ได้ว่า sx(0,k) = ReX_(k) เป๊ะ เพราะ sin(2*pi*k*0/n)=0 เสมอ ทำให้ไม่ต้องพอร์ต
ImX/ImX_ เลยแม้แต่บรรทัดเดียว (ตัดทอนได้ถูกต้อง ไม่ใช่ลัดขั้นตอน):

    sx(0,k) = ReX_(k)*cos(0) + ImX_(k)*sin(0) = ReX_(k)*1 + ImX_(k)*0 = ReX_(k)

ReX_(k) คำนวณด้วย np.convolve (แทน inner-loop ตรงตัวของ Pine) เพื่อความเร็ว —
คำนวณ FT ทั้งช่วงราคาได้ในครั้งเดียว (ไม่ต้องวน recompute ทุกบาร์แบบ S420 เพราะ
FT ไม่มี state สะสมข้ามบาร์ เป็นฟังก์ชันของหน้าต่าง N แท่งล่าสุดล้วนๆ)

ข้อแตกต่างจาก Pine ต้นฉบับ ที่ต้อง "ปรับให้เข้ากับ backtest engine ของโปรเจกต์":
  1) MA_TYPE รองรับแค่ SMA/EMA/WMA/RMA (Pine มี ALMA/FRAMA/SWMA/VWMA/
     LinearRegression ด้วย — ยังไม่พอร์ต เพราะ default ของ Pine คือ EMA และ
     ไม่ใช่จุดสนใจหลักของกลยุทธ์นี้ ใส่ MA_TYPE อื่นแล้วจะได้ error ชัดเจน ไม่ใช่
     ผลลัพธ์ผิดเงียบๆ)
  2) Pine เข้าไม้ "ทุกบาร์" ที่เงื่อนไข longCondition/shortCondition เป็นจริง
     (pyramiding=10 พร้อมไม่มี strategy.close ใดๆ นอกจาก TP/SL/trailing ที่
     default ปิดอยู่ — คือถือไม้สะสมไปเรื่อยๆ ตามเทรนด์) ไม่เข้ากับ convention
     1 สัญญาณ/ไม้ต่อรอบของ engine โปรเจกต์นี้ เลยตีความใหม่เป็น "เข้าเฉพาะบาร์แรก
     ที่ regime เปลี่ยน" (fast/med/slow สลับข้างกัน) แทน
  3) Pine ไม่มี SL/TP โดย default (point-based, default=0=ปิด) — ใช้ ATR-based
     SL/TP แทน (SL_ATR_MULT/TP_RR ใน DEFAULT_CFG) ตาม convention ของ
     strategy อื่นๆในโปรเจกต์นี้ที่ใช้ _atr() ร่วมกัน (ดู strategy119.py)
  4) linreg(offset) รองรับเฉพาะกรณี non-repaint (offset ที่ไม่เกินขอบเขตข้อมูล
     ที่มีจริง ณ เวลานั้น) — Pine default offset=0 อยู่แล้วจึงไม่กระทบ config
     เริ่มต้น
"""

from __future__ import annotations

import os
import sys

import numpy as np

# strategy119.py อยู่ที่ root ของโปรเจกต์ ไม่ใช่ในโฟลเดอร์นี้ (strategy/s422/)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from strategy119 import _atr, _bars, _wait

DEFAULT_CFG = {
    "FT_LOOKBACK": 64,        # N ของ Pine ("Lookback Period")
    "SIN1": 1, "SIN2": 2, "SIN3": 3,   # First/Second/Third sinusoid
    "SLOW_MA": 200, "MED_MA": 20, "FAST_MA": 5,
    "MA_TYPE": "EMA",         # SMA/EMA/WMA/RMA (ดู docstring หัวไฟล์)
    "USE_MA": True,           # ตรงกับ input "Use MA" (plotSMA) ของ Pine
    "USE_LINREG": False,
    "LINREG_LEN": 13,
    "LINREG_OFFSET": 0,
    "ATR_PERIOD": 14,
    "SL_ATR_MULT": 1.5,
    "TP_RR": 2.0,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "BE_RR": 0.5,
    "CANCEL_BARS": 3,
}

_MA_TYPES = ("SMA", "EMA", "WMA", "RMA")


def _sma_series(values, period):
    out = np.empty(len(values), dtype=float)
    for i in range(len(values)):
        window = values[max(0, i - period + 1):i + 1]
        out[i] = window.mean()
    return out


def _ema_series(values, period):
    alpha = 2.0 / (period + 1)
    out = np.empty(len(values), dtype=float)
    prev = None
    for i, v in enumerate(values):
        prev = v if prev is None else prev + alpha * (v - prev)
        out[i] = prev
    return out


def _rma_series(values, period):
    """Wilder's smoothing — ตรงกับ Pine rma()."""
    alpha = 1.0 / period
    out = np.empty(len(values), dtype=float)
    prev = None
    for i, v in enumerate(values):
        prev = v if prev is None else prev + alpha * (v - prev)
        out[i] = prev
    return out


def _wma_series(values, period):
    out = np.empty(len(values), dtype=float)
    for i in range(len(values)):
        window = values[max(0, i - period + 1):i + 1]
        n = len(window)
        weights = np.arange(1, n + 1, dtype=float)
        out[i] = float(np.dot(window, weights) / weights.sum())
    return out


_MA_FUNCS = {"SMA": _sma_series, "EMA": _ema_series, "WMA": _wma_series, "RMA": _rma_series}


def _ma_series(values, period, ma_type):
    fn = _MA_FUNCS.get(ma_type)
    if fn is None:
        raise ValueError(f"MA_TYPE '{ma_type}' not supported (only {_MA_TYPES})")
    return fn(values, period)


def _linreg_series(values, period, offset=0):
    """Pine linreg(series, length, offset) — fit เส้นตรงบน `period` จุดล่าสุด
    (causal) แล้วประเมินค่าที่ตำแหน่ง (period-1+offset); offset=0 (default ของ
    Pine) = ค่า fit ที่จุดปัจจุบันพอดี."""
    out = np.empty(len(values), dtype=float)
    for i in range(len(values)):
        window = values[max(0, i - period + 1):i + 1]
        n = len(window)
        if n < 2:
            out[i] = window[-1]
            continue
        xs = np.arange(n, dtype=float)
        mean_x, mean_y = xs.mean(), window.mean()
        var_x = ((xs - mean_x) ** 2).sum()
        slope = float(np.dot(xs - mean_x, window - mean_y) / var_x) if var_x != 0.0 else 0.0
        intercept = mean_y - slope * mean_x
        out[i] = intercept + slope * (n - 1 + offset)
    return out


def _ft_raw_series(closes, n, k):
    """คืน sx(0,k)=ReX_(k) ของทุกจุดตั้งแต่ index n-1..len(closes)-1 (numpy array
    ความยาว len(closes)-n+1) — ใช้ np.convolve แทน inner-loop ของ Pine
    (พิสูจน์สมการเทียบเท่าไว้ใน docstring หัวไฟล์)."""
    kernel = np.cos(2.0 * np.pi * k * np.arange(n) / n)
    full = np.convolve(closes, kernel, mode="full")
    raw_sum = full[n - 1:len(closes)]
    if k == 0 or (n % 2 == 0 and k == n // 2):
        return raw_sum / n
    return 2.0 * raw_sum / n


def compute_series(rates, cfg=None):
    """คำนวณ slow/med/fast MA (+ close ที่ align กัน) ทั้งช่วงราคาในครั้งเดียว —
    คืน (dict, None) หรือ (None, เหตุผล). dict มี numpy array ความยาวเท่ากัน:
    'bars_tail' (แท่ง OHLC ที่ index ตรงกับจุด FT แรก), 'close','slow','med','fast'."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        n = int(c["FT_LOOKBACK"])
        sin1, sin2, sin3 = int(c["SIN1"]), int(c["SIN2"]), int(c["SIN3"])
        slow_p, med_p, fast_p = int(c["SLOW_MA"]), int(c["MED_MA"]), int(c["FAST_MA"])
        ma_type = str(c["MA_TYPE"]).upper()
        use_ma = bool(c["USE_MA"])
        use_linreg = bool(c["USE_LINREG"])
        linreg_len = int(c["LINREG_LEN"])
        linreg_offset = int(c["LINREG_OFFSET"])
        if n < 2 or slow_p < 1 or med_p < 1 or fast_p < 1:
            return None, "Invalid cfg periods"
        if use_ma and ma_type not in _MA_TYPES:
            return None, f"MA_TYPE '{ma_type}' not supported (only {_MA_TYPES})"
    except (KeyError, TypeError, ValueError) as exc:
        return None, f"Invalid cfg: {exc}"

    try:
        bars = _bars(rates)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return None, f"Invalid rates: {exc}"

    warmup_extra = max(slow_p, med_p, fast_p) + (linreg_len if use_linreg else 0) + 2
    if len(bars) < n + warmup_extra:
        return None, "Not enough data"

    closes = np.array([bar["close"] for bar in bars], dtype=float)
    close_tail = closes[n - 1:]

    slow_raw = close_tail + _ft_raw_series(closes, n, sin1)
    med_raw = close_tail + _ft_raw_series(closes, n, sin2)
    fast_raw = close_tail + _ft_raw_series(closes, n, sin3)

    if use_ma:
        slow_series = _ma_series(slow_raw, slow_p, ma_type)
        med_series = _ma_series(med_raw, med_p, ma_type)
        fast_series = _ma_series(fast_raw, fast_p, ma_type)
    else:
        slow_series, med_series, fast_series = slow_raw, med_raw, fast_raw

    if use_linreg:
        slow_series = _linreg_series(slow_series, linreg_len, linreg_offset)
        med_series = _linreg_series(med_series, linreg_len, linreg_offset)
        fast_series = _linreg_series(fast_series, linreg_len, linreg_offset)

    if len(slow_series) < 2:
        return None, "Not enough FT/MA history"

    return {
        "bars_tail": bars[n - 1:], "close": close_tail,
        "slow": slow_series, "med": med_series, "fast": fast_series,
    }, None


def compute_state(rates, cfg=None):
    """คืน state ปัจจุบัน (บาร์สุดท้าย) ไม่ตัดสินใจเปิดไม้ — ใช้ร่วมกันทั้งใน
    detect_s422() (โหมด one-shot) และ backtest_s422.py (ที่จะดึงทั้ง series
    มาเดินเองโดยตรง ไม่ต้องเรียกฟังก์ชันนี้ซ้ำทุกบาร์ เพราะ compute_series()
    คำนวณทั้งช่วงในครั้งเดียวอยู่แล้ว)."""
    series, err = compute_series(rates, cfg)
    if series is None:
        return None, err
    close, slow, med, fast = series["close"], series["slow"], series["med"], series["fast"]
    event = series["bars_tail"][-1]

    cur_long = fast[-1] > med[-1] and close[-1] > slow[-1]
    cur_short = fast[-1] < med[-1] and close[-1] < slow[-1]
    prev_long = fast[-2] > med[-2] and close[-2] > slow[-2]
    prev_short = fast[-2] < med[-2] and close[-2] < slow[-2]

    return {
        "event": event, "slow": float(slow[-1]), "med": float(med[-1]), "fast": float(fast[-1]),
        "cur_long": cur_long, "cur_short": cur_short,
        "signal_long": cur_long and not prev_long,
        "signal_short": cur_short and not prev_short,
        "bars": series["bars_tail"],
    }, None


def detect_s422(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S422 FTSMA — Fourier-smoothed triple-MA regime flip + ATR SL/TP (ดู
    docstring บนสุดของไฟล์นี้สำหรับรายละเอียดที่ปรับให้เข้ากับ engine กลาง)."""
    del dt_bkk, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    state, err = compute_state(rates, c)
    if state is None:
        return _wait(err)

    if not (state["signal_long"] or state["signal_short"]):
        return _wait(f"No regime flip (fast={state['fast']:.2f} med={state['med']:.2f} "
                      f"slow={state['slow']:.2f} close={state['event']['close']:.2f})")

    try:
        atr_period = int(c["ATR_PERIOD"])
        sl_mult = float(c["SL_ATR_MULT"])
        tp_rr = max(1.5, float(c["TP_RR"]))
    except (KeyError, TypeError, ValueError) as exc:
        return _wait(f"Invalid cfg: {exc}")

    atr = _atr(state["bars"], atr_period)
    if atr <= 0.0:
        return _wait("ATR is zero")

    close = state["event"]["close"]
    signal = "BUY" if state["signal_long"] else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")

    entry = round(close, 2)
    risk = atr * sl_mult
    sl = round(entry - risk, 2) if signal == "BUY" else round(entry + risk, 2)
    tp = round(entry + risk * tp_rr, 2) if signal == "BUY" else round(entry - risk * tp_rr, 2)

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S422 {signal} FTSMA regime flip",
        "reason": (f"fast={state['fast']:.2f} med={state['med']:.2f} slow={state['slow']:.2f} "
                   f"close={close:.2f} ATR={atr:.2f}"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
