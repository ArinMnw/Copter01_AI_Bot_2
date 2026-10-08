"""Past-closed-bar/grid replay accelerators, independently checked by reference.

Threshold searches select the first causal event in each chunk. Future ticks
never initialize references, stops, levels or bar signals. No source ledger.
"""

from decimal import Decimal, ROUND_HALF_UP

import numpy as np


def close_single_position(times, bids, asks, entry_index, is_buy, config, chunk_size):
    if config.trailing_step_points:
        raise ValueError("Stepped trailing requires reference replay")
    entry = float(asks[entry_index] if is_buy else bids[entry_index])
    stop = entry - config.initial_stop_price if is_buy else entry + config.initial_stop_price
    best = float(bids[entry_index] if is_buy else asks[entry_index])
    index = entry_index + 1
    while index < len(times):
        last = min(index + chunk_size, len(times))
        quote = bids[index:last] if is_buy else asks[index:last]
        extrema = np.maximum.accumulate(np.maximum(quote, best)) if is_buy else np.minimum.accumulate(np.minimum(quote, best))
        gains = (extrema - entry if is_buy else entry - extrema) / config.point
        active = gains >= config.trailing_activation_points - 1e-7
        candidate = extrema - config.trailing_distance_price if is_buy else extrema + config.trailing_distance_price
        levels = np.maximum(stop, np.where(active, candidate, stop)) if is_buy else np.minimum(stop, np.where(active, candidate, stop))
        hits = np.flatnonzero(quote <= levels if is_buy else quote >= levels)
        if len(hits):
            hit = int(hits[0])
            fill = float(levels[hit] if config.stop_fill_mode == "level" else quote[hit])
            return index + hit, fill
        best, stop = float(extrema[-1]), float(levels[-1])
        index = last
    return None, None


def replay_closed_candidate(times, bids, asks, bars, candle, execution, chunk_size=4096):
    # Search on CLOSE times, never bar opens/current-bar OHLC.
    closes = bars["close_ms"]
    if len(closes) == 0 or len(times) == 0:
        return []
    if np.any(np.diff(closes) <= 0) or np.any(closes != bars["open_ms"] + candle.minutes * 60000):
        raise ValueError("Invalid bar chronology/duration")
    last_closed = np.searchsorted(closes, times, side="right") - 1
    n = len(times)
    index, used_bar, results = 0, -1, []
    body = bars["close"] - bars["open"]
    if candle.entry_mode == "body":
        bar_buy = (body > 0) & (body >= candle.body_min_price)
        bar_sell = (body < 0) & (-body >= candle.body_min_price)
    elif candle.entry_mode == "engulf":
        previous_open = np.roll(bars["open"], 1)
        previous_close = np.roll(bars["close"], 1)
        bar_buy = ((previous_close < previous_open) & (body > 0) & (bars["open"] <= previous_close)
                   & (bars["close"] >= previous_open) & (body >= candle.body_min_price))
        bar_sell = ((previous_close > previous_open) & (body < 0) & (bars["open"] >= previous_close)
                    & (bars["close"] <= previous_open) & (-body >= candle.body_min_price))
        bar_buy[0] = bar_sell[0] = False
    once = candle.entry_mode != "breakout" or not candle.allow_breakout_reentry
    while index < n:
        entry_index = None
        while index < n:
            last = min(index + chunk_size, n)
            ids = last_closed[index:last]
            valid = (ids >= 0) & ((ids != used_bar) if once else True)
            safe = np.maximum(ids, 0)
            if candle.entry_mode == "breakout":
                buy = bids[index:last] >= bars["high"][safe] + candle.breakout_buffer_price - 1e-9
                sell = bids[index:last] <= bars["low"][safe] - candle.breakout_buffer_price + 1e-9
            else:
                buy, sell = bar_buy[safe], bar_sell[safe]
            hits = np.flatnonzero((buy | sell) & valid)
            if len(hits):
                hit = int(hits[0])
                entry_index = index + hit
                is_buy = bool(buy[hit])
                used_bar = int(ids[hit])
                break
            index = last
        if entry_index is None:
            break
        close_index, fill = close_single_position(times, bids, asks, entry_index, is_buy, execution, chunk_size)
        results.append({"open_ms": int(times[entry_index]), "close_ms": int(times[close_index]) if close_index is not None else None,
                        "side": "buy" if is_buy else "sell", "volume": execution.volume,
                        "open_price": float(asks[entry_index] if is_buy else bids[entry_index]), "close_price": fill})
        if close_index is None:
            break
        index = close_index + 1
    return results


def replay_grid_candidate(times, bids, asks, config, chunk_size=4096):
    if not len(times):
        return []
    n, index = len(times), 1
    reference = (bids[0] + asks[0]) / 2
    low, high = float(asks[0]), float(bids[0])
    legs, results = [], []
    is_buy, target = None, None
    while index < n:
        last = min(index + chunk_size, n)
        bid, ask = bids[index:last], asks[index:last]
        if not legs:
            if config.entry_mode == "fixed_close":
                rise, fall = ask - reference, reference - bid
            else:
                lows = np.minimum.accumulate(np.minimum(ask, low))
                highs = np.maximum.accumulate(np.maximum(bid, high))
                rise, fall = ask - lows, highs - bid
            buy = rise >= config.entry_reversal_price
            sell = fall >= config.entry_reversal_price
            hits = np.flatnonzero(buy | sell)
            if not len(hits):
                low, high = min(low, float(ask.min())), max(high, float(bid.max()))
                index = last
                continue
            hit = int(hits[0])
            is_buy = bool(buy[hit] and (not sell[hit] or rise[hit] >= fall[hit]))
            at = index + hit
            fill = float(asks[at] if is_buy else bids[at])
            volume = config.initial_volume
        else:
            tp_hit = bid >= target if is_buy else ask <= target
            adverse = legs[-1]["open_price"] - ask if is_buy else bid - legs[-1]["open_price"]
            grid_hit = adverse >= config.grid_step_price
            hits = np.flatnonzero(tp_hit | grid_hit)
            if not len(hits):
                index = last
                continue
            hit = int(hits[0])
            at = index + hit
            if tp_hit[hit]:
                for leg in legs:
                    results.append({**leg, "close_ms": int(times[at]), "close_price": target})
                legs = []
                reference, low, high = target, float(asks[at]), float(bids[at])
                index = at + 1
                continue
            fill = float(asks[at] if is_buy else bids[at])
            if config.grid_fill_mode == "level":
                fill = legs[-1]["open_price"] + (-config.grid_step_price if is_buy else config.grid_step_price)
            if config.fixed_volume:
                volume = config.initial_volume
            else:
                raw = legs[-1]["volume"] * config.volume_multiplier
                volume = min(config.max_volume, int(raw * 10 + .5 + 1e-9) / 10)
        legs.append({"open_ms": int(times[at]), "side": "buy" if is_buy else "sell",
                     "volume": volume, "open_price": fill})
        total_volume = sum(leg["volume"] for leg in legs)
        average = sum(leg["open_price"] * leg["volume"] for leg in legs) / total_volume
        unrounded = average + (config.basket_target_price if is_buy else -config.basket_target_price)
        target = (float(Decimal(str(unrounded)).quantize(Decimal(1).scaleb(-config.price_digits), rounding=ROUND_HALF_UP))
                  if config.target_rounding == "half_up" else round(unrounded, config.price_digits))
        index = at + 1
    results.extend({**leg, "close_ms": None, "close_price": None} for leg in legs)
    return results
