from config import *
import config
from mt5_utils import get_structure, find_swing_tp


_s4_debug_last: dict[str, str] = {}


def _s4_debug(group: str, signature: str, message: str) -> None:
    if not getattr(config, "TRADE_DEBUG", False):
        return
    if _s4_debug_last.get(group) == signature:
        return
    _s4_debug_last[group] = signature
    print(message)


def _in_body(price: float, bar) -> bool:
    body_low = min(float(bar["open"]), float(bar["close"]))
    body_high = max(float(bar["open"]), float(bar["close"]))
    return body_low <= float(price) <= body_high


def _find_prev_swing_high(rates, lookback=100):
    """หา Swing High ย่อยล่าสุด ก่อนแท่ง [2]

    Pattern: เขียว[i] + แดง[i+1]  (2 แท่ง)
    swing_h = max(High[i], High[i+1])
    ไม่มีแท่งหลัง pair (ถึงแท่ง2) ที่ High >= swing_h

    คืน dict: {price, bar_from_2, candle} หรือ None
    """
    r = rates[-min(lookback, len(rates)):-3]
    total = len(rates)
    r_start = total - min(lookback, total)

    for i in range(len(r) - 2, 0, -1):
        bull_i    = float(r[i]["close"])   > float(r[i]["open"])
        bull_next = float(r[i+1]["close"]) > float(r[i+1]["open"])
        if not bull_i:  continue   # r[i] ต้องเขียว
        if bull_next:   continue   # r[i+1] ต้องแดง

        swing_h = max(float(r[i]["high"]), float(r[i+1]["high"]))
        if i - 1 >= 0:
            prev_bar = r[i-1]
            prev_bull = float(prev_bar["close"]) > float(prev_bar["open"])
            if not prev_bull and _in_body(swing_h, prev_bar):
                continue

        # ไม่มีแท่งหลัง pair จนถึงแท่ง2 ที่ High >= swing_h
        if any(float(r[j]["high"]) >= swing_h for j in range(i + 2, len(r))): continue

        max_idx = i if float(r[i]["high"]) >= float(r[i+1]["high"]) else i + 1
        bar_from_2 = (total - 3) - (r_start + max_idx)
        max_bar = r[max_idx]
        return {"price": swing_h, "bar_from_2": bar_from_2,
                "time": int(max_bar["time"]),
                "candle": {"open": float(max_bar["open"]), "high": swing_h,
                           "low":  float(max_bar["low"]),  "close": float(max_bar["close"])}}
    return None


def _find_prev_swing_low(rates, lookback=100):
    """หา Swing Low ย่อยล่าสุด ก่อนแท่ง [2]

    Pattern: แดง[i] + เขียว[i+1]  (2 แท่ง)
    swing_l = min(Low[i], Low[i+1])
    ไม่มีแท่งหลัง pair (ถึงแท่ง2) ที่ Low <= swing_l

    คืน dict: {price, bar_from_2, candle} หรือ None
    """
    r = rates[-min(lookback, len(rates)):-3]
    total = len(rates)
    r_start = total - min(lookback, total)

    for i in range(len(r) - 2, 0, -1):
        bull_i    = float(r[i]["close"])   > float(r[i]["open"])
        bull_next = float(r[i+1]["close"]) > float(r[i+1]["open"])
        if bull_i:        continue   # r[i] ต้องแดง
        if not bull_next: continue   # r[i+1] ต้องเขียว

        swing_l = min(float(r[i]["low"]), float(r[i+1]["low"]))
        if i - 1 >= 0:
            prev_bar = r[i-1]
            prev_bull = float(prev_bar["close"]) > float(prev_bar["open"])
            if prev_bull and _in_body(swing_l, prev_bar):
                continue

        # ไม่มีแท่งหลัง pair จนถึงแท่ง2 ที่ Low <= swing_l
        if any(float(r[j]["low"]) <= swing_l for j in range(i + 2, len(r))): continue

        min_idx = i if float(r[i]["low"]) <= float(r[i+1]["low"]) else i + 1
        bar_from_2 = (total - 3) - (r_start + min_idx)
        min_bar = r[min_idx]
        return {"price": swing_l, "bar_from_2": bar_from_2,
                "time": int(min_bar["time"]),
                "candle": {"open": float(min_bar["open"]), "high": float(min_bar["high"]),
                           "low":  swing_l, "close": float(min_bar["close"])}}
    return None


