# -*- coding: utf-8 -*-
"""S362 - Close-location entropy-compression release.

S362 converts each closed candle into a close-location value (CLV) inside its
high-low range, discretizes CLV into directional auction states, and measures
normalized Shannon entropy.  Falling state entropy with a directional mean CLV
indicates repeated same-side closing control rather than diffuse candle closes.

All CLV and path inputs precede the release candle.  Entry is next-open market,
SL is beyond the closed release extreme plus ATR, and TP is at least 7R.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 80,
    "RECENT_BARS": 20,
    "CLV_BINS": 4,
    "CLV_ENTROPY_MAX": 0.92,
    "CLV_ENTROPY_DROP_MIN": 0.11,
    "MEAN_CLV_ABS_MIN": 0.20,
    "PATH_EFFICIENCY_MIN": 0.18,
    "NET_MOVE_ATR_MIN": 0.50,
    "RELEASE_BODY_ATR_MIN": 0.72,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.80,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "TP_RR": 10.0,
    "BE_RR": 0.05,
    "CANCEL_BARS": 3,
}


def _clv_profile(bars, bin_count):
    if len(bars) < 8 or bin_count < 2:
        return None
    clvs = []
    closes = []
    for bar in bars:
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        if not all(math.isfinite(value) for value in (high, low, close)):
            return None
        candle_range = high - low
        if candle_range <= 0.0:
            continue
        clvs.append(max(-1.0, min(1.0, (2.0 * close - high - low) / candle_range)))
        closes.append(close)
    if len(clvs) < 6 or len(closes) < 2:
        return None
    counts = [0] * bin_count
    for clv in clvs:
        index = min(bin_count - 1, int((clv + 1.0) * 0.5 * bin_count))
        counts[index] += 1
    entropy = 0.0
    for count in counts:
        if count:
            probability = count / len(clvs)
            entropy -= probability * math.log(probability)
    entropy /= math.log(bin_count)
    mean_clv = sum(clvs) / len(clvs)
    net_move = closes[-1] - closes[0]
    if abs(net_move) <= 1e-12 or abs(mean_clv) <= 1e-12:
        return None
    side = 1 if mean_clv > 0.0 else -1
    if net_move * side <= 0.0:
        return None
    travelled = sum(
        abs(closes[index] - closes[index - 1])
        for index in range(1, len(closes))
    )
    if travelled <= 0.0:
        return None
    path_efficiency = abs(net_move) / travelled
    return entropy, mean_clv, side, net_move, path_efficiency


def detect_s362(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow repeated same-side CLV control after entropy compresses."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        bin_count = max(2, int(c["CLV_BINS"]))
        entropy_max = float(c["CLV_ENTROPY_MAX"])
        entropy_drop_min = float(c["CLV_ENTROPY_DROP_MIN"])
        mean_clv_min = float(c["MEAN_CLV_ABS_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (entropy_max, entropy_drop_min, mean_clv_min)
    ):
        return _wait("Invalid config: CLV entropy gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 1)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 1:-1]
        baseline = history[:baseline_count]
        recent = history[baseline_count:]
        baseline_entropies = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _clv_profile(
                baseline[start:start + recent_count],
                bin_count,
            )
            if profile is not None:
                baseline_entropies.append(profile[0])
        recent_profile = _clv_profile(recent, bin_count)
        atr = _atr(bars[:-1], period)
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        ZeroDivisionError,
        AttributeError,
        statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    if recent_profile is None or not baseline_entropies:
        return _wait("CLV entropy profile is unavailable")

    entropy, mean_clv, side, net_move, path_efficiency = recent_profile
    baseline_entropy = statistics.median(baseline_entropies)
    entropy_drop = baseline_entropy - entropy
    if entropy > entropy_max or entropy_drop < entropy_drop_min:
        return _wait(
            f"No CLV entropy compression "
            f"({baseline_entropy:.3f}->{entropy:.3f}, "
            f"drop={entropy_drop:.3f})"
        )
    if abs(mean_clv) < mean_clv_min:
        return _wait(f"Mean CLV control is weak ({mean_clv:.3f})")
    if path_efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"CLV-controlled path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("CLV-controlled net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes CLV direction")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    close_fraction = (
        (event["close"] - event["low"]) / candle_range
        if side > 0
        else (event["high"] - event["close"]) / candle_range
    )
    if close_fraction < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release lacks directional close control")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(event["close"], 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor(
            (event["low"] - sl_buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (event["high"] + sl_buffer - 1e-12) * 100.0
        ) / 100.0
    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Release risk outside range ({risk / atr:.2f} ATR)")
    if risk / entry * 100.0 > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait("Release risk too large versus price")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    tp = (
        math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
        if side > 0
        else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    )
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S362 {signal} CLV Entropy {rr:g}R",
        "reason": (
            f"CLV entropy {baseline_entropy:.4f}->{entropy:.4f}, "
            f"drop={entropy_drop:.4f}, mean_clv={mean_clv:.4f}, "
            f"path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
