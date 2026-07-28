# -*- coding: utf-8 -*-
"""S115 — Structural Failed-to-Return (FTR) Imbalance Continuation.

Alpha thesis
------------
A high-volume displacement closes through a previously confirmed swing and
leaves a three-candle fair-value gap (FVG).  Price then attempts to retrace,
but low counter-flow volume cannot penetrate deeply into the gap.  The first
closed candle that resumes beyond the post-displacement high/low confirms a
failed-to-return setup.  A limit is placed just inside the imbalance rather
than assuming execution at the signal close.

This is deliberately different from S114: S114 requires high-effort
counter-trend absorption, while S115 requires weak, contracting counter-flow
after a structural BOS.  The detector is pure and uses only the closed bars
provided by the caller.  Limit spread checks and same-bar SL-first evaluation
belong to the replay/execution engine, as required by the repository contract.
"""

from __future__ import annotations

import math
from statistics import median


DEFAULT_CFG = {
    # Confirmed structure before displacement
    "ATR_PERIOD": 14,
    "SWING_LEFT": 3,
    "SWING_RIGHT": 3,
    "STRUCTURE_SCAN_BARS": 90,
    # BOS + institutional displacement
    "BOS_BODY_ATR": 1.20,
    "BOS_CLOSE_BEYOND_ATR": 0.12,
    "BOS_VOLUME_MULT": 1.25,
    "BOS_MIN_CLV": 0.55,
    "VOLUME_LOOKBACK": 30,
    # Three-candle imbalance
    "FVG_MIN_ATR": 0.15,
    "FVG_MAX_ATR": 1.80,
    # Failed-to-return window after the FVG is formed
    "FTR_MIN_BARS": 1,
    "FTR_MAX_BARS": 4,
    "FTR_TOUCH_TOL_ATR": 0.18,
    "FTR_MAX_GAP_PENETRATION": 0.35,
    "FTR_MAX_VOLUME_VS_BOS": 0.75,
    "FTR_MAX_RANGE_ATR": 1.20,
    # First closed continuation candle
    "CONFIRM_BODY_ATR": 0.22,
    "CONFIRM_BREAK_ATR": 0.05,
    "CONFIRM_MIN_CLV": 0.45,
    "CONFIRM_VOLUME_MULT": 0.85,
    # Limit entry and LTS risk controls
    "ENTRY_GAP_DEPTH": 0.20,
    "SL_BUFFER_ATR": 0.30,
    "MAX_RISK_ATR": 2.50,
    "TP_RR": 2.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 5,
    # Liquid XAUUSD hours in Bangkok time
    "TIME_FILTER_ENABLED": True,
    "TRADE_HOURS": (14, 15, 16, 17, 20, 21, 22),
    # Optional repository model (off for leakage-safe baseline research)
    "ML_FILTER_ENABLED": False,
    "ML_SCORE_THRESHOLD": 0.55,
    "ML_SYMBOL": "XAUUSD.iux",
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite numeric value")
    return number


def _normalise_rates(rates):
    """Return validated chronological OHLCV copies of MT5 rate records."""
    bars = []
    previous_time = None
    for raw in rates:
        timestamp = int(_finite(raw["time"]))
        if previous_time is not None and timestamp <= previous_time:
            raise ValueError("rates must have strictly increasing timestamps")
        previous_time = timestamp
        bar = {
            "time": timestamp,
            "open": _finite(raw["open"]),
            "high": _finite(raw["high"]),
            "low": _finite(raw["low"]),
            "close": _finite(raw["close"]),
            "tick_volume": max(0.0, _finite(raw["tick_volume"])),
        }
        if bar["high"] < max(bar["open"], bar["close"], bar["low"]):
            raise ValueError("high is below another OHLC value")
        if bar["low"] > min(bar["open"], bar["close"], bar["high"]):
            raise ValueError("low is above another OHLC value")
        bars.append(bar)
    return bars


def _atr(bars, period):
    if period < 1 or len(bars) < period + 1:
        return 0.0
    true_ranges = []
    for index in range(len(bars) - period, len(bars)):
        bar = bars[index]
        previous_close = bars[index - 1]["close"]
        true_ranges.append(max(
            bar["high"] - bar["low"],
            abs(bar["high"] - previous_close),
            abs(bar["low"] - previous_close),
        ))
    return sum(true_ranges) / len(true_ranges)


def _clv(bar):
    """Close-location value: an OHLC/tick-volume order-flow proxy."""
    spread = bar["high"] - bar["low"]
    if spread <= 0.0:
        return 0.0
    value = (2.0 * bar["close"] - bar["high"] - bar["low"]) / spread
    return max(-1.0, min(1.0, value))


def _confirmed_swings(bars, left, right, scan_bars):
    """Find pivots whose right-hand confirmation bars already existed."""
    highs, lows = [], []
    start = max(left, len(bars) - scan_bars)
    stop = len(bars) - right
    for index in range(start, stop):
        high, low = bars[index]["high"], bars[index]["low"]
        neighbours = range(index - left, index + right + 1)
        if all(bars[j]["high"] < high for j in neighbours if j != index):
            highs.append((index, high))
        if all(bars[j]["low"] > low for j in neighbours if j != index):
            lows.append((index, low))
    return highs, lows


def _ml_allows(cfg, rates, tf, direction, entry, dt_bkk):
    if not bool(cfg["ML_FILTER_ENABLED"]):
        return True, None
    try:
        import ml_scoring

        probability = float(ml_scoring.score_signal(
            cfg["ML_SYMBOL"], tf, direction, entry, dt_bkk,
            historical_rates=rates,
        ))
    except Exception:
        # An explicitly enabled filter is a safety gate and therefore fails closed.
        return False, None
    return probability >= float(cfg["ML_SCORE_THRESHOLD"]), probability


def _trade(direction, entry, sl, cfg, reason):
    """Create the complete LTS payload without losing minimum RR to rounding."""
    entry_r, sl_r = round(entry, 2), round(sl, 2)
    risk = entry_r - sl_r if direction == "BUY" else sl_r - entry_r
    if risk <= 0.0:
        return _wait("Invalid risk after price rounding")

    rr = max(1.5, float(cfg["TP_RR"]))
    raw_tp = entry_r + rr * risk if direction == "BUY" else entry_r - rr * risk
    if direction == "BUY":
        tp_r = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    else:
        tp_r = math.floor((raw_tp + 1e-12) * 100.0) / 100.0

    tag = "Bull FTR" if direction == "BUY" else "Bear FTR"
    return {
        "signal": direction,
        "entry": entry_r,
        "sl": sl_r,
        "tp": tp_r,
        "order_type": "limit",
        "pattern": f"S115 {tag}",
        "reason": reason,
        "be_rr": float(cfg["BE_RR"]) if cfg["BE_RR"] is not None else None,
        "cancel_bars": (int(cfg["CANCEL_BARS"])
                        if cfg["CANCEL_BARS"] is not None else None),
    }


def _candidate(bars, ftr_count, cfg):
    """Evaluate one BOS -> FVG -> FTR -> confirmation chronology."""
    bos_index = len(bars) - ftr_count - 3
    if bos_index < 2:
        return None
    before_bos = bars[:bos_index]
    atr = _atr(before_bos, int(cfg["ATR_PERIOD"]))
    if atr <= 0.0:
        return None

    pre = bars[bos_index - 1]
    bos = bars[bos_index]
    post = bars[bos_index + 1]
    ftr_bars = bars[bos_index + 2:-1]
    confirm = bars[-1]
    if len(ftr_bars) != ftr_count:
        return None

    highs, lows = _confirmed_swings(
        before_bos,
        int(cfg["SWING_LEFT"]),
        int(cfg["SWING_RIGHT"]),
        int(cfg["STRUCTURE_SCAN_BARS"]),
    )
    if not highs or not lows:
        return None

    volume_window = before_bos[-int(cfg["VOLUME_LOOKBACK"]):]
    baseline_volume = median(bar["tick_volume"] for bar in volume_window)
    if baseline_volume <= 0.0:
        return None
    bos_body = bos["close"] - bos["open"]
    if abs(bos_body) < atr * float(cfg["BOS_BODY_ATR"]):
        return None
    bos_volume_ratio = bos["tick_volume"] / baseline_volume
    if bos_volume_ratio < float(cfg["BOS_VOLUME_MULT"]):
        return None

    direction = 1 if bos_body > 0.0 else -1
    if direction * _clv(bos) < float(cfg["BOS_MIN_CLV"]):
        return None
    beyond = atr * float(cfg["BOS_CLOSE_BEYOND_ATR"])
    if direction > 0:
        structure_level = highs[-1][1]
        if not (pre["close"] <= structure_level
                and bos["close"] >= structure_level + beyond):
            return None
        distal, proximal = pre["high"], post["low"]
    else:
        structure_level = lows[-1][1]
        if not (pre["close"] >= structure_level
                and bos["close"] <= structure_level - beyond):
            return None
        distal, proximal = pre["low"], post["high"]

    gap = proximal - distal if direction > 0 else distal - proximal
    gap_atr = gap / atr
    if not (float(cfg["FVG_MIN_ATR"]) <= gap_atr
            <= float(cfg["FVG_MAX_ATR"])):
        return None

    # The attempted return must approach the proximal edge, stay shallow,
    # close outside the FVG, and do so on contracting counter-flow volume.
    touch_tolerance = atr * float(cfg["FTR_TOUCH_TOL_ATR"])
    penetration = gap * float(cfg["FTR_MAX_GAP_PENETRATION"])
    max_ftr_range = atr * float(cfg["FTR_MAX_RANGE_ATR"])
    if any(bar["high"] - bar["low"] > max_ftr_range for bar in ftr_bars):
        return None

    if direction > 0:
        if min(bar["low"] for bar in ftr_bars) > proximal + touch_tolerance:
            return None
        if min(bar["low"] for bar in ftr_bars) < proximal - penetration:
            return None
        if any(bar["close"] <= proximal for bar in ftr_bars):
            return None
    else:
        if max(bar["high"] for bar in ftr_bars) < proximal - touch_tolerance:
            return None
        if max(bar["high"] for bar in ftr_bars) > proximal + penetration:
            return None
        if any(bar["close"] >= proximal for bar in ftr_bars):
            return None

    ftr_volume = median(bar["tick_volume"] for bar in ftr_bars)
    contraction = ftr_volume / bos["tick_volume"]
    if contraction > float(cfg["FTR_MAX_VOLUME_VS_BOS"]):
        return None

    confirm_body = confirm["close"] - confirm["open"]
    if direction * confirm_body < atr * float(cfg["CONFIRM_BODY_ATR"]):
        return None
    if direction * _clv(confirm) < float(cfg["CONFIRM_MIN_CLV"]):
        return None
    if confirm["tick_volume"] < baseline_volume * float(cfg["CONFIRM_VOLUME_MULT"]):
        return None

    # First closed recapture only: prevents repeated signals on later trend bars.
    break_buffer = atr * float(cfg["CONFIRM_BREAK_ATR"])
    trigger = post["high"] if direction > 0 else post["low"]
    if direction > 0:
        if not (bars[-2]["close"] <= trigger
                and confirm["close"] >= trigger + break_buffer):
            return None
    else:
        if not (bars[-2]["close"] >= trigger
                and confirm["close"] <= trigger - break_buffer):
            return None

    return {
        "direction": "BUY" if direction > 0 else "SELL",
        "atr": atr,
        "distal": distal,
        "proximal": proximal,
        "gap": gap,
        "structure_level": structure_level,
        "bos_volume_ratio": bos_volume_ratio,
        "contraction": contraction,
        "ftr_count": ftr_count,
    }


def _validate_cfg(cfg):
    """Validate window relationships that could otherwise create ambiguity."""
    integer_keys = (
        "ATR_PERIOD", "SWING_LEFT", "SWING_RIGHT", "STRUCTURE_SCAN_BARS",
        "VOLUME_LOOKBACK", "FTR_MIN_BARS", "FTR_MAX_BARS",
    )
    values = {}
    for key in integer_keys:
        raw = _finite(cfg[key])
        value = int(raw)
        if raw != value:
            raise ValueError(f"{key} must be an integer")
        values[key] = value
    if any(value < 1 for value in values.values()):
        raise ValueError("cfg windows must be positive integers")
    if values["FTR_MAX_BARS"] < values["FTR_MIN_BARS"]:
        raise ValueError("FTR_MAX_BARS must be >= FTR_MIN_BARS")

    numeric_keys = (
        "BOS_BODY_ATR", "BOS_CLOSE_BEYOND_ATR", "BOS_VOLUME_MULT",
        "BOS_MIN_CLV", "FVG_MIN_ATR", "FVG_MAX_ATR",
        "FTR_TOUCH_TOL_ATR", "FTR_MAX_GAP_PENETRATION",
        "FTR_MAX_VOLUME_VS_BOS", "FTR_MAX_RANGE_ATR",
        "CONFIRM_BODY_ATR", "CONFIRM_BREAK_ATR", "CONFIRM_MIN_CLV",
        "CONFIRM_VOLUME_MULT", "ENTRY_GAP_DEPTH", "SL_BUFFER_ATR",
        "MAX_RISK_ATR", "TP_RR", "ML_SCORE_THRESHOLD",
    )
    numbers = {key: _finite(cfg[key]) for key in numeric_keys}
    if any(value < 0.0 for value in numbers.values()):
        raise ValueError("numeric cfg values cannot be negative")
    positive_keys = (
        "BOS_BODY_ATR", "BOS_VOLUME_MULT", "FVG_MAX_ATR",
        "FTR_MAX_VOLUME_VS_BOS", "FTR_MAX_RANGE_ATR",
        "CONFIRM_VOLUME_MULT", "MAX_RISK_ATR", "TP_RR",
    )
    if any(numbers[key] <= 0.0 for key in positive_keys):
        raise ValueError("scale and risk cfg values must be positive")
    if numbers["FVG_MIN_ATR"] > numbers["FVG_MAX_ATR"]:
        raise ValueError("FVG_MIN_ATR must be <= FVG_MAX_ATR")
    unit_interval = ("FTR_MAX_GAP_PENETRATION", "ENTRY_GAP_DEPTH")
    if any(not 0.0 <= numbers[key] <= 1.0 for key in unit_interval):
        raise ValueError("gap fractions must be between 0 and 1")
    probability_keys = ("BOS_MIN_CLV", "CONFIRM_MIN_CLV", "ML_SCORE_THRESHOLD")
    if any(not 0.0 <= numbers[key] <= 1.0 for key in probability_keys):
        raise ValueError("CLV and probability thresholds must be between 0 and 1")
    if cfg["BE_RR"] is not None and _finite(cfg["BE_RR"]) <= 0.0:
        raise ValueError("BE_RR must be positive or None")
    if cfg["CANCEL_BARS"] is not None:
        cancel_raw = _finite(cfg["CANCEL_BARS"])
        if cancel_raw != int(cancel_raw) or int(cancel_raw) < 1:
            raise ValueError("CANCEL_BARS must be a positive integer or None")
    hours = tuple(cfg["TRADE_HOURS"])
    if any(int(hour) != hour or not 0 <= int(hour) <= 23 for hour in hours):
        raise ValueError("TRADE_HOURS must contain integer hours from 0 to 23")
    return values


def detect_s115(rates, tf, dt_bkk, cfg):
    """Return an S115 signal from chronological, fully closed MT5 bars."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        windows = _validate_cfg(c)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid cfg: {exc}")

    required = max(
        windows["STRUCTURE_SCAN_BARS"] + windows["SWING_RIGHT"] + 3,
        windows["ATR_PERIOD"] + windows["FTR_MAX_BARS"] + 4,
        windows["VOLUME_LOOKBACK"] + windows["FTR_MAX_BARS"] + 4,
    )
    if rates is None or len(rates) < required:
        return _wait(f"Not enough data ({0 if rates is None else len(rates)}/{required})")
    if dt_bkk is None:
        return _wait("dt_bkk is required")
    try:
        if bool(c["TIME_FILTER_ENABLED"]) and dt_bkk.hour not in tuple(c["TRADE_HOURS"]):
            return _wait(f"Outside trade hours ({dt_bkk.hour:02d}:00 BKK)")
        bars = _normalise_rates(rates)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid input: {exc}")

    setup = None
    try:
        for ftr_count in range(windows["FTR_MIN_BARS"], windows["FTR_MAX_BARS"] + 1):
            setup = _candidate(bars, ftr_count, c)
            if setup is not None:
                break
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
        return _wait(f"Invalid cfg: {exc}")
    if setup is None:
        return _wait("No confirmed BOS + FVG failed-to-return setup")

    direction = setup["direction"]
    atr = setup["atr"]
    depth = float(c["ENTRY_GAP_DEPTH"])
    if direction == "BUY":
        entry = setup["proximal"] - setup["gap"] * depth
        sl = setup["distal"] - atr * float(c["SL_BUFFER_ATR"])
        if entry >= bars[-1]["close"]:
            return _wait("BUY limit is not below confirmation close")
        risk = entry - sl
    else:
        entry = setup["proximal"] + setup["gap"] * depth
        sl = setup["distal"] + atr * float(c["SL_BUFFER_ATR"])
        if entry <= bars[-1]["close"]:
            return _wait("SELL limit is not above confirmation close")
        risk = sl - entry
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Risk outside allowed range ({risk / atr:.2f} ATR)")

    allowed, probability = _ml_allows(c, rates, tf, direction, entry, dt_bkk)
    if not allowed:
        suffix = "unavailable" if probability is None else f"{probability:.2f}"
        return _wait(f"Blocked by ML ({suffix})")

    reason = (
        f"{direction} BOS through {setup['structure_level']:.2f}; "
        f"FVG={setup['gap'] / atr:.2f}ATR, BOS volume={setup['bos_volume_ratio']:.2f}x; "
        f"{setup['ftr_count']}-bar FTR volume contracted to "
        f"{setup['contraction']:.2f}x before first closed continuation"
    )
    return _trade(direction, entry, sl, c, reason)
