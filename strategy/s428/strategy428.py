# -*- coding: utf-8 -*-
"""S428 - Flawless Victory Strategy (พอร์ตจาก Pine v4 © Bunghole, MPL-2.0) —
Long-only mean-reversion: Bollinger Band แตะขอบล่าง + RSI guard = BUY, แตะขอบ
บน + RSI guard = ปิดไม้ (flat) ไม่มี short เลย (ต้นฉบับไม่เคย strategy.short())

ไม่มี security()/request.security() เลย → **ไม่มีความเสี่ยง repaint** (ต่างจาก
S420/S427 ที่ต้องระวัง) ทุกอินดิเคเตอร์คำนวณบน TF ปัจจุบันตรงๆ

ต้นฉบับมี 3 เวอร์ชันสลับกันด้วย input toggle (v1/v2/v3) — default เปิดแค่ v1:
  v1 (default): BB(len=20, mult=1.0) + RSI(14), buy: close<lowerBB and rsi>42,
                 sell(flat): close>upperBB and rsi>70 — **ไม่มี SL/TP**
  v2: BB(len=17, mult=1.0) + RSI, buy: close<lowerBB and rsi>42,
      sell: close>upperBB and rsi>76, SL=6.604% TP=2.328% (จาก avg entry)
  v3: BB(len=20, mult=1.0, เหมือน v1) + MFI(14) + RSI, buy: close<lowerBB and
      mfi<60, sell: close>upperBB and rsi>65 and mfi>64, SL=8.882% TP=2.317%
เลือกด้วย cfg["VERSION"] = 1/2/3 (default 1 ตรง Pine default)

⚠️ default_qty_type=percent_of_equity, default_qty_value=100 (เข้าเต็ม 100%
ของ equity ทุกไม้!) initial_capital=100000, ไม่มี commission — เก็บไว้ใน
docstring backtest_s428.py สำหรับโหมด --tv-mode"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT,):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from strategy119 import _bars, _wait

TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60}

DEFAULT_CFG = {
    "VERSION": 1,       # 1/2/3 ตาม docstring ด้านบน
    "RSI_LEN": 14,
    "MFI_LEN": 14,
    "ALLOW_BUY": True,
}


def _rma(values, length):
    """Wilder RMA — seed ด้วย SMA ของ length แรก (เหมือน Pine rma())"""
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


def _rsi_series(closes, length):
    n = len(closes)
    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        change = closes[i] - closes[i - 1]
        gains[i] = max(change, 0.0)
        losses[i] = max(-change, 0.0)
    up = _rma(gains, length)
    down = _rma(losses, length)
    out = [None] * n
    for i in range(n):
        if up[i] is None or down[i] is None:
            continue
        if down[i] == 0.0:
            out[i] = 100.0
        elif up[i] == 0.0:
            out[i] = 0.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + up[i] / down[i])
    return out


def _mfi_series(bars, length):
    n = len(bars)
    typical = [(b["high"] + b["low"] + b["close"]) / 3.0 for b in bars]
    volume = [float(b.get("tick_volume", 0.0)) for b in bars]
    up_flow = [0.0] * n
    down_flow = [0.0] * n
    for i in range(1, n):
        change = typical[i] - typical[i - 1]
        if change > 0.0:
            up_flow[i] = volume[i] * typical[i]
        elif change < 0.0:
            down_flow[i] = volume[i] * typical[i]
    out = [None] * n
    for i in range(length, n):
        upper = sum(up_flow[i - length + 1:i + 1])
        lower = sum(down_flow[i - length + 1:i + 1])
        if lower == 0.0:
            out[i] = 100.0
        elif upper == 0.0:
            out[i] = 0.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + upper / lower)
    return out


def _bb_series(closes, length, mult):
    n = len(closes)
    upper = [None] * n
    lower = [None] * n
    for i in range(length - 1, n):
        window = closes[i - length + 1:i + 1]
        basis = sum(window) / length
        var = sum((x - basis) ** 2 for x in window) / length
        dev = mult * (var ** 0.5)
        upper[i] = basis + dev
        lower[i] = basis - dev
    return upper, lower


def compute_state(rates, tf="", cfg=None):
    """คืน (state, None) หรือ (None, เหตุผล). state = {"event","buy_trigger",
    "sell_trigger","sl_pct","tp_pct"}"""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    base_minutes = TF_MINUTES.get(str(tf).upper())
    if base_minutes is None:
        return None, f"Unsupported tf {tf}"

    if rates is None or len(rates) < 40:
        return None, "Not enough data"
    try:
        bars = _bars(rates)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return None, f"Invalid rates: {exc}"

    version = int(c["VERSION"])
    closes = [b["close"] for b in bars]
    rsi_len = int(c["RSI_LEN"])
    rsi = _rsi_series(closes, rsi_len)

    if version == 2:
        bb_len, sl_pct, tp_pct = 17, 6.604, 2.328
    elif version == 3:
        bb_len, sl_pct, tp_pct = 20, 8.882, 2.317
    else:
        bb_len, sl_pct, tp_pct = 20, None, None

    upper, lower = _bb_series(closes, bb_len, 1.0)
    i = len(bars) - 1
    if upper[i] is None or rsi[i] is None:
        return None, "Not enough data for BB/RSI warm-up"

    close_i = closes[i]
    if version == 1:
        buy_trigger = close_i < lower[i] and rsi[i] > 42.0
        sell_trigger = close_i > upper[i] and rsi[i] > 70.0
    elif version == 2:
        buy_trigger = close_i < lower[i] and rsi[i] > 42.0
        sell_trigger = close_i > upper[i] and rsi[i] > 76.0
    else:
        mfi_len = int(c["MFI_LEN"])
        mfi = _mfi_series(bars, mfi_len)
        if mfi[i] is None:
            return None, "Not enough data for MFI warm-up"
        buy_trigger = close_i < lower[i] and mfi[i] < 60.0
        sell_trigger = close_i > upper[i] and rsi[i] > 65.0 and mfi[i] > 64.0

    return {
        "event": bars[-1], "buy_trigger": bool(buy_trigger), "sell_trigger": bool(sell_trigger),
        "sl_pct": sl_pct, "tp_pct": tp_pct,
    }, None


def detect_s428(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S428 Flawless Victory Strategy — long-only (ดู docstring บนสุดของไฟล์นี้)
    signal="BUY" เมื่อ buy_trigger; "CLOSE" เมื่อ sell_trigger (แจ้งให้ปิดไม้
    long ที่ถืออยู่ ไม่ใช่เปิด short) — คนเรียกต้องจัดการ state การถือไม้เอง"""
    del dt_bkk, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    state, err = compute_state(rates, tf, c)
    if state is None:
        return _wait(err)

    if state["sell_trigger"]:
        return {"signal": "CLOSE", "entry": round(state["event"]["close"], 2),
                "pattern": "S428 CLOSE Flawless Victory", "reason": "sell trigger (flat)"}

    if not state["buy_trigger"]:
        return _wait("No trigger")
    if not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")

    entry = round(state["event"]["close"], 2)
    sl = tp = None
    if state["sl_pct"] is not None:
        sl = round(entry * (1.0 - state["sl_pct"] / 100.0), 2)
        tp = round(entry * (1.0 + state["tp_pct"] / 100.0), 2)

    return {
        "signal": "BUY",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S428 BUY Flawless Victory v{c['VERSION']}",
        "reason": "BB+RSI mean-reversion buy trigger",
        "be_rr": None,
        "cancel_bars": None,
    }
