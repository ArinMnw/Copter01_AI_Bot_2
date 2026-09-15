# -*- coding: utf-8 -*-
"""S431 - Breakout Pattern Setup [WillyAlgoTrader] v1.7.2: พอร์ตจาก Pine v6
"Breakout Pattern Setup" (ผู้ใช้ส่งโค้ดมาให้ตรงๆ) — หา channel (คู่เส้น
trendline บน/ล่าง) ที่ fit กับ pivot high/low ล่าสุด แล้วรอราคาทะลุ (breakout)
ออกจาก channel พร้อม TP1/TP2/TP3 คำนวณจากความสูง channel (chMaxWidth) และ
SL ที่ขอบตรงข้าม เลื่อน SL ไป breakeven หลัง TP1 โดน

⚠️ ข้อสำคัญที่ต้องรู้ก่อนอ่านผล backtest: สคริปต์ต้นฉบับเป็น `indicator()` ไม่ใช่
`strategy()` — ไม่มี position sizing/realized-PnL ในตัวเอง แค่วาดเส้น+ส่ง
alert() ไม่เคย "ปิดไม้บางส่วน" ที่ TP1/TP2 จริง (แค่เลื่อน SL ไป breakeven และ
นับ winCount/lossCount ใน dashboard เฉยๆ) ไม้เดียวจะปิดจริงก็ต่อเมื่อโดน TP3,
SL (ก่อน TP1), BE-exit (โดน SL หลัง TP1 = breakeven), หรือ timeout เท่านั้น
พอร์ตนี้แปลงเป็น backtest วัด P&L จริงโดยตีความไม้ 1 ไม้ = position เดียว
ปิดที่จุดจบจริงจุดใดจุดหนึ่งข้างต้น (ไม่แบ่งปิดบางส่วนที่ TP1/TP2 เหมือนต้นฉบับ
ไม่ได้ track เพราะเป็นแค่ indicator) — timeout ใช้ราคาปิดของแท่งที่ timeout
เป็นราคาออกโดยประมาณ (ต้นฉบับไม่ได้นิยามราคาออกตอน timeout ไว้เลย เพราะไม่ใช่
position จริง)

deviation อื่นจาก Pine ต้นฉบับ (ตาม convention เดียวกับ S420-S430):
  1) ATR ของโปรเจกต์นี้เป็น SMA ของ True Range (ไม่ใช่ Wilder RMA แบบ
     ta.atr() จริงของ Pine) — เหมือนที่ strategy430.py เลือกใช้เพื่อความ
     สอดคล้องกันทั้งโปรเจกต์ ไม่ใช่จุดสนใจหลักของกลยุทธ์นี้
  2) volConfirmInput (volume spike mult) และ momentumFilterInput (RSI bias)
     ใน Pine ต้นฉบับ**ไม่ได้ gate การเข้าไม้จริง** ใช้แค่คำนวณ strengthScore/
     breakStrength label (Strong/Medium/Weak) ที่ไปโชว์ dashboard/alert
     เท่านั้น พอร์ตนี้เลยไม่ implement สองตัวนี้ (ไม่กระทบผลเทรดเลย)
  3) volContractionInput **gate การตรวจจับ channel จริง** (ส่วนหนึ่งของเงื่อนไข
     validate channel) — พอร์ตนี้ implement ตัวนี้ไว้ครบ ใช้ tick_volume ของ
     MT5 แทน volume จริง (XAUUSD ไม่มี real volume)
  4) entryPrice ใช้ close ของแท่ง breakout ตรงตามสคริปต์ (ไม่ fill ที่ open
     แท่งถัดไปแบบ strategy อื่นในโปรเจกต์ เพราะ script คำนวณ SL/TP จาก close
     แท่งนั้นเป๊ะ ถือว่าเป็น market order ทันทีที่แท่งปิด)
"""

from __future__ import annotations

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from strategy119 import _bars

