# -*- coding: utf-8 -*-
"""S419 - Orochi-style Auction Market Theory: breakout-with-acceptance.

Translates the "Orochi Trading" framework (Auction Market Theory + TPO/Volume
Profile + VWAP + order flow) into codeable rules. Per the framework: price
seeks value through auction, VWAP is the session's fair-value reference, and
the Volume Profile's Point of Control (POC) and Value Area (VAH/VAL, the
price band holding VALUE_AREA_PCT of traded volume) mark where the auction
has actually transacted. Two setups were implemented and both toggle-able
via SETUP cfg ("fade", "breakout", "both"):

  - Failed auction (fade/reversal): price wicks beyond VAL or VAH but closes
    back inside the value area - the market rejected that price, trade back
    toward POC.
  - Breakout with acceptance (continuation): price closes beyond VAL/VAH and
    *stays* there for ACCEPTANCE_BARS consecutive closes - the market has
    accepted the new price, trade the continuation.

Empirical finding (dual-window ablation, 2026-08-06): the framework's own
emphasis - "when VWAP and the Value Area edge coincide, that confluence
identifies a level with both theoretical and empirical support" - does NOT
hold up here. Requiring VWAP within VWAP_PROXIMITY_ATR of the tested edge
(the literal translation of that claim) made the strategy fail dual-window
outright (WF net negative) in every combination tested. Removing that gate
entirely and keeping only the breakout/acceptance setup produced a large,
dual-window-positive, robust result instead (best found: combined ratio
7.77, n=5002, and every parameter variant tried in the sweep was
dual-window-positive - not fragile like a small-n result). The fade setup
never worked standalone in any configuration (always net negative or ~flat).
This mirrors the same lesson from S418 the same day: literal confluence
requirements can hurt more than they help versus the raw single-signal
version. DEFAULT_CFG below reflects the winning breakout-only, no-VWAP-gate
configuration; VWAP_PROXIMITY_ATR and SETUP remain adjustable for future
re-exploration since this is one parameter sweep's result, not proof the
fade/confluence ideas can never work.

Also tried before the breakthrough below: TF sweep (M5 confirmed best;
M15/M30 worse, H1 outright negative), volume-profile shape
(PROFILE_BINS=32/VALUE_AREA_PCT=0.6 looked best on a single 3-month window,
ratio 8.93, but a 2nd 3-month window collapsed it to 2.34 - single-window
tuning is an overfitting trap here). Session filter swept too
(SESSION_START/END_HOUR): unfiltered 0-24 beat every restricted window -
unlike most other campaign strategies, this edge is not time-of-day
dependent. Volume/order-flow confirmation (VOLUME_CONFIRM_* cfg, gates the
breakout on elevated tick_volume vs baseline) was initially mis-reported as
an improvement (ratio 8.96) from an invalid test that compared two
same-regime halves of the H1 window instead of true H1-vs-WF; properly
validated against the real WF window it nets out to ~7.59, no real
improvement - left implemented and toggle-able (default False) but not
adopted.

BREAKTHROUGH (2026-08-06): VALUE_AREA_MODE="prior_session" - instead of a
continuously-sliding PROFILE_LOOKBACK_BARS rolling window, compute the
Value Area/VWAP once from the immediately preceding, already-closed session
(bounded by SESSION_ANCHOR_HOUR, the BKK hour that starts a new session
day) and hold it fixed through the current session. This is closer to how
Auction Market Theory is actually used in practice - today's price action
judged against yesterday's completed value area, not an ever-shifting
window. Swept SESSION_ANCHOR_HOUR against the REAL 2026-H1/2025-H2(WF)
dual-window from the start this time (the volume-confirm mistake above
taught that lesson). SESSION_ANCHOR_HOUR=20 (new session starts 20:00 BKK)
is the winner: H1 net+2674.89 DD206.92 ratio12.93 (n=3118), WF
net+434.74 DD247.18 ratio1.76 (n=2771), combined ratio **12.58** - clears
the campaign's dual-window ratio>=10 screening bar on a large, both-windows-
positive sample (n=5889 total). Three other anchor hours also cleared 10
(16->11.02, 8->10.70, 12->10.67); anchor 4 and 6 looked strong on H1 alone
(ratio 10-13) but WF went negative there - excluded, dual_pos matters more
than a high single-window number. DEFAULT_CFG below reflects the anchor=20
winner. This is now S419's actual best-validated result, not the earlier
7.77 rolling-window baseline (VALUE_AREA_MODE="rolling" still works and is
kept for comparison/future re-exploration).

Entry is market at the event candle's close, stop just beyond the structure
that defined the setup, TP at TP_RR (>=7 enforced) - matching the
campaign-wide tight-SL / RR>=7 screening bar.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from strategy119 import _atr, _bars
from strategy197 import _wait


DEFAULT_CFG = {
    "ATR_PERIOD": 14,
    "PROFILE_LOOKBACK_BARS": 96,
    "PROFILE_BINS": 24,
    "VALUE_AREA_PCT": 0.70,
    "VWAP_PROXIMITY_ATR": 999.0,
    "FADE_WICK_BUFFER_ATR": 0.05,
    "BREAKOUT_BUFFER_ATR": 0.05,
    "ACCEPTANCE_BARS": 2,
    "VOLUME_CONFIRM_ENABLED": False,
    "VOLUME_CONFIRM_BASELINE_BARS": 10,
    "VOLUME_CONFIRM_MULT": 1.1,
    "VALUE_AREA_MODE": "prior_session",
    "SESSION_ANCHOR_HOUR": 20,
    "PRIOR_SESSION_MIN_BARS": 20,
    "SETUP": "breakout",
    "SL_BUFFER_ATR": 0.25,
    "MIN_RISK_ABS": 0.60,
    "MAX_RISK_ATR": 1.75,
    "TP_RR": 7.0,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "SESSION_START_HOUR": 0,
    "SESSION_END_HOUR": 24,
    "BE_RR": 0.10,
    "CANCEL_BARS": 3,
}


def _vwap(hist):
    """Volume-weighted average of typical price over hist."""
    num = den = 0.0
    for b in hist:
        typical = (b["high"] + b["low"] + b["close"]) / 3.0
        vol = b["tick_volume"]
        num += typical * vol
        den += vol
    return (num / den) if den > 0.0 else None


def _value_area(hist, bins, value_pct):
    """Volume-profile POC/VAH/VAL from a price-binned tick_volume histogram.
    Each bar's volume is split evenly across the bins its high-low range
    spans, then the value area expands outward from the POC bin toward
    whichever neighbour holds more volume until value_pct is captured."""
    if not hist:
        return None
    lo = min(b["low"] for b in hist)
    hi = max(b["high"] for b in hist)
    if hi <= lo:
        return None
    bin_size = (hi - lo) / bins
    if bin_size <= 0.0:
        return None
    volumes = [0.0] * bins
    for b in hist:
        lo_idx = min(bins - 1, max(0, int((b["low"] - lo) / bin_size)))
        hi_idx = min(bins - 1, max(0, int((b["high"] - lo) / bin_size)))
        span = hi_idx - lo_idx + 1
        share = b["tick_volume"] / span
        for i in range(lo_idx, hi_idx + 1):
            volumes[i] += share
    total = sum(volumes)
    if total <= 0.0:
        return None

    poc_idx = max(range(bins), key=lambda i: volumes[i])
    poc = lo + (poc_idx + 0.5) * bin_size

    included = {poc_idx}
    acc = volumes[poc_idx]
    left, right = poc_idx - 1, poc_idx + 1
    target = total * value_pct
    while acc < target and (left >= 0 or right < bins):
        left_vol = volumes[left] if left >= 0 else -1.0
        right_vol = volumes[right] if right < bins else -1.0
        if right_vol >= left_vol and right < bins:
            acc += volumes[right]
            included.add(right)
            right += 1
        elif left >= 0:
            acc += volumes[left]
            included.add(left)
            left -= 1
        elif right < bins:
            acc += volumes[right]
            included.add(right)
            right += 1
        else:
            break

    val = lo + min(included) * bin_size
    vah = lo + (max(included) + 1) * bin_size
    return {"poc": poc, "val": val, "vah": vah}


def _bkk_session_day(unix_ts, anchor_hour):
    """Calendar date (BKK, UTC+7, no DST) of the session this bar belongs to,
    where a new session starts at anchor_hour BKK time."""
    bkk_dt = datetime.utcfromtimestamp(unix_ts + 7 * 3600)
    if bkk_dt.hour < anchor_hour:
        bkk_dt = bkk_dt - timedelta(days=1)
    return bkk_dt.date()


def _prior_session_bars(hist, event_time, anchor_hour, min_bars):
    """Bars belonging to the session immediately before the event's own
    session - a fixed reference, not a rolling window."""
    event_day = _bkk_session_day(event_time, anchor_hour)
    prior_day = event_day - timedelta(days=1)
    prior_bars = [b for b in hist if _bkk_session_day(b["time"], anchor_hour) == prior_day]
    if len(prior_bars) < min_bars:
        return None
    return prior_bars


def _accepted_beyond(bars_tail, edge, side):
    """True if every bar in bars_tail closed beyond `edge` in `side` direction."""
    if side > 0:
        return all(b["close"] > edge for b in bars_tail)
    return all(b["close"] < edge for b in bars_tail)


def _avg_volume(hist, n):
    seg = hist[-n:] if n else hist
    if not seg:
        return None
    return sum(b["tick_volume"] for b in seg) / len(seg)


def detect_s419(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """Orochi-style Value Area fade (failed auction) + breakout-with-acceptance."""
    del tf, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    try:
        atr_period = max(1, int(c["ATR_PERIOD"]))
        lookback = max(20, int(c["PROFILE_LOOKBACK_BARS"]))
        bins = max(6, int(c["PROFILE_BINS"]))
        value_pct = float(c["VALUE_AREA_PCT"])
        vwap_prox_atr = float(c["VWAP_PROXIMITY_ATR"])
        fade_buf_atr = float(c["FADE_WICK_BUFFER_ATR"])
        breakout_buf_atr = float(c["BREAKOUT_BUFFER_ATR"])
        acceptance_bars = max(1, int(c["ACCEPTANCE_BARS"]))
        volume_confirm_on = bool(c["VOLUME_CONFIRM_ENABLED"])
        volume_baseline_bars = max(5, int(c["VOLUME_CONFIRM_BASELINE_BARS"]))
        volume_confirm_mult = float(c["VOLUME_CONFIRM_MULT"])
        setup_mode = str(c["SETUP"]).lower()
        start_hour = int(c["SESSION_START_HOUR"])
        end_hour = int(c["SESSION_END_HOUR"])
        value_area_mode = str(c["VALUE_AREA_MODE"]).lower()
        session_anchor_hour = int(c["SESSION_ANCHOR_HOUR"])
        prior_session_min_bars = max(5, int(c["PRIOR_SESSION_MIN_BARS"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid config: {exc}")
    if not 0.0 < value_pct < 1.0:
        return _wait("Invalid config: VALUE_AREA_PCT out of range")
    if setup_mode not in ("fade", "breakout", "both"):
        return _wait("Invalid config: SETUP must be fade/breakout/both")
    if value_area_mode not in ("rolling", "prior_session"):
        return _wait("Invalid config: VALUE_AREA_MODE must be rolling/prior_session")

    required = max(atr_period + 5, lookback + acceptance_bars + 3)
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

    if value_area_mode == "prior_session":
        profile_hist = _prior_session_bars(hist, event["time"], session_anchor_hour, prior_session_min_bars)
        if profile_hist is None:
            return _wait("Prior session has too few bars")
    else:
        profile_hist = hist[-lookback:]
    va = _value_area(profile_hist, bins, value_pct)
    if va is None:
        return _wait("Value area unavailable")
    vwap = _vwap(profile_hist)
    if vwap is None:
        return _wait("VWAP unavailable")

    val, vah = va["val"], va["vah"]
    vwap_prox = atr * vwap_prox_atr
    fade_buf = atr * fade_buf_atr
    breakout_buf = atr * breakout_buf_atr

    side = 0
    hits = []

    if setup_mode in ("fade", "both"):
        if event["low"] < val - fade_buf and event["close"] > val and abs(vwap - val) <= vwap_prox:
            side, hits = 1, ["FADE@VAL"]
        elif event["high"] > vah + fade_buf and event["close"] < vah and abs(vwap - vah) <= vwap_prox:
            side, hits = -1, ["FADE@VAH"]

    if side == 0 and setup_mode in ("breakout", "both"):
        window = bars[-acceptance_bars:]
        volume_ok = True
        if volume_confirm_on:
            baseline_hist = hist[:-acceptance_bars] if len(hist) > acceptance_bars else hist
            baseline_avg = _avg_volume(baseline_hist, volume_baseline_bars)
            window_avg = _avg_volume(window, len(window))
            volume_ok = (baseline_avg is not None and baseline_avg > 0.0
                         and window_avg is not None
                         and window_avg >= baseline_avg * volume_confirm_mult)
        if (volume_ok and event["close"] > vah + breakout_buf and abs(vwap - vah) <= vwap_prox
                and _accepted_beyond(window, vah, 1)):
            side, hits = 1, ["BREAKOUT@VAH"]
        elif (volume_ok and event["close"] < val - breakout_buf and abs(vwap - val) <= vwap_prox
                and _accepted_beyond(window, val, -1)):
            side, hits = -1, ["BREAKOUT@VAL"]

    if side == 0:
        return _wait(f"No setup (val={val:.2f}, vah={vah:.2f}, vwap={vwap:.2f})")

    signal = "BUY" if side > 0 else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")

    sl_buffer = atr * float(c["SL_BUFFER_ATR"])
    entry = round(event["close"], 2)
    is_fade = hits[0].startswith("FADE")
    if side > 0:
        if is_fade:
            anchor = event["low"]
        else:
            anchor = min(b["low"] for b in bars[-acceptance_bars:])
        sl = round(min(anchor, val) - sl_buffer if is_fade else anchor - sl_buffer, 2)
    else:
        if is_fade:
            anchor = event["high"]
        else:
            anchor = max(b["high"] for b in bars[-acceptance_bars:])
        sl = round(max(anchor, vah) + sl_buffer if is_fade else anchor + sl_buffer, 2)

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
        "pattern": f"S419 {signal} Orochi {hits[0]} {rr:g}R",
        "reason": f"{hits[0]} val={val:.2f} vah={vah:.2f} poc={va['poc']:.2f} vwap={vwap:.2f}",
        "be_rr": float(c["BE_RR"]),
        "cancel_bars": int(c["CANCEL_BARS"]),
    }
