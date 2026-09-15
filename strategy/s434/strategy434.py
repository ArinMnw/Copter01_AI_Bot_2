# -*- coding: utf-8 -*-
"""S434 - Breakout Probability (Expo) — พอร์ตจาก Pine v5 (indicator ล้วน ไม่มี
strategy()/position sizing ในตัวเอง) — indicator ต้นฉบับสะสมสถิติ (running count
จากจุดเริ่ม chart) แยกตามสีแท่งก่อนหน้า (เขียว/แดง) ว่าแท่งถัดไปทำ higher-high
(hh = h>=h[1]+step*i) หรือ lower-low (ll = l<=l[1]-step*i) บ่อยกว่ากัน ที่ระดับ
i=0..nbr-1 (perc% step) แล้วเทียบ a1/b1 (เขียว) หรือ a2/b2 (แดง) เพื่อสรุป BIAS
(BULLISH/BEARISH) วาดเป็นเส้น/label ราคาบนชาร์ต — ต้นฉบับใช้แค่ระดับ i=0 (x=0,
คือ h[1]/l[1] เป๊ะ ไม่มี offset) ในการตัดสิน BIAS/backtest แม้ nbr จะปรับได้ถึง 5
เส้น (เส้นอื่นเป็นแค่ visual ไม่กระทบ BIAS)

⚠️ ต้นฉบับมีบั๊ก look-ahead ในตัวเอง: ฟังก์ชัน Backtest(v) ของ Pine เช็ค h/l ของ
"แท่งปัจจุบัน" (แท่งเดียวกับที่เพิ่งใช้อัปเดตสถิติ hh/ll ผ่าน Score() ไปหมาดๆ) กับ
BIAS ที่มาจากสถิติที่เพิ่งอัปเดตนั้นเอง = self-referential (ใช้ผลลัพธ์ของแท่งเดียวกัน
มาทั้งสร้างสถิติและมาเช็คว่าตรงสถิติหรือเปล่า) ทำให้ WR ที่ dashboard โชว์สูงเทียม
ไม่ใช่สัญญาณ predictive จริง พอร์ตนี้แก้ look-ahead โดยเลื่อน BIAS ไปทำนาย "แท่ง
ถัดไป" แทน (เข้าไม้ที่ close ของแท่งที่เพิ่งอัปเดตสถิติ แล้ววัดผลจากแท่งถัดไปเป็นต้นไป
เท่านั้น) — ตีความเป็นกลยุทธ์ตามนี้:
  - ทุกแท่ง m (m>=1) อัปเดตสถิติก่อน: prevGreen = close[m-1]>open[m-1],
    brokeUp = high[m]>=high[m-1], brokeDown = low[m]<=low[m-1] (คู่ตรงกับ
    ต้นฉบับ green/hh/ll ที่ x=0 เป๊ะ) แล้วค่อยดู BIAS จากสีแท่ง m เอง (close[m]
    vs open[m]) เทียบกับสถิติที่เพิ่งอัปเดตผ่าน m: BULLISH ถ้า a>=b (hh-rate >=
    ll-rate ของสีนั้น) ไม่งั้น BEARISH — ตรง `math.max(a,b)==a?"BULLISH":"BEARISH"`
    ของต้นฉบับเป๊ะ
  - เข้าไม้ที่ close(m) ทิศ BIAS, TP = high[m] (BULLISH) หรือ low[m] (BEARISH)
    = ระดับ i=0 เป๊ะที่ต้นฉบับ Backtest() ใช้ (h[1]/l[1] ของแท่งถัดไปในมุมมอง Pine
    = high/low ของแท่ง m เอง ในมุมมอง index ของเรา)
  - SL = ATR(atrLen)*atrMult (ต้นฉบับไม่มี SL จริง เพราะเป็นแค่ indicator วัด
    win/loss การแตะระดับ ไม่ใช่ position — พอร์ตนี้ต้องเพิ่มเพื่อให้เป็นกลยุทธ์เทรด
    ได้จริง ตาม convention เดียวกับ S420-S433)
  - ไม่เปิดไม้ซ้อน/ไม่มี flip (ต้นฉบับไม่มี alertcondition closelong/closeshort
    แบบ S432/S433 ให้ตีความ) รอ SL/TP ปิดก่อนถึงเปิดไม้ใหม่ได้
  - ต้องมีตัวอย่างสะสมของสีนั้นๆ อย่างน้อย MIN_SAMPLES แท่งก่อนเริ่มเชื่อ BIAS
    (ต้นฉบับเริ่มนับจาก 0 ตัวอย่างทันที ทำให้ช่วงต้น chart อัตราส่วนสุ่ม/ไม่นิ่ง —
    พอร์ตนี้เพิ่ม floor กันสัญญาณสุ่มช่วง warmup)

deviation อื่นจาก Pine ต้นฉบับ:
  1) ATR เป็น SMA ของ True Range (ไม่ใช่ Wilder RMA)
  2) ระดับ i=1..nbr-1 (step ที่ไกลกว่า h[1]/l[1]), Backtest() panel, table
     สถิติ WIN/LOSS, เส้น/label/linefill เป็นแค่ visual ทั้งหมด ไม่กระทบ BIAS —
     พอร์ตนี้ไม่ implement เพราะไม่มีผลต่อไม้เทรด
  3) doji (close==open) ต้นฉบับนับเป็นไม่เขียวไม่แดง แต่ branch if/else ของ
     Pine (`green ? : `) ปฏิบัติกับ doji เหมือน "แดง" อยู่ดี (เพราะเช็คแค่ green
     เป็น false) พอร์ตนี้ทำตามพฤติกรรมจริงนี้: close<=open ถือเป็น "แดง"
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from strategy119 import _bars
from strategy197 import _wait

MINTICK = 0.01  # XAUUSD ไม่มี real tick size ผ่าน API เลยใช้ค่ามาตรฐานโปรเจกต์

DEFAULT_CFG = {
    "ATR_LEN": 14,
    "ATR_MULT": 1.5,
    "MIN_SAMPLES": 30,
    # TP floor เพิ่มเข้ามา (ไม่มีในต้นฉบับ) — บังคับ TP ห่าง entry อย่างน้อย
    # ATR*MIN_TP_ATR_MULT แทนการใช้ high[m]/low[m] ดิบๆ (ระดับ i=0 ของต้นฉบับ) ซึ่ง
    # มักใกล้ entry มากจนแพ้ spread ถี่ๆ — 0.0 = ปิด (พฤติกรรมเดิมตรงต้นฉบับ 100%)
    "MIN_TP_ATR_MULT": 0.0,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
}


# sweep MIN_TP_ATR_MULT x ATR_MULT 365d + walk-forward dual-window
# (2026-09-02, ดู sweep_s434_result_*.json + wf_s434_output.log + project
# memory s434_breakout_probability_negative_result) พบว่า TP floor (บังคับ TP
# ห่าง entry อย่างน้อย ATR*MIN_TP_ATR_MULT แทน high[m]/low[m] ดิบๆ ของต้นฉบับ)
# กู้ TF สูงให้กำไรจริงและผ่าน walk-forward ทั้งสองครึ่งปี — M1/M5/M15/M30 ยังคง
# ติดลบทุก combo ที่ลอง (M30 ดีสุดก็แค่ PF~1.02-1.05 บางเกินไป) เลยคงค่า default
# ไว้ (= พฤติกรรมเดิมตรงต้นฉบับ 100%, ไม่ควรเทรดจริง)
TF_CFG_OVERRIDES = {
    "H1":  {"ATR_MULT": 1.0, "MIN_TP_ATR_MULT": 2.0},   # PF 1.19 (H1-half 1.24 / H2-half 1.14)
    "H4":  {"ATR_MULT": 1.0, "MIN_TP_ATR_MULT": 3.0},   # PF 1.30 (1.09 / 1.61) — n บาง (188/365d)
    "H12": {"ATR_MULT": 2.0, "MIN_TP_ATR_MULT": 0.75},  # PF 2.06 (2.18 / 1.94) — แข็งแรงสุด WR~83%
    "D1":  {"ATR_MULT": 1.0, "MIN_TP_ATR_MULT": 1.5},   # PF 2.16 (3.43 / 1.19) — ครึ่งหลังอ่อนลงมาก n=24
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


def _bias_side(hh_count, ll_count, total, min_samples):
    """คืน 1 (BULLISH) / -1 (BEARISH) / 0 (ตัวอย่างไม่พอ) ตาม a>=b ของต้นฉบับ"""
    if total < min_samples:
        return 0
    a = hh_count / total
    b = ll_count / total
    return 1 if a >= b else -1


def run_backtest(bars_raw, cfg=None, spread=0.20, contract_multiplier=1.0):
    """เดินลูปทั้งช่วงบาร์ สะสมสถิติ hh/ll แยกสีแท่งก่อนหน้า + เข้าไม้ตาม BIAS
    ที่เลื่อนไปทำนายแท่งถัดไป (แก้ look-ahead ของต้นฉบับ) คืน (trades, stats_extra)"""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    bars = _bars(bars_raw)
    n = len(bars)
    opens = np.array([b["open"] for b in bars], dtype=float)
    highs = np.array([b["high"] for b in bars], dtype=float)
    lows = np.array([b["low"] for b in bars], dtype=float)
    closes = np.array([b["close"] for b in bars], dtype=float)

    atr_len = int(c["ATR_LEN"])
    atr_mult = float(c["ATR_MULT"])
    min_samples = int(c["MIN_SAMPLES"])
    min_tp_atr_mult = float(c.get("MIN_TP_ATR_MULT", 0.0))
    allow_buy = bool(c.get("ALLOW_BUY", True))
    allow_sell = bool(c.get("ALLOW_SELL", True))

    warmup = max(min_samples, 2)
    if n <= warmup + atr_len + 5:
        return [], {"error": "not enough bars"}

    atr = _atr_series(bars, atr_len)
    atr_safe = np.where(np.isnan(atr), np.maximum(highs - lows, MINTICK * 10.0), atr)
    atr_safe = np.maximum(atr_safe, MINTICK * 10.0)

    green_total = green_hh = green_ll = 0
    red_total = red_hh = red_ll = 0

    trade_open = False
    direction = 0
    entry_price = sl_price = tp_price = 0.0
    entry_bar = 0

    trades = []
    entries = 0

    def close_trade(j, exit_price, outcome):
        pnl = (direction * (exit_price - entry_price) - spread) * contract_multiplier
        trades.append({
            "entry_bar": entry_bar, "exit_bar": j,
            "direction": "BUY" if direction > 0 else "SELL",
            "entry": round(entry_price, 2), "sl": round(sl_price, 2), "tp": round(tp_price, 2),
            "exit_price": round(exit_price, 2), "outcome": outcome, "profit": round(pnl, 2),
            "pattern": "S434 Breakout Probability (Expo)",
            "reason": "",
        })

    for m in range(1, n):
        prev_green = closes[m - 1] > opens[m - 1]
        broke_up = highs[m] >= highs[m - 1]
        broke_down = lows[m] <= lows[m - 1]

        if prev_green:
            green_total += 1
            if broke_up:
                green_hh += 1
            if broke_down:
                green_ll += 1
        else:
            red_total += 1
            if broke_up:
                red_hh += 1
            if broke_down:
                red_ll += 1

        # --- exit check ไม้เปิดอยู่ (เฉพาะแท่งหลังแท่งเข้าไม้) ---
        if trade_open and m > entry_bar:
            if direction > 0:
                tp_side, sl_side = highs[m] >= tp_price, lows[m] <= sl_price
            else:
                tp_side, sl_side = lows[m] <= tp_price, highs[m] >= sl_price

            if sl_side:
                close_trade(m, sl_price, "SL")
                trade_open = False
            elif tp_side:
                close_trade(m, tp_price, "TP")
                trade_open = False

        if trade_open:
            continue

        # --- BIAS จากสีแท่ง m เอง + สถิติที่เพิ่งอัปเดตผ่านแท่ง m ---
        cur_green = closes[m] > opens[m]
        if cur_green:
            side = _bias_side(green_hh, green_ll, green_total, min_samples)
        else:
            side = _bias_side(red_hh, red_ll, red_total, min_samples)

        if side == 0:
            continue
        if side > 0 and not allow_buy:
            continue
        if side < 0 and not allow_sell:
            continue

        atr_j = float(atr_safe[m])
        close_m = float(closes[m])
        direction = side
        entry_price = close_m
        entry_bar = m
        if side > 0:
            tp_price = max(float(highs[m]), entry_price + atr_j * min_tp_atr_mult)
            sl_price = entry_price - atr_j * atr_mult
        else:
            tp_price = min(float(lows[m]), entry_price - atr_j * min_tp_atr_mult)
            sl_price = entry_price + atr_j * atr_mult
        trade_open = True
        entries += 1

    return trades, {"entries": entries}


def compute_state(bars_raw, cfg=None):
    """เดินลูปครั้งเดียว (single-pass) ไล่ทั้งหน้าต่าง `bars_raw` สะสมสถิติ hh/ll
    แยกสีแท่งให้ครบ แล้วดูว่าแท่งสุดท้าย (แท่งปิดล่าสุด) ให้ BIAS หรือไม่ — ใช้สำหรับ
    live detect_s434() เรียกใหม่ทุกครั้งด้วยหน้าต่างข้อมูลสดที่โตขึ้นเรื่อยๆ (ไม่
    persist state ข้ามการเรียก ตรง convention detect_sXXX ของโปรเจกต์)

    คืน (state, error) — state=None ถ้าข้อมูลไม่พอ"""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    bars = _bars(bars_raw)
    n = len(bars)
    opens = np.array([b["open"] for b in bars], dtype=float)
    highs = np.array([b["high"] for b in bars], dtype=float)
    lows = np.array([b["low"] for b in bars], dtype=float)
    closes = np.array([b["close"] for b in bars], dtype=float)

    atr_len = int(c["ATR_LEN"])
    atr_mult = float(c["ATR_MULT"])
    min_samples = int(c["MIN_SAMPLES"])
    min_tp_atr_mult = float(c.get("MIN_TP_ATR_MULT", 0.0))

    warmup = max(min_samples, 2)
    if n <= warmup + atr_len + 5:
        return None, f"not enough bars (n={n})"

    last = n - 1

    atr = _atr_series(bars, atr_len)
    atr_safe = np.where(np.isnan(atr), np.maximum(highs - lows, MINTICK * 10.0), atr)
    atr_safe = np.maximum(atr_safe, MINTICK * 10.0)

    green_total = green_hh = green_ll = 0
    red_total = red_hh = red_ll = 0

    for m in range(1, n):
        prev_green = closes[m - 1] > opens[m - 1]
        broke_up = highs[m] >= highs[m - 1]
        broke_down = lows[m] <= lows[m - 1]
        if prev_green:
            green_total += 1
            if broke_up:
                green_hh += 1
            if broke_down:
                green_ll += 1
        else:
            red_total += 1
            if broke_up:
                red_hh += 1
            if broke_down:
                red_ll += 1

    cur_green = closes[last] > opens[last]
    if cur_green:
        side = _bias_side(green_hh, green_ll, green_total, min_samples)
        samples = green_total
    else:
        side = _bias_side(red_hh, red_ll, red_total, min_samples)
        samples = red_total

    atr_j = float(atr_safe[last])
    if side == 0:
        return {"signal_dir": 0, "atr": atr_j, "samples": samples}, None

    close_last = float(closes[last])
    if side > 0:
        tp = max(float(highs[last]), close_last + atr_j * min_tp_atr_mult)
        sl = close_last - atr_j * atr_mult
    else:
        tp = min(float(lows[last]), close_last - atr_j * min_tp_atr_mult)
        sl = close_last + atr_j * atr_mult

    return {
        "signal_dir": side, "atr": atr_j, "samples": samples,
        "entry": close_last, "sl": sl, "tp": tp,
    }, None


def detect_s434(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S434 Breakout Probability (Expo) — เรียก compute_state() ใหม่ทุกครั้งจาก
    `rates` ทั้งหน้าต่างที่ได้รับ ให้สัญญาณเฉพาะตอนแท่งปิดล่าสุดมี BIAS (ตัวอย่าง
    สะสม >= MIN_SAMPLES) เท่านั้น"""
    del dt_bkk, kwargs
    c = cfg_for_tf(tf, cfg)

    state, err = compute_state(rates, c)
    if state is None:
        return _wait(err)

    if state["signal_dir"] == 0:
        return _wait(f"No BIAS at last bar (samples={state['samples']} atr={state['atr']:.2f})")

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
        "pattern": f"S434 {signal} Breakout Probability (Expo)",
        "reason": f"samples={state['samples']} atr={state['atr']:.2f}",
    }
