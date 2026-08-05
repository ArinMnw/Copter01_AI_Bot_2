# -*- coding: utf-8 -*-
"""S406 — Asian Garman–Klass Compression Release 7R.

Garman–Klass volatility combines each closed candle's high/low range and
open/close displacement.  S406 requires its recent median to contract below
disjoint baseline blocks, then trades a participated close breakout during the
underrepresented Asian/pre-London portfolio window.  Orders fill next-open,
use the release-candle extreme plus ATR for the stop, and target at least 7R.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "COMPRESSION_RATIO_MAX": 0.85,
    "COMPRESSION_DROP_ATR_MIN": 0.02,
    "RELEASE_RANGE_RATIO_MIN": 1.45,
    "EVENT_VOLUME_RATIO_MIN": 1.05,
    "EVENT_BODY_ATR_MIN": 0.55,
    "EVENT_RANGE_ATR_MIN": 0.70,
    "EVENT_BODY_FRACTION_MIN": 0.65,
    "EVENT_CLOSE_FRACTION": 0.72,
    "REQUIRE_CLOSE_BREAK": True,
    "SESSION_START_HOUR": 6,
    "SESSION_END_HOUR": 15,
    "SL_BUFFER_ATR": 0.18,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "FADE_RELEASE": False,
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _gk_volatility(bar):
    high = float(bar["high"])
    low = float(bar["low"])
    open_price = float(bar["open"])
    close = float(bar["close"])
    if min(high, low, open_price, close) <= 0.0 or high < low:
        raise ValueError("invalid OHLC for Garman-Klass estimator")
    log_hl = math.log(high / low)
    log_co = math.log(close / open_price)
    variance = 0.5 * log_hl * log_hl - (2.0 * math.log(2.0) - 1.0) * log_co * log_co
    return close * math.sqrt(max(variance, 0.0))


def _block_score(bars):
    values = [_gk_volatility(bar) for bar in bars]
    return statistics.median(values)


def detect_s406(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S406 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        compression_max = float(c["COMPRESSION_RATIO_MAX"])
        drop_min = float(c["COMPRESSION_DROP_ATR_MIN"])
        release_min = float(c["RELEASE_RANGE_RATIO_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: compression windows are inconsistent")
    gates = (compression_max, drop_min, release_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: compression gates are invalid")
    required = max(period + 3, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured Asian release window")
    try:
        bars = _bars(rates[-required:])
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        segment_count = baseline_count // recent_count
        baseline = baseline[-segment_count * recent_count:]
        baseline_scores = [
            _block_score(baseline[index:index + recent_count])
            for index in range(0, len(baseline), recent_count)
        ]
        recent_score = _block_score(recent)
        baseline_score = statistics.median(baseline_scores)
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if baseline_score <= 0.0 or recent_score <= 0.0 or atr <= 0.0:
        return _wait("Garman-Klass score or ATR is unavailable")
    compression_ratio = recent_score / baseline_score
    compression_drop_atr = (baseline_score - recent_score) / atr
    if compression_ratio > compression_max:
        return _wait(f"Range volatility is not compressed ({compression_ratio:.3f})")
    if compression_drop_atr < drop_min:
        return _wait(f"Compression drop is weak ({compression_drop_atr:.3f} ATR)")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0:
        return _wait("Release candle is invalid")
    side = 1 if body > 0.0 else -1
    median_range = statistics.median(bar["high"] - bar["low"] for bar in recent)
    if median_range <= 0.0 or candle_range < median_range * release_min:
        return _wait("Release range is weak versus compression")
    if abs(body) < atr * float(c["EVENT_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["EVENT_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    if abs(body) / candle_range < float(c["EVENT_BODY_FRACTION_MIN"]):
        return _wait("Release lacks body control")
    location = (
        (event["close"] - event["low"]) / candle_range
        if side > 0 else (event["high"] - event["close"]) / candle_range
    )
    if location < float(c["EVENT_CLOSE_FRACTION"]):
        return _wait(f"Release close lacks directional control ({location:.3f})")
    median_volume = statistics.median(float(bar["tick_volume"]) for bar in recent)
    volume_ratio = event["tick_volume"] / median_volume
    if volume_ratio < float(c["EVENT_VOLUME_RATIO_MIN"]):
        return _wait(f"Release participation is weak ({volume_ratio:.3f}x)")
    if bool(c["REQUIRE_CLOSE_BREAK"]):
        close_ceiling = max(bar["close"] for bar in recent)
        close_floor = min(bar["close"] for bar in recent)
        if side > 0 and event["close"] <= close_ceiling:
            return _wait("BUY release did not break recent closes")
        if side < 0 and event["close"] >= close_floor:
            return _wait("SELL release did not break recent closes")

    trade_side = -side if bool(c["FADE_RELEASE"]) else side
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
        return _wait(f"Release risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Release risk too large versus price")
    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + trade_side * rr * risk
    tp = (
        math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
        if trade_side > 0 else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    )
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": (
            f"S406 {signal} Asian GK Compression "
            f"{'False-Break Fade' if bool(c['FADE_RELEASE']) else 'Release'} {rr:g}R"
        ),
        "reason": (
            f"gk={recent_score:.4f}, baseline={baseline_score:.4f}, "
            f"ratio={compression_ratio:.4f}, drop_atr={compression_drop_atr:.4f}, "
            f"release={candle_range / median_range:.4f}x"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
