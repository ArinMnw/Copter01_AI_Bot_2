# -*- coding: utf-8 -*-
"""S429 - UT Bot Alerts Strategy (พอร์ตจาก Pine v5 by StrategiesForEveryone,
core signal by @QuantNomad) — ATR trailing-stop crossover (UT Bot) + EMA200
trend filter: BUY เมื่อราคาตัดขึ้นเหนือ ATR trailing stop และ close>EMA200,
SELL(short) เมื่อตัดลงใต้ trailing stop และ close<EMA200

ไม่มี security() ที่ repaint (ตัวเลือก Heikin Ashi source ใช้
`lookahead=barmerge.lookahead_off` อยู่แล้วในต้นฉบับ, default ปิดอยู่ด้วย
h=false) → ไม่มีความเสี่ยง repaint

⚠️ ต้นฉบับซับซ้อนมาก มี partial take-profit (ปิด 50% ที่ TP แล้วลาก SL ที่
เหลือ), breakeven trail, stop-loss เลือกได้ 2 แบบ (ATR หรือ swing high/low),
session/date filter, position sizing แบบ cash-based ที่หน่วยดูไม่สอดคล้องกัน
เอง (long_amount คำนวณเป็นหน่วย "contracts" แต่ default_qty_type=cash ซึ่ง
ตีความเป็น USD — เป็นข้อบกพร่องที่พบได้ในสคริปต์ public ทั่วไป) — พอร์ตนี้
ตัดทอนเหลือ:
  - SL = ATR(14)*1.5 จาก current candle เท่านั้น (ไม่พอร์ต swing high/low mode)
  - TP = entry + SL_distance*RR(3.0) → ปิดเต็มไม้ (ไม่พอร์ต partial 50%+trail)
  - Breakeven trail ที่ RR=0.75 (ย้าย SL ไป entry เมื่อราคาไปถึงระยะ BE)
  - ปิดไม้ก่อนกำหนดถ้าเกิดสัญญาณตรงข้ามระหว่างที่ไม้กำลังกำไรอยู่ (ตรงต้นฉบับ)
  - ไม่พอร์ต session/date filter (backtest ใช้ --start/--end ควบคุมช่วงแทน)
  - fill ที่ close ของแท่งสัญญาณเอง (ตรงกับ process_orders_on_close=true ของ
    ต้นฉบับ ต่างจาก S420-428 ที่ fill ที่ open ของแท่งถัดไป)
  - position sizing ใช้ risk-based ที่ถูกต้องเชิงหน่วย: qty_oz = (equity *
    risk%/100) / stop_distance_price (ไม่ใช้สูตร cash-type ที่หน่วยไม่ตรงกัน
    ของต้นฉบับ) — เปิดผ่าน --tv-mode ใน backtest, default ยังใช้ fixed lot
    ตาม convention เดิมของโปรเจกต์
  - ATR ที่นี่ใช้สูตร SMA ของ True Range (ตาม `_atr()` ที่ใช้ทั่วโปรเจกต์)
    ไม่ใช่ RMA/Wilder สมูทตาม `ta.atr()` ของ Pine เป๊ะ (ต่างเล็กน้อยแต่
    consistent กับ strategy อื่นในโปรเจกต์นี้)"""

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
    "KEY_VALUE": 3.0,       # 'a' ใน UT Bot — คูณ TR เพื่อได้ nLoss (ระยะ trailing)
    "ATR_SL_PERIOD": 14,
    "ATR_SL_MULT": 1.5,
    "EMA_TREND_LEN": 200,
    "RR_BE": 0.75,
    "RR_TP": 3.0,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
}


def _true_range_series(bars):
    n = len(bars)
    out = [None] * n
    if n == 0:
        return out
    out[0] = bars[0]["high"] - bars[0]["low"]
    for i in range(1, n):
        prev_close = bars[i - 1]["close"]
        out[i] = max(bars[i]["high"] - bars[i]["low"],
                      abs(bars[i]["high"] - prev_close),
                      abs(bars[i]["low"] - prev_close))
    return out


def _atr_series(bars, period):
    tr = _true_range_series(bars)
    n = len(bars)
    out = [None] * n
    for i in range(period - 1, n):
        out[i] = sum(tr[i - period + 1:i + 1]) / period
    return out