def _is_pivot_high(rates, idx: int, left: int, right: int) -> bool:
    center = float(rates[idx]["high"])
    for j in range(idx - left, idx):
        if float(rates[j]["high"]) >= center:
            return False
    for j in range(idx + 1, idx + right + 1):
        if float(rates[j]["high"]) > center:
            return False
    return True


def _is_pivot_low(rates, idx: int, left: int, right: int) -> bool:
    center = float(rates[idx]["low"])
    for j in range(idx - left, idx):
        if float(rates[j]["low"]) <= center:
            return False
    for j in range(idx + 1, idx + right + 1):
        if float(rates[j]["low"]) < center:
            return False
    return True


def _find_prev_pivot_swing_high(rates, lookback=100, left=15, right=10):
    total = len(rates)
    if total < left + right + 3:
        return None
    start = max(left, total - min(lookback, total))
    end = total - right
    for i in range(end - 1, start - 1, -1):
        if not _is_pivot_high(rates, i, left, right):
            continue
        swing_h = float(rates[i]["high"])
        bar_from_2 = (total - 3) - i
        bar = rates[i]
        return {
            "price": swing_h,
            "bar_from_2": bar_from_2,
            "time": int(bar["time"]),
            "candle": {
                "open": float(bar["open"]),
                "high": swing_h,
                "low": float(bar["low"]),
                "close": float(bar["close"]),
            },
        }
    return None


def _find_prev_pivot_swing_low(rates, lookback=100, left=15, right=10):
    total = len(rates)
    if total < left + right + 3:
        return None
    start = max(left, total - min(lookback, total))
    end = total - right
    for i in range(end - 1, start - 1, -1):
        if not _is_pivot_low(rates, i, left, right):
            continue
        swing_l = float(rates[i]["low"])
        bar_from_2 = (total - 3) - i
        bar = rates[i]
        return {
            "price": swing_l,
            "bar_from_2": bar_from_2,
            "time": int(bar["time"]),
            "candle": {
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": swing_l,
                "close": float(bar["close"]),
            },
        }
    return None


def _find_hh(rates, current_sh, lookback=100):
    """หา Higher High: Swing High เก่าที่สูงกว่า H ปัจจุบัน

    scan โดยตรงใน bars ที่ time < cur_time (ไม่ผ่าน _find_prev_swing_high)
    เพื่อเลี่ยงการตัด `:-3` ซ้อนที่ทำให้ pair ใกล้ cur_time หลุดหน้าต่าง
    """
    if not current_sh:
        return None
    cur_price = current_sh["price"]
    cur_time = int(current_sh.get("time", 0) or 0)

    total = len(rates)
    filtered_end = 0
    for j in range(total):
        if int(rates[j]["time"]) < cur_time:
            filtered_end = j + 1
        else:
            break
    if filtered_end < 3:
        return None
    r_start = max(0, filtered_end - lookback)
    r = rates[r_start:filtered_end]

    for i in range(len(r) - 2, 0, -1):
        bull_i    = float(r[i]["close"])   > float(r[i]["open"])
        bull_next = float(r[i+1]["close"]) > float(r[i+1]["open"])
        if not bull_i:  continue   # r[i] ต้องเขียว
        if bull_next:   continue   # r[i+1] ต้องแดง

        swing_h = max(float(r[i]["high"]), float(r[i+1]["high"]))
        if swing_h <= cur_price:
            continue

        if i - 1 >= 0:
            prev_bar = r[i-1]
            prev_bull = float(prev_bar["close"]) > float(prev_bar["open"])
            if not prev_bull and _in_body(swing_h, prev_bar):
                continue

        if any(float(r[j]["high"]) >= swing_h for j in range(i + 2, len(r))):
            continue

        max_idx = i if float(r[i]["high"]) >= float(r[i+1]["high"]) else i + 1
        bar_from_2 = (total - 3) - (r_start + max_idx)
        max_bar = r[max_idx]
        return {"price": swing_h, "bar_from_2": bar_from_2,
                "time": int(max_bar["time"]),
                "candle": {"open": float(max_bar["open"]), "high": swing_h,
                           "low":  float(max_bar["low"]),  "close": float(max_bar["close"])}}
    return None


