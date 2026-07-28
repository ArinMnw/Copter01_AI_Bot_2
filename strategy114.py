# -*- coding: utf-8 -*-
"""S114 — Effort/Result Absorption Continuation.

The detector looks for an established directional impulse followed by a
counter-trend pullback whose tick-volume effort is large but whose price
progress is small.  A closed confirmation candle must then break the final
absorption candle in the impulse direction.  Entry is a limit order inside
the absorption zone; the function never assumes a fill at the signal close.

Only bars supplied in ``rates`` are used.  They must all be closed by the
caller, which keeps this detector pure and free from look-ahead bias.
"""

from __future__ import annotations

import math
from statistics import median


DEFAULT_CFG = {
    # Baseline volatility and directional impulse
    "ATR_PERIOD": 14,
    "IMPULSE_BARS": 18,
    "MIN_IMPULSE_ATR": 2.20,
    "MIN_EFFICIENCY": 0.32,
    "MIN_DELTA_BIAS": 0.12,
    # Counter-trend pullback / absorption
    "PULLBACK_MIN_BARS": 3,
    "PULLBACK_MAX_BARS": 7,
    "PULLBACK_MIN_RETRACE": 0.18,
    "PULLBACK_MAX_RETRACE": 0.68,
    "EFFORT_VOLUME_MULT": 1.10,
    "MAX_RESULT_RATIO": 0.48,
    "ABSORPTION_VOLUME_MULT": 1.25,
    "ABSORPTION_MAX_BODY_RATIO": 0.42,
    "ABSORPTION_MIN_WICK_RATIO": 0.30,
    "ABSORPTION_CLOSE_LOCATION": 0.55,
    # Closed-bar confirmation
    "CONFIRM_BODY_ATR": 0.18,
    "CONFIRM_MIN_CLV": 0.35,
    "CONFIRM_VOLUME_MULT": 0.85,
    # Limit execution and portfolio risk
    "ENTRY_ZONE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.25,
    "MAX_RISK_ATR": 2.80,
    "TP_RR": 1.80,
    "BE_RR": 1.00,
    "CANCEL_BARS": 4,
    # Liquid XAUUSD windows in Bangkok time. Disable for broad research.
    "TIME_FILTER_ENABLED": True,
    "TRADE_HOURS": (14, 15, 16, 17, 20, 21, 22),
    # Optional repository model; disabled by default for leakage-safe tests.
    "ML_FILTER_ENABLED": False,
    "ML_SCORE_THRESHOLD": 0.55,
    "ML_SYMBOL": "XAUUSD.iux",
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def _number(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non-finite numeric value")
    return value


def _normalise_rates(rates):
    """Copy required MT5 fields into finite floats without mutating input."""
    bars = []
    for raw in rates:
        bar = {
            "open": _number(raw["open"]),
            "high": _number(raw["high"]),
            "low": _number(raw["low"]),
            "close": _number(raw["close"]),
            "tick_volume": max(0.0, _number(raw["tick_volume"])),
        }
        if bar["high"] < max(bar["open"], bar["close"], bar["low"]):
            raise ValueError("high is below OHLC value")
        if bar["low"] > min(bar["open"], bar["close"], bar["high"]):
            raise ValueError("low is above OHLC value")
        bars.append(bar)
    return bars


def _atr(bars, period):
    if period < 1 or len(bars) < period + 1:
        return 0.0
    values = []
    for i in range(len(bars) - period, len(bars)):
        high, low = bars[i]["high"], bars[i]["low"]
        previous_close = bars[i - 1]["close"]
        values.append(max(high - low, abs(high - previous_close),
                          abs(low - previous_close)))
    return sum(values) / len(values)


def _clv(bar):
    """Close-location value in [-1, 1], an OHLC order-flow proxy."""
    spread = bar["high"] - bar["low"]
    if spread <= 0.0:
        return 0.0
    value = (2.0 * bar["close"] - bar["high"] - bar["low"]) / spread
    return max(-1.0, min(1.0, value))


def _efficiency(bars):
    if len(bars) < 2:
        return 0.0
    path = sum(abs(bars[i]["close"] - bars[i - 1]["close"])
               for i in range(1, len(bars)))
    return abs(bars[-1]["close"] - bars[0]["close"]) / path if path else 0.0


def _delta_bias(bars):
    total_volume = sum(bar["tick_volume"] for bar in bars)
    if total_volume <= 0.0:
        return 0.0
    signed_volume = sum(_clv(bar) * bar["tick_volume"] for bar in bars)
    return signed_volume / total_volume


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
        # An explicitly enabled safety filter must fail closed.
        return False, None
    return probability >= float(cfg["ML_SCORE_THRESHOLD"]), probability


def _trade(direction, entry, sl, cfg, reason):
    """Build a complete LTS payload and preserve RR after cent rounding."""
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

    side_tag = "Bull" if direction == "BUY" else "Bear"
    return {
        "signal": direction,
        "entry": entry_r,
        "sl": sl_r,
        "tp": tp_r,
        "order_type": "limit",
        "pattern": f"S114 {side_tag} Absorption",
        "reason": reason,
        "be_rr": float(cfg["BE_RR"]) if cfg["BE_RR"] is not None else None,
        "cancel_bars": (int(cfg["CANCEL_BARS"])
                        if cfg["CANCEL_BARS"] is not None else None),
    }


def _candidate(bars, pullback_bars, cfg, atr):
    """Return setup metrics for a pullback ending one bar before confirmation."""
    impulse_n = int(cfg["IMPULSE_BARS"])
    confirm = bars[-1]
    pullback = bars[-1 - pullback_bars:-1]
    impulse = bars[-1 - pullback_bars - impulse_n:-1 - pullback_bars]
    if len(impulse) != impulse_n or len(pullback) != pullback_bars:
        return None

    impulse_move = impulse[-1]["close"] - impulse[0]["close"]
    direction = 1 if impulse_move > 0.0 else -1 if impulse_move < 0.0 else 0
    if not direction or abs(impulse_move) < atr * float(cfg["MIN_IMPULSE_ATR"]):
        return None
    efficiency = _efficiency(impulse)
    delta = _delta_bias(impulse)
    if efficiency < float(cfg["MIN_EFFICIENCY"]):
        return None
    if direction * delta < float(cfg["MIN_DELTA_BIAS"]):
        return None

    pullback_move = pullback[-1]["close"] - impulse[-1]["close"]
    if direction * pullback_move >= 0.0:
        return None
    retrace = abs(pullback_move) / abs(impulse_move)
    if not (float(cfg["PULLBACK_MIN_RETRACE"]) <= retrace
            <= float(cfg["PULLBACK_MAX_RETRACE"])):
        return None

    impulse_volume = median(bar["tick_volume"] for bar in impulse)
    pullback_volume = sum(bar["tick_volume"] for bar in pullback) / len(pullback)
    if impulse_volume <= 0.0:
        return None
    effort = pullback_volume / impulse_volume
    if effort < float(cfg["EFFORT_VOLUME_MULT"]):
        return None

    path_range = sum(bar["high"] - bar["low"] for bar in pullback)
    result_ratio = abs(pullback_move) / path_range if path_range > 0.0 else 1.0
    if result_ratio > float(cfg["MAX_RESULT_RATIO"]):
        return None

    absorption = pullback[-1]
    absorption_range = absorption["high"] - absorption["low"]
    if absorption_range <= 0.0:
        return None
    body_ratio = abs(absorption["close"] - absorption["open"]) / absorption_range
    if body_ratio > float(cfg["ABSORPTION_MAX_BODY_RATIO"]):
        return None
    if absorption["tick_volume"] < impulse_volume * float(cfg["ABSORPTION_VOLUME_MULT"]):
        return None

    close_location = (absorption["close"] - absorption["low"]) / absorption_range
    lower_wick = min(absorption["open"], absorption["close"]) - absorption["low"]
    upper_wick = absorption["high"] - max(absorption["open"], absorption["close"])
    wick = lower_wick if direction > 0 else upper_wick
    location_ok = (
        close_location >= float(cfg["ABSORPTION_CLOSE_LOCATION"])
        if direction > 0 else
        close_location <= 1.0 - float(cfg["ABSORPTION_CLOSE_LOCATION"])
    )
    if not location_ok or wick / absorption_range < float(cfg["ABSORPTION_MIN_WICK_RATIO"]):
        return None

    confirm_body = confirm["close"] - confirm["open"]
    break_ok = (confirm["close"] > absorption["high"] if direction > 0
                else confirm["close"] < absorption["low"])
    if direction * confirm_body < atr * float(cfg["CONFIRM_BODY_ATR"]):
        return None
    if not break_ok or direction * _clv(confirm) < float(cfg["CONFIRM_MIN_CLV"]):
        return None
    if confirm["tick_volume"] < impulse_volume * float(cfg["CONFIRM_VOLUME_MULT"]):
        return None

    return {
        "direction": "BUY" if direction > 0 else "SELL",
        "absorption": absorption,
        "pullback": pullback,
        "effort": effort,
        "result_ratio": result_ratio,
        "efficiency": efficiency,
        "delta": delta,
        "retrace": retrace,
    }


def detect_s114(rates, tf, dt_bkk, cfg):
    """Detect S114 from closed MT5 bars and return the standard LTS payload."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    try:
        impulse_n = int(c["IMPULSE_BARS"])
        pullback_min = int(c["PULLBACK_MIN_BARS"])
        pullback_max = int(c["PULLBACK_MAX_BARS"])
        atr_period = int(c["ATR_PERIOD"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return _wait("Invalid cfg integer parameter")
    if impulse_n < 2 or pullback_min < 1 or pullback_max < pullback_min or atr_period < 1:
        return _wait("Invalid cfg window parameter")

    required = max(atr_period + 1, impulse_n + pullback_max + 1)
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

    # Exclude the confirmation bar from the volatility baseline.
    atr = _atr(bars[:-1], atr_period)
    if atr <= 0.0:
        return _wait("ATR is zero")

    setup = None
    for pullback_n in range(pullback_min, pullback_max + 1):
        setup = _candidate(bars, pullback_n, c, atr)
        if setup is not None:
            break
    if setup is None:
        return _wait("No confirmed effort/result absorption pullback")

    direction = setup["direction"]
    absorption = setup["absorption"]
    fraction = max(0.0, min(1.0, float(c["ENTRY_ZONE_FRACTION"])))
    if direction == "BUY":
        entry = absorption["low"] + fraction * (absorption["high"] - absorption["low"])
        sl = min(bar["low"] for bar in setup["pullback"]) - atr * float(c["SL_BUFFER_ATR"])
        if entry >= bars[-1]["close"]:
            return _wait("BUY limit is not below confirmation close")
        risk = entry - sl
    else:
        entry = absorption["high"] - fraction * (absorption["high"] - absorption["low"])
        sl = max(bar["high"] for bar in setup["pullback"]) + atr * float(c["SL_BUFFER_ATR"])
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
        f"{direction} impulse ER={setup['efficiency']:.2f}, "
        f"delta={setup['delta']:+.2f}; pullback effort={setup['effort']:.2f}x "
        f"but result={setup['result_ratio']:.2f}, retrace={setup['retrace']:.0%}; "
        "closed confirmation broke absorption"
    )
    return _trade(direction, entry, sl, c, reason)
