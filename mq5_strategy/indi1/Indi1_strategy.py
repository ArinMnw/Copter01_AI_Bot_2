# -*- coding: utf-8 -*-
"""Indi1 Strategy - port ของ GenoSmartSignal.mq5 / Indi1_EA.mq5 (Pine "Geno Smart signal V2.3").

"3 เส้น" = Trend Line BB (Follow Line BB) + Trend Line MA (Follow Line MA) + Line 2 (Kernel)
เขียวพร้อมกัน; ฝั่ง Sell = แดงทั้ง 3 เส้น.

กฎเข้า (Buy; Sell สลับด้าน) - ประเมินเมื่อแท่ง LTF (M5) ปิด:
  1) HTF (H1): 2 แท่งที่ปิดล่าสุดติดกัน 3 เส้นเขียวทั้งคู่
  2) LTF แท่ง T: "เกิด" 3 เส้นเขียวพร้อมกัน (แท่งก่อนหน้ายังไม่ครบ) หรือเกิด Smart Buy
  3) LTF แท่ง T+1 ปิดแล้ว 3 เส้นยังเขียว (หรือ Smart Buy ของ T ยังอยู่ = Trend Line MA ยังเขียว)
     -> เข้า market ที่ open แท่งถัดไป
  SL = swing ZigZag ล่าสุดของ LTF -/+ buffer, TP = RR x ระยะ SL, lot จาก Risk % ของ balance
  Fibo breakeven: แท่ง LTF ปิดเลย 50% ของ entry->TP -> เลื่อน SL ไป entry +/- 50 จุด
ถือได้ทีละ 1 ไม้, ไม่กลับด้านเมื่อสัญญาณตรงข้าม.

ยังไม่ได้ตรวจ parity ตัวเลขเทียบ buffer ใน MT5 จริง.
"""

from __future__ import annotations

import math
from typing import Any

NAN = float("nan")

DEFAULT_CFG = {
    "POINT": 0.01,
    "TICK_SIZE": 0.01,
    "CONTRACT_SIZE": 100.0,        # XAUUSD: 1 lot = 100 oz
    "LTF_SECONDS": 300,            # M5
    "HTF_SECONDS": 3600,           # H1
    # Follow Line BB+ATR (Trend Line BB)
    "BB1_PERIOD": 21,
    "BB1_DEV": 1.0,
    "USE_ATR1": True,
    "ATR1_PERIOD": 5,
    # Follow Line MA-type (Trend Line MA)
    "MA_TYPE": "EMA",              # RMA SMA EMA WMA SMMA
    "MA_LEN": 21,
    "BB2_DEV": 1.0,
    "ATR2_PERIOD": 5,
    # Kernel regression (Line 2)
    "K_FILTER": "smooth",          # none | smooth | zerolag
    "K_TYPE": "rq",                # rq | gauss | periodic | locper
    "K_H": 8,
    "K_R": 1.0,
    "K_X": 20,
    "K_LAG": 2,
    # ZigZag
    "ZZ_LEN": 13,
    # Direction / risk
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "MAX_ENTRIES_PER_H1": 3,           # เจอสัญญาณ H1 แล้วเข้าได้กี่ไม้ จนกว่าจะเกิดสัญญาณ H1 ใหม่ (0 = ไม่จำกัด)
    "CONCURRENT": True,                # True = ถือหลายไม้พร้อมกันได้ (ไม้ใหม่ต้องรอสัญญาณ M5 ใหม่)
    "INITIAL_BALANCE": 10000.0,
    "RISK_PCT": 1.0,
    "RR": 2.5,
    "SL_BUFFER_TICKS": 100,
    "MIN_SL_POINTS": 0,
    "MAX_SPREAD_POINTS": 0,
    "MIN_LOT": 0.01,
    "LOT_STEP": 0.01,
    "COMMISSION_PER_LOT_USD": 0.0,
    # Fibo breakeven
    "USE_BE": True,
    "BE_FIB": 0.5,
    "BE_LOCK_POINTS": 50,
}


def _ok(x: float) -> bool:
    return not math.isnan(x)


def _sma(a, k: int, n: int) -> float:
    if k < n - 1:
        return NAN
    return sum(a[k - n + 1:k + 1]) / n


def _stdev(a, k: int, n: int) -> float:
    if k < n - 1:
        return NAN
    w = a[k - n + 1:k + 1]
    m = sum(w) / n
    return math.sqrt(sum((x - m) ** 2 for x in w) / n)