def _find_ll(rates, current_sl, lookback=100):
    """หา Lower Low: Swing Low เก่าที่ต่ำกว่า L ปัจจุบัน

    scan โดยตรงใน bars ที่ time < cur_time (ไม่ผ่าน _find_prev_swing_low)
    เพื่อเลี่ยงการตัด `:-3` ซ้อนที่ทำให้ pair ใกล้ cur_time หลุดหน้าต่าง
    """
    if not current_sl:
        return None
    cur_price = current_sl["price"]
    cur_time = int(current_sl.get("time", 0) or 0)

    total = len(rates)
    filtered_end = 0
    for j in range(total):
        if int(rates[j]["time"]) < cur_time:
            filtered_end = j + 1
        else:
            break
    if filtered_end < 3:
        return None
    r_start = max(0, filtered_end - lookback)
    r = rates[r_start:filtered_end]

    for i in range(len(r) - 2, 0, -1):
        bull_i    = float(r[i]["close"])   > float(r[i]["open"])
        bull_next = float(r[i+1]["close"]) > float(r[i+1]["open"])
        if bull_i:        continue   # r[i] ต้องแดง
        if not bull_next: continue   # r[i+1] ต้องเขียว

        swing_l = min(float(r[i]["low"]), float(r[i+1]["low"]))
        if swing_l >= cur_price:
            continue

        if i - 1 >= 0:
            prev_bar = r[i-1]
            prev_bull = float(prev_bar["close"]) > float(prev_bar["open"])
            if prev_bull and _in_body(swing_l, prev_bar):
                continue

        if any(float(r[j]["low"]) <= swing_l for j in range(i + 2, len(r))):
            continue

        min_idx = i if float(r[i]["low"]) <= float(r[i+1]["low"]) else i + 1
        bar_from_2 = (total - 3) - (r_start + min_idx)
        min_bar = r[min_idx]
        return {"price": swing_l, "bar_from_2": bar_from_2,
                "time": int(min_bar["time"]),
                "candle": {"open": float(min_bar["open"]), "high": float(min_bar["high"]),
                           "low":  swing_l, "close": float(min_bar["close"])}}
    return None


def _find_pivot_hh(rates, current_sh, lookback=100, left=15, right=10):
    if not current_sh:
        return None
    cur_price = float(current_sh["price"])
    cur_time = int(current_sh.get("time", 0) or 0)
    for i in range(len(rates) - 1, -1, -1):
        if int(rates[i]["time"]) >= cur_time:
            continue
        info = _find_prev_pivot_swing_high(rates[:i + 1], lookback=lookback, left=left, right=right)
        if info and float(info["price"]) > cur_price:
            return info
    return None


def _find_pivot_ll(rates, current_sl, lookback=100, left=15, right=10):
    if not current_sl:
        return None
    cur_price = float(current_sl["price"])
    cur_time = int(current_sl.get("time", 0) or 0)
    for i in range(len(rates) - 1, -1, -1):
        if int(rates[i]["time"]) >= cur_time:
            continue
        info = _find_prev_pivot_swing_low(rates[:i + 1], lookback=lookback, left=left, right=right)
        if info and float(info["price"]) < cur_price:
            return info
    return None


def _get_s4_prev_swing_high(rates, lookback=100):
    left = max(1, int(getattr(config, "SWING_PIVOT_LEFT", 15) or 15))
    right = max(1, int(getattr(config, "SWING_PIVOT_RIGHT", 10) or 10))
    return _find_prev_pivot_swing_high(rates, lookback=lookback, left=left, right=right) or _find_prev_swing_high(rates, lookback=lookback)


def _get_s4_prev_swing_low(rates, lookback=100):
    left = max(1, int(getattr(config, "SWING_PIVOT_LEFT", 15) or 15))
    right = max(1, int(getattr(config, "SWING_PIVOT_RIGHT", 10) or 10))
    return _find_prev_pivot_swing_low(rates, lookback=lookback, left=left, right=right) or _find_prev_swing_low(rates, lookback=lookback)


