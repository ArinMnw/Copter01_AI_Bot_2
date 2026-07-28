# -*- coding: utf-8 -*-
"""S181 - Range/close-variance liquidity-sweep reclaim with a 7R target."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "DISLOCATION_WINDOW": 64,
    "SWEEP_LOOKBACK": 12,
    "DISLOCATION_QUANTILE": 0.82,
    "MIN_DISLOCATION_RATIO": 1.80,
    "EXHAUSTION_RANGE_MIN_ATR": 0.90,
    "EXHAUSTION_VOLUME_QUANTILE": 0.55,
    "MIN_WICK_FRACTION": 0.32,
    "SWEEP_BUFFER_ATR": 0.02,
    "RECLAIM_CLOSE_EDGE": 0.58,
    "RECLAIM_VOLUME_QUANTILE": 0.35,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.40,
    "MAX_RISK_PRICE_PCT": 0.35,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s181(rates, tf, dt_bkk, cfg):
    """Fade a swept extreme after range variance fails to transmit to closes."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(24, int(c["DISLOCATION_WINDOW"]))
        sweep_lookback = max(4, int(c["SWEEP_LOOKBACK"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(window + 3, sweep_lookback + 4, period + 4)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-2], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    history = bars[-window - 2:-2]
    ratios = []
    for index in range(1, len(history)):
        bar = history[index]
        bar_range = bar["high"] - bar["low"]
        close_move = abs(bar["close"] - history[index - 1]["close"])
        ratios.append(bar_range / max(close_move, atr * 0.05))
    ratio_floor = max(
        float(c["MIN_DISLOCATION_RATIO"]),
        _quantile(ratios, c["DISLOCATION_QUANTILE"]),
    )

    exhaustion = bars[-2]
    reclaim = bars[-1]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    close_move = abs(exhaustion["close"] - history[-1]["close"])
    dislocation = exhaustion_range / max(close_move, atr * 0.05)
    if (exhaustion_range < atr * float(c["EXHAUSTION_RANGE_MIN_ATR"])
            or dislocation < ratio_floor):
        return _wait(
            f"Range/close variance is not dislocated ({dislocation:.2f}<{ratio_floor:.2f})"
        )
    volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < volume_floor:
        return _wait("Variance dislocation lacks participation volume")

    structure = bars[-sweep_lookback - 2:-2]
    prior_high = max(bar["high"] for bar in structure)
    prior_low = min(bar["low"] for bar in structure)
    location = (exhaustion["close"] - exhaustion["low"]) / exhaustion_range
    upper_wick = exhaustion["high"] - max(exhaustion["open"], exhaustion["close"])
    lower_wick = min(exhaustion["open"], exhaustion["close"]) - exhaustion["low"]
    wick_fraction = float(c["MIN_WICK_FRACTION"])
    sweep_buffer = atr * float(c["SWEEP_BUFFER_ATR"])
    swept_low = (exhaustion["low"] < prior_low - sweep_buffer
                 and lower_wick / exhaustion_range >= wick_fraction
                 and location >= 0.50)
    swept_high = (exhaustion["high"] > prior_high + sweep_buffer
                  and upper_wick / exhaustion_range >= wick_fraction
                  and location <= 0.50)
    if swept_low == swept_high:
        return _wait("No unambiguous wick-dominant structural sweep")
    side = 1 if swept_low else -1

    reclaim_range = reclaim["high"] - reclaim["low"]
    if reclaim_range <= 0.0:
        return _wait("Reclaim range is zero")
    reclaim_location = (reclaim["close"] - reclaim["low"]) / reclaim_range
    exhaustion_midpoint = (exhaustion["high"] + exhaustion["low"]) * 0.50
    reclaim_volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["RECLAIM_VOLUME_QUANTILE"]
    )
    edge = float(c["RECLAIM_CLOSE_EDGE"])
    if side > 0:
        confirmed = (reclaim["close"] > reclaim["open"]
                     and reclaim["close"] > exhaustion_midpoint
                     and reclaim_location >= edge)
    else:
        confirmed = (reclaim["close"] < reclaim["open"]
                     and reclaim["close"] < exhaustion_midpoint
                     and reclaim_location <= 1.0 - edge)
    if not confirmed or reclaim["tick_volume"] < reclaim_volume_floor:
        return _wait("Swept variance dislocation lacks confirmed reclaim")

    fraction = float(c["ENTRY_RANGE_FRACTION"])
    if side > 0:
        entry = reclaim["high"] - fraction * reclaim_range
        if entry >= reclaim["close"]:
            return _wait("BUY limit is not below reclaim close")
        sl = min(exhaustion["low"], reclaim["low"]) - atr * float(c["SL_BUFFER_ATR"])
        entry = round(entry, 2)
        sl = math.floor((sl + 1e-12) * 100.0) / 100.0
    else:
        entry = reclaim["low"] + fraction * reclaim_range
        if entry <= reclaim["close"]:
            return _wait("SELL limit is not above reclaim close")
        sl = max(exhaustion["high"], reclaim["high"]) + atr * float(c["SL_BUFFER_ATR"])
        entry = round(entry, 2)
        sl = math.ceil((sl - 1e-12) * 100.0) / 100.0
    risk = side * (entry - sl)
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Sweep-reclaim risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Sweep-reclaim risk too large versus price ({risk_pct:.2f}%)")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + side * rr * risk
    if side > 0:
        signal = "BUY"
        tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    else:
        signal = "SELL"
        tp = math.floor((raw_tp + 1e-12) * 100.0) / 100.0
    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S181 {signal} Range-Variance Sweep {rr:g}R",
        "reason": (f"Range/close dislocation={dislocation:.2f} versus {ratio_floor:.2f}; "
                   "wick sweep absorbed and reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
