# -*- coding: utf-8 -*-
"""S432 - Market Path Forecast [BOSWaves] v1.0: พอร์ตจาก Pine v6 (indicator ล้วน
ไม่มี strategy()/position sizing ในตัวเอง) — swing tracker (highest/lowest
swingLen บาร์) หา leg บน/ล่างล่าสุด สะสมสถิติ %move และระยะเวลา (bar count)
ของ leg ในอดีต (แยกทิศ bull/bear + รวม all) แล้วใช้ weighted average/deviation
(น้ำหนัก = ลำดับ ใหม่สุดน้ำหนักมากสุด) คำนวณเป้าราคาคาดการณ์ (T1/T2/T3/
Extension/Opposite/Invalidation) ทุกครั้งที่ทิศ swing กลับตัว (directionChanged)
พร้อม snap เป้าเข้าใกล้ pivot high/low ในอดีต (historical structure) ถ้าอยู่ใน
รัศมี ATR ที่กำหนด

⚠️ ต้นฉบับเป็น indicator วาด path forecast cone + label ราคาเฉยๆ ไม่มีไม้เทรด
จริง พอร์ตนี้ตีความเป็นกลยุทธ์ trend-flip เอง (ไม่ได้อยู่ใน Pine ต้นฉบับ):
  - เข้าไม้ที่ close ของแท่ง directionChanged ทิศเดียวกับ forecastSide
    (ตรงกับ alertcondition "Market Path Bullish/Bearish" ของต้นฉบับเป๊ะ)
  - SL = forecastInvalidation, TP = forecastTarget3 (เป้าปลายทาง 100% ของ
    baseDistance ที่คำนวณจาก forecastPct) คำนวณที่แท่งเข้าไม้แท่งเดียว
    (ไม่ trail ตาม snap ใหม่ทุกแท่งเหมือนของ non-islast วาดใหม่ทุกแท่ง — ค้าง
    ค่าไว้ตอนเข้าไม้เพื่อให้ backtest วัด SL/TP คงที่ได้)
  - ถ้าทิศกลับตัวอีกครั้ง (directionChanged) ก่อนโดน SL/TP/timeout ปิดไม้เดิม
    ทันทีที่ close แท่งนั้น (outcome=FLIP) แล้วเปิดไม้ใหม่ทิศตรงข้ามถ้า
    forecastReady (เพราะ forecast เดิมถือว่า invalidate ไปแล้วตามตรรกะ
    indicator ที่ลบ/วาดใหม่ทุกครั้งที่ dir เปลี่ยน)
  - timeout = calculatedForecastBars (adaptive หรือ fixed ตาม input) นับจาก
    แท่งเข้าไม้ ปิดที่ close ของแท่ง timeout (ต้นฉบับไม่ได้นิยามราคาออกตอน
    timeout เพราะไม่ใช่ position จริง — ใช้ convention เดียวกับ S431)

deviation อื่นจาก Pine ต้นฉบับ (ตาม convention เดียวกับ S420-S431):
  1) ATR เป็น SMA ของ True Range (ไม่ใช่ Wilder RMA แบบ ta.atr() จริงของ Pine)
  2) fastEMA/slowEMA (momentum bend) และ pathStretch/pathBend/confidenceInterval
     /levelStartPct ใช้แค่วาด path cone + label position เท่านั้น ไม่กระทบ
     ราคาระดับ T1-T3/Extension/Opposite/Invalidation เลย พอร์ตนี้เลยไม่
     implement (ไม่กระทบผลเทรด)
  3) countConfluence ถูก define ไว้ใน Pine ต้นฉบับแต่ไม่เคยถูกเรียกใช้จริง
     ในสคริปต์ที่ได้รับมา (ไม่มีผลต่อ output ใดๆ) พอร์ตนี้เลยข้าม
  4) โครงสร้าง historical structure (SRZone box/line, broken-tracking,
     maxStructureZones, structureMaxAge) ใช้แค่วาดกล่อง S/R บนชาร์ต ไม่มีผล
     ต่อการคำนวณ snapLevel (snapLevel ใช้ structurePrices/structureHighs
     array ล้วน ไม่ผูกกับ SRZone object) พอร์ตนี้เลยเก็บเฉพาะ
     structurePrices/structureHighs (cap 100 ตัวล่าสุดเหมือนต้นฉบับ) ไม่ทำ
     box/line object
  5) entryPrice ใช้ close ของแท่ง directionChanged ตรงตาม alertcondition
     ต้นฉบับ (ไม่ fill ที่ open แท่งถัดไป)
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
    "SWING_LEN": 16,
    "SAMPLES": 20,
    "ATR_LEN": 200,
    "ADAPTIVE_HORIZON": True,
    "FIXED_FORECAST_BARS": 78,
    "MIN_FORECAST_BARS": 8,
    "MAX_FORECAST_BARS": 105,
    "MIN_TARGET_ATR": 5.0,
    "FORECAST_ZONE_ATR": 0.10,
    "STRUCT_LEN": 5,
    "STRUCT_SNAP_ATR": 0.75,
    "STRUCT_SNAP_STRENGTH": 0.65,
    # --- SL/TP tuning (ตรงตาม raw_t3/raw_inv ของ Pine ต้นฉบับที่ค่าเริ่มต้น) ---
    "TP_BASE_MULT": 2.0,    # tp = close + side*baseDistance*TP_BASE_MULT (ต้นฉบับ Pine = T3 เต็ม 1.0
                            # แต่ sweep_s432.py 365d M15/H1 พบว่า 2.0 ดีกว่าทั้งสอง TF และผ่าน
                            # dual-window robustness เลยตั้งเป็น default ใหม่ของพอร์ตนี้)
    "SL_ATR_MULT": 1.50,    # sl floor #1 = atr*SL_ATR_MULT (ต้นฉบับ rawInvalidation)
    "SL_BASE_MULT": 0.40,   # sl floor #2 = baseDistance*SL_BASE_MULT (เอา max ของสองตัว)
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
}


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


def _find_pivots(values, length, is_high):
    """คืน (confirm_index, center_index, price) ของ pivot high/low แบบ
    ta.pivothigh/pivotlow (ชนะทุกจุดในหน้าต่าง length ทั้งสองข้างเป๊ะ ไม่เสมอ)."""
    n = len(values)
    out = []
    for c in range(length, n - length):
        window = values[c - length:c + length + 1]
        center = values[c]
        if is_high:
            if center == max(window) and list(window).count(center) == 1:
                out.append((c + length, c, center))
        else:
            if center == min(window) and list(window).count(center) == 1:
                out.append((c + length, c, center))
    return out


def _push_sample(values, value, maximum):
    if value is not None and not math.isnan(value) and value > 0:
        values.append(value)
        if len(values) > maximum:
            values.pop(0)


def _weighted_average(values):
    if not values:
        return None
    tw = 0.0
    ws = 0.0
    for i, v in enumerate(values):
        w = i + 1.0
        ws += v * w
        tw += w
    return ws / tw if tw > 0 else None


def _weighted_deviation(values, mean_value):
    if not values or mean_value is None:
        return 0.0
    tw = 0.0
    wv = 0.0
    for i, v in enumerate(values):
        w = i + 1.0
        diff = v - mean_value
        wv += diff * diff * w
        tw += w
    return math.sqrt(wv / tw) if tw > 0 else 0.0


def _snap_level(structure_prices, structure_highs, raw, max_dist, blend, want_high, anchor, side):
    if math.isnan(raw):
        return raw
    best_price = raw
    best_distance = max_dist + MINTICK
    for p, is_high in zip(structure_prices, structure_highs):
        correct_side = p > anchor if side > 0 else p < anchor
        if is_high == want_high and correct_side:
            distance = abs(p - raw)
            if distance <= max_dist and distance < best_distance:
                best_distance = distance
                best_price = p
    return raw * (1.0 - blend) + best_price * blend


def run_backtest(bars_raw, cfg=None, spread=0.20, contract_multiplier=1.0):
    """เดินลูปทั้งช่วงบาร์ จำลอง swing/forecast engine + trend-flip entry ครบ
    คืน (trades, stats_extra)"""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    bars = _bars(bars_raw)
    n = len(bars)
    highs = np.array([b["high"] for b in bars], dtype=float)
    lows = np.array([b["low"] for b in bars], dtype=float)
    closes = np.array([b["close"] for b in bars], dtype=float)

    swing_len = int(c["SWING_LEN"])
    samples_n = int(c["SAMPLES"])
    atr_len = int(c["ATR_LEN"])
    struct_len = int(c["STRUCT_LEN"])
    adaptive_horizon = bool(c["ADAPTIVE_HORIZON"])
    fixed_forecast_bars = int(c["FIXED_FORECAST_BARS"])
    min_forecast_bars = int(c["MIN_FORECAST_BARS"])
    max_forecast_bars = int(c["MAX_FORECAST_BARS"])
    min_target_atr = float(c["MIN_TARGET_ATR"])
    zone_atr_mult = float(c["FORECAST_ZONE_ATR"])
    tp_base_mult = float(c["TP_BASE_MULT"])
    sl_atr_mult = float(c["SL_ATR_MULT"])
    sl_base_mult = float(c["SL_BASE_MULT"])
    snap_atr_mult = float(c["STRUCT_SNAP_ATR"])
    snap_strength = float(c["STRUCT_SNAP_STRENGTH"])

    warmup = max(swing_len, struct_len * 2 + 1, 10) + 2
    if n <= warmup + atr_len + 5:
        return [], {"error": "not enough bars"}

    atr = _atr_series(bars, atr_len)
    atr_safe = np.where(np.isnan(atr), np.maximum(highs - lows, MINTICK * 10.0), atr)
    atr_safe = np.maximum(atr_safe, MINTICK * 10.0)

    H = pd.Series(highs).rolling(swing_len, min_periods=swing_len).max().to_numpy()
    L = pd.Series(lows).rolling(swing_len, min_periods=swing_len).min().to_numpy()

    hi_pivots_all = _find_pivots(highs, struct_len, is_high=True)
    lo_pivots_all = _find_pivots(lows, struct_len, is_high=False)
    hi_by_confirm = {}
    for confirm_idx, _center_idx, price in hi_pivots_all:
        hi_by_confirm.setdefault(confirm_idx, []).append(price)
    lo_by_confirm = {}
    for confirm_idx, _center_idx, price in lo_pivots_all:
        lo_by_confirm.setdefault(confirm_idx, []).append(price)

    structure_prices = []
    structure_highs = []

    dir_ = False
    hi_price = float("nan")
    hi_idx = None
    lo_price = float("nan")
    lo_idx = None

    bull_pcts, bear_pcts, all_pcts = [], [], []
    bull_durs, bear_durs, all_durs = [], [], []

    trade_open = False
    direction = 0
    entry_price = sl_price = tp_price = 0.0
    entry_bar = 0
    horizon_bars = 0

    trades = []
    flips = entries = timeouts = 0

    def close_trade(j, exit_price, outcome):
        pnl = (direction * (exit_price - entry_price) - spread) * contract_multiplier
        trades.append({
            "entry_bar": entry_bar, "exit_bar": j,
            "direction": "BUY" if direction > 0 else "SELL",
            "entry": round(entry_price, 2), "sl": round(sl_price, 2), "tp": round(tp_price, 2),
            "exit_price": round(exit_price, 2), "outcome": outcome, "profit": round(pnl, 2),
            "pattern": "S432 Market Path Forecast",
            "reason": f"horizon={horizon_bars}",
        })

    for j in range(n):
        for price in hi_by_confirm.get(j, []):
            structure_prices.append(price)
            structure_highs.append(True)
            if len(structure_prices) > 100:
                structure_prices.pop(0)
                structure_highs.pop(0)
        for price in lo_by_confirm.get(j, []):
            structure_prices.append(price)
            structure_highs.append(False)
            if len(structure_prices) > 100:
                structure_prices.pop(0)
                structure_highs.pop(0)

        if j < warmup:
            continue

        prev_dir = dir_
        if not np.isnan(H[j]) and highs[j] == H[j]:
            dir_ = True
        if not np.isnan(L[j]) and lows[j] == L[j]:
            dir_ = False

        if (not np.isnan(H[j - 1]) and highs[j - 1] == H[j - 1]
                and not np.isnan(H[j]) and highs[j] < H[j]):
            hi_price = highs[j - 1]
            hi_idx = j - 1
        if (not np.isnan(L[j - 1]) and lows[j - 1] == L[j - 1]
                and not np.isnan(L[j]) and lows[j] > L[j]):
            lo_price = lows[j - 1]
            lo_idx = j - 1

        direction_changed = dir_ != prev_dir

        if direction_changed and not math.isnan(hi_price) and not math.isnan(lo_price) \
                and hi_idx is not None and lo_idx is not None:
            leg_bars = float(abs(hi_idx - lo_idx))
            if not dir_:
                bull_move = abs((hi_price - lo_price) / lo_price * 100.0)
                _push_sample(bull_pcts, bull_move, samples_n)
                _push_sample(bull_durs, leg_bars, samples_n)
                _push_sample(all_pcts, bull_move, samples_n * 2)
                _push_sample(all_durs, leg_bars, samples_n * 2)
            else:
                bear_move = abs((hi_price - lo_price) / hi_price * 100.0)
                _push_sample(bear_pcts, bear_move, samples_n)
                _push_sample(bear_durs, leg_bars, samples_n)
                _push_sample(all_pcts, bear_move, samples_n * 2)
                _push_sample(all_durs, leg_bars, samples_n * 2)

        # --- exit check ไม้เปิดอยู่ (เฉพาะแท่งหลังแท่งเข้าไม้ และไม่ใช่แท่ง flip) ---
        if trade_open and j > entry_bar and not direction_changed:
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
            elif j - entry_bar >= horizon_bars:
                timeouts += 1
                close_trade(j, float(closes[j]), "TIMEOUT")
                trade_open = False

        # --- ทิศกลับตัว: ปิดไม้เดิม (ถ้ามี) แล้วเปิดไม้ใหม่ถ้า forecastReady ---
        if direction_changed:
            if trade_open:
                flips += 1
                close_trade(j, float(closes[j]), "FLIP")
                trade_open = False

            is_bear = not dir_
            side = -1 if is_bear else 1
            dir_pcts = bear_pcts if is_bear else bull_pcts
            dir_durs = bear_durs if is_bear else bull_durs

            forecast_pct = _weighted_average(dir_pcts)
            forecast_dur = _weighted_average(dir_durs)
            directional_samples = len(dir_pcts)

            if directional_samples < 3 or forecast_pct is None:
                forecast_pct = _weighted_average(all_pcts)
                forecast_dur = _weighted_average(all_durs)
                forecast_std = _weighted_deviation(all_pcts, forecast_pct)
            else:
                forecast_std = _weighted_deviation(dir_pcts, forecast_pct)

            origin = hi_price if is_bear else lo_price
            origin_idx = hi_idx if is_bear else lo_idx

            forecast_ready = (
                len(all_pcts) >= 3 and forecast_pct is not None and forecast_pct > 0
                and forecast_dur is not None and forecast_dur > 0
                and not math.isnan(origin) and origin > 0 and origin_idx is not None
            )

            if forecast_ready:
                close_j = float(closes[j])
                atr_j = float(atr_safe[j])

                elapsed_bars = max(j - origin_idx, 0)
                adaptive_bars_left = int(round(forecast_dur)) - elapsed_bars
                clamped_adaptive = max(min_forecast_bars, min(max_forecast_bars, adaptive_bars_left))
                horizon = clamped_adaptive if adaptive_horizon else fixed_forecast_bars

                raw_swing_target = origin * (1.0 - forecast_pct / 100.0) if is_bear \
                    else origin * (1.0 + forecast_pct / 100.0)
                min_ahead = atr_j * min_target_atr
                main_target = min(raw_swing_target, close_j - min_ahead) if is_bear \
                    else max(raw_swing_target, close_j + min_ahead)
                base_distance = max(abs(main_target - close_j), min_ahead)

                raw_t3 = close_j + side * base_distance * tp_base_mult
                raw_inv = close_j - side * max(atr_j * sl_atr_mult, base_distance * sl_base_mult)

                snap_distance = atr_j * snap_atr_mult
                target_wants_high = not is_bear
                opposite_wants_high = is_bear

                t3 = _snap_level(structure_prices, structure_highs, raw_t3, snap_distance,
                                  snap_strength, target_wants_high, close_j, side)
                inv = _snap_level(structure_prices, structure_highs, raw_inv, snap_distance,
                                   snap_strength, opposite_wants_high, close_j, -side)

                min_spacing = atr_j * zone_atr_mult * 2.4
                if not is_bear:
                    t3 = max(t3, close_j + min_spacing * 3.0)
                    inv = min(inv, close_j - min_spacing)
                else:
                    t3 = min(t3, close_j - min_spacing * 3.0)
                    inv = max(inv, close_j + min_spacing)

                direction = side
                entry_price = close_j
                entry_bar = j
                sl_price = inv
                tp_price = t3
                horizon_bars = horizon
                trade_open = True
                entries += 1

    return trades, {
        "entries": entries, "flips": flips, "timeouts": timeouts,
        "bull_legs": len(bull_pcts), "bear_legs": len(bear_pcts),
    }


def compute_state(bars_raw, cfg=None):
    """เดินลูปครั้งเดียว (single-pass, O(n)) ไล่ทั้งหน้าต่าง `bars_raw` ที่ได้รับ
    มาเพื่อสร้าง swing-sample/structure state สะสมให้ครบ แล้วดูว่าแท่งสุดท้าย
    (แท่งปิดล่าสุด) มี directionChanged เกิดขึ้นหรือไม่ — ใช้สำหรับ live
    detect_s432() เรียกใหม่ทุกครั้งด้วยหน้าต่างข้อมูลสดที่โตขึ้นเรื่อยๆ (ไม่ persist
    state ข้ามการเรียก ตรงตาม convention detect_sXXX ของโปรเจกต์ที่คำนวณใหม่จาก
    `rates` ที่ได้รับทุกครั้ง) — คำนวณ forecast target (T3/Invalidation) เฉพาะ
    ตอนแท่งสุดท้ายจริงๆ เท่านั้น (แท่งก่อนหน้าข้ามส่วนนี้เพื่อความเร็ว เพราะไม่มีผล
    ต่อผลลัพธ์ที่ต้องการ)

    คืน (state, error) — state=None ถ้าข้อมูลไม่พอ/ยังไม่มีสัญญาณที่แท่งสุดท้าย
    state เมื่อมีสัญญาณ: {"signal_dir": 1/-1, "entry": float, "sl": float,
    "tp": float, "horizon_bars": int, "atr": float, "dir": bool,
    "bull_legs": int, "bear_legs": int}"""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    bars = _bars(bars_raw)
    n = len(bars)
    highs = np.array([b["high"] for b in bars], dtype=float)
    lows = np.array([b["low"] for b in bars], dtype=float)
    closes = np.array([b["close"] for b in bars], dtype=float)

    swing_len = int(c["SWING_LEN"])
    samples_n = int(c["SAMPLES"])
    atr_len = int(c["ATR_LEN"])
    struct_len = int(c["STRUCT_LEN"])
    adaptive_horizon = bool(c["ADAPTIVE_HORIZON"])
    fixed_forecast_bars = int(c["FIXED_FORECAST_BARS"])
    min_forecast_bars = int(c["MIN_FORECAST_BARS"])
    max_forecast_bars = int(c["MAX_FORECAST_BARS"])
    min_target_atr = float(c["MIN_TARGET_ATR"])
    zone_atr_mult = float(c["FORECAST_ZONE_ATR"])
    snap_atr_mult = float(c["STRUCT_SNAP_ATR"])
    snap_strength = float(c["STRUCT_SNAP_STRENGTH"])
    tp_base_mult = float(c["TP_BASE_MULT"])
    sl_atr_mult = float(c["SL_ATR_MULT"])
    sl_base_mult = float(c["SL_BASE_MULT"])

    warmup = max(swing_len, struct_len * 2 + 1, 10) + 2
    if n <= warmup + atr_len + 5:
        return None, f"not enough bars (n={n})"

    last = n - 1

    atr = _atr_series(bars, atr_len)
    atr_safe = np.where(np.isnan(atr), np.maximum(highs - lows, MINTICK * 10.0), atr)
    atr_safe = np.maximum(atr_safe, MINTICK * 10.0)

    H = pd.Series(highs).rolling(swing_len, min_periods=swing_len).max().to_numpy()
    L = pd.Series(lows).rolling(swing_len, min_periods=swing_len).min().to_numpy()

    hi_pivots_all = _find_pivots(highs, struct_len, is_high=True)
    lo_pivots_all = _find_pivots(lows, struct_len, is_high=False)
    hi_by_confirm = {}
    for confirm_idx, _center_idx, price in hi_pivots_all:
        hi_by_confirm.setdefault(confirm_idx, []).append(price)
    lo_by_confirm = {}
    for confirm_idx, _center_idx, price in lo_pivots_all:
        lo_by_confirm.setdefault(confirm_idx, []).append(price)

    structure_prices = []
    structure_highs = []

    dir_ = False
    hi_price = float("nan")
    hi_idx = None
    lo_price = float("nan")
    lo_idx = None

    bull_pcts, bear_pcts, all_pcts = [], [], []
    bull_durs, bear_durs, all_durs = [], [], []

    last_direction_changed = False

    for j in range(n):
        for price in hi_by_confirm.get(j, []):
            structure_prices.append(price)
            structure_highs.append(True)
            if len(structure_prices) > 100:
                structure_prices.pop(0)
                structure_highs.pop(0)
        for price in lo_by_confirm.get(j, []):
            structure_prices.append(price)
            structure_highs.append(False)
            if len(structure_prices) > 100:
                structure_prices.pop(0)
                structure_highs.pop(0)

        if j < warmup:
            continue

        prev_dir = dir_
        if not np.isnan(H[j]) and highs[j] == H[j]:
            dir_ = True
        if not np.isnan(L[j]) and lows[j] == L[j]:
            dir_ = False

        if (not np.isnan(H[j - 1]) and highs[j - 1] == H[j - 1]
                and not np.isnan(H[j]) and highs[j] < H[j]):
            hi_price = highs[j - 1]
            hi_idx = j - 1
        if (not np.isnan(L[j - 1]) and lows[j - 1] == L[j - 1]
                and not np.isnan(L[j]) and lows[j] > L[j]):
            lo_price = lows[j - 1]
            lo_idx = j - 1

        direction_changed = dir_ != prev_dir

        if direction_changed and not math.isnan(hi_price) and not math.isnan(lo_price) \
                and hi_idx is not None and lo_idx is not None:
            leg_bars = float(abs(hi_idx - lo_idx))
            if not dir_:
                bull_move = abs((hi_price - lo_price) / lo_price * 100.0)
                _push_sample(bull_pcts, bull_move, samples_n)
                _push_sample(bull_durs, leg_bars, samples_n)
                _push_sample(all_pcts, bull_move, samples_n * 2)
                _push_sample(all_durs, leg_bars, samples_n * 2)
            else:
                bear_move = abs((hi_price - lo_price) / hi_price * 100.0)
                _push_sample(bear_pcts, bear_move, samples_n)
                _push_sample(bear_durs, leg_bars, samples_n)
                _push_sample(all_pcts, bear_move, samples_n * 2)
                _push_sample(all_durs, leg_bars, samples_n * 2)

        if j == last:
            last_direction_changed = direction_changed

    if not last_direction_changed:
        return {
            "signal_dir": 0, "dir": dir_, "atr": float(atr_safe[last]),
            "bull_legs": len(bull_pcts), "bear_legs": len(bear_pcts),
        }, None

    is_bear = not dir_
    side = -1 if is_bear else 1
    dir_pcts = bear_pcts if is_bear else bull_pcts
    dir_durs = bear_durs if is_bear else bull_durs

    forecast_pct = _weighted_average(dir_pcts)
    forecast_dur = _weighted_average(dir_durs)
    directional_samples = len(dir_pcts)

    if directional_samples < 3 or forecast_pct is None:
        forecast_pct = _weighted_average(all_pcts)
        forecast_dur = _weighted_average(all_durs)
        forecast_std = _weighted_deviation(all_pcts, forecast_pct)
    else:
        forecast_std = _weighted_deviation(dir_pcts, forecast_pct)

    origin = hi_price if is_bear else lo_price
    origin_idx = hi_idx if is_bear else lo_idx

    forecast_ready = (
        len(all_pcts) >= 3 and forecast_pct is not None and forecast_pct > 0
        and forecast_dur is not None and forecast_dur > 0
        and not math.isnan(origin) and origin > 0 and origin_idx is not None
    )

    if not forecast_ready:
        return {
            "signal_dir": 0, "dir": dir_, "atr": float(atr_safe[last]),
            "bull_legs": len(bull_pcts), "bear_legs": len(bear_pcts),
        }, None

    close_j = float(closes[last])
    atr_j = float(atr_safe[last])

    elapsed_bars = max(last - origin_idx, 0)
    adaptive_bars_left = int(round(forecast_dur)) - elapsed_bars
    clamped_adaptive = max(min_forecast_bars, min(max_forecast_bars, adaptive_bars_left))
    horizon = clamped_adaptive if adaptive_horizon else fixed_forecast_bars

    raw_swing_target = origin * (1.0 - forecast_pct / 100.0) if is_bear \
        else origin * (1.0 + forecast_pct / 100.0)
    min_ahead = atr_j * min_target_atr
    main_target = min(raw_swing_target, close_j - min_ahead) if is_bear \
        else max(raw_swing_target, close_j + min_ahead)
    base_distance = max(abs(main_target - close_j), min_ahead)

    raw_t3 = close_j + side * base_distance * tp_base_mult
    raw_inv = close_j - side * max(atr_j * sl_atr_mult, base_distance * sl_base_mult)

    snap_distance = atr_j * snap_atr_mult
    target_wants_high = not is_bear
    opposite_wants_high = is_bear

    t3 = _snap_level(structure_prices, structure_highs, raw_t3, snap_distance,
                      snap_strength, target_wants_high, close_j, side)
    inv = _snap_level(structure_prices, structure_highs, raw_inv, snap_distance,
                       snap_strength, opposite_wants_high, close_j, -side)

    min_spacing = atr_j * zone_atr_mult * 2.4
    if not is_bear:
        t3 = max(t3, close_j + min_spacing * 3.0)
        inv = min(inv, close_j - min_spacing)
    else:
        t3 = min(t3, close_j - min_spacing * 3.0)
        inv = max(inv, close_j + min_spacing)

    return {
        "signal_dir": side, "dir": dir_, "atr": atr_j,
        "entry": close_j, "sl": inv, "tp": t3, "horizon_bars": horizon,
        "forecast_pct": forecast_pct, "forecast_std": forecast_std,
        "bull_legs": len(bull_pcts), "bear_legs": len(bear_pcts),
    }, None


def detect_s432(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S432 Market Path Forecast [BOSWaves] — เรียก compute_state() ใหม่ทุกครั้ง
    จาก `rates` ทั้งหน้าต่างที่ได้รับ (ตาม convention detect_sXXX ของโปรเจกต์ ไม่
    persist state ข้ามการเรียก) ให้สัญญาณเฉพาะตอนแท่งปิดล่าสุด (rates[-1]) เป็น
    แท่ง directionChanged จริง (ตรง alertcondition ของต้นฉบับเป๊ะ) พร้อม
    SL=Invalidation, TP=Target3 (ดู docstring บนสุดของไฟล์นี้สำหรับรายละเอียด
    การตีความเป็นกลยุทธ์ trend-flip และ deviation จาก Pine ต้นฉบับ)

    order_type="market" เสมอ (entry=close ของแท่ง directionChanged ตรงตาม
    alertcondition ต้นฉบับ ไม่ใช่ limit รอราคาย้อนกลับแบบ S420)"""
    del dt_bkk, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    state, err = compute_state(rates, c)
    if state is None:
        return _wait(err)

    if state["signal_dir"] == 0:
        return _wait(f"No directionChanged at last bar (dir={state['dir']} "
                      f"bull_legs={state['bull_legs']} bear_legs={state['bear_legs']} "
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
        "pattern": f"S432 {signal} Market Path Forecast",
        "reason": (f"horizon={state['horizon_bars']} forecast_pct={state['forecast_pct']:.2f} "
                   f"forecast_std={state['forecast_std']:.2f} atr={state['atr']:.2f} "
                   f"bull_legs={state['bull_legs']} bear_legs={state['bear_legs']}"),
    }
