import time as _time

import MetaTrader5 as mt5

import config
from strategy4 import _find_prev_pivot_swing_high, _find_prev_pivot_swing_low

_s12_state = {
    "side": None,              # "BUY" | "SELL" | None
    "order_count": 0,          # orders opened in the current zone
    "last_entry_price": None,  # entry price of the latest S12 order
    "tickets": [],             # active S12 position tickets
    "last_sl_time": 0.0,       # latest timestamp when an S12 position hit SL
}


def _s12_get_raw_extremes(bars):
    return (
        max(float(r["high"]) for r in bars),
        min(float(r["low"]) for r in bars),
    )


def s12_get_swing_context(rates, lookback: int):
    """Return both pivot range and active display range for S12.

    - pivot_* keeps the confirmed pivot anchors
    - active_* can move early after a breakout to avoid stale zones
    """
    if rates is None or len(rates) == 0:
        return None

    n = min(max(1, int(lookback)), len(rates))
    bars = rates[-n:]
    left = max(1, int(getattr(config, "SWING_PIVOT_LEFT", 15) or 15))
    right = max(1, int(getattr(config, "SWING_PIVOT_RIGHT", 10) or 10))

    sh_info = _find_prev_pivot_swing_high(bars, lookback=n, left=left, right=right)
    sl_info = _find_prev_pivot_swing_low(bars, lookback=n, left=left, right=right)
    raw_high, raw_low = _s12_get_raw_extremes(bars)

    pivot_high = float(sh_info["price"]) if sh_info else raw_high
    pivot_low = float(sl_info["price"]) if sl_info else raw_low
    active_high = pivot_high
    active_low = pivot_low

    # Keep the provisional breakout range sticky until a new confirmed pivot
    # replaces it. If raw extremes already extend beyond the confirmed pivot
    # anchors, use those active extremes instead of snapping back on the next bar.
    if raw_high > pivot_high:
        active_high = raw_high
    if raw_low < pivot_low:
        active_low = raw_low

    return {
        "pivot_swing_high": pivot_high,
        "pivot_swing_low": pivot_low,
        "active_swing_high": active_high,
        "active_swing_low": active_low,
        "raw_high": raw_high,
        "raw_low": raw_low,
    }


def s12_get_swing(rates, lookback: int):
    """Return the active S12 swing high/low from M5 rates."""
    context = s12_get_swing_context(rates, lookback)
    if not context:
        return None, None
    return context["active_swing_high"], context["active_swing_low"]


def s12_get_zone_levels(rates, lookback: int, zone_dist: float):
    """Return the current S12 range/zone levels used by both bot and MQ5."""
    context = s12_get_swing_context(rates, lookback)
    if not context:
        return None
    swing_high = context["active_swing_high"]
    swing_low = context["active_swing_low"]
    return {
        "pivot_swing_high": context["pivot_swing_high"],
        "pivot_swing_low": context["pivot_swing_low"],
        "swing_high": swing_high,
        "swing_low": swing_low,
        "buy_zone_bot": swing_low,
        "buy_zone_top": swing_low + float(zone_dist),
        "sell_zone_bot": swing_high - float(zone_dist),
        "sell_zone_top": swing_high,
    }


def s12_get_tp(rates_m15, direction: str):
    """Return TP from M15 pivot swing first, then fallback to raw range."""
    if rates_m15 is None or len(rates_m15) < 5:
        return None

    n = min(max(50, int(getattr(config, "S12_LOOKBACK", 100) or 100) // 2), len(rates_m15))
    bars = rates_m15[-n:]
    left = max(1, int(getattr(config, "SWING_PIVOT_LEFT", 15) or 15))
    right = max(1, int(getattr(config, "SWING_PIVOT_RIGHT", 10) or 10))

    if direction == "BUY":
        sh_info = _find_prev_pivot_swing_high(bars, lookback=n, left=left, right=right)
        return float(sh_info["price"]) if sh_info else max(float(r["high"]) for r in bars)

    sl_info = _find_prev_pivot_swing_low(bars, lookback=n, left=left, right=right)
    return float(sl_info["price"]) if sl_info else min(float(r["low"]) for r in bars)


def s12_cleanup_tickets():
    """Remove closed S12 tickets from state and track the latest SL time."""
    if not _s12_state["tickets"]:
        return

    open_tickets = {p.ticket for p in (mt5.positions_get(symbol=config.SYMBOL) or [])}
    closed = [t for t in _s12_state["tickets"] if t not in open_tickets]
    _s12_state["tickets"] = [t for t in _s12_state["tickets"] if t in open_tickets]

    if closed:
        for t in closed:
            deals = mt5.history_deals_get(position=t)
            if deals:
                close_deal = sorted(deals, key=lambda d: d.time)[-1]
                if getattr(close_deal, "reason", -1) == mt5.DEAL_REASON_SL:
                    _s12_state["last_sl_time"] = _time.time()
                    break

    if not _s12_state["tickets"]:
        _s12_state["side"] = None
        _s12_state["order_count"] = 0
        _s12_state["last_entry_price"] = None
