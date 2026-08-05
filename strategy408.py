# -*- coding: utf-8 -*-
"""S408 — Yang–Zhang Gap-Share Dislocation Release 7R.

S408 separates bar-to-bar opening jumps from drift-robust Rogers–Satchell
intrabar diffusion.  Expansion in the recent jump share versus disjoint
baseline blocks identifies discontinuous repricing rather than ordinary wide
candles.  A participated closed event confirms the net path; entry is next-open
with an event-extreme ATR stop and a target of at least 7R.
"""

from __future__ import annotations

import math
import statistics

from strategy383 import _atr, _bars, _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "BASELINE_BARS": 72,
    "RECENT_BARS": 24,
    "GAP_SHARE_MIN": 0.0002,
    "GAP_SHARE_RATIO_MIN": 1.20,
    "GAP_SHARE_RISE_MIN": 0.00005,
    "GAP_ENERGY_MIN": 0.000000003,
    "PATH_EFFICIENCY_MIN": 0.12,
    "NET_MOVE_ATR_MIN": 0.35,
    "EVENT_VOLUME_RATIO_MIN": 1.00,
    "EVENT_BODY_ATR_MIN": 0.45,
    "EVENT_RANGE_ATR_MIN": 0.65,
    "EVENT_BODY_FRACTION_MIN": 0.60,
    "EVENT_CLOSE_FRACTION": 0.78,
    "SESSION_START_HOUR": 15,
    "SESSION_END_HOUR": 23,
    "SL_BUFFER_ATR": 0.18,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "FADE_DISLOCATION": False,
    "TP_RR": 7.0,
    "BE_RR": 0.02,
    "CANCEL_BARS": 3,
}


def _yz_components(bars):
    if len(bars) < 9:
        return None
    gap_energy = rs_energy = oc_energy = 0.0
    signed_gap = 0.0
    for index in range(1, len(bars)):
        previous_close = bars[index - 1]["close"]
        bar = bars[index]
        if min(previous_close, bar["open"], bar["high"], bar["low"],
               bar["close"]) <= 0.0:
            return None
        gap = math.log(bar["open"] / previous_close)
        oc = math.log(bar["close"] / bar["open"])
        rs = (math.log(bar["high"] / bar["open"])
              * math.log(bar["high"] / bar["close"])
              + math.log(bar["low"] / bar["open"])
              * math.log(bar["low"] / bar["close"]))
        gap_energy += gap * gap
        oc_energy += oc * oc
        rs_energy += max(rs, 0.0)
        signed_gap += gap * abs(gap)
    total = gap_energy + rs_energy + oc_energy
    if total <= 0.0 or not math.isfinite(total):
        return None
    return {
        "share": gap_energy / total,
        "energy": gap_energy,
        "signed": signed_gap,
    }


def detect_s408(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Return a complete S408 market payload from fully closed bars."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(24, int(c["BASELINE_BARS"]))
        recent_count = max(12, int(c["RECENT_BARS"]))
        share_min = float(c["GAP_SHARE_MIN"])
        ratio_min = float(c["GAP_SHARE_RATIO_MIN"])
        rise_min = float(c["GAP_SHARE_RISE_MIN"])
        energy_min = float(c["GAP_ENERGY_MIN"])
        path_min = float(c["PATH_EFFICIENCY_MIN"])
        net_min = float(c["NET_MOVE_ATR_MIN"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if baseline_count < recent_count or baseline_count // recent_count < 2:
        return _wait("Invalid config: Yang-Zhang windows are inconsistent")
    gates = (share_min, ratio_min, rise_min, energy_min, path_min, net_min)
    if not all(math.isfinite(value) and value >= 0.0 for value in gates):
        return _wait("Invalid config: Yang-Zhang gates are invalid")
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
            _yz_components(baseline[index:index + recent_count])
            for index in range(0, len(baseline), recent_count)
        ]
        recent_metrics = _yz_components(recent)
        if recent_metrics is None or any(item is None for item in baseline_metrics):
            return _wait("Yang-Zhang components are unavailable")
        baseline_share = statistics.median(item["share"]
                                           for item in baseline_metrics)
        atr = _atr(bars[:-1], period)
    except (
        KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError,
        AttributeError, statistics.StatisticsError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is unavailable")
    share = recent_metrics["share"]
    ratio = share / max(baseline_share, 1e-12)
    rise = share - baseline_share
    if share < share_min:
        return _wait(f"Gap share is weak ({share:.6f})")
    if ratio < ratio_min:
        return _wait(f"Gap-share ratio is weak ({ratio:.3f})")
    if rise < rise_min:
        return _wait(f"Gap-share rise is weak ({rise:.6f})")
    if recent_metrics["energy"] < energy_min:
        return _wait("Opening-gap energy is weak")

    returns = [recent[index]["close"] - recent[index - 1]["close"]
               for index in range(1, len(recent))]
    travelled = sum(abs(value) for value in returns)
    net_move = recent[-1]["close"] - recent[0]["close"]
    if travelled <= 0.0 or net_move == 0.0:
        return _wait("Recent path is unavailable")
    path_side = 1 if net_move > 0.0 else -1
    path_efficiency = abs(net_move) / travelled
    if path_efficiency < path_min:
        return _wait(f"Dislocation path is inefficient ({path_efficiency:.3f})")
    if abs(net_move) < atr * net_min:
        return _wait("Dislocation move is too small versus ATR")

    body = event["close"] - event["open"]
    candle_range = event["high"] - event["low"]
    if body == 0.0 or candle_range <= 0.0:
        return _wait("Event candle is invalid")
    event_side = 1 if body > 0.0 else -1
    trade_side = -path_side if bool(c["FADE_DISLOCATION"]) else path_side
    if event_side != trade_side:
        return _wait("Event direction does not confirm dislocation setup")
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
            f"S408 {signal} Yang-Zhang Gap-Share "
            f"{'Fade' if bool(c['FADE_DISLOCATION']) else 'Release'} {rr:g}R"
        ),
        "reason": (
            f"gap_share={share:.6f}, baseline={baseline_share:.6f}, "
            f"ratio={ratio:.3f}, rise={rise:.6f}, "
            f"gap_energy={recent_metrics['energy']:.8f}, path={path_efficiency:.3f}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
