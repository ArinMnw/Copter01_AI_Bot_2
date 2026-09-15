# -*- coding: utf-8 -*-
"""S433 - AI Gold Star 123 (Coppock Curve) — พอร์ตจาก Pine v6 (indicator ล้วน
ไม่มี strategy()/position sizing ในตัวเอง) — Coppock Curve = WMA(roc(src,rocLong)
+ roc(src,rocShort), wmaLen) แล้วจับจังหวะ "จุดกลับตัวของเส้น" (bullCross =
ta.crossover(coppock, coppock[1]) = จุดต่ำสุดท้องถิ่น, bearCross =
ta.crossunder(coppock, coppock[1]) = จุดสูงสุดท้องถิ่น) เป็นสัญญาณเข้าไม้

⚠️ ต้นฉบับเป็น indicator วาดเส้น/histogram + dashboard เฉยๆ ไม่มีไม้เทรดจริง
พอร์ตนี้ตีความเป็นกลยุทธ์ trend-flip ตาม alertcondition ของต้นฉบับเป๊ะ (ต้นฉบับมี
alert action "closelong"/"closeshort" ที่ยิงพร้อมกับ bearCross/bullCross ฝั่ง
ตรงข้ามอยู่แล้ว จึงตีความเป็น flip position ได้ตรงไปตรงมา ไม่ใช่การตีความเพิ่มเอง):
  - เข้าไม้ที่ bullCross/bearCross (ทิศเดียวกับสัญญาณ)
  - SL = entry -+ ATR(atrLen)*atrMult (i_atrMult default 1.5)
  - TP = entry -+ risk*tp3R (ใช้ TP3 R-multiple เป็นเป้าปิดไม้เต็มจำนวนเดียว —
    ต้นฉบับมี TP1/TP2/TP3 เป็นแค่ alert แจ้งราคาผ่าน ไม่ได้ปิดสถานะบางส่วนจริง
    พอร์ตนี้เลยไม่ทำ partial close ตาม TP1/TP2)
  - ถ้าเกิดสัญญาณสวนทาง (bearCross ระหว่างถือ long, bullCross ระหว่างถือ short)
    ก่อนโดน SL/TP ปิดไม้เดิมทันทีที่ close แท่งนั้น (outcome=FLIP) แล้วเปิดไม้ใหม่
    ทิศตรงข้ามทันที (ตรงกับ action closelong/closeshort ของต้นฉบับ)

deviation อื่นจาก Pine ต้นฉบับ (ตาม convention เดียวกับ S420-S432):
  1) ATR เป็น SMA ของ True Range (ไม่ใช่ Wilder RMA แบบ ta.atr() จริงของ Pine)
  2) entryPrice ต้นฉบับใช้ close[1] (ราคาปิดแท่งก่อนแท่งสัญญาณ) ซึ่งเป็นราคาที่
     ผ่านไปแล้วตอนสัญญาณยืนยัน (isconfirmed) — backtest ใช้ close ของแท่งสัญญาณ
     เอง (close[0]) แทนเพื่อไม่ให้เกิด look-ahead/fill ที่ราคาที่ผ่านไปแล้ว
  3) ตัวกรองเสริมทั้งหมดที่ default ปิดอยู่ในต้นฉบับ (Adaptive Filter, Divergence
     Filter, Slope Acceleration Filter, Volume Confirmation Filter, HTF Alignment
     Filter, Volatility-Adjusted Zero Line, Signal Persistence Filter) ไม่ได้พอร์ต
     มา — เหลือเฉพาะ ADX Filter (i_useAdxFilter) ที่พอร์ตนี้ implement ไว้เพราะ
     เป็นตัวกรองหลักที่มักถูกเปิดใช้ ตัวอื่นซับซ้อนและ default ปิดจึงไม่กระทบผลลัพธ์
     ที่ DEFAULT_CFG (ทุกตัวปิด = ตรงกับ default ของ Pine ต้นฉบับ 100%)
  4) Zero-line cross markers/dashboard/trade-level lines เป็นแค่ visual ไม่มีผล
     ต่อไม้เทรด พอร์ตนี้เลยไม่ทำ
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import pandas as pd

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from strategy119 import _bars
from strategy197 import _wait

MINTICK = 0.01  # XAUUSD ไม่มี real tick size ผ่าน API เลยใช้ค่ามาตรฐานโปรเจกต์

DEFAULT_CFG = {
    "ROC_LONG": 14,
    "ROC_SHORT": 11,
    "WMA_LEN": 10,
    "USE_ADX_FILTER": False,
    "ADX_THRESH": 20.0,
    "ADX_LEN": 14,
    "ATR_LEN": 14,
    "ATR_MULT": 1.5,
    "TP3_R": 3.0,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
}

# sweep ATR_MULT x TP3_R 365d + walk-forward dual-window (2026-09-02, ดู
# sweep_s433_result*.json + project memory s433_coppock_ai_gold_star_progress)
# พบว่า ATR_MULT/TP3_R ผูกกับ TF: มีแค่ H4/H12 เท่านั้นที่ tuned params ดีขึ้นจริง
# และผ่าน walk-forward ทั้งสองครึ่งปี (M1/M5/M15/M30/H1 ไม่มี combo ไหนทะลุ PF>1
# ผ่าน walk-forward เลย รวมถึง D1 ที่ full-year PF ดูดีแต่ n น้อยเกินไปจนไม่
# น่าเชื่อถือ — คงค่า default ไว้ที่ D1 และ TF อื่นทั้งหมด)
TF_CFG_OVERRIDES = {
    "H4": {"ATR_MULT": 2.5, "TP3_R": 2.0},
    "H12": {"ATR_MULT": 2.0, "TP3_R": 2.0},
}


def cfg_for_tf(tf, cfg=None):
    """คืน config ที่ผสาน DEFAULT_CFG -> TF_CFG_OVERRIDES[tf] -> cfg (ผู้เรียก
    override ได้เสมอ) ใช้ตัวเดียวกันทั้ง backtest และ live detect เพื่อไม่ให้
    ค่า tuned ต่อ TF เพี้ยนกันระหว่างสองทาง"""
    merged = dict(DEFAULT_CFG)
    merged.update(TF_CFG_OVERRIDES.get(tf, {}))
    if cfg:
        merged.update(cfg)
    return merged


def _atr_series(bars, period):
    """SMA ของ True Range (ดู docstring หัวไฟล์ข้อ 1)."""
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


def _rma_series(values, period):
    """Wilder RMA — ใช้สำหรับ ADX filter (ta.dmi ต้นฉบับใช้ RMA จริง ไม่ใช่ SMA)."""
    n = len(values)
    out = np.full(n, np.nan, dtype=float)
    if n <= period:
        return out
    seed = np.nanmean(values[:period])
    out[period - 1] = seed
    prev = seed
    for i in range(period, n):
        prev = (prev * (period - 1) + values[i]) / period
        out[i] = prev
    return out


def _wma(values, length):
    weights = np.arange(1, length + 1, dtype=float)  # เก่าสุด=1 ... ใหม่สุด=length
    wsum = weights.sum()
    return (pd.Series(values).rolling(length)
            .apply(lambda x: np.dot(x, weights) / wsum, raw=True).to_numpy())


def _roc(values, length):
    values = np.asarray(values, dtype=float)
    shifted = pd.Series(values).shift(length).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (values - shifted) / shifted * 100.0
    return out


def _adx_series(bars, length):
    n = len(bars)
    highs = np.array([b["high"] for b in bars], dtype=float)
    lows = np.array([b["low"] for b in bars], dtype=float)
    closes = np.array([b["close"] for b in bars], dtype=float)
    prev_high = np.concatenate(([highs[0]], highs[:-1]))
    prev_low = np.concatenate(([lows[0]], lows[:-1]))
    prev_close = np.concatenate(([closes[0]], closes[:-1]))

    up_move = highs - prev_high
    down_move = prev_low - lows
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = np.maximum(highs - lows, np.maximum(np.abs(highs - prev_close), np.abs(lows - prev_close)))

    tr_rma = _rma_series(tr, length)
    plus_dm_rma = _rma_series(plus_dm, length)
    minus_dm_rma = _rma_series(minus_dm, length)

    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = 100.0 * plus_dm_rma / tr_rma
        minus_di = 100.0 * minus_dm_rma / tr_rma
        dx = 100.0 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = _rma_series(np.nan_to_num(dx, nan=0.0), length)
    return adx


def _coppock_series(bars, c):
    closes = np.array([b["close"] for b in bars], dtype=float)
    roc_long = _roc(closes, int(c["ROC_LONG"]))
    roc_short = _roc(closes, int(c["ROC_SHORT"]))
    coppock = _wma(roc_long + roc_short, int(c["WMA_LEN"]))
    return coppock


def run_backtest(bars_raw, cfg=None, spread=0.20, contract_multiplier=1.0):
    """เดินลูปทั้งช่วงบาร์ จำลอง Coppock turning-point + trend-flip entry ครบ
    คืน (trades, stats_extra)"""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    bars = _bars(bars_raw)
    n = len(bars)
    highs = np.array([b["high"] for b in bars], dtype=float)
    lows = np.array([b["low"] for b in bars], dtype=float)
    closes = np.array([b["close"] for b in bars], dtype=float)

    roc_long = int(c["ROC_LONG"])
    roc_short = int(c["ROC_SHORT"])
    wma_len = int(c["WMA_LEN"])
    atr_len = int(c["ATR_LEN"])
    atr_mult = float(c["ATR_MULT"])
    tp3_r = float(c["TP3_R"])
    use_adx = bool(c["USE_ADX_FILTER"])
    adx_len = int(c["ADX_LEN"])
    adx_thresh = float(c["ADX_THRESH"])
    allow_buy = bool(c.get("ALLOW_BUY", True))
    allow_sell = bool(c.get("ALLOW_SELL", True))

    warmup = max(roc_long, roc_short) + wma_len + 5
    if n <= warmup + atr_len + 5:
        return [], {"error": "not enough bars"}

    coppock = _coppock_series(bars, c)
    atr = _atr_series(bars, atr_len)
    atr_safe = np.where(np.isnan(atr), np.maximum(highs - lows, MINTICK * 10.0), atr)
    atr_safe = np.maximum(atr_safe, MINTICK * 10.0)
    adx = _adx_series(bars, adx_len) if use_adx else None

    trade_open = False
    direction = 0
    entry_price = sl_price = tp_price = 0.0
    entry_bar = 0

    trades = []
    flips = entries = 0

    def close_trade(j, exit_price, outcome):
        pnl = (direction * (exit_price - entry_price) - spread) * contract_multiplier
        trades.append({
            "entry_bar": entry_bar, "exit_bar": j,
            "direction": "BUY" if direction > 0 else "SELL",
            "entry": round(entry_price, 2), "sl": round(sl_price, 2), "tp": round(tp_price, 2),
            "exit_price": round(exit_price, 2), "outcome": outcome, "profit": round(pnl, 2),
            "pattern": "S433 AI Gold Star 123 (Coppock)",
            "reason": "",
        })

    for j in range(warmup, n):
        c0, c1, c2 = coppock[j], coppock[j - 1], coppock[j - 2]
        if math.isnan(c0) or math.isnan(c1) or math.isnan(c2):
            continue

        bull_cross = (c0 > c1) and (c1 <= c2)
        bear_cross = (c0 < c1) and (c1 >= c2)

        adx_pass = True
        if use_adx:
            adx_j = adx[j]
            adx_pass = not math.isnan(adx_j) and adx_j >= adx_thresh

        new_long = bull_cross and adx_pass and allow_buy
        new_short = bear_cross and adx_pass and allow_sell
        new_signal = new_long or new_short

        # --- exit check ไม้เปิดอยู่ (เฉพาะแท่งหลังแท่งเข้าไม้ และไม่ใช่แท่ง flip) ---
        if trade_open and j > entry_bar and not new_signal:
            if direction > 0:
                tp_side, sl_side = highs[j] >= tp_price, lows[j] <= sl_price
            else:
                tp_side, sl_side = lows[j] <= tp_price, highs[j] >= sl_price

            if sl_side:
                close_trade(j, sl_price, "SL")
                trade_open = False
            elif tp_side:
                close_trade(j, tp_price, "TP")
                trade_open = False

        # --- สัญญาณสวนทาง/สัญญาณใหม่: ปิดไม้เดิม (ถ้ามี) แล้วเปิดไม้ใหม่ ---
        if new_signal:
            side = 1 if new_long else -1
            if trade_open and direction != side:
                flips += 1
                close_trade(j, float(closes[j]), "FLIP")
                trade_open = False

            if not trade_open:
                atr_j = float(atr_safe[j])
                close_j = float(closes[j])
                direction = side
                entry_price = close_j
                entry_bar = j
                if side > 0:
                    sl_price = entry_price - atr_j * atr_mult
                    risk = entry_price - sl_price
                    tp_price = entry_price + risk * tp3_r
                else:
                    sl_price = entry_price + atr_j * atr_mult
                    risk = sl_price - entry_price
                    tp_price = entry_price - risk * tp3_r
                trade_open = True
                entries += 1

    return trades, {"entries": entries, "flips": flips}


def compute_state(bars_raw, cfg=None):
    """เดินลูปครั้งเดียว (single-pass) ไล่ทั้งหน้าต่าง `bars_raw` แล้วดูว่าแท่ง
    สุดท้าย (แท่งปิดล่าสุด) มี bullCross/bearCross เกิดขึ้นหรือไม่ — ใช้สำหรับ live
    detect_s433() เรียกใหม่ทุกครั้งด้วยหน้าต่างข้อมูลสดที่โตขึ้นเรื่อยๆ (ไม่ persist
    state ข้ามการเรียก ตรงตาม convention detect_sXXX ของโปรเจกต์)

    คืน (state, error) — state=None ถ้าข้อมูลไม่พอ"""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    bars = _bars(bars_raw)
    n = len(bars)
    highs = np.array([b["high"] for b in bars], dtype=float)
    lows = np.array([b["low"] for b in bars], dtype=float)
    closes = np.array([b["close"] for b in bars], dtype=float)

    roc_long = int(c["ROC_LONG"])
    roc_short = int(c["ROC_SHORT"])
    wma_len = int(c["WMA_LEN"])
    atr_len = int(c["ATR_LEN"])
    atr_mult = float(c["ATR_MULT"])
    tp3_r = float(c["TP3_R"])
    use_adx = bool(c["USE_ADX_FILTER"])
    adx_len = int(c["ADX_LEN"])
    adx_thresh = float(c["ADX_THRESH"])

    warmup = max(roc_long, roc_short) + wma_len + 5
    if n <= warmup + atr_len + 5:
        return None, f"not enough bars (n={n})"

    last = n - 1
    coppock = _coppock_series(bars, c)
    atr = _atr_series(bars, atr_len)
    atr_safe = np.where(np.isnan(atr), np.maximum(highs - lows, MINTICK * 10.0), atr)
    atr_safe = np.maximum(atr_safe, MINTICK * 10.0)

    c0, c1, c2 = coppock[last], coppock[last - 1], coppock[last - 2]
    if math.isnan(c0) or math.isnan(c1) or math.isnan(c2):
        return {"signal_dir": 0, "atr": float(atr_safe[last])}, None

    bull_cross = (c0 > c1) and (c1 <= c2)
    bear_cross = (c0 < c1) and (c1 >= c2)

    adx_pass = True
    if use_adx:
        adx = _adx_series(bars, adx_len)
        adx_j = adx[last]
        adx_pass = not math.isnan(adx_j) and adx_j >= adx_thresh

    if not adx_pass or not (bull_cross or bear_cross):
        return {"signal_dir": 0, "atr": float(atr_safe[last]), "coppock": float(c0)}, None

    side = 1 if bull_cross else -1
    atr_j = float(atr_safe[last])
    close_j = float(closes[last])
    if side > 0:
        sl = close_j - atr_j * atr_mult
        risk = close_j - sl
        tp = close_j + risk * tp3_r
    else:
        sl = close_j + atr_j * atr_mult
        risk = sl - close_j
        tp = close_j - risk * tp3_r

    return {
        "signal_dir": side, "atr": atr_j, "coppock": float(c0),
        "entry": close_j, "sl": sl, "tp": tp,
    }, None


def detect_s433(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S433 AI Gold Star 123 (Coppock Curve) — เรียก compute_state() ใหม่ทุกครั้ง
    จาก `rates` ทั้งหน้าต่างที่ได้รับ ให้สัญญาณเฉพาะตอนแท่งปิดล่าสุด (rates[-1])
    เป็นแท่ง bullCross/bearCross จริง (ตรง alertcondition ของต้นฉบับเป๊ะ)"""
    del dt_bkk, kwargs
    c = cfg_for_tf(tf, cfg)

    state, err = compute_state(rates, c)
    if state is None:
        return _wait(err)

    if state["signal_dir"] == 0:
        return _wait(f"No bullCross/bearCross at last bar (coppock={state.get('coppock')} "
                     f"atr={state['atr']:.2f})")

    signal = "BUY" if state["signal_dir"] > 0 else "SELL"
    if signal == "BUY" and not bool(c.get("ALLOW_BUY", True)):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c.get("ALLOW_SELL", True)):
        return _wait("SELL disabled")

    entry = round(state["entry"], 2)
    sl = round(state["sl"], 2)
    tp = round(state["tp"], 2)

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S433 {signal} AI Gold Star 123 (Coppock)",
        "reason": f"coppock={state['coppock']:.4f} atr={state['atr']:.2f}",
    }
