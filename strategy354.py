# -*- coding: utf-8 -*-
"""S354 - Haar finest-detail energy-compression release.

S354 measures the share of return energy held by first-level Haar details.
A falling recent share means adjacent-return noise is being suppressed and
energy is migrating to slower scales, without requiring the rare final-coarse
coherence condition used by S353.

All wavelet and path inputs precede the release candle.  Entry is next-open
market, SL is beyond the closed release extreme plus ATR, and TP is at least
7R.
"""

from __future__ import annotations

import math
import statistics

from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy353 import _is_power_of_two


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_RETURNS": 96,
    "RECENT_RETURNS": 32,
    "RECENT_FINE_ENERGY_MAX": 0.45,
    "FINE_ENERGY_DROP_MIN": 0.08,
    "PATH_EFFICIENCY_MIN": 0.22,
    "NET_MOVE_ATR_MIN": 0.55,
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
    "TP_RR": 8.0,
    "BE_RR": 0.08,
    "CANCEL_BARS": 3,
}


def _fine_energy_share(values):
    if len(values) < 8 or not _is_power_of_two(len(values)):
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    total_energy = sum(value * value for value in values)
    if total_energy <= 1e-18:
        return None
    scale = math.sqrt(2.0)
    fine_energy = sum(
        ((values[index] - values[index + 1]) / scale) ** 2
        for index in range(0, len(values), 2)
    )
    return fine_energy / total_energy


def detect_s354(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after high-frequency Haar detail energy contracts."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(32, int(c["BASELINE_RETURNS"]))
        recent_count = max(8, int(c["RECENT_RETURNS"]))
        fine_energy_max = float(c["RECENT_FINE_ENERGY_MAX"])
        fine_energy_drop_min = float(c["FINE_ENERGY_DROP_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if (
        not _is_power_of_two(recent_count)
        or baseline_count < recent_count
        or baseline_count % recent_count != 0
    ):
        return _wait(
            "Invalid config: wavelet windows must be aligned powers of two"
        )
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for value in (fine_energy_max, fine_energy_drop_min)
    ):
        return _wait("Invalid config: Haar detail-energy gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 2)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        history = bars[-baseline_count - recent_count - 2:-1]
        returns = [
            history[index]["close"] - history[index - 1]["close"]
            for index in range(1, len(history))
        ]
        baseline = returns[:baseline_count]
        recent = returns[baseline_count:]
        baseline_shares = []
        for start in range(0, baseline_count, recent_count):
            share = _fine_energy_share(
                baseline[start:start + recent_count]
            )
            if share is not None:
                baseline_shares.append(share)
        recent_share = _fine_energy_share(recent)
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
    if recent_share is None or not baseline_shares:
        return _wait("Haar detail-energy profile is unavailable")

    baseline_share = statistics.median(baseline_shares)
    energy_drop = baseline_share - recent_share
    if (
        recent_share > fine_energy_max
        or energy_drop < fine_energy_drop_min
    ):
        return _wait(
            f"No Haar detail-energy compression "
            f"({baseline_share:.3f}->{recent_share:.3f}, "
            f"drop={energy_drop:.3f})"
        )

    recent_bars = history[-recent_count - 1:]
    net_move = recent_bars[-1]["close"] - recent_bars[0]["close"]
    travelled = sum(
        abs(
            recent_bars[index]["close"]
            - recent_bars[index - 1]["close"]
        )
        for index in range(1, len(recent_bars))
    )
    if travelled <= 0.0 or abs(net_move) <= 1e-12:
        return _wait("Recent path has no directional movement")
    side = 1 if net_move > 0.0 else -1
    efficiency = abs(net_move) / travelled
    if efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Compressed path is inefficient ({efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Compressed net move is too small")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes compressed path")
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
        "pattern": f"S354 {signal} Haar Detail Compression {rr:g}R",
        "reason": (
            f"fine Haar energy {baseline_share:.4f}->"
            f"{recent_share:.4f}, drop={energy_drop:.4f}, "
            f"efficiency={efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
