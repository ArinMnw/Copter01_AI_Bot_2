import config
from config import *
from mt5_utils import find_swing_tp
from strategy4 import _find_prev_swing_high, _find_prev_swing_low


def _applied_price_from_bar(bar, applied_price: str) -> float:
    mode = str(applied_price or "close").strip().lower()
    o = float(bar["open"])
    h = float(bar["high"])
    l = float(bar["low"])
    c = float(bar["close"])
    if mode == "open":
        return o
    if mode == "high":
        return h
    if mode == "low":
        return l
    if mode in ("median", "hl2"):
        return (h + l) / 2.0
    if mode in ("typical", "hlc3"):
        return (h + l + c) / 3.0
    if mode in ("weighted", "hlcc4", "weighted_close"):
        return (h + l + (2.0 * c)) / 4.0
    return c


def _calc_rsi_values(rates, period=14, applied_price: str = "close"):
    prices = [_applied_price_from_bar(r, applied_price) for r in rates]
    n = len(prices)
    if n <= period:
        return [None] * n

    rsis = [None] * n
    gains = []
    losses = []
    for i in range(1, period + 1):
        delta = prices[i] - prices[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        rsis[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsis[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, n):
        delta = prices[i] - prices[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        if avg_loss == 0:
            rsis[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsis[i] = 100.0 - (100.0 / (1.0 + rs))
    return rsis


def _fmt_rsi(v):
    return f"{float(v):.2f}" if v is not None else "-"


def _pivot_low(values, idx: int, left: int, right: int) -> bool:
    if idx - left < 0 or idx + right >= len(values):
        return False
    center = values[idx]
    if center is None:
        return False
    window = values[idx - left:idx + right + 1]
    if any(v is None for v in window):
        return False
    if center != min(window):
        return False
    return window.count(center) == 1


def _pivot_high(values, idx: int, left: int, right: int) -> bool:
    if idx - left < 0 or idx + right >= len(values):
        return False
    center = values[idx]
    if center is None:
        return False
    window = values[idx - left:idx + right + 1]
    if any(v is None for v in window):
        return False
    if center != max(window):
        return False
    return window.count(center) == 1


def _find_rsi_pivot_lows(rsi_values, left: int, right: int):
    return [i for i in range(len(rsi_values)) if _pivot_low(rsi_values, i, left, right)]


def _find_rsi_pivot_highs(rsi_values, left: int, right: int):
    return [i for i in range(len(rsi_values)) if _pivot_high(rsi_values, i, left, right)]


def _find_previous_valid_pivot(pivots, current_idx: int, min_range: int, max_range: int):
    """
    เลือก immediate previous pivot ตัวเดียว (ตรงกับ TV `valuewhen(plFound, ..., 1)`)
    ถ้าตัวก่อนหน้าทันที out-of-range → return None (ไม่ walk back หาตัวเก่ากว่า)
    """
    if not pivots:
        return None
    prev_idx = pivots[-1]   # immediate previous (newest ก่อน current)
    if prev_idx >= current_idx:
        return None
    gap = current_idx - prev_idx
    if min_range <= gap <= max_range:
        return prev_idx
    return None


def _find_prev_swing_high_before_index(rates, idx: int):
    subset = rates[:idx]
    if len(subset) < 6:
        return None
    try:
        return _find_prev_swing_high(subset)
    except Exception:
        return None


def _find_prev_swing_low_before_index(rates, idx: int):
    subset = rates[:idx]
    if len(subset) < 6:
        return None
    try:
        return _find_prev_swing_low(subset)
    except Exception:
        return None


def _build_bullish_setup(rates, rsi_values, period: int, applied_price: str,
                         left: int, right: int, min_range: int, max_range: int,
                         hidden: bool):
    lows = _find_rsi_pivot_lows(rsi_values, left, right)
    if len(lows) < 2:
        return None

    cur_idx = lows[-1]
    prev_idx = _find_previous_valid_pivot(lows[:-1], cur_idx, min_range, max_range)
    if prev_idx is None:
        return None

    cur_price_low = float(rates[cur_idx]["low"])
    prev_price_low = float(rates[prev_idx]["low"])
    cur_rsi = rsi_values[cur_idx]
    prev_rsi = rsi_values[prev_idx]
    if cur_rsi is None or prev_rsi is None:
        return None

    # cur pivot ต้องเป็น low ต่ำสุดในช่วง prev→cur (ไม่มีแท่งระหว่างกลางทำ low ต่ำกว่า)
    if cur_idx > prev_idx + 1:
        min_low_between = min(float(rates[i]["low"]) for i in range(prev_idx + 1, cur_idx))
        if min_low_between < cur_price_low:
            return None

    if hidden:
        matched = cur_price_low > prev_price_low and cur_rsi < prev_rsi
        pattern_name = "Hidden Bullish"
        price_cmp = ">"
        rsi_cmp = "<"
    else:
        matched = cur_price_low < prev_price_low and cur_rsi > prev_rsi
        pattern_name = "Regular Bullish"
        price_cmp = "<"
        rsi_cmp = ">"

    if not matched:
        return None

    # Limit entry @ low ของแท่ง cur pivot — รอ pullback กลับมาแตะ
    entry = round(cur_price_low, 2)
    sl = round(cur_price_low - SL_BUFFER(), 2)
    if sl >= entry:
        return None
    tp_swing = find_swing_tp(rates, "BUY", entry, sl)
    tp = tp_swing if tp_swing else round(entry + (entry - sl), 2)

    return {
        "signal": "BUY",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 9 RSI Divergence 🟢 BUY — {pattern_name}",
        "reason": (
            f"RSI({period}, {applied_price}) Pivot Low ปัจจุบัน:`{_fmt_rsi(cur_rsi)}` {rsi_cmp} ก่อนหน้า:`{_fmt_rsi(prev_rsi)}`\n"
            f"Price Low ปัจจุบัน:`{cur_price_low:.2f}` {price_cmp} ก่อนหน้า:`{prev_price_low:.2f}`\n"
            f"Pivot Left/Right: `{left}/{right}` | Lookback Range: `{min_range}-{max_range}` bars\n"
            f"BUY LIMIT @ Low ของแท่ง pivot = `{entry:.2f}` | SL: `{sl:.2f}`"
        ),
        "order_mode": "limit",
        "entry_label": "BUY LIMIT ที่",
        "swing_low": cur_price_low,
        "div_type": pattern_name,
        "pivot_prev_index": prev_idx,
        "pivot_cur_index": cur_idx,
        "pivot_prev_time": int(rates[prev_idx]["time"]),
        "pivot_cur_time": int(rates[cur_idx]["time"]),
        "price_prev": round(prev_price_low, 2),
        "price_cur": round(cur_price_low, 2),
        "rsi_prev": _fmt_rsi(prev_rsi),
        "rsi_cur": _fmt_rsi(cur_rsi),
    }


def _build_bearish_setup(rates, rsi_values, period: int, applied_price: str,
                         left: int, right: int, min_range: int, max_range: int,
                         hidden: bool):
    highs = _find_rsi_pivot_highs(rsi_values, left, right)
    if len(highs) < 2:
        return None

    cur_idx = highs[-1]
    prev_idx = _find_previous_valid_pivot(highs[:-1], cur_idx, min_range, max_range)
    if prev_idx is None:
        return None

    cur_price_high = float(rates[cur_idx]["high"])
    prev_price_high = float(rates[prev_idx]["high"])
    cur_rsi = rsi_values[cur_idx]
    prev_rsi = rsi_values[prev_idx]
    if cur_rsi is None or prev_rsi is None:
        return None

    # cur pivot ต้องเป็น high สูงสุดในช่วง prev→cur (ไม่มีแท่งระหว่างกลางทำ high สูงกว่า)
    if cur_idx > prev_idx + 1:
        max_high_between = max(float(rates[i]["high"]) for i in range(prev_idx + 1, cur_idx))
        if max_high_between > cur_price_high:
            return None

    if hidden:
        matched = cur_price_high < prev_price_high and cur_rsi > prev_rsi
        pattern_name = "Hidden Bearish"
        price_cmp = "<"
        rsi_cmp = ">"
    else:
        matched = cur_price_high > prev_price_high and cur_rsi < prev_rsi
        pattern_name = "Regular Bearish"
        price_cmp = ">"
        rsi_cmp = "<"

    if not matched:
        return None

    # Limit entry @ high ของแท่ง cur pivot — รอ pullback กลับมาแตะ
    entry = round(cur_price_high, 2)
    sl = round(cur_price_high + SL_BUFFER(), 2)
    if sl <= entry:
        return None
    tp_swing = find_swing_tp(rates, "SELL", entry, sl)
    tp = tp_swing if tp_swing else round(entry - (sl - entry), 2)

    return {
        "signal": "SELL",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 9 RSI Divergence 🔴 SELL — {pattern_name}",
        "reason": (
            f"RSI({period}, {applied_price}) Pivot High ปัจจุบัน:`{_fmt_rsi(cur_rsi)}` {rsi_cmp} ก่อนหน้า:`{_fmt_rsi(prev_rsi)}`\n"
            f"Price High ปัจจุบัน:`{cur_price_high:.2f}` {price_cmp} ก่อนหน้า:`{prev_price_high:.2f}`\n"
            f"Pivot Left/Right: `{left}/{right}` | Lookback Range: `{min_range}-{max_range}` bars\n"
            f"SELL LIMIT @ High ของแท่ง pivot = `{entry:.2f}` | SL: `{sl:.2f}`"
        ),
        "order_mode": "limit",
        "entry_label": "SELL LIMIT ที่",
        "swing_high": cur_price_high,
        "div_type": pattern_name,
        "pivot_prev_index": prev_idx,
        "pivot_cur_index": cur_idx,
        "pivot_prev_time": int(rates[prev_idx]["time"]),
        "pivot_cur_time": int(rates[cur_idx]["time"]),
        "price_prev": round(prev_price_high, 2),
        "price_cur": round(cur_price_high, 2),
        "rsi_prev": _fmt_rsi(prev_rsi),
        "rsi_cur": _fmt_rsi(cur_rsi),
    }


def strategy_9(rates):
    """ท่าที่ 9: RSI Pivot Divergence ให้สอดคล้องกับ indicator RSIDivergencePane.mq5"""
    period = int(getattr(config, "RSI9_PERIOD", 14))
    applied_price = str(getattr(config, "RSI9_APPLIED_PRICE", "close"))
    left = int(getattr(config, "RSI9_PIVOT_LOOKBACK_LEFT", 5))
    right = int(getattr(config, "RSI9_PIVOT_LOOKBACK_RIGHT", 5))
    max_range = int(getattr(config, "RSI9_LOOKBACK_RANGE_MAX", 60))
    min_range = int(getattr(config, "RSI9_LOOKBACK_RANGE_MIN", 5))
    plot_bullish = bool(getattr(config, "RSI9_PLOT_BULLISH", True))
    plot_hidden_bullish = bool(getattr(config, "RSI9_PLOT_HIDDEN_BULLISH", False))
    plot_bearish = bool(getattr(config, "RSI9_PLOT_BEARISH", True))
    plot_hidden_bearish = bool(getattr(config, "RSI9_PLOT_HIDDEN_BEARISH", False))

    min_bars = period + left + right + max_range + 5
    if len(rates) < min_bars:
        return {"signal": "WAIT", "reason": "ข้อมูลไม่พอสำหรับ RSI Pivot Divergence"}

    rsi_values = _calc_rsi_values(rates, period=period, applied_price=applied_price)

    if plot_bullish:
        bullish = _build_bullish_setup(
            rates, rsi_values, period, applied_price, left, right, min_range, max_range, False
        )
        if bullish:
            return bullish

    if plot_hidden_bullish:
        hidden_bullish = _build_bullish_setup(
            rates, rsi_values, period, applied_price, left, right, min_range, max_range, True
        )
        if hidden_bullish:
            return hidden_bullish

    if plot_bearish:
        bearish = _build_bearish_setup(
            rates, rsi_values, period, applied_price, left, right, min_range, max_range, False
        )
        if bearish:
            return bearish

    if plot_hidden_bearish:
        hidden_bearish = _build_bearish_setup(
            rates, rsi_values, period, applied_price, left, right, min_range, max_range, True
        )
        if hidden_bearish:
            return hidden_bearish

    return {"signal": "WAIT", "reason": "ไม่พบ RSI Pivot Divergence"}