def strategy_4(rates):
    """
    ท่าที่ 4 — นัยยะสำคัญ FVG

    BUY:
      1. [1] เขียว + High[1] > High[2]  → FVG เกิด
      2. Close[1] > Swing High ก่อนหน้า → [1] กลืนกิน significant level
      3. Swing High ต้องอยู่ในช่วง FVG gap ระหว่าง High[2] และ Low[0]
      4. Low[0] > Swing High             → Gap ยังเปิด ([0] อยู่เหนือ Swing)
      Entry = Swing High | SL = Low[1] − SL_BUFFER() | TP = Swing High ย่อยถัดไป

    SELL (สลับสี):
      1. [1] แดง + Low[1] < Low[2]      → FVG เกิด
      2. Close[1] < Swing Low ก่อนหน้า  → [1] กลืนกิน
      3. Swing Low ต้องอยู่ในช่วง FVG gap ระหว่าง High[0] และ Low[2]
      4. High[0] < Swing Low            → Gap ยังเปิด
      Entry = Swing Low | SL = High[1] + SL_BUFFER()
    """
    if len(rates) < 6:
        return {"signal": "WAIT", "reason": "ข้อมูลไม่เพียงพอ"}

    def c(i):
        r = rates[i]
        o  = float(r["open"]);  h = float(r["high"])
        l  = float(r["low"]);   cl= float(r["close"])
        return o, h, l, cl, cl > o

    o0, h0, l0, cl0, bull0 = c(-1)   # [0] live/closed
    o1, h1, l1, cl1, bull1 = c(-2)   # [1] ปิดแล้ว — Imbalance + กลืนกิน
    o2, h2, l2, cl2, bull2 = c(-3)   # [2] ฐาน

    ms   = get_structure(rates)
    sh   = ms["swing_high"]
    sl_z = ms["swing_low"]
    now  = now_bkk().strftime("%H:%M:%S")
    engulf_gap = engulf_min_price()
    bar_time = int(rates[-1]["time"])

    # ── BUY ───────────────────────────────────────────────────
    # [1] เขียว + High[1] > High[2] (FVG เกิด)
    # [1] Close > Swing High ก่อนหน้า (กลืนกิน significant level)
    # Swing High ต้องอยู่ในช่วง gap: High[2] < Swing High < Low[0]
    # BUY FVG: [1] เขียว + Low[0] > High[2] → gap จริง
    if bull1 and h1 > h2 and l0 > h2:
        sh_info = _get_s4_prev_swing_high(rates)
        prev_sh  = sh_info["price"] if sh_info else None
        swing_in_gap = prev_sh is not None and h2 < prev_sh < l0
        _s4_debug(
            "buy_check",
            f"{bar_time}|{h2:.2f}|{l0:.2f}|{prev_sh if prev_sh is not None else 'None'}|{swing_in_gap}",
            f"[{now}] S4 BUY check: gap=({h2:.2f}-{l0:.2f}) swing={prev_sh if prev_sh is not None else 'None'} in_gap={swing_in_gap}",
        )
        # [0] ต้องอยู่เหนือ Swing High (Low[0] > Swing High) → Gap ยังเปิด
        gap_open = prev_sh and l0 > prev_sh

        if prev_sh and cl1 > prev_sh + engulf_gap and swing_in_gap and gap_open:
            entry    = round(prev_sh, 2)
            sl       = round(l1 - SL_BUFFER(), 2)
            tp_swing = find_swing_tp(rates, "BUY", entry, sl)
            tp       = tp_swing if tp_swing else round(entry + (entry - sl), 2)
            tp_note  = f"Swing High:{tp}" if tp_swing else "RR1:1 (fallback)"
            rr       = round(abs(tp - entry) / abs(entry - sl), 2) if abs(entry - sl) > 0 else 0

            return {
                "signal":  "BUY",
                "pattern": "ท่าที่ 4 นัยยะสำคัญ FVG 🟢 BUY",
                "entry":   entry,
                "sl":      sl,
                "tp":      tp,
                "reason":  (
                    f"✅ [1] เขียวกลืน Swing High:{prev_sh:.2f} Close:{cl1:.2f}\n"
                    f"✅ [0] Low[0]:{l0:.2f} > Swing High:{prev_sh:.2f} Gap ยังเปิด\n"
                    f"📍 Swing แท่ง[{-(sh_info['bar_from_2']+3) if sh_info else '?'}] O:{sh_info['candle']['open']:.2f} H:{sh_info['candle']['high']:.2f} L:{sh_info['candle']['low']:.2f} C:{sh_info['candle']['close']:.2f}\n"
                    f"📌 BUY LIMIT @ Swing High:{entry} SL:{sl} TP:{tp} RR1:{rr}"
                ),
                "candles": [
                    {"open":o2,"high":h2,"low":l2,"close":cl2},
                    {"open":o1,"high":h1,"low":l1,"close":cl1},
                    {"open":o0,"high":h0,"low":l0,"close":cl0},
                ],
                "swing_high": sh, "swing_low": sl_z,
            }

        if not sh_info:
            _s4_debug("buy_wait_no_previous_swing_high", f"{bar_time}|none", f"[{now}] S4 BUY wait: no previous swing high")
            return {"signal": "WAIT", "pattern": "ท่าที่ 4 นัยยะสำคัญ FVG 🟢 BUY",
                    "reason": "⚠️ ไม่พบ Swing High ก่อนหน้า"}
        if prev_sh and cl1 <= prev_sh + engulf_gap:
            _s4_debug(
                "buy_wait_close_not_break",
                f"{bar_time}|{prev_sh:.2f}|{cl1:.2f}|{engulf_gap:.2f}",
                f"[{now}] S4 BUY wait: close_not_break swing={prev_sh:.2f} close1={cl1:.2f} gap_min={engulf_gap:.2f}",
            )
            return {"signal": "WAIT", "pattern": "ท่าที่ 4 นัยยะสำคัญ FVG 🟢 BUY",
                    "reason": f"⚠️ [1] Close:{cl1:.2f} ยังไม่ห่าง Swing High:{prev_sh:.2f} ขั้นต่ำ {engulf_gap:.2f}"}
        if prev_sh and not swing_in_gap:
            _s4_debug(
                "buy_wait_swing_outside_gap",
                f"{bar_time}|{prev_sh:.2f}|{h2:.2f}|{l0:.2f}",
                f"[{now}] S4 BUY wait: swing_outside_gap swing={prev_sh:.2f} gap=({h2:.2f}-{l0:.2f})",
            )
            return {"signal": "WAIT", "pattern": "ท่าที่ 4 นัยยะสำคัญ FVG 🟢 BUY",
                    "reason": f"⚠️ Swing High:{prev_sh:.2f} อยู่นอก FVG gap ({h2:.2f} - {l0:.2f})"}
        _s4_debug(
            "buy_wait_gap_closed",
            f"{bar_time}|{l0:.2f}|{prev_sh:.2f}",
            f"[{now}] S4 BUY wait: gap_closed low0={l0:.2f} swing={prev_sh:.2f}",
        )
        return {"signal": "WAIT", "pattern": "ท่าที่ 4 นัยยะสำคัญ FVG 🟢 BUY",
                "reason": f"⏳ [0] Low[0]:{l0:.2f} ≤ Swing High:{prev_sh:.2f} Gap ปิดแล้ว รอ setup ใหม่"}

    # ── SELL ──────────────────────────────────────────────────
    # [1] แดง + Low[1] < Low[2] (FVG เกิด)
    # [1] Close < Swing Low ก่อนหน้า (กลืนกิน)
    # Swing Low ต้องอยู่ในช่วง gap: High[0] < Swing Low < Low[2]
    # SELL FVG: [1] แดง + High[0] < Low[2] → gap จริง
    if not bull1 and l1 < l2 and h0 < l2:
        sl_info = _get_s4_prev_swing_low(rates)
        prev_sl  = sl_info["price"] if sl_info else None
        swing_in_gap = prev_sl is not None and h0 < prev_sl < l2
        _s4_debug(
            "sell_check",
            f"{bar_time}|{h0:.2f}|{l2:.2f}|{prev_sl if prev_sl is not None else 'None'}|{swing_in_gap}",
            f"[{now}] S4 SELL check: gap=({h0:.2f}-{l2:.2f}) swing={prev_sl if prev_sl is not None else 'None'} in_gap={swing_in_gap}",
        )
        # [0] ต้องอยู่ใต้ Swing Low (High[0] < Swing Low) → Gap ยังเปิด
        gap_open = prev_sl and h0 < prev_sl

        if prev_sl and cl1 < prev_sl - engulf_gap and swing_in_gap and gap_open:
            entry    = round(prev_sl, 2)
            sl       = round(h1 + SL_BUFFER(), 2)
            tp_swing = find_swing_tp(rates, "SELL", entry, sl)
            tp       = tp_swing if tp_swing else round(entry - (sl - entry), 2)
            tp_note  = f"Swing Low:{tp}" if tp_swing else "RR1:1 (fallback)"
            rr       = round(abs(tp - entry) / abs(sl - entry), 2) if abs(sl - entry) > 0 else 0

            return {
                "signal":  "SELL",
                "pattern": "ท่าที่ 4 นัยยะสำคัญ FVG 🔴 SELL",
                "entry":   entry,
                "sl":      sl,
                "tp":      tp,
                "reason":  (
                    f"✅ [1] แดงกลืน Swing Low:{prev_sl:.2f} Close:{cl1:.2f}\n"
                    f"✅ [0] High[0]:{h0:.2f} < Swing Low:{prev_sl:.2f} Gap ยังเปิด\n"
                    f"📍 Swing แท่ง[{-(sl_info['bar_from_2']+3) if sl_info else '?'}] O:{sl_info['candle']['open']:.2f} H:{sl_info['candle']['high']:.2f} L:{sl_info['candle']['low']:.2f} C:{sl_info['candle']['close']:.2f}\n"
                    f"📌 SELL LIMIT @ Swing Low:{entry} SL:{sl} TP:{tp} RR1:{rr}"
                ),
                "candles": [
                    {"open":o2,"high":h2,"low":l2,"close":cl2},
                    {"open":o1,"high":h1,"low":l1,"close":cl1},
                    {"open":o0,"high":h0,"low":l0,"close":cl0},
                ],
                "swing_high": sh, "swing_low": sl_z,
            }

        if not sl_info:
            _s4_debug("sell_wait_no_previous_swing_low", f"{bar_time}|none", f"[{now}] S4 SELL wait: no previous swing low")
            return {"signal": "WAIT", "pattern": "ท่าที่ 4 นัยยะสำคัญ FVG 🔴 SELL",
                    "reason": "⚠️ ไม่พบ Swing Low ก่อนหน้า"}
        if prev_sl and cl1 >= prev_sl - engulf_gap:
            _s4_debug(
                "sell_wait_close_not_break",
                f"{bar_time}|{prev_sl:.2f}|{cl1:.2f}|{engulf_gap:.2f}",
                f"[{now}] S4 SELL wait: close_not_break swing={prev_sl:.2f} close1={cl1:.2f} gap_min={engulf_gap:.2f}",
            )
            return {"signal": "WAIT", "pattern": "ท่าที่ 4 นัยยะสำคัญ FVG 🔴 SELL",
                    "reason": f"⚠️ [1] Close:{cl1:.2f} ยังไม่ห่าง Swing Low:{prev_sl:.2f} ขั้นต่ำ {engulf_gap:.2f}"}
        if prev_sl and not swing_in_gap:
            _s4_debug(
                "sell_wait_swing_outside_gap",
                f"{bar_time}|{prev_sl:.2f}|{h0:.2f}|{l2:.2f}",
                f"[{now}] S4 SELL wait: swing_outside_gap swing={prev_sl:.2f} gap=({h0:.2f}-{l2:.2f})",
            )
            return {"signal": "WAIT", "pattern": "ท่าที่ 4 นัยยะสำคัญ FVG 🔴 SELL",
                    "reason": f"⚠️ Swing Low:{prev_sl:.2f} อยู่นอก FVG gap ({h0:.2f} - {l2:.2f})"}
        _s4_debug(
            "sell_wait_gap_closed",
            f"{bar_time}|{h0:.2f}|{prev_sl:.2f}",
            f"[{now}] S4 SELL wait: gap_closed high0={h0:.2f} swing={prev_sl:.2f}",
        )
        return {"signal": "WAIT", "pattern": "ท่าที่ 4 นัยยะสำคัญ FVG 🔴 SELL",
                "reason": f"⏳ [0] High[0]:{h0:.2f} ≥ Swing Low:{prev_sl:.2f} Gap ปิดแล้ว รอ setup ใหม่"}

    return {"signal": "WAIT", "reason": "ไม่พบ Setup นัยยะสำคัญ FVG"}
