# -*- coding: utf-8 -*-
"""S407 — Corwin–Schultz Implied-Spread Expansion 7R.

The Corwin–Schultz estimator extracts an implied transaction-cost shock from
paired high/low observations.  S407 compares the recent upper-tail estimate
with disjoint baseline blocks, requires an efficient directional excursion,
then enters only after a fully closed participated candle confirms that move.
The market order fills next-open, uses the event extreme plus ATR for its stop,
and targets at least 7R without inspecting any future candle.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "SPREAD_QUANTILE": 0.70,
    "SPREAD_RATIO_MIN": 1.20,
    "SPREAD_RISE_MIN": 0.00002,
    "POSITIVE_PAIR_FRACTION_MIN": 0.08,
    "PATH_EFFICIENCY_MIN": 0.12,
    "NET_MOVE_ATR_MIN": 0.35,
    "EVENT_VOLUME_RATIO_MIN": 1.00,
    "EVENT_BODY_ATR_MIN": 0.45,
    "EVENT_RANGE_ATR_MIN": 0.65,
    "EVENT_BODY_FRACTION_MIN": 0.58,
    "EVENT_CLOSE_FRACTION": 0.68,
    "REQUIRE_RANGE_REENTRY": False,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.18,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "FADE_EXCURSION": False,
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _linear_quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _pair_spread(first, second):
    """Return the non-negative Corwin–Schultz spread estimate for two bars."""
    highs = (first["high"], second["high"])
    lows = (first["low"], second["low"])
    if min(*highs, *lows) <= 0.0:
        raise ValueError("non-positive price in spread estimator")
    beta = sum(math.log(high / low) ** 2 for high, low in zip(highs, lows))
    high_two = max(highs)
    low_two = min(lows)
    gamma = math.log(high_two / low_two) ** 2
    denominator = 3.0 - 2.0 * math.sqrt(2.0)
    alpha = (
        (math.sqrt(2.0 * beta) - math.sqrt(beta)) / denominator
        - math.sqrt(gamma / denominator)
    )
    alpha = max(0.0, min(alpha, 20.0))
    exp_alpha = math.exp(alpha)
    return 2.0 * (exp_alpha - 1.0) / (1.0 + exp_alpha)


def _spread_metrics(bars, quantile):
    if len(bars) < 9:
        return None
    values = [_pair_spread(bars[index - 1], bars[index])
              for index in range(1, len(bars))]
    positives = sum(value > 0.0 for value in values)
    return {
        "score": _linear_quantile(values, quantile),
        "mean": statistics.fmean(values),
        "positive_fraction": positives / len(values),
    }


def detect_s407(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S407 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        quantile = float(c["SPREAD_QUANTILE"])
        ratio_min = float(c["SPREAD_RATIO_MIN"])
        rise_min = float(c["SPREAD_RISE_MIN"])
        positive_min = float(c["POSITIVE_PAIR_FRACTION_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_move_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: spread windows are inconsistent")
    if not 0.50 <= quantile <= 0.95:
        return _wait("Invalid config: spread quantile is invalid")
    gates = (ratio_min, rise_min, positive_min, path_min, net_move_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: spread gates are invalid")
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
            _spread_metrics(baseline[index:index + recent_count], quantile)
            for index in range(0, len(baseline), recent_count)
        ]
        recent_metrics = _spread_metrics(recent, quantile)
        if recent_metrics is None or any(item is None for item in baseline_metrics):
            return _wait("Corwin-Schultz spread is unavailable")
        baseline_score = statistics.median(item["score"] for item in baseline_metrics)
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is unavailable")
    spread_score = recent_metrics["score"]
    if spread_score <= 0.0:
        return _wait("Recent implied spread has no positive shock")
    spread_ratio = spread_score / max(baseline_score, 1e-9)
    spread_rise = spread_score - baseline_score
    if spread_ratio < ratio_min:
        return _wait(f"Implied-spread ratio is weak ({spread_ratio:.3f})")
    if spread_rise < rise_min:
        return _wait(f"Implied-spread rise is weak ({spread_rise:.6f})")
    if recent_metrics["positive_fraction"] < positive_min:
        return _wait("Implied-spread shock is too isolated")

    returns = [recent[index]["close"] - recent[index - 1]["close"]
               for index in range(1, len(recent))]
    travelled = sum(abs(value) for value in returns)
    net_move = recent[-1]["close"] - recent[0]["close"]
    if travelled <= 0.0 or net_move == 0.0:
        return _wait("Recent excursion is unavailable")
    excursion_side = 1 if net_move > 0.0 else -1
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Excursion path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_move_min:
        return _wait("Excursion is too small versus ATR")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0:
        return _wait("Rejection candle is invalid")
    event_side = 1 if body > 0.0 else -1
    trade_side = -excursion_side if bool(c["FADE_EXCURSION"]) else excursion_side
    if event_side != trade_side:
        return _wait("Event direction does not confirm spread-shock setup")
    if bool(c["REQUIRE_RANGE_REENTRY"]):
        prior_high = max(bar["high"] for bar in recent)
        prior_low = min(bar["low"] for bar in recent)
        if excursion_side > 0 and event["high"] <= prior_high:
            return _wait("Upside excursion did not sweep the recent range")
        if excursion_side > 0 and event["close"] >= prior_high:
            return _wait("Upside sweep did not close back inside")
        if excursion_side < 0 and event["low"] >= prior_low:
            return _wait("Downside excursion did not sweep the recent range")
        if excursion_side < 0 and event["close"] <= prior_low:
            return _wait("Downside sweep did not close back inside")
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
        return _wait("Event lacks rejection-body control")
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
            f"S407 {signal} Corwin-Schultz Spread "
            f"{'Shock Reversal' if bool(c['FADE_EXCURSION']) else 'Expansion'} {rr:g}R"
        ),
        "reason": (
            f"spread={spread_score:.6f}, baseline={baseline_score:.6f}, "
            f"ratio={spread_ratio:.3f}, rise={spread_rise:.6f}, "
            f"positive={recent_metrics['positive_fraction']:.3f}, "
            f"path={path_efficiency:.3f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