def _ema_series(values, length):
    n = len(values)
    out = [None] * n
    if n < length:
        return out
    seed = sum(values[:length]) / length
    out[length - 1] = seed
    alpha = 2.0 / (length + 1.0)
    prev = seed
    for i in range(length, n):
        prev = alpha * values[i] + (1.0 - alpha) * prev
        out[i] = prev
    return out


def _ut_bot_series(bars, key_value):
    """คืน (trailing_stop, above, below) — above[i]/below[i] = True ตรงจุดที่
    ราคาตัดขึ้น/ลงผ่าน trailing stop (non-repaint, ใช้แท่งที่ปิดแล้วเท่านั้น)"""
    tr = _true_range_series(bars)
    n = len(bars)
    src = [b["close"] for b in bars]
    stop = [0.0] * n
    for i in range(n):
        n_loss = key_value * (tr[i] or 0.0)
        prev_stop = stop[i - 1] if i > 0 else 0.0
        prev_src = src[i - 1] if i > 0 else 0.0
        if src[i] > prev_stop and prev_src > prev_stop:
            stop[i] = max(prev_stop, src[i] - n_loss)
        elif src[i] < prev_stop and prev_src < prev_stop:
            stop[i] = min(prev_stop, src[i] + n_loss)
        elif src[i] > prev_stop:
            stop[i] = src[i] - n_loss
        else:
            stop[i] = src[i] + n_loss

    above = [False] * n
    below = [False] * n
    for i in range(1, n):
        above[i] = src[i - 1] <= stop[i - 1] and src[i] > stop[i]
        below[i] = stop[i - 1] <= src[i - 1] and stop[i] > src[i]
    return stop, above, below


def compute_state(rates, tf="", cfg=None):
    """คืน (state, None) หรือ (None, เหตุผล). state = {"event","buy_trigger",
    "sell_trigger","sl_long","sl_short","bullish","bearish"}"""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    base_minutes = TF_MINUTES.get(str(tf).upper())
    if base_minutes is None:
        return None, f"Unsupported tf {tf}"

    ema_len = int(c["EMA_TREND_LEN"])
    if rates is None or len(rates) < ema_len + 5:
        return None, "Not enough data"
    try:
        bars = _bars(rates)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return None, f"Invalid rates: {exc}"

    closes = [b["close"] for b in bars]
    ema200 = _ema_series(closes, ema_len)
    atr_sl = _atr_series(bars, int(c["ATR_SL_PERIOD"]))
    _, above, below = _ut_bot_series(bars, float(c["KEY_VALUE"]))

    i = len(bars) - 1
    if ema200[i] is None or atr_sl[i] is None:
        return None, "Not enough data for EMA/ATR warm-up"

    close_i = closes[i]
    bullish = close_i > ema200[i]
    bearish = close_i < ema200[i]
    sl_mult = float(c["ATR_SL_MULT"])
    sl_long = close_i - atr_sl[i] * sl_mult
    sl_short = close_i + atr_sl[i] * sl_mult

    return {
        "event": bars[-1], "buy_trigger": bool(above[i] and bullish),
        "sell_trigger": bool(below[i] and bearish),
        "sl_long": sl_long, "sl_short": sl_short,
        "bullish": bullish, "bearish": bearish,
    }, None


def detect_s429(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S429 UT Bot Alerts Strategy — ดู docstring บนสุดของไฟล์นี้ (⚠️ พอร์ต
    เฉพาะ core signal + ATR SL/TP/BE เท่านั้น ไม่มี partial TP/session filter)"""
    del dt_bkk, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    state, err = compute_state(rates, tf, c)
    if state is None:
        return _wait(err)

    if state["buy_trigger"] and bool(c["ALLOW_BUY"]):
        signal = "BUY"
    elif state["sell_trigger"] and bool(c["ALLOW_SELL"]):
        signal = "SELL"
    else:
        return _wait("No trigger")

    entry = round(state["event"]["close"], 2)
    rr_tp = float(c["RR_TP"])
    if signal == "BUY":
        sl = round(state["sl_long"], 2)
        distance = entry - sl
        tp = round(entry + distance * rr_tp, 2)
    else:
        sl = round(state["sl_short"], 2)
        distance = sl - entry
        tp = round(entry - distance * rr_tp, 2)

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S429 {signal} UT Bot Alerts",
        "reason": f"UT Bot cross + EMA{c['EMA_TREND_LEN']} trend filter",
        "be_rr": float(c["RR_BE"]),
        "cancel_bars": None,
    }
