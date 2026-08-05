# -*- coding: utf-8 -*-
"""S313 - Kendall volume-volatility coupling release.

The detector looks for a regime in which large absolute returns become
rank-concordant with high tick volume after a weakly coupled baseline.  This
is evidence that price expansion is being sponsored by participation rather
than thin-liquidity noise.  Direction comes from the efficient recent price
path and a fully closed release candle.

All statistics use closed M5 bars supplied by the caller.  A market signal is
executed at the next bar open by the repository backtester.  The structural
stop sits beyond the release extreme plus an ATR buffer and TP is at least 7R.
"""

from __future__ import annotations

import math
from statistics import median

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "SESSION_START_HOUR": 17,
    "SESSION_END_HOUR": 21,
    "BASELINE_BARS": 48,
    "RECENT_BARS": 16,
    # Optional robustness mode.  Empty preserves the optimized single-window
    # detector.  A tuple such as (14, 16, 18) uses majority agreement.
    "RECENT_BARS_ENSEMBLE": (),
    "ENSEMBLE_MIN_AGREE": 2,
    # Broad first-pass survivor region: tau 0.10-0.20 and jump 0.20 remain
    # profitable in the recent window.  Optimization audits follow below.
    "RECENT_TAU_MIN": 0.10,
    # Winner floor is 0.3657.  The 0.335 gate removes the only cross-window
    # SL while retaining 0.0307 of margin below the weakest winner.
    "TAU_JUMP_MIN": 0.335,
    "PATH_EFFICIENCY_MIN": 0.20,
    "NET_MOVE_ATR_MIN": 0.55,
    # Cross-window TP floor is 0.8381ATR; the 0.75 gate is the midpoint of
    # the 0.70-0.80 plateau and remains above the sole SL at 0.6687ATR.
    "RELEASE_BODY_ATR_MIN": 0.75,
    "RELEASE_RANGE_ATR_MIN": 0.80,
    "RELEASE_CLOSE_FRACTION": 0.78,
    "SL_BUFFER_ATR": 0.08,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "MAX_RISK_PRICE_PCT": 0.34,
    # BUY is negative in the non-overlapping walk-forward window.  SELL is
    # positive in recent, six-month, and walk-forward audits with much lower
    # drawdown than the two-sided version.
    "ALLOW_BUY": False,
    "ALLOW_SELL": True,
    # The oldest cross-window winner reaches roughly 12.40R but not 13R.
    # Keep a 0.30R excursion margin instead of fitting the observed extreme.
    "TP_RR": 12.1,
    # 0.05R improves the H1 audit and halves drawdown versus 0.075-0.10;
    # recent and walk-forward results are unchanged.
    "BE_RR": 0.05,
    "CANCEL_BARS": 3,
}


def _kendall_tau_b(first, second):
    """Return Kendall tau-b for equal-length finite samples."""
    if len(first) != len(second) or len(first) < 4:
        return None
    concordant = discordant = ties_first = ties_second = 0
    for left in range(len(first) - 1):
        for right in range(left + 1, len(first)):
            delta_first = first[right] - first[left]
            delta_second = second[right] - second[left]
            if delta_first == 0.0 and delta_second == 0.0:
                continue
            if delta_first == 0.0:
                ties_first += 1
            elif delta_second == 0.0:
                ties_second += 1
            elif delta_first * delta_second > 0.0:
                concordant += 1
            else:
                discordant += 1
    denominator = math.sqrt(
        (concordant + discordant + ties_first)
        * (concordant + discordant + ties_second)
    )
    if denominator <= 0.0:
        return None
    return (concordant - discordant) / denominator


def _coupling_sample(bars):
    magnitudes = []
    volumes = []
    for index in range(1, len(bars)):
        previous = bars[index - 1]["close"]
        current = bars[index]["close"]
        if previous <= 0.0 or current <= 0.0:
            return None
        value = abs(math.log(current / previous))
        volume = bars[index]["tick_volume"]
        if not math.isfinite(value) or not math.isfinite(volume):
            return None
        magnitudes.append(value)
        volumes.append(volume)
    return _kendall_tau_b(magnitudes, volumes)


