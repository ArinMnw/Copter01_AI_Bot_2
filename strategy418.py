# -*- coding: utf-8 -*-
"""S418 - ICT concept scoring; empirically converged on FVG-only.

Started as a literal point-scoring implementation of ICT confluence: four
independent structural concepts (Fair Value Gap, Order Block, Break of
Structure / Change of Character, Liquidity Sweep) each contribute
CONCEPT_POINTS to a side's score, and a side triggers once its score clears
MIN_SCORE. Ablation testing across the dual-window protocol (2026-H1 /
2025-H2) found that *requiring confluence hurts*: every 2+-concept
combination underperformed FVG alone, Order Block alone is weak, Sweep is
net noise, and BOS/CHoCH is a coin flip (initially measured as literally
zero signals - that was a bug, see below - and after fixing it, still a
net-negative concept). The DEFAULT_CFG below reflects the winning
configuration: FVG only (OB/BOSCHOCH/SWEEP disabled), no session filter,
STOP_SWING_BARS=8, SL_BUFFER_ATR=0.10, TP_RR=8. Combined dual-window ratio
10.37 on n=5323 trades (2656 + 2667), both windows net positive. The other
concepts remain implemented and toggle-able via *_ENABLED cfg keys for
future re-exploration, since this is an empirical finding from one
parameter sweep, not a proof that OB/BOS/Sweep can never contribute.

Bug fixed during tuning: the stop was originally anchored to the same
SWING_BARS=20 extreme used to *define* BOS/CHoCH, which for a breakout-style
entry is typically many ATR away and blew the MAX_RISK_ATR cap on nearly
every occurrence - BOS/CHoCH measured 0 closed trades despite the underlying
break condition firing ~3900 times over 6 months. STOP_SWING_BARS now anchors
the stop to a separate, tighter recent extreme independent of SWING_BARS.

This is the literal-concept counterpart to the earlier confluence_scan.py
experiment, which scored agreement between whole *strategies* instead of
individual structural concepts and did not survive dual-window testing -
every positive composite there collapsed to near-zero or below once the
single largest contributing trade was removed (n was only 10-46). That
fragility does not apply here: n is in the thousands per window, and the
edge is spread across most months rather than 1-2 trades (see memory:
confluence_scoring_negative_result.md for the full write-up of both
experiments). One legitimate caveat: 2025-H2 (WF) is much weaker than
2026-H1 (ratio 1.33 vs 9.05) - net positive but choppier, not as strong
out-of-sample as in-sample.

Entry is market at the event candle's close; the stop sits just beyond the
STOP_SWING_BARS-bar swing extreme, TP at TP_RR (>=7 enforced), matching the
campaign-wide tight-SL / RR>=7 screening bar.
"""

from __future__ import annotations

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "LOOKBACK_BARS": 120,
    "SWING_BARS": 20,
    "STOP_SWING_BARS": 8,
    "CHOCH_TREND_BARS": 40,
    "FVG_MAX_ZONES": 3,
    "OB_DISPLACEMENT_ATR": 1.0,
    "SWEEP_BUFFER_ATR": 0.05,
    "CONCEPT_POINTS": 20.0,
    "MIN_SCORE": 20.0,
    "FVG_ENABLED": True,
    "OB_ENABLED": False,
    "BOSCHOCH_ENABLED": False,
    "SWEEP_ENABLED": False,
    "SL_BUFFER_ATR": 0.10,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "TP_RR": 8.0,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "SESSION_START_HOUR": 0,
    "SESSION_END_HOUR": 24,
    "BE_RR": 0.10,
    "CANCEL_BARS": 3,
}


def _active_fvgs(hist, lookback, max_zones):
    """Unmitigated 3-candle fair value gaps, most recent `max_zones` per side."""
    seg = hist[-lookback:] if lookback else hist
    zones = []
    for i in range(2, len(seg)):
        c0, c1, c2 = seg[i], seg[i - 1], seg[i - 2]
        if c1["close"] > c1["open"] and c1["close"] > c2["high"] and c0["low"] > c2["high"]:
            zones.append({"side": 1, "bot": c2["high"], "top": c0["low"], "formed_at": i})
        elif c1["close"] < c1["open"] and c1["close"] < c2["low"] and c0["high"] < c2["low"]:
            zones.append({"side": -1, "bot": c0["high"], "top": c2["low"], "formed_at": i})

    active = {1: [], -1: []}
    for zone in zones:
        mitigated = False
        for j in range(zone["formed_at"] + 1, len(seg)):
            close = seg[j]["close"]
            if zone["side"] == 1 and close < zone["bot"]:
                mitigated = True
                break
            if zone["side"] == -1 and close > zone["top"]:
                mitigated = True
                break
        if not mitigated:
            active[zone["side"]].append(zone)

    for side in (1, -1):
        active[side].sort(key=lambda z: z["formed_at"], reverse=True)
        active[side] = active[side][:max_zones]
    return active


def _active_order_block(hist, side, atr, lookback, disp_atr):
    seg = hist[-lookback:] if lookback else hist
    for i in range(len(seg) - 1, 1, -1):
        disp = seg[i]
        body = disp["close"] - disp["open"]
        if side > 0 and body > 0.0 and body >= disp_atr * atr:
            ob = seg[i - 1]
            if ob["close"] < ob["open"]:
                return {"bot": ob["low"], "top": ob["high"]}
        elif side < 0 and body < 0.0 and -body >= disp_atr * atr:
            ob = seg[i - 1]
            if ob["close"] > ob["open"]:
                return {"bot": ob["low"], "top": ob["high"]}
    return None