DEFAULT_CFG = {
    "PIVOT_LEN": 5,
    "MIN_TOUCHES": 2,
    "MAX_CHANNEL_BARS": 120,
    "CONVERGENCE_MIN": 0.02,
    "TOUCH_TOLERANCE_ATR": 0.15,
    "DEVIATION_MAX_ATR": 0.3,
    "MIN_CHANNEL_WIDTH_ATR": 0.5,
    "VOL_CONTRACTION_FILTER": True,
    "VOL_CONTRACTION_THRESH": 0.85,
    "SL_PADDING_ATR": 0.0,
    "ATR_PERIOD": 20,
    "MAX_PIVOTS": 60,
    "RESCAN_INTERVAL": 10,
    "MAX_PIVOT_SCAN": 15,
    "WARMUP_MINIMUM": 50,
    "TRADE_TIMEOUT_MULT": 3,
    "MAX_WIDTH_MULT": 10.0,
}


def _atr_series(bars, period):
    """ค่าเฉลี่ย True Range ย้อนหลัง `period` แท่งแบบ SMA (เหมือน strategy430._atr_series
    — ดู docstring หัวไฟล์ข้อ 1)."""
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
    """คืนลิสต์ (confirm_index, center_index, price) ของทุกจุด pivot high/low
    — confirm_index = center_index + length (ตรงกับ `bar_index - pivotLenInput`
    ของ Pine ที่ใช้ตอน push เข้า array). ta.pivothigh/pivotlow ของ Pine คือจุด
    สูงสุด/ต่ำสุดที่ "ชนะ" ทุกจุดในหน้าต่าง length ทั้งสองข้างเป๊ะ (ไม่เสมอ)."""
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


def _line_at(x1, y1, x2, y2, x):
    dx = x2 - x1
    if abs(dx) <= 1e-10:
        return y1
    return y1 + (y2 - y1) * (x - x1) / dx


def _fit_best_line(xs, ys, dev_tol, touch_tol, min_touches, want_below):
    """brute-force หาคู่จุด (a,b) ที่ fit เส้นตรงดีที่สุด (touches มากสุด) โดย
    ทุกจุดต้องอยู่ "ฝั่งที่ถูกต้อง" ของเส้น (ไม่เกิน dev_tol) — ตรงกับ nested
    loop ของ Pine ต้นฉบับเป๊ะ (หา resistance: ทุกจุดต้องอยู่ใต้เส้น, หา
    support: ทุกจุดต้องอยู่เหนือเส้น) touches นับเมื่อ |diff|<=touch_tol"""
    n = len(xs)
    best = None
    best_touches = 0
    for a in range(n - 1):
        for b in range(a + 1, n):
            ax, ay, bx, by = xs[a], ys[a], xs[b], ys[b]
            if abs(bx - ax) < 1.0:
                continue
            ok = True
            touches = 0
            for k in range(n):
                proj = _line_at(ax, ay, bx, by, xs[k])
                diff = ys[k] - proj
                if want_below:  # resistance: จุดต้องไม่อยู่เหนือเส้นเกิน dev_tol
                    if diff > dev_tol:
                        ok = False
                        break
                else:  # support: จุดต้องไม่อยู่ใต้เส้นเกิน dev_tol
                    if diff < -dev_tol:
                        ok = False
                        break
                if abs(diff) <= touch_tol:
                    touches += 1
            if ok and touches >= min_touches and touches > best_touches:
                best_touches = touches
                best = (ax, ay, bx, by, touches)
    return best


