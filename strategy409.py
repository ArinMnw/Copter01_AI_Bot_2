# -*- coding: utf-8 -*-
"""S409 — Opening-Gap Response-Correlation Release 7R.

S409 measures whether bar-to-bar opening jumps are followed through or faded by
the same bar's open-to-close return.  It compares recent absolute gap-response
correlation with disjoint baseline blocks, requires a directional gap bias and
an efficient price path, then waits for a participated fully closed event.
Market fills occur next-open with an event-extreme ATR stop and >=7R target.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "CORR_ABS_MIN": 0.15,
    "CORR_RATIO_MIN": 1.20,
    "CORR_RISE_MIN": 0.05,
    "GAP_BIAS_FRACTION_MIN": 0.08,
    "PATH_EFFICIENCY_MIN": 0.12,
    "NET_MOVE_ATR_MIN": 0.35,
    "REQUIRE_PATH_ALIGNMENT": True,
    "FOLLOW_THROUGH": True,
    "EVENT_VOLUME_RATIO_MIN": 1.00,
    "EVENT_BODY_ATR_MIN": 0.45,
    "EVENT_RANGE_ATR_MIN": 0.65,
    "EVENT_BODY_FRACTION_MIN": 0.60,
    "EVENT_CLOSE_FRACTION": 0.72,
    "SESSION_START_HOUR": 7,
    "SESSION_END_HOUR": 15,
    "SL_BUFFER_ATR": 0.18,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 8.25,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _pearson(left, right):
    if len(left) != len(right) or len(left) < 8:
        return None
    mean_left = statistics.fmean(left)
    mean_right = statistics.fmean(right)
    centered_left = [value - mean_left for value in left]
    centered_right = [value - mean_right for value in right]
    sum_left = sum(value * value for value in centered_left)
    sum_right = sum(value * value for value in centered_right)
    if sum_left <= 0.0 or sum_right <= 0.0:
        return None
    covariance = sum(a * b for a, b in zip(centered_left, centered_right))
    return covariance / math.sqrt(sum_left * sum_right)


def _response_metrics(bars):
    if len(bars) < 9:
        return None
    gaps = []
    intrabars = []
    for index in range(1, len(bars)):
        previous_close = bars[index - 1]["close"]
        bar = bars[index]
        if min(previous_close, bar["open"], bar["close"]) <= 0.0:
            return None
        gaps.append(math.log(bar["open"] / previous_close))
        intrabars.append(math.log(bar["close"] / bar["open"]))
    correlation = _pearson(gaps, intrabars)
    absolute_gap = sum(abs(value) for value in gaps)
    if correlation is None or absolute_gap <= 0.0:
        return None
    return {
        "correlation": correlation,
        "gap_bias": sum(gaps) / absolute_gap,
        "gap_energy": sum(value * value for value in gaps),
    }


def detect_s409(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S409 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        corr_min = float(c["CORR_ABS_MIN"])
        ratio_min = float(c["CORR_RATIO_MIN"])
        rise_min = float(c["CORR_RISE_MIN"])
        bias_min = float(c["GAP_BIAS_FRACTION_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: response windows are inconsistent")
    gates = (corr_min, ratio_min, rise_min, bias_min, path_min, net_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: response gates are invalid")
    required = max(period + 3, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates[-required:])
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        segment_count = baseline_count // recent_count
        baseline = baseline[-segment_count * recent_count:]
        baseline_metrics = [
            _response_metrics(baseline[index:index + recent_count])
            for index in range(0, len(baseline), recent_count)
        ]
        recent_metrics = _response_metrics(recent)
        if recent_metrics is None or any(item is None for item in baseline_metrics):
            return _wait("Gap-response correlation is unavailable")
        baseline_abs_corr = statistics.median(
            abs(item["correlation"]) for item in baseline_metrics
        )
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is unavailable")
    correlation = recent_metrics["correlation"]
    absolute_corr = abs(correlation)
    ratio = absolute_corr / max(baseline_abs_corr, 1e-9)
    rise = absolute_corr - baseline_abs_corr
    if absolute_corr < corr_min:
        return _wait(f"Gap-response correlation is weak ({absolute_corr:.3f})")
    if ratio < ratio_min:
        return _wait(f"Correlation ratio is weak ({ratio:.3f})")
    if rise < rise_min:
        return _wait(f"Correlation rise is weak ({rise:.3f})")
    follow_through = bool(c["FOLLOW_THROUGH"])
    if follow_through and correlation <= 0.0:
        return _wait("Gap response is not follow-through")
    if not follow_through and correlation >= 0.0:
        return _wait("Gap response is not fading")
    gap_bias = recent_metrics["gap_bias"]
    if abs(gap_bias) < bias_min:
        return _wait(f"Directional gap bias is weak ({gap_bias:.3f})")
    gap_side = 1 if gap_bias > 0.0 else -1
    trade_side = gap_side if follow_through else -gap_side

    returns = [recent[index]["close"] - recent[index - 1]["close"]
               for index in range(1, len(recent))]
    travelled = sum(abs(value) for value in returns)
    net_move = recent[-1]["close"] - recent[0]["close"]
    if travelled <= 0.0 or net_move == 0.0:
        return _wait("Recent path is unavailable")
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Response path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_min:
        return _wait("Response move is too small versus ATR")
    if bool(c["REQUIRE_PATH_ALIGNMENT"]) and trade_side * net_move <= 0.0:
        return _wait("Price path disagrees with inferred gap response")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0 or trade_side * body <= 0.0:
        return _wait("Event direction does not confirm gap response")
    median_volume = statistics.median(float(bar["tick_volume"]) for bar in recent)
    if median_volume <= 0.0:
        return _wait("Recent volume is unavailable")
    volume_ratio = event["tick_volume"] / median_volume
    if volume_ratio < float(c["EVENT_VOLUME_RATIO_MIN"]):
        return _wait(f"Event participation is weak ({volume_ratio:.3f}x)")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Event body is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Event range is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Event lacks directional body control")
    location = ((event["close"] - event["low"]) / candle_range
                if trade_side > 0 else (event["high"] - event["close"]) / candle_range)
    if location < float(c["EVENT_CLOSE_FRACTION"]):
        return _wait(f"Event close lacks directional control ({location:.3f})")

    signal = "BUY" if trade_side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(event["close"], 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if trade_side > 0:
        sl = math.floor((event["low"] - sl_buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + sl_buffer - 1e-12) * 100.0) / 100.0
    risk = trade_side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Event risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Event risk too large versus price")
    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + trade_side * rr * risk
    tp = (math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
          if trade_side > 0 else math.floor((raw_tp + 1e-12) * 100.0) / 100.0)
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": (
            f"S409 {signal} Gap-Response "
            f"{'Follow-Through' if follow_through else 'Fade'} {rr:g}R"
        ),
        "reason": (
            f"corr={correlation:.4f}, baseline_abs={baseline_abs_corr:.4f}, "
            f"ratio={ratio:.3f}, rise={rise:.3f}, bias={gap_bias:.3f}, "
            f"path={path_efficiency:.3f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
