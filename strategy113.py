# -*- coding: utf-8 -*-
"""S113 — Wyckoff VSA Fractal Reversal.

Alpha:
    Detect a Wyckoff spring/upthrust at the edge of a compressed trading
    range, require abnormal tick volume (VSA stopping/effort volume), then
    wait for a one-bar micro change of character before entering.  The
    confirmation makes this deliberately different from the immediate
    liquidity-sweep entries used by S95/S112.

The detector is a pure function.  It only uses closed bars supplied in
``rates`` and has no MT5 or repository-state dependency unless the optional
ML filter is enabled.
"""

from __future__ import annotations

import math
from statistics import median


DEFAULT_CFG = {
    # Wyckoff range and compression
    "RANGE_BARS": 48,
    "RANGE_Q": 0.10,
    "RANGE_MIN_ATR": 2.5,
    "RANGE_MAX_ATR": 9.0,
    "SQUEEZE_LOOKBACK": 24,
    "SQUEEZE_RATIO_MAX": 0.90,
    # Spring / upthrust and VSA
    "SWEEP_MIN_ATR": 0.08,
    "SWEEP_MAX_ATR": 1.25,
    "WICK_MIN_RATIO": 0.35,
    "CLOSE_LOCATION_MIN": 0.62,
    "VOLUME_LOOKBACK": 30,
    "VOLUME_SPIKE_MULT": 1.35,
    "SPREAD_MIN_ATR": 0.70,
    # Confirmation / fractal context
    "MICRO_BREAK_BARS": 3,
    "CONFIRM_BODY_MIN_ATR": 0.10,
    "CONFIRM_VOLUME_MULT": 0.75,
    "HTF_FACTOR": 3,
    "HTF_CONTEXT_BARS": 12,
    "HTF_BUY_MAX_POS": 0.55,
    "HTF_SELL_MIN_POS": 0.45,
    # Risk and execution
    "ATR_PERIOD": 14,
    "SL_BUFFER_ATR": 0.20,
    "TP_RR": 1.50,
    "TP_MAX_RR": 2.00,
    "TIME_FILTER_ENABLED": True,
    # XAU order-flow windows that survived the 730-day session audit:
    # London impulse (14 BKK) and New York impulse (20 BKK).
    "TRADE_HOURS": (14, 20),
    # Optional repository ML model
    "ML_FILTER_ENABLED": False,
    "ML_SCORE_THRESHOLD": 0.55,
    "ML_SYMBOL": "XAUUSD.iux",
}


def _wait(reason):
    return {"signal": "WAIT", "reason": reason}


