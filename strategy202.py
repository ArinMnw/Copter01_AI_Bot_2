# -*- coding: utf-8 -*-
"""S202 - Kurtosis and variance-ratio confluence structural-sweep reclaim, 16.9R."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile
from strategy196 import _variance_ratio
from strategy197 import _log_returns, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "KURT_WINDOW": 84,
    "KURT_MIN": 2.00,
    "VR_HORIZON": 4,
    "VR_MAX": 0.95,
    "REGIME_MIN_ATR_BP": 0.0,
    "RETURN_QUANTILE": 0.75,
    "STRUCTURE_LOOKBACK": 44,
    "SWEEP_BUFFER_ATR": 0.02,
    "EXHAUSTION_BODY_MIN_ATR": 0.36,
    "EXHAUSTION_VOLUME_QUANTILE": 0.50,
    "RECLAIM_CLOSE_EDGE": 0.58,
    "RECLAIM_VOLUME_QUANTILE": 0.35,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.08,
    "MAX_RISK_ATR": 1.35,
    "MAX_RISK_PRICE_PCT": 0.34,
    "TP_RR": 16.90,
    "BE_RR": 0.55,
    "CANCEL_BARS": 4,
    # Inverse regime gate (2026-07-20): S202 is a reversal setup, so it should
    # want the OPPOSITE regime to the S206 drive — trade only when recent
    # breakouts revert (mean-reverting market). 0.0 disables (validated default).
    "REGIME_LOOKBACK": 600,
    "REGIME_HORIZON": 6,
    "REGIME_FOLLOW_ATR": 1.00,
    "REGIME_ADVERSE_ATR": 1.00,
    "REGIME_MIN_EVENTS": 12,
    "RANGE_BARS": 8,
    "BREAK_BODY_MIN_FRACTION": 0.40,
    "FADE_MAX_RATE": 0.0,
    # Active-session window (BKK), 2026-07-20: cutting the quiet Asian hours
    # 00-11 removes 16 tiny BE-capped losers without touching a single winner,
    # and improves BOTH validation windows (2026-H1 +812->+834, 2025-H2
    # -47->-34) plus PF 22->53. -1/-1 disables the filter.
    "SESSION_START_HOUR": 12,
    "SESSION_END_HOUR": 23,
}


def _excess_kurtosis(returns):
    """Sample excess kurtosis of the return window."""
    count = len(returns)
    if count < 8:
        return 0.0
    mean = sum(returns) / count
    m2 = sum((value - mean) ** 2 for value in returns) / count
    if m2 <= 0.0:
        return 0.0
    m4 = sum((value - mean) ** 4 for value in returns) / count
    return m4 / (m2 * m2) - 3.0


def detect_s202(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Fade a structural sweep only in a fat-tailed anti-persistent regime."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    start_hour = int(c.get("SESSION_START_HOUR", -1))
    end_hour = int(c.get("SESSION_END_HOUR", -1))
    if start_hour >= 0 and end_hour >= 0:
        if dt_bkk is None:
            return _wait("dt_bkk missing for session filter")
        if not start_hour <= dt_bkk.hour < end_hour:
            return _wait("Outside configured session window")
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(40, int(c["KURT_WINDOW"]))
        structure_lookback = max(4, int(c["STRUCTURE_LOOKBACK"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    required = max(window + period + 4, structure_lookback + 4)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-2], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    regime_floor = float(c.get("REGIME_MIN_ATR_BP", 0.0))
    if regime_floor > 0.0:
        reference_price = float(bars[-1]["close"])
        if (reference_price <= 0.0
                or atr / reference_price * 10000.0 < regime_floor):
            return _wait("Volatility regime below floor")

    history = bars[-window - 2:-2]
    returns = _log_returns(history)
    if not returns:
        return _wait("Invalid return history")
    kurtosis = _excess_kurtosis(returns)
    if kurtosis < float(c["KURT_MIN"]):
        return _wait(f"Return tails are not fat (kurt={kurtosis:.2f})")
    variance_ratio = _variance_ratio(returns, max(2, int(c["VR_HORIZON"])))
    if variance_ratio <= 0.0 or variance_ratio > float(c["VR_MAX"]):
        return _wait(f"Regime is not anti-persistent (VR={variance_ratio:.2f})")
    fade_ceiling = float(c.get("FADE_MAX_RATE", 0.0))
    if fade_ceiling > 0.0:
        from strategy218 import _continuation_rate
        cont_rate, cont_events = _continuation_rate(bars, atr, c)
        if cont_rate is None or cont_events < int(c["REGIME_MIN_EVENTS"]):
            return _wait(f"Not enough regime evidence (events={cont_events})")
        if cont_rate > fade_ceiling:
            return _wait(f"Market is not mean-reverting (cont-rate={cont_rate:.2f})")
    return_floor = _quantile([abs(value) for value in returns], c["RETURN_QUANTILE"])

    exhaustion = bars[-2]
    reclaim = bars[-1]
    previous_close = history[-1]["close"]
    if previous_close <= 0.0 or exhaustion["close"] <= 0.0:
        return _wait("Non-positive price")
    shock_return = math.log(exhaustion["close"] / previous_close)
    if abs(shock_return) < return_floor:
        return _wait("Exhaustion return is not locally extreme")
    exhaustion_body = exhaustion["close"] - exhaustion["open"]
    exhaustion_range = exhaustion["high"] - exhaustion["low"]
    if (exhaustion_range <= 0.0
            or abs(exhaustion_body) < atr * float(c["EXHAUSTION_BODY_MIN_ATR"])):
        return _wait("Fat-tail shock lacks directional body")
    side = 1 if exhaustion_body < 0.0 else -1
    if side * shock_return >= 0.0:
        return _wait("Shock return and reversal side disagree")
    volume_floor = _quantile(
        [bar["tick_volume"] for bar in history], c["EXHAUSTION_VOLUME_QUANTILE"]
    )
    if exhaustion["tick_volume"] < volume_floor:
        return _wait("Fat-tail shock lacks volume")

    structure = bars[-structure_lookback - 2:-2]
    buffer = atr * float(c["SWEEP_BUFFER_ATR"])
    if side > 0 and exhaustion["low"] >= min(bar["low"] for bar in structure) - buffer:
        return _wait("Lower shock did not sweep structure")
    if side < 0 and exhaustion["high"] <= max(bar["high"] for bar in structure) + buffer:
        return _wait("Upper shock did not sweep structure")

    reclaim_range = reclaim["high"] - reclaim["low"]
    if reclaim_range <= 0.0:
        return _wait("Reclaim range is zero")
    reclaim_location = (reclaim["close"] - reclaim["low"]) / reclaim_range
    exhaustion_midpoint = (exhaustion["open"] + exhaustion["close"]) * 0.50
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
        return _wait("Fat-tail shock lacks confirmed reclaim")

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
        return _wait(f"Kurtosis-sweep risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Kurtosis-sweep risk too large versus price ({risk_pct:.2f}%)")

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
        "pattern": f"S202 {signal} Kurt-VR Confluence Sweep {rr:g}R",
        "reason": (f"Kurtosis={kurtosis:.2f}, VR={variance_ratio:.2f}; "
                   "structural sweep reclaimed"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