def _swing_high(hist, n):
    seg = hist[-n:] if n else hist
    return max(b["high"] for b in seg) if seg else None


def _swing_low(hist, n):
    seg = hist[-n:] if n else hist
    return min(b["low"] for b in seg) if seg else None


def _trend_slope(hist, n):
    seg = hist[-n:] if n else hist
    if len(seg) < 2:
        return 0.0
    return seg[-1]["close"] - seg[0]["close"]


def detect_s418(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Score BUY/SELL by literal FVG + Order Block + BOS/CHoCH + Liquidity Sweep."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        atr_period = max(1, int(c["ATR_PERIOD"]))
        lookback = max(20, int(c["LOOKBACK_BARS"]))
        swing_bars = max(3, int(c["SWING_BARS"]))
        stop_swing_bars = max(2, int(c["STOP_SWING_BARS"]))
        trend_bars = max(3, int(c["CHOCH_TREND_BARS"]))
        max_zones = max(1, int(c["FVG_MAX_ZONES"]))
        disp_atr = float(c["OB_DISPLACEMENT_ATR"])
        sweep_buffer_atr = float(c["SWEEP_BUFFER_ATR"])
        points = float(c["CONCEPT_POINTS"])
        min_score = float(c["MIN_SCORE"])
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
        fvg_on = bool(c["FVG_ENABLED"])
        ob_on = bool(c["OB_ENABLED"])
        boschoch_on = bool(c["BOSCHOCH_ENABLED"])
        sweep_on = bool(c["SWEEP_ENABLED"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")

    required = max(atr_period + 5, lookback + 3, trend_bars + 3)
    if rates is None or len(rates) < required or dt_bkk is None:
        return _wait("Not enough data or dt_bkk missing")
    if not start_hour <= dt_bkk.hour < end_hour:
        return _wait("Outside configured session window")
    try:
        bars = _bars(rates)
        event = bars[-1]
        hist = bars[:-1]
        atr = _atr(hist, atr_period)
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if atr <= 0.0:
        return _wait("ATR is zero")

    fvgs = _active_fvgs(hist, lookback, max_zones)
    swing_high = _swing_high(hist, swing_bars)
    swing_low = _swing_low(hist, swing_bars)
    prior_swing_high = _swing_high(hist[:-1], swing_bars)
    prior_swing_low = _swing_low(hist[:-1], swing_bars)
    trend = _trend_slope(hist, trend_bars)
    sweep_buffer = atr * sweep_buffer_atr

    scores = {1: 0.0, -1: 0.0}
    hits = {1: [], -1: []}

    price = event["close"]
    if fvg_on:
        for side in (1, -1):
            for zone in fvgs[side]:
                if zone["bot"] <= price <= zone["top"]:
                    scores[side] += points
                    hits[side].append("FVG")
                    break

    if ob_on:
        for side in (1, -1):
            ob = _active_order_block(hist, side, atr, lookback, disp_atr)
            if ob is not None and ob["bot"] <= price <= ob["top"]:
                scores[1 if side > 0 else -1] += points
                hits[side].append("OB")

    if boschoch_on:
        bos_buy = swing_high is not None and event["close"] > swing_high
        bos_sell = swing_low is not None and event["close"] < swing_low
        if bos_buy:
            choch_buy = trend < 0.0
            scores[1] += points
            hits[1].append("CHoCH" if choch_buy else "BOS")
        if bos_sell:
            choch_sell = trend > 0.0
            scores[-1] += points
            hits[-1].append("CHoCH" if choch_sell else "BOS")

    if sweep_on:
        if prior_swing_low is not None and event["low"] < prior_swing_low - sweep_buffer and event["close"] > prior_swing_low:
            scores[1] += points
            hits[1].append("SWEEP")
        if prior_swing_high is not None and event["high"] > prior_swing_high + sweep_buffer and event["close"] < prior_swing_high:
            scores[-1] += points
            hits[-1].append("SWEEP")

    buy_ok = scores[1] >= min_score
    sell_ok = scores[-1] >= min_score
    if buy_ok and sell_ok:
        side = 1 if scores[1] > scores[-1] else (-1 if scores[-1] > scores[1] else 0)
        if side == 0:
            return _wait("BUY/SELL score tie at threshold")
    elif buy_ok:
        side = 1
    elif sell_ok:
        side = -1
    else:
        return _wait(f"Score below threshold (buy={scores[1]:.0f}, sell={scores[-1]:.0f})")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")

    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(price, 2)
    stop_swing_low = _swing_low(hist, stop_swing_bars)
    stop_swing_high = _swing_high(hist, stop_swing_bars)
    if side > 0:
        anchor = stop_swing_low if stop_swing_low is not None else event["low"]
        sl = round(min(anchor, event["low"]) - sl_buffer, 2)
    else:
        anchor = stop_swing_high if stop_swing_high is not None else event["high"]
        sl = round(max(anchor, event["high"]) + sl_buffer, 2)

    risk = side * (entry - sl)
    if risk < float(c["MIN_RISK_ABS"]):
        return _wait(f"Risk below spread-honesty floor ({risk:.2f})")
    if risk > atr * float(c["MAX_RISK_ATR"]):
        return _wait(f"Risk outside range ({risk / atr:.2f} ATR)")

    rr = max(7.0, float(c["TP_RR"]))
    tp = round(entry + side * rr * risk, 2)

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S418 {signal} ICT Confluence {rr:g}R score={scores[side]:.0f}",
        "reason": f"concepts={'+'.join(hits[side])} buy={scores[1]:.0f} sell={scores[-1]:.0f}",
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