def _trade(direction, entry, sl, tp, reason):
    """Round to a XAU-compatible cent without rounding RR below 1:1.5."""
    entry_r, sl_r, tp_r = round(entry, 2), round(sl, 2), round(tp, 2)
    risk = entry_r - sl_r if direction == "BUY" else sl_r - entry_r
    if risk <= 0:
        return _wait("Invalid risk after price rounding")
    if direction == "BUY":
        min_tp = entry_r + 1.5 * risk
        if tp_r < min_tp:
            tp_r = math.ceil((min_tp - 1e-12) * 100.0) / 100.0
    else:
        max_tp = entry_r - 1.5 * risk
        if tp_r > max_tp:
            tp_r = math.floor((max_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": direction, "entry": entry_r,
        "sl": sl_r, "tp": tp_r, "reason": reason,
    }


def _f(bar, key):
    return float(bar[key])


def _atr(bars, period):
    if len(bars) < period + 1:
        return 0.0
    values = []
    for i in range(len(bars) - period, len(bars)):
        high, low = _f(bars[i], "high"), _f(bars[i], "low")
        prev_close = _f(bars[i - 1], "close")
        values.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return sum(values) / len(values)


def _quantile(values, q):
    ordered = sorted(float(v) for v in values)
    if not ordered:
        return 0.0
    pos = (len(ordered) - 1) * max(0.0, min(1.0, float(q)))
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    weight = pos - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def _resample(bars, factor):
    """Aggregate closed LTF bars into timestamp-aligned, completed HTF bars."""
    factor = max(1, int(factor))
    if factor == 1:
        return list(bars)

    # MT5 timestamps let us align to real timeframe boundaries.  Only groups
    # with exactly ``factor`` bars are accepted; the final live HTF bucket is
    # intentionally discarded even though its component LTF bars are closed.
    has_time = False
    if len(bars):
        try:
            bars[0]["time"]
            has_time = True
        except (KeyError, IndexError, TypeError, ValueError):
            pass
    if has_time and len(bars) >= factor + 2:
        gaps = [
            int(bars[i]["time"]) - int(bars[i - 1]["time"])
            for i in range(max(1, len(bars) - 30), len(bars))
            if int(bars[i]["time"]) > int(bars[i - 1]["time"])
        ]
        base_seconds = int(median(gaps)) if gaps else 0
        bucket_seconds = base_seconds * factor
        if bucket_seconds > 0:
            out, current, current_key, count = [], None, None, 0
            for bar in bars:
                key = int(bar["time"]) // bucket_seconds
                if key != current_key:
                    if current is not None and count == factor:
                        out.append(current)
                    current_key, count = key, 1
                    current = {
                        "open": _f(bar, "open"), "high": _f(bar, "high"),
                        "low": _f(bar, "low"), "close": _f(bar, "close"),
                    }
                else:
                    count += 1
                    current["high"] = max(current["high"], _f(bar, "high"))
                    current["low"] = min(current["low"], _f(bar, "low"))
                    current["close"] = _f(bar, "close")
            return out

    # Fallback for tests that provide dictionaries without MT5 timestamps.
    usable = len(bars) - (len(bars) % factor)
    out = []
    for start in range(0, usable, factor):
        chunk = bars[start:start + factor]
        out.append({
            "open": _f(chunk[0], "open"),
            "high": max(_f(b, "high") for b in chunk),
            "low": min(_f(b, "low") for b in chunk),
            "close": _f(chunk[-1], "close"),
        })
    return out


def _ml_allows(cfg, rates, tf, direction, entry, dt_bkk):
    if not cfg["ML_FILTER_ENABLED"]:
        return True, None
    try:
        import ml_scoring

        probability = ml_scoring.score_signal(
            cfg["ML_SYMBOL"], tf, direction, entry, dt_bkk,
            historical_rates=rates,
        )
        probability = float(probability)
    except Exception:
        # A requested safety filter must fail closed, not silently disappear.
        return False, None
    return probability >= float(cfg["ML_SCORE_THRESHOLD"]), probability


def detect_s113(rates, tf, dt_bkk, cfg):
    """Return a S113 signal dictionary using closed MT5 bars only."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    required = max(
        int(c["RANGE_BARS"]) + 3,
        int(c["VOLUME_LOOKBACK"]) + 3,
        int(c["ATR_PERIOD"]) * 3 + 3,
        int(c["HTF_FACTOR"]) * int(c["HTF_CONTEXT_BARS"]) + 3,
    )
    if rates is None or len(rates) < required:
        return _wait(f"Not enough data ({0 if rates is None else len(rates)}/{required})")
    if dt_bkk is None:
        return _wait("dt_bkk is required")
    if c["TIME_FILTER_ENABLED"] and dt_bkk.hour not in tuple(c["TRADE_HOURS"]):
        return _wait(f"Outside trade hours ({dt_bkk.hour:02d}:00 BKK)")

    atr_period = int(c["ATR_PERIOD"])
    atr = _atr(rates[:-2], atr_period)
    if atr <= 0:
        return _wait("ATR is zero")

    spring = rates[-2]
    confirm = rates[-1]
    range_bars = int(c["RANGE_BARS"])
    base = rates[-2 - range_bars:-2]
    q = float(c["RANGE_Q"])
    range_low = _quantile((_f(b, "low") for b in base), q)
    range_high = _quantile((_f(b, "high") for b in base), 1.0 - q)
    range_width = range_high - range_low
    width_atr = range_width / atr
    if not float(c["RANGE_MIN_ATR"]) <= width_atr <= float(c["RANGE_MAX_ATR"]):
        return _wait(f"No valid trading range ({width_atr:.1f} ATR)")

    squeeze_n = int(c["SQUEEZE_LOOKBACK"])
    recent_atr = _atr(base[-squeeze_n:], min(atr_period, squeeze_n - 1))
    prior_slice = rates[-2 - range_bars - squeeze_n:-2 - range_bars]
    prior_atr = _atr(prior_slice, min(atr_period, max(1, len(prior_slice) - 1)))
    if prior_atr > 0 and recent_atr > prior_atr * float(c["SQUEEZE_RATIO_MAX"]):
        return _wait("Range is not compressed")

    s_open, s_high = _f(spring, "open"), _f(spring, "high")
    s_low, s_close = _f(spring, "low"), _f(spring, "close")
    s_range = s_high - s_low
    if s_range <= 0 or s_range < atr * float(c["SPREAD_MIN_ATR"]):
        return _wait("Sweep candle spread too small")

    volume_window = rates[-2 - int(c["VOLUME_LOOKBACK"]):-2]
    normal_volume = median(max(0.0, _f(b, "tick_volume")) for b in volume_window)
    spring_volume = max(0.0, _f(spring, "tick_volume"))
    if normal_volume <= 0 or spring_volume < normal_volume * float(c["VOLUME_SPIKE_MULT"]):
        return _wait("No VSA volume spike")

    c_open, c_high = _f(confirm, "open"), _f(confirm, "high")
    c_low, c_close = _f(confirm, "low"), _f(confirm, "close")
    confirm_volume = max(0.0, _f(confirm, "tick_volume"))
    if confirm_volume < normal_volume * float(c["CONFIRM_VOLUME_MULT"]):
        return _wait("Confirmation volume too low")

    htf = _resample(rates[:-2], int(c["HTF_FACTOR"]))
    htf = htf[-int(c["HTF_CONTEXT_BARS"]):]
    if len(htf) < 3:
        return _wait("Not enough HTF context")
    htf_high = max(_f(b, "high") for b in htf)
    htf_low = min(_f(b, "low") for b in htf)
    htf_width = htf_high - htf_low
    if htf_width <= 0:
        return _wait("HTF range is zero")
    htf_pos = (s_close - htf_low) / htf_width

    micro_n = max(1, int(c["MICRO_BREAK_BARS"]))
    micro = rates[-2 - micro_n:-2]
    micro_high = max(_f(b, "high") for b in micro)
    micro_low = min(_f(b, "low") for b in micro)
    min_sweep = atr * float(c["SWEEP_MIN_ATR"])
    max_sweep = atr * float(c["SWEEP_MAX_ATR"])
    min_confirm_body = atr * float(c["CONFIRM_BODY_MIN_ATR"])
    wick_min = float(c["WICK_MIN_RATIO"])
    close_loc = float(c["CLOSE_LOCATION_MIN"])

    # BUY: spring below support, strong close back into range, then micro-CHoCH.
    sweep_depth = range_low - s_low
    lower_wick = min(s_open, s_close) - s_low
    buy_spring = (
        min_sweep <= sweep_depth <= max_sweep
        and s_close > range_low
        and lower_wick / s_range >= wick_min
        and (s_close - s_low) / s_range >= close_loc
    )
    buy_confirm = (
        c_close > c_open
        and c_close - c_open >= min_confirm_body
        and c_close > max(s_high, micro_high)
        and htf_pos <= float(c["HTF_BUY_MAX_POS"])
    )
    if buy_spring and buy_confirm:
        entry = c_close
        sl = s_low - atr * float(c["SL_BUFFER_ATR"])
        risk = entry - sl
        if risk > 0:
            min_tp = entry + risk * max(1.5, float(c["TP_RR"]))
            max_tp = entry + risk * max(1.5, float(c["TP_MAX_RR"]))
            tp = min(max(range_high, min_tp), max_tp)
            allowed, probability = _ml_allows(c, rates, tf, "BUY", entry, dt_bkk)
            if not allowed:
                suffix = "unavailable" if probability is None else f"{probability:.2f}"
                return _wait(f"Blocked by ML ({suffix})")
            reason = (
                f"Wyckoff Spring + VSA {spring_volume / normal_volume:.2f}x + "
                f"micro-CHoCH above {max(s_high, micro_high):.2f}"
            )
            return _trade("BUY", entry, sl, tp, reason)

    # SELL: upthrust above resistance, weak close back inside, then CHoCH down.
    sweep_depth = s_high - range_high
    upper_wick = s_high - max(s_open, s_close)
    sell_spring = (
        min_sweep <= sweep_depth <= max_sweep
        and s_close < range_high
        and upper_wick / s_range >= wick_min
        and (s_high - s_close) / s_range >= close_loc
    )
    sell_confirm = (
        c_close < c_open
        and c_open - c_close >= min_confirm_body
        and c_close < min(s_low, micro_low)
        and htf_pos >= float(c["HTF_SELL_MIN_POS"])
    )
    if sell_spring and sell_confirm:
        entry = c_close
        sl = s_high + atr * float(c["SL_BUFFER_ATR"])
        risk = sl - entry
        if risk > 0:
            min_tp = entry - risk * max(1.5, float(c["TP_RR"]))
            max_tp = entry - risk * max(1.5, float(c["TP_MAX_RR"]))
            tp = max(min(range_low, min_tp), max_tp)
            allowed, probability = _ml_allows(c, rates, tf, "SELL", entry, dt_bkk)
            if not allowed:
                suffix = "unavailable" if probability is None else f"{probability:.2f}"
                return _wait(f"Blocked by ML ({suffix})")
            reason = (
                f"Wyckoff Upthrust + VSA {spring_volume / normal_volume:.2f}x + "
                f"micro-CHoCH below {min(s_low, micro_low):.2f}"
            )
            return _trade("SELL", entry, sl, tp, reason)

    return _wait("No confirmed Wyckoff Spring/Upthrust + VSA setup")