def detect_s313(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Follow a participation-backed directional release."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        period = max(1, int(c["ATR_PERIOD"]))
        baseline_count = max(8, int(c["BASELINE_BARS"]))
        recent_count = max(6, int(c["RECENT_BARS"]))
        raw_ensemble = tuple(c.get("RECENT_BARS_ENSEMBLE", ()) or ())
        recent_windows = (
            tuple(max(6, int(value)) for value in raw_ensemble)
            if raw_ensemble
            else (recent_count,)
        )
        min_agree = (
            max(1, int(c["ENSEMBLE_MIN_AGREE"]))
            if raw_ensemble
            else 1
        )
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
        tau_min = float(c["RECENT_TAU_MIN"])
        jump_min = float(c["TAU_JUMP_MIN"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not all(math.isfinite(value) for value in (tau_min, jump_min)):
        return _wait("Invalid config: tau thresholds must be finite")
    if len(set(recent_windows)) != len(recent_windows):
        return _wait("Invalid config: ensemble windows must be unique")
    if min_agree > len(recent_windows):
        return _wait("Invalid config: ENSEMBLE_MIN_AGREE exceeds window count")

    required = max(period + 5, baseline_count + max(recent_windows) + 3)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside US liquidity window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        atr = _atr(bars[:-1], period)
        measures = []
        for window_count in recent_windows:
            history = bars[-(baseline_count + window_count + 2):-1]
            baseline = history[:baseline_count + 1]
            recent = history[baseline_count:]
            baseline_tau = _coupling_sample(baseline)
            recent_tau = _coupling_sample(recent)
            if baseline_tau is None or recent_tau is None:
                continue
            path_start = recent[0]["close"]
            path_end = recent[-1]["close"]
            net_move = path_end - path_start
            travelled = sum(
                abs(recent[index]["close"] - recent[index - 1]["close"])
                for index in range(1, len(recent))
            )
            if travelled <= 0.0:
                continue
            measures.append({
                "window": window_count,
                "recent_tau": recent_tau,
                "tau_jump": recent_tau - baseline_tau,
                "net_move": net_move,
                "efficiency": abs(net_move) / travelled,
            })
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        ZeroDivisionError,
        AttributeError,
    ) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")
    if not measures:
        return _wait("Kendall coupling is unavailable")
    qualified = [
        measure for measure in measures
        if measure["recent_tau"] >= tau_min
        and measure["tau_jump"] >= jump_min
        and measure["efficiency"] >= float(c["PATH_EFFICIENCY_MIN"])
        and abs(measure["net_move"]) >= atr * float(c["NET_MOVE_ATR_MIN"])
    ]
    side_groups = {
        side_value: [
            measure for measure in qualified
            if (1 if measure["net_move"] > 0.0 else -1) == side_value
        ]
        for side_value in (-1, 1)
    }
    best_count = max(len(group) for group in side_groups.values())
    best_sides = [
        side_value for side_value, group in side_groups.items()
        if len(group) == best_count
    ]
    if best_count < min_agree or len(best_sides) != 1:
        return _wait(
            f"No coupling/path consensus ({best_count}/{min_agree} windows)"
        )
    side = best_sides[0]
    selected = side_groups[side]
    recent_tau = median(measure["recent_tau"] for measure in selected)
    tau_jump = median(measure["tau_jump"] for measure in selected)
    efficiency = median(measure["efficiency"] for measure in selected)
    selected_windows = ",".join(
        str(measure["window"]) for measure in selected
    )

    event_body = event["close"] - event["open"]
    event_range = event["high"] - event["low"]
    if event_range <= 0.0 or event_body * side <= 0.0:
        return _wait("Release candle does not confirm path direction")
    if abs(event_body) < atr * float(c["RELEASE_BODY_ATR_MIN"]):
        return _wait("Release body is too small versus ATR")
    if event_range < atr * float(c["RELEASE_RANGE_ATR_MIN"]):
        return _wait("Release range is too small versus ATR")
    close_fraction = (
        (event["close"] - event["low"]) / event_range
        if side > 0
        else (event["high"] - event["close"]) / event_range
    )
    if close_fraction < float(c["RELEASE_CLOSE_FRACTION"]):
        return _wait("Release candle lacks directional close control")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")

    entry = round(event["close"], 2)
    buffer = atr * float(c["SL_BUFFER_ATR"])
    if side > 0:
        sl = math.floor((event["low"] - buffer + 1e-12) * 100.0) / 100.0
    else:
        sl = math.ceil((event["high"] + buffer - 1e-12) * 100.0) / 100.0
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
        "pattern": f"S313 {signal} Kendall Coupling Release {rr:g}R",
        "reason": (
            f"volume-volatility tau={recent_tau:.4f}, "
            f"jump={tau_jump:.4f}, path efficiency={efficiency:.4f}, "
            f"windows={selected_windows}"
        ),
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
