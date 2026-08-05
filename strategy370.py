# -*- coding: utf-8 -*-
"""S370 - Garman-Klass volatility-energy concentration release.

S370 estimates range-based variance per candle with the Garman-Klass
estimator.  A normalized Herfindahl index measures whether recent volatility
energy has become concentrated in a small number of candles versus disjoint
baseline blocks.  Variance-weighted candle direction, net path, and a fully
closed release must agree before entry.

All concentration and path features precede the release candle.  Entry is
next-open market, SL is beyond the closed release extreme plus ATR, and TP is
at least 7R.
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
    "CONCENTRATION_MIN": 0.08,
    "CONCENTRATION_RATIO_MIN": 1.20,
    "DIRECTIONAL_ENERGY_MIN": 0.24,
    "PATH_EFFICIENCY_MIN": 0.22,
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
    "TP_RR": 8.0,
    "BE_RR": 0.01,
    "CANCEL_BARS": 3,
}


def _gk_concentration_profile(bars):
    if len(bars) < 8:
        return None
    energies = []
    signed_energy = 0.0
    closes = []
    body_coefficient = 2.0 * math.log(2.0) - 1.0
    for bar in bars:
        open_price = float(bar["open"])
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        if not all(
            math.isfinite(value) and value > 0.0
            for value in (open_price, high, low, close)
        ):
            return None
        log_range = math.log(high / low)
        log_body = math.log(close / open_price)
        energy = max(
            0.0,
            0.5 * log_range * log_range
            - body_coefficient * log_body * log_body,
        )
        energies.append(energy)
        if close > open_price:
            signed_energy += energy
        elif close < open_price:
            signed_energy -= energy
        closes.append(close)
    total = sum(energies)
    count = len(energies)
    if total <= 1e-18 or count < 2:
        return None
    raw_hhi = sum(value * value for value in energies) / (total * total)
    concentration = max(0.0, (count * raw_hhi - 1.0) / (count - 1.0))
    directional_energy = signed_energy / total
    net_move = closes[-1] - closes[0]
    travelled = sum(
        abs(closes[index] - closes[index - 1])
        for index in range(1, len(closes))
    )
    if (
        travelled <= 0.0
        or abs(net_move) <= 1e-12
        or abs(directional_energy) <= 1e-12
    ):
        return None
    side = 1 if directional_energy > 0.0 else -1
    if net_move * side <= 0.0:
        return None
    path_efficiency = abs(net_move) / travelled
    return (
        concentration,
        abs(directional_energy),
        side,
        net_move,
        path_efficiency,
    )


def detect_s370(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a release after GK volatility energy becomes concentrated."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(8, int(c["RECENT_BARS"]))
        concentration_min = float(c["CONCENTRATION_MIN"])
        concentration_ratio_min = float(c["CONCENTRATION_RATIO_MIN"])
        directional_energy_min = float(c["DIRECTIONAL_ENERGY_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count:
        return _wait("Invalid config: baseline shorter than recent window")
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (
            concentration_min,
            concentration_ratio_min,
            directional_energy_min,
        )
    ):
        return _wait("Invalid config: concentration gates are invalid")

    required = max(period + 5, baseline_count + recent_count + 1)
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
        baseline_concentrations = []
        for start in range(0, len(baseline) - recent_count + 1, recent_count):
            profile = _gk_concentration_profile(
                baseline[start:start + recent_count]
            )
            if profile is not None:
                baseline_concentrations.append(profile[0])
        recent_profile = _gk_concentration_profile(recent)
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
    if recent_profile is None or not baseline_concentrations:
        return _wait("GK concentration profile is unavailable")

    concentration, directional_energy, side, net_move, path_efficiency = (
        recent_profile
    )
    baseline_concentration = statistics.median(baseline_concentrations)
    if baseline_concentration <= 0.0:
        return _wait("Baseline GK concentration is zero")
    concentration_ratio = concentration / baseline_concentration
    if (
        concentration < concentration_min
        or concentration_ratio < concentration_ratio_min
    ):
        return _wait(
            f"No GK concentration expansion ({baseline_concentration:.3f}->"
            f"{concentration:.3f}, ratio={concentration_ratio:.3f})"
        )
    if directional_energy < directional_energy_min:
        return _wait(f"Directional GK energy is weak ({directional_energy:.3f})")
    if path_efficiency < float(c["PATH_EFFICIENCY_MIN"]):
        return _wait(f"Concentrated path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * float(c["NET_MOVE_ATR_MIN"]):
        return _wait("Concentrated net move is too small")

    body = float(event["close"]) - float(event["open"])
    candle_range = float(event["high"]) - float(event["low"])
    if candle_range <= 0.0 or body * side <= 0.0:
        return _wait("Release opposes GK-energy direction")
    if abs(body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if candle_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    close_fraction = (
        (float(event["close"]) - float(event["low"])) / candle_range
        if side > 0
        else (float(event["high"]) - float(event["close"])) / candle_range
    )
    if close_fraction < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release lacks directional close control")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")
    entry = round(float(event["close"]), 2)
    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor(
            (float(event["low"]) - sl_buffer + 1e-12) * 100.0
        ) / 100.0
    else:
        sl = math.ceil(
            (float(event["high"]) + sl_buffer - 1e-12) * 100.0
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
        "pattern": f"S370 {signal} GK Concentration {rr:g}R",
        "reason": (
            f"GK concentration {baseline_concentration:.4f}->"
            f"{concentration:.4f}, ratio={concentration_ratio:.4f}, "
            f"directional={directional_energy:.4f}, "
            f"path={path_efficiency:.4f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