def _wma(a, k: int, n: int) -> float:
    if k < n - 1:
        return NAN
    return sum(a[k - j] * (n - j) for j in range(n)) / (n * (n + 1) / 2.0)


def _ema_step(prev: float, x: float, n: int) -> float:
    if not _ok(prev):
        return x
    al = 2.0 / (n + 1)
    return al * x + (1 - al) * prev


def _rma_step(prev: float, src, k: int, n: int) -> float:
    if not _ok(prev):
        return _sma(src, k, n)
    al = 1.0 / n
    return al * src[k] + (1 - al) * prev


def _value(bar: Any, key: str) -> float:
    return float(bar[key])


def _kernel_weights(c) -> list:
    n = int(c["K_X"]) + 2
    lb, rel, per = float(c["K_H"]), float(c["K_R"]), float(c["K_LAG"])
    out = []
    for i in range(n):
        if c["K_TYPE"] == "gauss":
            lg = lb - per
            w = math.exp(-i * i / (2 * lg * lg))
        elif c["K_TYPE"] == "periodic":
            w = math.exp(-2 * math.sin(math.pi * i / per) ** 2 / (lb * lb))
        elif c["K_TYPE"] == "locper":
            w = (math.exp(-2 * math.sin(math.pi * i / per) ** 2 / (lb * lb))
                 * math.exp(-i * i / (2 * lb * lb)))
        else:
            w = (1 + (i * i) / (lb * lb * 2 * rel)) ** (-rel)
        out.append(w)
    return out