def run_backtest(bars_raw, cfg=None, spread=0.20, contract_multiplier=1.0):
    """เดินลูปทั้งช่วงบาร์ จำลอง channel detection + breakout + TP1/TP2/TP3/SL/BE/
    timeout ครบ คืน (trades, stats_extra) — stats_extra มี totalPatterns/
    bullBreaks/bearBreaks/timeoutCount ไว้ debug"""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    bars = _bars(bars_raw)
    n = len(bars)
    highs = np.array([b["high"] for b in bars], dtype=float)
    lows = np.array([b["low"] for b in bars], dtype=float)
    closes = np.array([b["close"] for b in bars], dtype=float)
    vols = np.array([b["tick_volume"] for b in bars], dtype=float)
    cumvol = np.cumsum(vols)
    atr = _atr_series(bars, int(c["ATR_PERIOD"]))

    pivot_len = int(c["PIVOT_LEN"])
    min_touches = int(c["MIN_TOUCHES"])
    max_channel_bars = int(c["MAX_CHANNEL_BARS"])
    rescan_interval = int(c["RESCAN_INTERVAL"])
    max_pivot_scan = int(c["MAX_PIVOT_SCAN"])
    warmup_bars = max(pivot_len * 2 + max_channel_bars, int(c["WARMUP_MINIMUM"]))
    timeout_mult = int(c["TRADE_TIMEOUT_MULT"])
    max_pivots = int(c["MAX_PIVOTS"])

    if n <= warmup_bars + 5:
        return [], {"error": "not enough bars"}

    hi_pivots_all = _find_pivots(highs, pivot_len, is_high=True)
    lo_pivots_all = _find_pivots(lows, pivot_len, is_high=False)
    hi_by_confirm = {}
    for confirm_idx, center_idx, price in hi_pivots_all:
        hi_by_confirm.setdefault(confirm_idx, []).append((center_idx, price))
    lo_by_confirm = {}
    for confirm_idx, center_idx, price in lo_pivots_all:
        lo_by_confirm.setdefault(confirm_idx, []).append((center_idx, price))

    hi_list = []  # [(bar_index, price), ...] ล่าสุดอยู่หน้าสุด (unshift)
    lo_list = []

    channel_active = False
    ch = {}  # hiX1,hiY1,hiX2,hiY2,loX1,loY1,loX2,loY2,chMaxWidth,chDetectBar
    trade_open = False
    breakout_dir = 0
    breakout_bar = 0
    entry_price = sl_price = sl_price_orig = tp1 = tp2 = tp3 = 0.0
    tp1_hit = tp2_hit = tp3_hit = sl_hit = be_exit = False

    trades = []
    total_patterns = bull_breaks = bear_breaks = timeout_count = 0

    dev_mult = float(c["DEVIATION_MAX_ATR"])
    touch_mult = float(c["TOUCH_TOLERANCE_ATR"])
    min_width_mult = float(c["MIN_CHANNEL_WIDTH_ATR"])
    max_width_mult = float(c["MAX_WIDTH_MULT"])
    conv_min = float(c["CONVERGENCE_MIN"])
    sl_pad_mult = float(c["SL_PADDING_ATR"])
    vol_filter_on = bool(c["VOL_CONTRACTION_FILTER"])
    vol_thresh = float(c["VOL_CONTRACTION_THRESH"])

    def close_trade(j, exit_price, outcome):
        pnl = (breakout_dir * (exit_price - entry_price) - spread) * contract_multiplier
        trades.append({
            "entry_bar": breakout_bar, "exit_bar": j,
            "direction": "BUY" if breakout_dir > 0 else "SELL",
            "entry": round(entry_price, 2), "sl": round(sl_price_orig, 2),
            "tp1": round(tp1, 2), "tp2": round(tp2, 2), "tp3": round(tp3, 2),
            "exit_price": round(exit_price, 2), "outcome": outcome, "profit": round(pnl, 2),
            "tp1_hit": tp1_hit, "tp2_hit": tp2_hit,
            "pattern": "S431 Breakout Channel",
            "reason": f"touches={ch.get('chHiTouches', 0)}H/{ch.get('chLoTouches', 0)}L "
                      f"conv={ch.get('chConvergence', 0.0):.3f} width={ch.get('chMaxWidth', 0.0):.2f}",
        })

    for j in range(warmup_bars, n):
        atr_j = float(atr[j]) if not np.isnan(atr[j]) else 0.0

        for center_idx, price in hi_by_confirm.get(j, []):
            hi_list.insert(0, (center_idx, price))
            if len(hi_list) > max_pivots:
                hi_list.pop()
        for center_idx, price in lo_by_confirm.get(j, []):
            lo_list.insert(0, (center_idx, price))
            if len(lo_list) > max_pivots:
                lo_list.pop()
        new_pivot = (j in hi_by_confirm) or (j in lo_by_confirm)

        # --- channel scan (ตรงกับ shouldScan ของ Pine) ---
        rescan_due = (j % rescan_interval == 0)
        should_scan = ((new_pivot or rescan_due) and not channel_active and not trade_open
                        and len(hi_list) >= min_touches and len(lo_list) >= min_touches)

        if should_scan and atr_j > 0.0:
            hx = [float(idx) for idx, _ in hi_list if j - idx <= max_channel_bars][:max_pivot_scan + 1]
            hy = [p for idx, p in hi_list if j - idx <= max_channel_bars][:max_pivot_scan + 1]
            lx = [float(idx) for idx, _ in lo_list if j - idx <= max_channel_bars][:max_pivot_scan + 1]
            ly = [p for idx, p in lo_list if j - idx <= max_channel_bars][:max_pivot_scan + 1]

            dev_tol = atr_j * dev_mult
            touch_tol = atr_j * touch_mult

            best_hi = _fit_best_line(hx, hy, dev_tol, touch_tol, min_touches, want_below=True) if len(hx) >= min_touches else None
            best_lo = _fit_best_line(lx, ly, dev_tol, touch_tol, min_touches, want_below=False) if len(lx) >= min_touches else None

            if best_hi and best_lo:
                hi_x1, hi_y1, hi_x2, hi_y2, hi_touches = best_hi
                lo_x1, lo_y1, lo_x2, lo_y2, lo_touches = best_lo

                hi_min_x, hi_max_x = min(hi_x1, hi_x2), max(hi_x1, hi_x2)
                lo_min_x, lo_max_x = min(lo_x1, lo_x2), max(lo_x1, lo_x2)
                overlap_start = max(hi_min_x, lo_min_x)
                overlap_end = min(hi_max_x, lo_max_x)
                max_h = 0.0
                if overlap_end > overlap_start:
                    samples = max(int((overlap_end - overlap_start) / 5.0), 2)
                    for s in range(samples + 1):
                        sx = overlap_start + (overlap_end - overlap_start) * s / samples
                        hu = _line_at(hi_x1, hi_y1, hi_x2, hi_y2, sx)
                        lo_v = _line_at(lo_x1, lo_y1, lo_x2, lo_y2, sx)
                        max_h = max(max_h, hu - lo_v)
                else:
                    mid_x = (hi_min_x + hi_max_x + lo_min_x + lo_max_x) / 4.0
                    max_h = abs(_line_at(hi_x1, hi_y1, hi_x2, hi_y2, mid_x)
                                - _line_at(lo_x1, lo_y1, lo_x2, lo_y2, mid_x))

                start_x = min(hi_min_x, lo_min_x)
                upper_now = _line_at(hi_x1, hi_y1, hi_x2, hi_y2, float(j))
                lower_now = _line_at(lo_x1, lo_y1, lo_x2, lo_y2, float(j))
                width_now = upper_now - lower_now
                upper_start = _line_at(hi_x1, hi_y1, hi_x2, hi_y2, start_x)
                lower_start = _line_at(lo_x1, lo_y1, lo_x2, lo_y2, start_x)
                width_start = upper_start - lower_start
                conv_rate = (1.0 - width_now / width_start) if width_start > 0 else 0.0

                not_inv = width_now > 0
                is_conv = conv_rate >= conv_min
                width_ok = atr_j * min_width_mult <= width_now < atr_j * max_width_mult
                is_inside = not_inv and lower_now <= closes[j - 1] <= upper_now

                vol_cont_ok = True
                if vol_filter_on:
                    pat_start_idx = int(start_x)
                    pat_bars = max(j - pat_start_idx, 1)
                    saf_pat_bars = min(pat_bars, j)
                    pre_bars = min(saf_pat_bars, pat_start_idx)
                    vol_sma = float(np.mean(vols[max(0, j - 20):j])) if j >= 1 else 0.0
                    vol_in_pat = ((cumvol[j] - cumvol[j - saf_pat_bars]) / saf_pat_bars) if saf_pat_bars > 0 else vol_sma
                    if pre_bars > 0 and j - saf_pat_bars - pre_bars >= 0:
                        vol_pre_pat = (cumvol[j - saf_pat_bars] - cumvol[j - saf_pat_bars - pre_bars]) / pre_bars
                    else:
                        vol_pre_pat = vol_sma
                    vol_cont_ratio = (vol_in_pat / vol_pre_pat) if vol_pre_pat else 1.0
                    vol_cont_ok = vol_cont_ratio < vol_thresh

                if not_inv and is_conv and width_ok and is_inside and vol_cont_ok:
                    channel_active = True
                    ch = {
                        "hiX1": hi_x1, "hiY1": hi_y1, "hiX2": hi_x2, "hiY2": hi_y2,
                        "loX1": lo_x1, "loY1": lo_y1, "loX2": lo_x2, "loY2": lo_y2,
                        "chMaxWidth": max_h, "chDetectBar": j,
                        "chHiTouches": hi_touches, "chLoTouches": lo_touches, "chConvergence": conv_rate,
                    }
                    total_patterns += 1

        # --- breakout detection (เฉพาะตอน channel active + ยังไม่ breakout) ---
        broke_this_bar = False
        if channel_active and breakout_dir == 0:
            upper_now = _line_at(ch["hiX1"], ch["hiY1"], ch["hiX2"], ch["hiY2"], float(j))
            lower_now = _line_at(ch["loX1"], ch["loY1"], ch["loX2"], ch["loY2"], float(j))
            if closes[j] > upper_now:
                broke_this_bar = True
                breakout_dir = 1
                break_boundary, opp_boundary = upper_now, lower_now
            elif closes[j] < lower_now:
                broke_this_bar = True
                breakout_dir = -1
                break_boundary, opp_boundary = lower_now, upper_now

            if broke_this_bar:
                breakout_bar = j
                entry_price = float(closes[j])
                if breakout_dir > 0:
                    sl_price = opp_boundary - atr_j * sl_pad_mult
                    target = break_boundary + ch["chMaxWidth"]
                    full_move = abs(target - entry_price)
                    tp1, tp2, tp3 = entry_price + full_move / 3.0, entry_price + full_move * 2.0 / 3.0, entry_price + full_move
                    bull_breaks += 1
                else:
                    sl_price = opp_boundary + atr_j * sl_pad_mult
                    target = break_boundary - ch["chMaxWidth"]
                    full_move = abs(entry_price - target)
                    tp1, tp2, tp3 = entry_price - full_move / 3.0, entry_price - full_move * 2.0 / 3.0, entry_price - full_move
                    bear_breaks += 1
                sl_price_orig = sl_price
                tp1_hit = tp2_hit = tp3_hit = sl_hit = be_exit = False
                trade_open = True
            else:
                # ยังไม่ breakout — เช็ค timeout ของ channel เอง (ไม่มี trade ให้เสีย)
                if j - ch["chDetectBar"] > max_channel_bars:
                    channel_active = False

        # --- TP/SL/BE hit detection (เฉพาะแท่งหลัง breakout bar) ---
        closed_this_bar = False
        if trade_open and breakout_dir != 0 and not sl_hit and not be_exit and j > breakout_bar:
            if breakout_dir > 0:
                tp1_side, tp2_side, tp3_side = highs[j] >= tp1, highs[j] >= tp2, highs[j] >= tp3
                sl_side = lows[j] <= sl_price
            else:
                tp1_side, tp2_side, tp3_side = lows[j] <= tp1, lows[j] <= tp2, lows[j] <= tp3
                sl_side = highs[j] >= sl_price

            if sl_side:
                if tp1_hit:
                    be_exit = True
                    close_trade(j, entry_price, "BE")
                    closed_this_bar = True
                else:
                    sl_hit = True
                    close_trade(j, sl_price, "SL")
                    closed_this_bar = True
            else:
                if tp1_side and not tp1_hit:
                    tp1_hit = True
                    sl_price = entry_price  # trailing SL -> breakeven
                if tp2_side and not tp2_hit:
                    tp2_hit = True
                if tp3_side and not tp3_hit:
                    tp3_hit = True
                    close_trade(j, tp3, "TP3")
                    closed_this_bar = True

        if not closed_this_bar and trade_open and breakout_dir != 0 and not (tp3_hit or sl_hit or be_exit):
            if j - breakout_bar > max_channel_bars * timeout_mult:
                timeout_count += 1
                close_trade(j, float(closes[j]), "TIMEOUT")
                closed_this_bar = True

        if closed_this_bar:
            trade_open = False
            channel_active = False
            breakout_dir = 0

    return trades, {
        "total_patterns": total_patterns, "bull_breaks": bull_breaks,
        "bear_breaks": bear_breaks, "timeout_count": timeout_count,
    }
