# -*- coding: utf-8 -*-
"""EA Strategy 2 - Thirakorn SMC v2 ported from ``Thirakorn_SMC (16).mq5``.

The source EA is hard-wired to M1.  For research, this port applies the same
bar logic to whichever timeframe is supplied by the runner.  Signals are
evaluated after a bar closes and market entries are placed at the next bar's
open, matching the EA's ``IsNewBar()`` flow.

The port intentionally keeps the source defaults: fractal(2), CHoCH/BOS,
BOS-created order-block retests, 200/600-point SL/TP, 08:00-22:00 session,
breakeven at 150 points (+10 points), and trailing from 200 points at a
300-point distance.  Liquidity sweeps are tracked for parity with the EA but
are descriptive only; the source does not gate entries with them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


BKK = timezone(timedelta(hours=7))
POINT = 0.01

DEFAULT_CFG = {
    "POINT": POINT,
    "SL_POINTS": 200,
    "TP_POINTS": 600,
    "USE_BREAKEVEN": True,
    "BREAKEVEN_TRIGGER_POINTS": 150,
    "BREAKEVEN_LOCK_POINTS": 10,
    "USE_TRAILING": True,
    "TRAIL_TRIGGER_POINTS": 200,
    "TRAIL_DISTANCE_POINTS": 300,
    "TRAIL_STEP_POINTS": 10,
    "SWING_BARS": 2,
    "BOS_CONFIRM_COUNT": 1,
    "MAX_BARS_LOOKBACK": 500,
    "ONE_TRADE_PER_CYCLE": True,
    "ENTER_ON_BOS_CONFIRM": False,
    "USE_FIB_OB_FILTER": True,
    "OB_SEARCH_MAX_BARS": 20,
    "ENABLE_OB_RETEST_ENTRY": True,
    "OB_MIN_BARS_BEFORE_RETEST": 3,
    "MIN_LEG_POINTS": 100,
    "OB_MAX_BARS_VALID": 50,
    "OB_PREFER_DEEPER_MAX_POINTS": 300,
    "MAX_OPEN_POSITIONS": 2,
    "USE_LIQUIDITY_SWEEP": True,
    "SWEEP_VALID_BARS": 15,
    "SESSION_START_HOUR": 8,
    "SESSION_END_HOUR": 22,
    # Enhanced controls are opt-in so the original MQ5 parity backtest remains
    # reproducible.  The live adapter enables only the controls configured in
    # config.py.
    "REQUIRE_LIQUIDITY_SWEEP": False,
    "STRICT_ONE_ENTRY_PER_LEG": False,
    "USE_ATR_STOPS": False,
    "ATR_PERIOD": 14,
    "ATR_SL_MULT": 1.5,
    "ATR_BUFFER_MULT": 0.25,
    "ATR_MIN_SL_POINTS": 120,
    "ATR_MAX_SL_POINTS": 600,
    "ATR_RR": 3.0,
    "MAX_SPREAD_POINTS": 0,
    "SLIPPAGE_POINTS": 0,
    "COMMISSION_PER_LOT_USD": 0.0,
    "TIMEFRAME_SECONDS": 60,
}


@dataclass
class OrderBlock:
    high: float
    low: float
    bullish: bool
    active: bool
    in_zone: bool
    created_bar: int
    created_time: int
    from_choch: bool
    fib50: float


@dataclass
class Position:
    direction: int
    entry: float
    sl: float
    initial_sl: float
    tp: float
    entry_bar: int
    reason: str


def _value(bar: Any, key: str) -> float:
    return float(bar[key])


def _bar_time_chart(raw_time: int) -> datetime:
    # The source gates entries in intended Thai time (UTC+7), not chart time.
    return datetime.fromtimestamp(int(raw_time), tz=BKK)


def _in_session(raw_time: int, start_hour: int, end_hour: int) -> bool:
    hour = _bar_time_chart(raw_time).hour
    if start_hour <= end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def _is_swing_high(highs, index: int, width: int) -> bool:
    h = highs[index]
    return all(highs[index - k] <= h and highs[index + k] <= h for k in range(1, width + 1))


def _is_swing_low(lows, index: int, width: int) -> bool:
    low = lows[index]
    return all(lows[index - k] >= low and lows[index + k] >= low for k in range(1, width + 1))


def _initial_swings(highs, lows, times, start_bar: int, width: int, lookback: int):
    # ``start_bar`` is the latest closed bar (MQ5 shift=1).  Source startup
    # scans shift=lookback..width+1, whose chronological indices are therefore
    # start-lookback+1 .. start-width inclusive.
    lo = max(width, start_bar - lookback + 1)
    hi = start_bar - width + 1
    swing_highs = []
    swing_lows = []
    for i in range(lo, hi):
        if _is_swing_high(highs, i, width):
            swing_highs.insert(0, (highs[i], int(times[i]), i))
        if _is_swing_low(lows, i, width):
            swing_lows.insert(0, (lows[i], int(times[i]), i))
    return swing_highs[:300], swing_lows[:300]


def _path_points(o: float, h: float, low: float, c: float):
    """Deterministic OHLC path used only to model tick-managed stops."""
    return (o, low, h, c) if c >= o else (o, h, low, c)


def _atr_series(highs, lows, closes, period: int):
    """Return a Wilder-style rolling ATR without third-party dependencies."""
    out = [0.0] * len(closes)
    trs = []
    for i in range(len(closes)):
        prev = closes[i - 1] if i else closes[i]
        tr = max(highs[i] - lows[i], abs(highs[i] - prev), abs(lows[i] - prev))
        trs.append(tr)
        lo = max(0, i - period + 1)
        out[i] = sum(trs[lo:i + 1]) / (i - lo + 1)
    return out


LIVE_STATE_VERSION = 2


def new_live_state(bars_raw, cfg=None):
    """Build the same transient state that the MQ5 EA creates in ``OnInit``.

    Historical bars seed only the fractal lists/reference levels.  CHoCH, BOS
    and order blocks are not replayed, matching the source EA after restart.
    """
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    bars = list(bars_raw)
    width = int(c["SWING_BARS"])
    if len(bars) < int(c["MAX_BARS_LOOKBACK"]) + width * 2 + 2:
        raise ValueError("not enough bars to initialize EA2")
    highs = [_value(bar, "high") for bar in bars]
    lows = [_value(bar, "low") for bar in bars]
    times = [int(bar["time"]) for bar in bars]
    first_live_bar = len(bars) - 1
    swing_highs, swing_lows = _initial_swings(
        highs, lows, times, first_live_bar, width, int(c["MAX_BARS_LOOKBACK"])
    )
    return {
        "version": LIVE_STATE_VERSION,
        "last_bar_time": 0,
        "trend": 0,
        "awaiting_confirm": False,
        "bos_count": 0,
        "entry_done_cycle": False,
        "ref_high": swing_highs[0][0] if swing_highs else 0.0,
        "ref_low": swing_lows[0][0] if swing_lows else 0.0,
        "last_bull_ob_low": 0.0,
        "last_bear_ob_high": 0.0,
        "swing_highs": [[price, raw_time] for price, raw_time, _ in swing_highs],
        "swing_lows": [[price, raw_time] for price, raw_time, _ in swing_lows],
        "order_blocks": [],
        "sweep_bear_bars_ago": 9999,
        "sweep_bull_bars_ago": 9999,
        "pending_events": [],
    }


def advance_live_state(bars_raw, state, cfg=None):
    """Advance persistent EA2 state using each newly closed M1 bar once."""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    bars = list(bars_raw)
    if not bars:
        return state, []
    opens = [_value(bar, "open") for bar in bars]
    highs = [_value(bar, "high") for bar in bars]
    lows = [_value(bar, "low") for bar in bars]
    closes = [_value(bar, "close") for bar in bars]
    times = [int(bar["time"]) for bar in bars]
    width = int(c["SWING_BARS"])
    point = float(c["POINT"])

    if not isinstance(state, dict) or int(state.get("version", 0)) != LIVE_STATE_VERSION:
        state = new_live_state(bars, c)
    last_bar_time = int(state.get("last_bar_time", 0) or 0)
    if last_bar_time and (last_bar_time > times[-1] or last_bar_time < times[0]):
        state = new_live_state(bars, c)
        last_bar_time = 0
    indices = [i for i, raw_time in enumerate(times) if raw_time > last_bar_time]
    if not last_bar_time:
        indices = [len(bars) - 1]

    events = []
    swing_highs = [list(item[:2]) for item in state.get("swing_highs", [])]
    swing_lows = [list(item[:2]) for item in state.get("swing_lows", [])]
    obs = [dict(item) for item in state.get("order_blocks", [])]

    def add_swing(items, price, raw_time):
        if any(int(item[1]) == int(raw_time) for item in items):
            return
        items.insert(0, [float(price), int(raw_time)])
        del items[300:]

    def find_ob_candle(bullish: bool, event_bar: int):
        stop = max(-1, event_bar - int(c["OB_SEARCH_MAX_BARS"]) - 1)
        for idx in range(event_bar, stop, -1):
            if bullish and closes[idx] < opens[idx]:
                return idx
            if not bullish and closes[idx] > opens[idx]:
                return idx
        return -1

    def create_ob(bullish: bool, event_bar: int, break_level: float, is_choch: bool):
        ob_idx = find_ob_candle(bullish, event_bar)
        if ob_idx < 0:
            return
        ob_high, ob_low = highs[ob_idx], lows[ob_idx]
        if bullish:
            leg_origin = min([ob_low] + lows[ob_idx + 1:event_bar + 1])
            if not is_choch and float(c["MIN_LEG_POINTS"]) > 0 and break_level - leg_origin < float(c["MIN_LEG_POINTS"]) * point:
                return
            fib50 = leg_origin + (break_level - leg_origin) * 0.5
            if not is_choch and bool(c["USE_FIB_OB_FILTER"]) and ob_low > fib50:
                return
        else:
            leg_origin = max([ob_high] + highs[ob_idx + 1:event_bar + 1])
            if not is_choch and float(c["MIN_LEG_POINTS"]) > 0 and leg_origin - break_level < float(c["MIN_LEG_POINTS"]) * point:
                return
            fib50 = leg_origin - (leg_origin - break_level) * 0.5
            if not is_choch and bool(c["USE_FIB_OB_FILTER"]) and ob_high < fib50:
                return
        if len(obs) >= 200:
            obs.pop(0)
        obs.append({
            "high": ob_high, "low": ob_low, "bullish": bullish,
            "active": True, "in_zone": False,
            "created_time": times[event_bar], "from_choch": is_choch,
            "fib50": fib50,
        })
        if bullish:
            state["last_bull_ob_low"] = ob_low
        else:
            state["last_bear_ob_high"] = ob_high

    def trigger_choch(bullish: bool, event_bar: int, break_level: float):
        state["trend"] = 1 if bullish else -1
        state["bos_count"] = 0
        state["awaiting_confirm"] = True
        state["entry_done_cycle"] = False
        create_ob(bullish, event_bar, break_level, True)
        state["ref_high" if bullish else "ref_low"] = 0.0

    for m in indices:
        # The latest closed bar is MQ5 shift=1, so shift=width+1 maps to
        # ``m-width`` in this chronological closed-bar array.
        candidate = m - width
        if candidate >= width and candidate + width < len(bars):
            if _is_swing_high(highs, candidate, width):
                add_swing(swing_highs, highs[candidate], times[candidate])
                if float(state.get("ref_high", 0.0) or 0.0) <= 0:
                    state["ref_high"] = highs[candidate]
            if _is_swing_low(lows, candidate, width):
                add_swing(swing_lows, lows[candidate], times[candidate])
                if float(state.get("ref_low", 0.0) or 0.0) <= 0:
                    state["ref_low"] = lows[candidate]

        if bool(c["USE_LIQUIDITY_SWEEP"]):
            state["sweep_bear_bars_ago"] = int(state.get("sweep_bear_bars_ago", 9999)) + 1
            state["sweep_bull_bars_ago"] = int(state.get("sweep_bull_bars_ago", 9999)) + 1
            if swing_highs and highs[m] > swing_highs[0][0] and closes[m] < swing_highs[0][0]:
                state["sweep_bear_bars_ago"] = 0
            if swing_lows and lows[m] < swing_lows[0][0] and closes[m] > swing_lows[0][0]:
                state["sweep_bull_bars_ago"] = 0

        trend = int(state.get("trend", 0))
        if trend != 1:
            guard = float(state.get("last_bear_ob_high", 0.0) or state.get("ref_high", 0.0) or 0.0)
            if guard > 0 and closes[m] > guard:
                trigger_choch(True, m, guard)
        trend = int(state.get("trend", 0))
        if trend != -1:
            guard = float(state.get("last_bull_ob_low", 0.0) or state.get("ref_low", 0.0) or 0.0)
            if guard > 0 and closes[m] < guard:
                trigger_choch(False, m, guard)

        trend = int(state.get("trend", 0))
        ref_high = float(state.get("ref_high", 0.0) or 0.0)
        if trend == 1 and ref_high > 0 and closes[m] > ref_high:
            state["bos_count"] = int(state.get("bos_count", 0)) + 1
            create_ob(True, m, ref_high, False)
            if bool(state.get("awaiting_confirm")) and int(state["bos_count"]) >= int(c["BOS_CONFIRM_COUNT"]):
                state["awaiting_confirm"] = False
                if bool(c["ENTER_ON_BOS_CONFIRM"]) and (not bool(state.get("entry_done_cycle")) or not bool(c["ONE_TRADE_PER_CYCLE"])):
                    events.append({"bar_time": times[m], "signal": "BUY", "reason": "BOS confirm"})
                    state["entry_done_cycle"] = True
            state["ref_high"] = 0.0
        ref_low = float(state.get("ref_low", 0.0) or 0.0)
        if trend == -1 and ref_low > 0 and closes[m] < ref_low:
            state["bos_count"] = int(state.get("bos_count", 0)) + 1
            create_ob(False, m, ref_low, False)
            if bool(state.get("awaiting_confirm")) and int(state["bos_count"]) >= int(c["BOS_CONFIRM_COUNT"]):
                state["awaiting_confirm"] = False
                if bool(c["ENTER_ON_BOS_CONFIRM"]) and (not bool(state.get("entry_done_cycle")) or not bool(c["ONE_TRADE_PER_CYCLE"])):
                    events.append({"bar_time": times[m], "signal": "SELL", "reason": "BOS confirm"})
                    state["entry_done_cycle"] = True
            state["ref_low"] = 0.0

        if bool(c["ENABLE_OB_RETEST_ENTRY"]) and int(state.get("trend", 0)) != 0:
            prefer_range = float(c["OB_PREFER_DEEPER_MAX_POINTS"]) * point
            for i, ob in enumerate(obs):
                if not ob.get("active") or ob.get("from_choch"):
                    continue
                timeframe_seconds = max(1, int(c.get("TIMEFRAME_SECONDS", 60)))
                age = (times[m] - int(ob["created_time"])) // timeframe_seconds
                if int(c["OB_MAX_BARS_VALID"]) > 0 and age > int(c["OB_MAX_BARS_VALID"]):
                    ob["active"] = False
                    continue
                if age < int(c["OB_MIN_BARS_BEFORE_RETEST"]):
                    continue
                if int(state["trend"]) == 1 and not ob["bullish"]:
                    continue
                if int(state["trend"]) == -1 and ob["bullish"]:
                    continue
                touching = lows[m] <= float(ob["high"]) and highs[m] >= float(ob["low"])
                reached_fib = lows[m] <= float(ob["fib50"]) if ob["bullish"] else highs[m] >= float(ob["fib50"])
                if not touching or not reached_fib:
                    ob["in_zone"] = False
                    continue
                prefer_idx = i
                for j, other in enumerate(obs):
                    if j == i or not other.get("active") or other.get("from_choch") or other["bullish"] != ob["bullish"]:
                        continue
                    other_age = (times[m] - int(other["created_time"])) // 60
                    if int(c["OB_MAX_BARS_VALID"]) > 0 and other_age > int(c["OB_MAX_BARS_VALID"]):
                        other["active"] = False
                        continue
                    if other_age < int(c["OB_MIN_BARS_BEFORE_RETEST"]):
                        continue
                    other_touch = lows[m] <= float(other["high"]) and highs[m] >= float(other["low"])
                    other_fib = lows[m] <= float(other["fib50"]) if other["bullish"] else highs[m] >= float(other["fib50"])
                    if not other_touch or not other_fib:
                        continue
                    chosen = obs[prefer_idx]
                    if int(state["trend"]) == 1 and float(other["low"]) < float(chosen["low"]) and float(chosen["low"]) - float(other["low"]) <= prefer_range:
                        prefer_idx = j
                    elif int(state["trend"]) == -1 and float(other["high"]) > float(chosen["high"]) and float(other["high"]) - float(chosen["high"]) <= prefer_range:
                        prefer_idx = j
                if prefer_idx != i:
                    ob["in_zone"] = True
                    continue
                if not ob.get("in_zone"):
                    if bool(c["STRICT_ONE_ENTRY_PER_LEG"]) and bool(state.get("entry_done_cycle")):
                        ob["active"] = False
                        ob["in_zone"] = True
                        continue
                    lq = (
                        ob["bullish"] and int(state.get("sweep_bull_bars_ago", 9999)) <= int(c["SWEEP_VALID_BARS"])
                    ) or (
                        not ob["bullish"] and int(state.get("sweep_bear_bars_ago", 9999)) <= int(c["SWEEP_VALID_BARS"])
                    )
                    events.append({
                        "bar_time": times[m],
                        "signal": "BUY" if ob["bullish"] else "SELL",
                        "reason": "OB retest" + (" + LQ" if lq else ""),
                    })
                    if bool(c["STRICT_ONE_ENTRY_PER_LEG"]):
                        state["entry_done_cycle"] = True
                    ob["active"] = False
                ob["in_zone"] = touching
        state["last_bar_time"] = times[m]

    state["swing_highs"] = swing_highs
    state["swing_lows"] = swing_lows
    state["order_blocks"] = obs[-200:]
    return state, events


def run_backtest(
    bars_raw, cfg=None, spread=0.20, contract_multiplier=1.0,
    start_bar=None, entry_filter=None,
):
    """Run EA2 and return ``(closed_trades, extra_stats)``.

    ``bars_raw`` must be chronological MT5 rates.  ``start_bar`` identifies the
    first research-period bar; earlier bars are used only to seed fractals.
    """
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    bars = list(bars_raw)
    n = len(bars)
    width = int(c["SWING_BARS"])
    if start_bar is None:
        start_bar = max(int(c["MAX_BARS_LOOKBACK"]) + width + 2, width * 2 + 5)
    start_bar = int(start_bar)
    if n <= start_bar + 2:
        return [], {"error": "not enough bars", "entries": 0, "open_positions": 0}

    opens = [_value(b, "open") for b in bars]
    highs = [_value(b, "high") for b in bars]
    lows = [_value(b, "low") for b in bars]
    closes = [_value(b, "close") for b in bars]
    times = [int(b["time"]) for b in bars]
    atrs = _atr_series(highs, lows, closes, max(1, int(c["ATR_PERIOD"])))
    adjacent_seconds = [times[i] - times[i - 1] for i in range(1, n) if times[i] > times[i - 1]]
    timeframe_seconds = min(adjacent_seconds) if adjacent_seconds else 60

    point = float(c["POINT"])
    sl_dist = float(c["SL_POINTS"]) * point
    tp_dist = float(c["TP_POINTS"]) * point
    max_positions = int(c["MAX_OPEN_POSITIONS"])

    swing_highs, swing_lows = _initial_swings(
        highs, lows, times, start_bar, width, int(c["MAX_BARS_LOOKBACK"])
    )
    ref_high = swing_highs[0][0] if swing_highs else 0.0
    ref_low = swing_lows[0][0] if swing_lows else 0.0
    trend = 0
    awaiting_confirm = False
    bos_count = 0
    entry_done_cycle = False
    last_bull_ob_low = 0.0
    last_bear_ob_high = 0.0
    obs: list[OrderBlock] = []
    positions: list[Position] = []
    trades = []
    entries = 0
    signal_counts = {"choch_up": 0, "choch_down": 0, "bos_up": 0, "bos_down": 0, "retest": 0}
    sweep_bear_bars_ago = 9999
    sweep_bull_bars_ago = 9999

    def close_position(pos: Position, bar_index: int, price: float, outcome: str):
        inferred_lot = contract_multiplier / 100.0
        commission = float(c["COMMISSION_PER_LOT_USD"]) * inferred_lot
        profit = pos.direction * (price - pos.entry) * contract_multiplier - commission
        trades.append({
            "entry_bar": pos.entry_bar,
            "exit_bar": bar_index,
            "direction": "BUY" if pos.direction > 0 else "SELL",
            "entry": round(pos.entry, 2),
            "sl": round(pos.initial_sl, 2),
            "tp": round(pos.tp, 2),
            "exit_price": round(price, 2),
            "outcome": outcome,
            "profit": round(profit, 2),
            "pattern": "EA2 Thirakorn SMC v2",
            "reason": pos.reason,
        })

    def manage_position(pos: Position, bar_index: int) -> bool:
        # MT5 OHLC is treated as Bid.  BUY executes at Ask and is managed on Bid;
        # SELL executes at Bid and is managed on Ask.
        shift = 0.0 if pos.direction > 0 else spread
        pts = [p + shift for p in _path_points(opens[bar_index], highs[bar_index], lows[bar_index], closes[bar_index])]
        cur = pts[0]

        # Handle opening gaps conservatively at the first executable price.
        if pos.direction > 0:
            if cur <= pos.sl:
                close_position(pos, bar_index, cur, "SL_GAP")
                return True
            if cur >= pos.tp:
                close_position(pos, bar_index, pos.tp, "TP")
                return True
        else:
            if cur >= pos.sl:
                close_position(pos, bar_index, cur, "SL_GAP")
                return True
            if cur <= pos.tp:
                close_position(pos, bar_index, pos.tp, "TP")
                return True

        for nxt in pts[1:]:
            favorable = (pos.direction > 0 and nxt > cur) or (pos.direction < 0 and nxt < cur)
            if favorable:
                tp_hit = nxt >= pos.tp if pos.direction > 0 else nxt <= pos.tp
                if tp_hit:
                    close_position(pos, bar_index, pos.tp, "TP")
                    return True
                profit_points = pos.direction * (nxt - pos.entry) / point
                best_sl = pos.sl
                if bool(c["USE_BREAKEVEN"]) and profit_points >= float(c["BREAKEVEN_TRIGGER_POINTS"]):
                    candidate = pos.entry + pos.direction * float(c["BREAKEVEN_LOCK_POINTS"]) * point
                    best_sl = max(best_sl, candidate) if pos.direction > 0 else min(best_sl, candidate)
                if bool(c["USE_TRAILING"]) and profit_points >= float(c["TRAIL_TRIGGER_POINTS"]):
                    candidate = nxt - pos.direction * float(c["TRAIL_DISTANCE_POINTS"]) * point
                    best_sl = max(best_sl, candidate) if pos.direction > 0 else min(best_sl, candidate)
                step = float(c["TRAIL_STEP_POINTS"]) * point
                if (pos.direction > 0 and best_sl > pos.sl + step) or (pos.direction < 0 and best_sl < pos.sl - step):
                    pos.sl = best_sl
            else:
                sl_hit = nxt <= pos.sl if pos.direction > 0 else nxt >= pos.sl
                if sl_hit:
                    close_position(pos, bar_index, pos.sl, "SL" if pos.sl == pos.initial_sl else "TRAIL")
                    return True
            cur = nxt
        return False

    entry_events = []

    def queue_entry(buy: bool, event_bar: int, reason: str, structure_level: float = 0.0):
        nonlocal entries
        entry_bar = event_bar + 1
        if entry_bar >= n or len(positions) >= max_positions:
            return False
        if entry_filter is not None and not entry_filter(buy, event_bar, times[event_bar]):
            return False
        if not _in_session(times[entry_bar], int(c["SESSION_START_HOUR"]), int(c["SESSION_END_HOUR"])):
            return False
        direction = 1 if buy else -1
        slippage = float(c["SLIPPAGE_POINTS"]) * point
        entry = opens[entry_bar] + (spread if buy else 0.0) + direction * slippage
        used_sl_dist = sl_dist
        if bool(c["USE_ATR_STOPS"]):
            atr = max(atrs[event_bar], point)
            used_sl_dist = atr * float(c["ATR_SL_MULT"])
            used_sl_dist = max(used_sl_dist, float(c["ATR_MIN_SL_POINTS"]) * point)
            used_sl_dist = min(used_sl_dist, float(c["ATR_MAX_SL_POINTS"]) * point)
            if structure_level > 0:
                structural = abs(entry - (structure_level - direction * atr * float(c["ATR_BUFFER_MULT"])))
                used_sl_dist = min(max(used_sl_dist, structural), float(c["ATR_MAX_SL_POINTS"]) * point)
        sl = entry - direction * used_sl_dist
        used_tp_dist = used_sl_dist * float(c["ATR_RR"]) if bool(c["USE_ATR_STOPS"]) else tp_dist
        tp = entry + direction * used_tp_dist
        positions.append(Position(direction, entry, sl, sl, tp, entry_bar, reason))
        entry_events.append({
            "event_bar": event_bar,
            "entry_bar": entry_bar,
            "signal": "BUY" if buy else "SELL",
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "reason": reason,
            "atr": atrs[event_bar],
        })
        entries += 1
        return True

    def find_ob_candle(bullish: bool, event_bar: int):
        stop = max(-1, event_bar - int(c["OB_SEARCH_MAX_BARS"]) - 1)
        for idx in range(event_bar, stop, -1):
            if bullish and closes[idx] < opens[idx]:
                return idx
            if not bullish and closes[idx] > opens[idx]:
                return idx
        return -1

    def create_ob(bullish: bool, event_bar: int, break_level: float, is_choch: bool):
        nonlocal last_bull_ob_low, last_bear_ob_high
        ob_idx = find_ob_candle(bullish, event_bar)
        if ob_idx < 0:
            return -1
        ob_high, ob_low = highs[ob_idx], lows[ob_idx]
        if bullish:
            leg_origin = min([ob_low] + lows[ob_idx + 1:event_bar + 1])
            if not is_choch and float(c["MIN_LEG_POINTS"]) > 0 and break_level - leg_origin < float(c["MIN_LEG_POINTS"]) * point:
                return -1
            fib50 = leg_origin + (break_level - leg_origin) * 0.5
            if not is_choch and bool(c["USE_FIB_OB_FILTER"]) and ob_low > fib50:
                return -1
        else:
            leg_origin = max([ob_high] + highs[ob_idx + 1:event_bar + 1])
            if not is_choch and float(c["MIN_LEG_POINTS"]) > 0 and leg_origin - break_level < float(c["MIN_LEG_POINTS"]) * point:
                return -1
            fib50 = leg_origin - (leg_origin - break_level) * 0.5
            if not is_choch and bool(c["USE_FIB_OB_FILTER"]) and ob_high < fib50:
                return -1
        if len(obs) >= 200:
            obs.pop(0)
        obs.append(OrderBlock(ob_high, ob_low, bullish, True, False, event_bar, times[event_bar], is_choch, fib50))
        if bullish:
            last_bull_ob_low = ob_low
        else:
            last_bear_ob_high = ob_high
        return len(obs) - 1

    def trigger_choch(bullish: bool, event_bar: int, break_level: float):
        nonlocal trend, awaiting_confirm, bos_count, entry_done_cycle, ref_high, ref_low
        trend = 1 if bullish else -1
        awaiting_confirm = True
        bos_count = 0
        entry_done_cycle = False
        signal_counts["choch_up" if bullish else "choch_down"] += 1
        create_ob(bullish, event_bar, break_level, True)
        if bullish:
            ref_high = 0.0
        else:
            ref_low = 0.0

    for m in range(start_bar, n - 1):
        if positions:
            positions = [pos for pos in positions if not manage_position(pos, m)]

        # ``m`` represents MQ5 shift=1; shift=SwingBars+1 is ``m-width`` in a
        # chronological array that excludes the still-forming bar.
        candidate = m - width
        if candidate >= width and candidate + width < n:
            if _is_swing_high(highs, candidate, width) and all(t != times[candidate] for _, t, _ in swing_highs):
                swing_highs.insert(0, (highs[candidate], times[candidate], candidate))
                swing_highs = swing_highs[:300]
                if ref_high <= 0:
                    ref_high = highs[candidate]
            if _is_swing_low(lows, candidate, width) and all(t != times[candidate] for _, t, _ in swing_lows):
                swing_lows.insert(0, (lows[candidate], times[candidate], candidate))
                swing_lows = swing_lows[:300]
                if ref_low <= 0:
                    ref_low = lows[candidate]

        if bool(c["USE_LIQUIDITY_SWEEP"]):
            sweep_bear_bars_ago += 1
            sweep_bull_bars_ago += 1
            if swing_highs and highs[m] > swing_highs[0][0] and closes[m] < swing_highs[0][0]:
                sweep_bear_bars_ago = 0
            if swing_lows and lows[m] < swing_lows[0][0] and closes[m] > swing_lows[0][0]:
                sweep_bull_bars_ago = 0

        if trend != 1:
            guard = last_bear_ob_high if last_bear_ob_high > 0 else ref_high
            if guard > 0 and closes[m] > guard:
                trigger_choch(True, m, guard)
        if trend != -1:
            guard = last_bull_ob_low if last_bull_ob_low > 0 else ref_low
            if guard > 0 and closes[m] < guard:
                trigger_choch(False, m, guard)

        if trend == 1 and ref_high > 0 and closes[m] > ref_high:
            broken = ref_high
            bos_count += 1
            signal_counts["bos_up"] += 1
            create_ob(True, m, broken, False)
            if awaiting_confirm and bos_count >= int(c["BOS_CONFIRM_COUNT"]):
                awaiting_confirm = False
                if bool(c["ENTER_ON_BOS_CONFIRM"]) and (not entry_done_cycle or not bool(c["ONE_TRADE_PER_CYCLE"])):
                    if queue_entry(True, m, "BOS confirm"):
                        entry_done_cycle = True
            ref_high = 0.0
        if trend == -1 and ref_low > 0 and closes[m] < ref_low:
            broken = ref_low
            bos_count += 1
            signal_counts["bos_down"] += 1
            create_ob(False, m, broken, False)
            if awaiting_confirm and bos_count >= int(c["BOS_CONFIRM_COUNT"]):
                awaiting_confirm = False
                if bool(c["ENTER_ON_BOS_CONFIRM"]) and (not entry_done_cycle or not bool(c["ONE_TRADE_PER_CYCLE"])):
                    if queue_entry(False, m, "BOS confirm"):
                        entry_done_cycle = True
            ref_low = 0.0

        if not bool(c["ENABLE_OB_RETEST_ENTRY"]) or trend == 0:
            continue
        prefer_range = float(c["OB_PREFER_DEEPER_MAX_POINTS"]) * point
        for i, ob in enumerate(obs):
            if not ob.active or ob.from_choch:
                continue
            # The MQ5 source divides wall-clock age by PeriodSeconds(), so a
            # weekend also ages the zone.  Preserve that behavior exactly.
            bars_since = (times[m] - ob.created_time) // timeframe_seconds
            if int(c["OB_MAX_BARS_VALID"]) > 0 and bars_since > int(c["OB_MAX_BARS_VALID"]):
                ob.active = False
                continue
            if bars_since < int(c["OB_MIN_BARS_BEFORE_RETEST"]):
                continue
            if trend == 1 and not ob.bullish:
                continue
            if trend == -1 and ob.bullish:
                continue
            touching = lows[m] <= ob.high and highs[m] >= ob.low
            reached_fib = lows[m] <= ob.fib50 if ob.bullish else highs[m] >= ob.fib50
            if not touching or not reached_fib:
                ob.in_zone = False
                continue
            prefer_idx = i
            for j, other in enumerate(obs):
                if j == i or not other.active or other.from_choch or other.bullish != ob.bullish:
                    continue
                other_age = (times[m] - other.created_time) // timeframe_seconds
                if int(c["OB_MAX_BARS_VALID"]) > 0 and other_age > int(c["OB_MAX_BARS_VALID"]):
                    other.active = False
                    continue
                if other_age < int(c["OB_MIN_BARS_BEFORE_RETEST"]):
                    continue
                other_touch = lows[m] <= other.high and highs[m] >= other.low
                other_fib = lows[m] <= other.fib50 if other.bullish else highs[m] >= other.fib50
                if not other_touch or not other_fib:
                    continue
                chosen = obs[prefer_idx]
                if trend == 1 and other.low < chosen.low and chosen.low - other.low <= prefer_range:
                    prefer_idx = j
                elif trend == -1 and other.high > chosen.high and other.high - chosen.high <= prefer_range:
                    prefer_idx = j
            if prefer_idx != i:
                ob.in_zone = True
                continue
            if not ob.in_zone:
                if bool(c["STRICT_ONE_ENTRY_PER_LEG"]) and entry_done_cycle:
                    ob.active = False
                    ob.in_zone = True
                    continue
                lq = ((ob.bullish and sweep_bull_bars_ago <= int(c["SWEEP_VALID_BARS"])) or
                      (not ob.bullish and sweep_bear_bars_ago <= int(c["SWEEP_VALID_BARS"])))
                if bool(c["REQUIRE_LIQUIDITY_SWEEP"]) and not lq:
                    ob.in_zone = True
                    continue
                structure_level = ob.low if ob.bullish else ob.high
                if queue_entry(ob.bullish, m, "OB retest" + (" + LQ" if lq else ""), structure_level):
                    signal_counts["retest"] += 1
                    if bool(c["STRICT_ONE_ENTRY_PER_LEG"]):
                        entry_done_cycle = True
                ob.active = False
            ob.in_zone = True

    # Match normal research convention: realize positions at the final Bid/Ask.
    last = n - 1
    for pos in positions:
        exit_price = closes[last] if pos.direction > 0 else closes[last] + spread
        close_position(pos, last, exit_price, "EOD")

    active_obs = [
        {
            "high": round(ob.high, 5), "low": round(ob.low, 5),
            "bullish": ob.bullish, "created_time": ob.created_time,
            "from_choch": ob.from_choch, "fib50": round(ob.fib50, 5),
        }
        for ob in obs if ob.active
    ][-20:]
    state_snapshot = {
        "last_bar_time": times[-1],
        "trend": trend,
        "awaiting_confirm": awaiting_confirm,
        "bos_count": bos_count,
        "entry_done_cycle": entry_done_cycle,
        "ref_high": ref_high,
        "ref_low": ref_low,
        "last_swing_high": swing_highs[0][0] if swing_highs else 0.0,
        "last_swing_low": swing_lows[0][0] if swing_lows else 0.0,
        "active_order_blocks": active_obs,
    }
    return trades, {
        "entries": entries, "open_positions": 0, "entry_events": entry_events,
        "state_snapshot": state_snapshot, **signal_counts,
    }