def compute_signals(bars_raw, cfg=None):
    """คืน dict ของ list ต่อแท่ง:
    g1/g2/gk  = Trend Line BB / Trend Line MA / Line 2 เป็นสีเขียว (bool)
    r1/r2/rk  = สีแดง (มีค่าและไม่ใช่เขียว)
    smart_buy/smart_sell, swing_low/swing_high (ค่า ZigZag ล่าสุด ณ แท่งนั้น)
    """
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    n = len(bars_raw)
    h = [_value(b, "high") for b in bars_raw]
    l = [_value(b, "low") for b in bars_raw]
    cl = [_value(b, "close") for b in bars_raw]

    tr = [0.0] * n
    atr1 = [NAN] * n
    atr2 = [NAN] * n
    ma = [NAN] * n
    ma_aux = [NAN] * n
    tl1 = [NAN] * n
    it1 = [NAN] * n
    tl2 = [NAN] * n
    it2 = [NAN] * n
    yd = [NAN] * n
    ks = [NAN] * n
    g1 = [False] * n
    g2 = [False] * n
    gk = [False] * n
    r1 = [False] * n
    r2 = [False] * n
    rk = [False] * n
    smart_buy = [False] * n
    smart_sell = [False] * n
    sw_low = [NAN] * n
    sw_high = [NAN] * n

    zz: list = []                  # (idx, price, is_high), 0 = ล่าสุด
    zdir = 0
    last_sh = NAN
    last_sl = NAN
    zlen = int(c["ZZ_LEN"])
    ma_type = str(c["MA_TYPE"]).upper()
    ma_len = int(c["MA_LEN"])
    a1p, a2p = int(c["ATR1_PERIOD"]), int(c["ATR2_PERIOD"])
    kw = _kernel_weights(c)
    kn = len(kw)
    ksum = sum(kw)

    for k in range(n):
        tr[k] = h[k] - l[k] if k == 0 else max(h[k] - l[k], abs(h[k] - cl[k - 1]), abs(l[k] - cl[k - 1]))
        atr1[k] = _rma_step(atr1[k - 1] if k else NAN, tr, k, a1p)
        atr2[k] = _rma_step(atr2[k - 1] if k else NAN, tr, k, a2p)

        # ---- ZigZag (เหมือน ZigStep ใน MQ5)
        kh = kl = False
        if k >= zlen - 1:
            kh = h[k] >= max(h[k - zlen + 1:k + 1])
            kl = l[k] <= min(l[k - zlen + 1:k + 1])
        prev_dir = zdir
        if kh and not kl:
            zdir = 1
        elif kl and not kh:
            zdir = -1
        if kh or kl:
            is_hi = zdir == 1
            ny = h[k] if is_hi else l[k]
            if zdir != prev_dir or not zz:
                zz.insert(0, (k, ny, is_hi))
                del zz[4:]
            elif (zdir == 1 and ny > zz[0][1]) or (zdir == -1 and ny < zz[0][1]):
                zz[0] = (k, ny, is_hi)
        if len(zz) >= 2:
            if zz[0][2]:
                last_sh = zz[0][1]
            else:
                last_sl = zz[0][1]
        sw_low[k] = last_sl
        sw_high[k] = last_sh

        # ---- Follow Line #1 (BB + ATR) = Trend Line BB
        m = _sma(cl, k, int(c["BB1_PERIOD"]))
        sd = _stdev(cl, k, int(c["BB1_PERIOD"]))
        bu = m + sd * float(c["BB1_DEV"])
        bl = m - sd * float(c["BB1_DEV"])
        sig = 1 if (_ok(bu) and cl[k] > bu) else -1 if (_ok(bl) and cl[k] < bl) else 0
        pv = tl1[k - 1] if k else NAN
        if sig == 1:
            tl = (l[k] - atr1[k]) if c["USE_ATR1"] else l[k]
            if tl < pv:
                tl = pv
        elif sig == -1:
            tl = (h[k] + atr1[k]) if c["USE_ATR1"] else h[k]
            if tl > pv:
                tl = pv
        else:
            tl = pv
        tl1[k] = tl
        it = it1[k - 1] if k else NAN
        if tl > pv:
            it = 1.0
        if tl < pv:
            it = -1.0
        it1[k] = it
        if _ok(tl):
            g1[k] = it > 0
            r1[k] = not g1[k]

        # ---- Follow Line #2 (MA-type) = Trend Line MA
        if ma_type == "SMA":
            ma[k] = _sma(cl, k, ma_len)
        elif ma_type == "WMA":
            ma[k] = _wma(cl, k, ma_len)
        elif ma_type == "RMA":
            ma_aux[k] = _rma_step(ma_aux[k - 1] if k else NAN, cl, k, ma_len)
            ma[k] = ma_aux[k]
        elif ma_type == "SMMA":
            prev = ma_aux[k - 1] if k else NAN
            ma_aux[k] = _sma(cl, k, ma_len) if not _ok(prev) else (prev * (ma_len - 1) + cl[k]) / ma_len
            ma[k] = ma_aux[k]
        else:  # EMA
            ma_aux[k] = _ema_step(ma_aux[k - 1] if k else NAN, cl[k], ma_len)
            ma[k] = ma_aux[k]
        sd2 = _stdev(cl, k, ma_len)
        bu2 = ma[k] + sd2 * float(c["BB2_DEV"])
        bl2 = ma[k] - sd2 * float(c["BB2_DEV"])
        sig2 = 1 if (_ok(bu2) and cl[k] > bu2) else -1 if (_ok(bl2) and cl[k] < bl2) else 0
        v = atr2[k]
        pv = tl2[k - 1] if k else NAN
        if sig2 == 1:
            tl = l[k] - v
            if tl < pv:
                tl = pv
        elif sig2 == -1:
            tl = h[k] + v
            if tl > pv:
                tl = pv
        else:
            tl = pv
        tl2[k] = tl
        it = it2[k - 1] if k else NAN
        if tl > pv:
            it = 1.0
        if tl < pv:
            it = -1.0
        it2[k] = it
        if _ok(tl):
            g2[k] = it > 0
            r2[k] = not g2[k]
        if k:
            smart_buy[k] = it2[k - 1] == -1 and it == 1
            smart_sell[k] = it2[k - 1] == 1 and it == -1

        # ---- Kernel regression = Line 2 (สองชั้นตามโค้ด Pine)
        if k >= kn - 1:
            yd[k] = sum(kw[j] * cl[k - j] for j in range(kn)) / ksum
            if k >= 2 * (kn - 1):
                yd2 = sum(kw[j] * yd[k - j] for j in range(kn)) / ksum
                if c["K_FILTER"] == "none":
                    ks[k] = yd[k]
                elif c["K_FILTER"] == "zerolag":
                    ks[k] = yd[k] + (yd[k] - yd2)
                else:
                    ks[k] = yd2
        if _ok(ks[k]):
            gk[k] = k > 0 and _ok(ks[k - 1]) and ks[k] > ks[k - 1]
            rk[k] = not gk[k]

    return {"g1": g1, "g2": g2, "gk": gk, "r1": r1, "r2": r2, "rk": rk,
            "smart_buy": smart_buy, "smart_sell": smart_sell,
            "swing_low": sw_low, "swing_high": sw_high}


def _all3(sig, k: int, buy: bool) -> bool:
    if k < 0:
        return False
    return (sig["g1"][k] and sig["g2"][k] and sig["gk"][k]) if buy else \
           (sig["r1"][k] and sig["r2"][k] and sig["rk"][k])


