# -*- coding: utf-8 -*-
"""S168 - Directional-efficiency volume hand-off BUY with a 7R target."""

from __future__ import annotations

import math

from strategy119 import _atr, _bars
from strategy149 import _quantile


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "EFFICIENCY_WINDOW": 36,
    "EFFICIENCY_MIN": 0.24,
    "NET_MOVE_MIN_ATR": 1.00,
    "PULLBACK_BODY_MIN_ATR": 0.05,
    "PULLBACK_BODY_MAX_ATR": 0.75,
    "PULLBACK_VOLUME_QUANTILE_MAX": 0.65,
    "REJECTION_CLOSE_LOCATION_MIN": 0.60,
    "REJECTION_VOLUME_QUANTILE_MIN": 0.50,
    "REJECTION_VOLUME_RATIO_MIN": 1.05,
    "ENTRY_RANGE_FRACTION": 0.50,
    "SL_BUFFER_ATR": 0.06,
    "MAX_RISK_ATR": 1.20,
    "MAX_RISK_PRICE_PCT": 0.30,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
    "CANCEL_BARS": 4,
}


def _wait(reason):
    return {"signal": "WAIT", "reason": str(reason)}


def detect_s168(rates, tf, dt_bkk, cfg):
    """Buy a high-volume rejection after a low-volume pullback in an efficient advance."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        window = max(20, int(c["EFFICIENCY_WINDOW"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if rates is None or len(rates) < window + period + 4 or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    try:
        bars = _bars(rates)
        atr = _atr(bars[:-2], period)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    closes = [bar["close"] for bar in bars]
    regime = closes[-window - 2:-2]
    net_move = regime[-1] - regime[0]
    path = sum(abs(regime[index] - regime[index - 1])
               for index in range(1, len(regime)))
    efficiency = abs(net_move) / max(path, 1e-12)
    if net_move < atr * float(c["NET_MOVE_MIN_ATR"]):
        return _wait("Regime displacement is not bullish enough")
    if efficiency < float(c["EFFICIENCY_MIN"]):
        return _wait(f"Bullish path is too noisy (ER={efficiency:.2f})")

    pullback = bars[-2]
    rejection = bars[-1]
    pullback_body = pullback["open"] - pullback["close"]
    if not (atr * float(c["PULLBACK_BODY_MIN_ATR"]) <= pullback_body
            <= atr * float(c["PULLBACK_BODY_MAX_ATR"])):
        return _wait("No bounded bearish pullback")

    history = bars[-window - 2:-2]
    volumes = [bar["tick_volume"] for bar in history]
    pullback_volume_max = _quantile(volumes, c["PULLBACK_VOLUME_QUANTILE_MAX"])
    rejection_volume_min = _quantile(volumes, c["REJECTION_VOLUME_QUANTILE_MIN"])
    if pullback["tick_volume"] > pullback_volume_max:
        return _wait("Pullback volume is not contracting")

    rejection_range = rejection["high"] - rejection["low"]
    if rejection_range <= 0.0:
        return _wait("Rejection range is zero")
    rejection_location = (rejection["close"] - rejection["low"]) / rejection_range
    if (rejection["close"] <= rejection["open"]
            or rejection["close"] <= pullback["open"]
            or rejection_location < float(c["REJECTION_CLOSE_LOCATION_MIN"])):
        return _wait("Pullback did not hand off to buyers")
    if (rejection["tick_volume"] < rejection_volume_min
            or rejection["tick_volume"] < (pullback["tick_volume"]
                                             * float(c["REJECTION_VOLUME_RATIO_MIN"]))):
        return _wait("Rejection volume does not confirm buyer hand-off")

    fraction = float(c["ENTRY_RANGE_FRACTION"])
    entry = rejection["high"] - fraction * rejection_range
    if entry >= rejection["close"]:
        return _wait("BUY limit is not below rejection close")
    sl = min(pullback["low"], rejection["low"]) - atr * float(c["SL_BUFFER_ATR"])
    entry = round(entry, 2)
    sl = math.floor((sl + 1e-12) * 100.0) / 100.0
    risk = entry - sl
    if risk <= 0.0 or risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Efficiency hand-off risk outside range ({risk / atr:.2f} ATR)")
    risk_pct = risk / entry * 100.0
    if risk_pct > float(c["MAX_RISK_PRICE_PCT"]):
        return _wait(f"Efficiency hand-off risk too large versus price ({risk_pct:.2f}%)")

    rr = max(7.0, float(c["TP_RR"]))
    raw_tp = entry + rr * risk
    tp = math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
    return {
        "signal": "BUY",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "limit",
        "pattern": f"S168 BUY Efficiency Hand-off {rr:g}R",
        "reason": (f"Bullish ER={efficiency:.2f}, net={net_move / atr:.2f}ATR; "
                   "low-volume pullback rejected on expanding volume"),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