def entry_signal(ltf, htf_all3_pair, i: int, buy: bool) -> bool:
    """กฎเข้า ณ การปิดแท่ง LTF index i (= shift 1 ใน EA). htf_all3_pair = HTF 2 แท่งล่าสุดครบ 3 เส้น."""
    if not htf_all3_pair or i < 3:
        return False
    t = i - 1
    smart_t = ltf["smart_buy" if buy else "smart_sell"][t]
    new_all3 = _all3(ltf, t, buy) and not _all3(ltf, t - 1, buy)
    if not (new_all3 or smart_t):
        return False
    still_all3 = _all3(ltf, i, buy)
    still_smart = smart_t and (ltf["g2"][i] if buy else ltf["r2"][i])
    return still_all3 or still_smart


def run_backtest(bars_raw, cfg=None, spread=0.20, htf_bars=None, start_bar=None):
    """คืน ``(closed_trades, extra_stats)`` (รูปแบบเดียวกับ ea_strategy_2.run_backtest).

    bars_raw = แท่ง LTF (M5), htf_bars = แท่ง HTF (H1) ต้องครอบคลุมช่วงเดียวกัน + warm-up.
    - สัญญาณประเมินเมื่อแท่ง LTF i ปิด -> เข้าที่ open แท่ง i+1 (buy จ่าย ask = open+spread)
    - SL/TP เช็คกับ high/low (sell เช็คฝั่ง ask = +spread); ชนทั้งคู่ในแท่งเดียว = นับ SL ก่อน
    - BE: ปิดแท่งเลย fibo -> SL ใหม่มีผลตั้งแต่แท่งถัดไป (แยกต่อไม้)
    - lot = balance(สะสม) x Risk% / (ระยะ SL x CONTRACT_SIZE) ปัดลงตาม LOT_STEP; ต่ำกว่า MIN_LOT = ข้าม
    - MAX_ENTRIES_PER_H1: จำนวนไม้ต่อสัญญาณ H1 (นับต่อฝั่ง รีเซ็ตเมื่อสัญญาณ H1 หาย)
    - CONCURRENT=False: ถือได้ทีละไม้
    """
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    if not htf_bars:
        return [], {"error": "htf_bars required", "entries": 0, "open_positions": 0}
    bars = list(bars_raw)
    n = len(bars)
    start_bar = 200 if start_bar is None else int(start_bar)
    if n <= start_bar + 3:
        return [], {"error": "not enough bars", "entries": 0, "open_positions": 0}

    ltf = compute_signals(bars, c)
    htf_list = list(htf_bars)
    htf = compute_signals(htf_list, c)
    o = [_value(b, "open") for b in bars]
    h = [_value(b, "high") for b in bars]
    l = [_value(b, "low") for b in bars]
    cl = [_value(b, "close") for b in bars]
    t_ltf = [int(b["time"]) for b in bars]
    t_htf = [int(b["time"]) for b in htf_list]
    ltf_s, htf_s = int(c["LTF_SECONDS"]), int(c["HTF_SECONDS"])

    point = float(c["POINT"])
    buf = float(c["SL_BUFFER_TICKS"]) * float(c["TICK_SIZE"])
    rr = float(c["RR"])
    balance = float(c["INITIAL_BALANCE"])
    contract = float(c["CONTRACT_SIZE"])
    max_per = int(c["MAX_ENTRIES_PER_H1"])

    trades = []
    positions: list = []
    counts = {"signals_buy": 0, "signals_sell": 0, "skipped_no_swing": 0, "skipped_bad_sl": 0,
              "skipped_small_lot": 0, "skipped_spread": 0, "breakevens": 0}
    entries = 0

    def close_pos(pos, bar_i, price, outcome):
        nonlocal balance
        profit = pos["dir"] * (price - pos["entry"]) * pos["lot"] * contract \
            - float(c["COMMISSION_PER_LOT_USD"]) * pos["lot"]
        balance += profit
        trades.append({
            "entry_bar": pos["bar"], "exit_bar": bar_i, "direction": pos["dir"],
            "entry": pos["entry"], "sl": pos["sl"], "tp": pos["tp"], "initial_sl": pos["sl0"],
            "lot": pos["lot"], "exit_price": price, "outcome": outcome, "profit": profit,
            "balance": balance, "pattern": "indi1", "reason": "3line_h1_m5",
        })
        positions.remove(pos)

    j = -1                         # index HTF แท่งล่าสุดที่ปิดแล้ว ณ เวลาปิดแท่ง LTF i
    n_used = {True: 0, False: 0}   # จำนวนไม้ที่เข้าไปแล้วในสัญญาณ H1 รอบนี้ (buy/sell)
    pending = 0
    pending_swing = NAN
    for i in range(start_bar, n):
        # 1) เข้าไม้ที่ open แท่งนี้ ตามสัญญาณแท่งก่อนหน้า
        if pending and (c["CONCURRENT"] or not positions):
            d = pending
            if c["MAX_SPREAD_POINTS"] and spread / point > c["MAX_SPREAD_POINTS"]:
                counts["skipped_spread"] += 1
            elif not _ok(pending_swing):
                counts["skipped_no_swing"] += 1
            else:
                entry = o[i] + spread if d == 1 else o[i]
                sl = pending_swing - buf if d == 1 else pending_swing + buf
                dist = abs(entry - sl)
                bad = (d == 1 and sl >= entry) or (d == -1 and sl <= entry)
                if bad or dist < float(c["MIN_SL_POINTS"]) * point or dist <= 0:
                    counts["skipped_bad_sl"] += 1
                else:
                    step = float(c["LOT_STEP"])
                    lot = math.floor(balance * float(c["RISK_PCT"]) / 100.0 / (dist * contract) / step) * step
                    if lot < float(c["MIN_LOT"]) - 1e-12:
                        counts["skipped_small_lot"] += 1
                    else:
                        n_used[d == 1] += 1
                        positions.append({"dir": d, "entry": entry, "sl": sl, "sl0": sl,
                                          "tp": entry + d * dist * rr, "bar": i, "lot": round(lot, 2), "be": False})
                        entries += 1
        pending = 0
        pending_swing = NAN

        for pos in list(positions):
            # 2) SL/TP ภายในแท่ง
            if pos["dir"] == 1:
                if l[i] <= pos["sl"]:
                    close_pos(pos, i, pos["sl"], "be" if pos["be"] else "sl")
                    continue
                if h[i] >= pos["tp"]:
                    close_pos(pos, i, pos["tp"], "tp")
                    continue
            else:
                if h[i] + spread >= pos["sl"]:
                    close_pos(pos, i, pos["sl"], "be" if pos["be"] else "sl")
                    continue
                if l[i] + spread <= pos["tp"]:
                    close_pos(pos, i, pos["tp"], "tp")
                    continue
            # 3) Fibo breakeven ตอนแท่ง i ปิด (นับแท่งที่เข้าด้วย)
            if c["USE_BE"] and not pos["be"]:
                level = pos["entry"] + (pos["tp"] - pos["entry"]) * float(c["BE_FIB"])
                lock = float(c["BE_LOCK_POINTS"]) * point
                if pos["dir"] == 1 and cl[i] > level and pos["entry"] + lock > pos["sl"] and pos["entry"] + lock < cl[i]:
                    pos["sl"] = pos["entry"] + lock
                    pos["be"] = True
                    counts["breakevens"] += 1
                elif pos["dir"] == -1 and cl[i] < level and pos["entry"] - lock < pos["sl"] and pos["entry"] - lock > cl[i] + spread:
                    pos["sl"] = pos["entry"] - lock
                    pos["be"] = True
                    counts["breakevens"] += 1

        # 4) สัญญาณ H1 (2 แท่งปิดล่าสุดครบ 3 เส้น) - ติดตามทุกแท่ง เพื่อรีเซ็ตโควตาเมื่อสัญญาณหาย
        close_time = t_ltf[i] + ltf_s
        while j + 1 < len(t_htf) and t_htf[j + 1] + htf_s <= close_time:
            j += 1
        pairs = {b: (j >= 1 and _all3(htf, j, b) and _all3(htf, j - 1, b)) for b in (True, False)}
        for b in (True, False):
            if not pairs[b]:
                n_used[b] = 0

        # 5) ประเมินสัญญาณเมื่อแท่ง i ปิด
        if i + 1 < n and (c["CONCURRENT"] or not positions):
            for buy in (True, False):
                if buy and not c["ALLOW_BUY"]:
                    continue
                if not buy and not c["ALLOW_SELL"]:
                    continue
                if max_per and n_used[buy] >= max_per:
                    continue
                if entry_signal(ltf, pairs[buy], i, buy):
                    counts["signals_buy" if buy else "signals_sell"] += 1
                    pending = 1 if buy else -1
                    pending_swing = ltf["swing_low" if buy else "swing_high"][i]
                    break

    extra = {"entries": entries, "open_positions": len(positions), "final_balance": balance, **counts}
    return trades, extra
