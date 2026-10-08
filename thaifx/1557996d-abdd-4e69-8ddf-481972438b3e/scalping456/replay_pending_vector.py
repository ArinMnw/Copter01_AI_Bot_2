"""First-event paper pending replay; no ledger reads or source resets.

Independent SL threshold searches are scheduled at their first causal quote.
Their results cannot change book/reference state before that quote. Prefix and
full-field reference parity tests cover level-entry gaps and hedged positions.
"""

import numpy as np

from diagnose_quote_paths import QuoteIndex
from strategy_scalping456 import Side, pending_price


def round_levels(values, digits):
    unique, inverse = np.unique(values, return_inverse=True)
    rounded = np.array([pending_price(float(v), digits) for v in unique])
    return rounded[inverse]


def first_stop(times, bids, asks, opening, side, entry, execution, chunk_size, require_valid_trail=False):
    if execution.trailing_step_points:
        raise ValueError("Stepped trailing requires reference engine")
    buy = side is Side.BUY
    best = float(bids[opening] if buy else asks[opening])
    stop = entry - execution.initial_stop_price if buy else entry + execution.initial_stop_price
    index = opening + 1
    while index < len(times):
        last = min(index + chunk_size, len(times))
        quotes = bids[index:last] if buy else asks[index:last]
        extrema = np.maximum.accumulate(np.maximum(quotes, best)) if buy else np.minimum.accumulate(np.minimum(quotes, best))
        gains = (extrema - entry if buy else entry - extrema) / execution.point
        active = gains >= execution.trailing_activation_points - 1e-7
        candidates = extrema - execution.trailing_distance_price if buy else extrema + execution.trailing_distance_price
        if require_valid_trail:
            valid = candidates < quotes - 1e-9 if buy else candidates > quotes + 1e-9
            permitted = np.where(active & valid, candidates, stop)
            after = np.maximum.accumulate(np.maximum(stop, permitted)) if buy else np.minimum.accumulate(np.minimum(stop, permitted))
        else:
            after = np.maximum(stop, np.where(active, candidates, stop)) if buy else np.minimum(stop, np.where(active, candidates, stop))
        # Level pending entries may gap far into profit on the opening quote.
        # Unlike market entry, that makes a strict prior-stop shift essential.
        prior = np.concatenate(([stop], after[:-1]))
        hits = np.flatnonzero(quotes <= prior if buy else quotes >= prior)
        if len(hits):
            hit = int(hits[0])
            fill = float(prior[hit] if execution.stop_fill_mode == "level" else quotes[hit])
            return index + hit, fill
        best, stop = float(extrema[-1]), float(after[-1])
        index = last
    return None, None


def replay_pending(times, bids, asks, config, *, indices=None, chunk_size=4096):
    if not len(times):
        return []
    if not isinstance(chunk_size, int) or chunk_size <= 0:
        raise ValueError("Positive chunk size required")
    if config.execution.trailing_step_points:
        raise ValueError("Stepped trailing requires reference engine")
    if len(times) != len(bids) or len(times) != len(asks) or np.any(np.diff(times) < 0):
        raise ValueError("Invalid quote chronology/lengths")
    if np.any(~np.isfinite(bids)) or np.any(~np.isfinite(asks)) or np.any(bids <= 0) or np.any(asks < bids):
        raise ValueError("Invalid executable quotes")
    bid_index, ask_index = indices if indices is not None else (QuoteIndex(bids), QuoteIndex(asks))
    n = len(times)
    reference = float((bids[0] + asks[0]) / 2)
    low, high = float(asks[0]), float(bids[0])
    pending, positions, results = {}, {}, []

    def desired(side):
        if config.anchor_mode == "fixed_close":
            value = reference + (1 if side is Side.BUY else -1) * config.entry_distance_price
        else:
            value = low + config.entry_distance_price if side is Side.BUY else high - config.entry_distance_price
        return pending_price(value, config.price_digits)

    def place(i):
        nonlocal low, high
        if config.opposite_policy == "oco" and positions:
            return
        flat = not positions
        if flat:
            low, high = min(low, float(asks[i])), max(high, float(bids[i]))
        for side in (Side.BUY, Side.SELL):
            if side in positions:
                continue
            level = desired(side)
            if side in pending:
                if config.anchor_mode != "rolling_extrema" or not flat:
                    continue
                level = min(pending[side], level) if side is Side.BUY else max(pending[side], level)
            valid = level > asks[i] + 1e-9 if side is Side.BUY else level < bids[i] - 1e-9
            if valid:
                pending[side] = level

    place(0)
    index = 1
    while index < n:
        exits = [p[1] for p in positions.values() if p[1] is not None]
        scheduled = min(exits) if exits else None
        bound = min(n, scheduled + 1) if scheduled is not None else n
        instant = None
        if not positions and config.anchor_mode == "rolling_extrema" and len(pending) == 2:
            # Pending modifications from quote i are available only at i+1.
            cursor = index
            while cursor < bound:
                last = min(cursor + chunk_size, bound)
                lows = np.minimum.accumulate(np.minimum(asks[cursor:last], low))
                highs = np.maximum.accumulate(np.maximum(bids[cursor:last], high))
                buy_after = np.minimum(pending[Side.BUY], round_levels(lows + config.entry_distance_price, config.price_digits))
                sell_after = np.maximum(pending[Side.SELL], round_levels(highs - config.entry_distance_price, config.price_digits))
                buy_before = np.concatenate(([pending[Side.BUY]], buy_after[:-1]))
                sell_before = np.concatenate(([pending[Side.SELL]], sell_after[:-1]))
                hits = np.flatnonzero((asks[cursor:last] >= buy_before - 1e-9) | (bids[cursor:last] <= sell_before + 1e-9))
                if len(hits):
                    hit = int(hits[0])
                    instant = cursor + hit
                    pending[Side.BUY], pending[Side.SELL] = float(buy_before[hit]), float(sell_before[hit])
                    if hit:
                        low, high = float(lows[hit - 1]), float(highs[hit - 1])
                    break
                low, high = float(lows[-1]), float(highs[-1])
                pending[Side.BUY], pending[Side.SELL] = float(buy_after[-1]), float(sell_after[-1])
                cursor = last
            if instant is None:
                break
        else:
            candidates = [scheduled] if scheduled is not None else []
            for side, level in pending.items():
                query = ask_index if side is Side.BUY else bid_index
                hit = query.first_crossing(index, bound, level, upper=side is Side.BUY)
                if hit is not None:
                    candidates.append(hit)
            if config.opposite_policy == "retain" or not positions:
                for side in (Side.BUY, Side.SELL):
                    if side in positions or side in pending:
                        continue
                    level = desired(side)
                    query = ask_index if side is Side.BUY else bid_index
                    hit = query.first_crossing(index, bound, level, upper=side is Side.SELL, strict=True)
                    if hit is not None:
                        candidates.append(hit)  # placement AFTER this quote, no retroactive fill
            if not candidates:
                break
            instant = min(candidates)
        closed = False
        for side in (Side.BUY, Side.SELL):
            if side in positions and positions[side][1] == instant:
                identity, _, fill = positions.pop(side)
                results[identity]["close_ms"] = int(times[instant])
                results[identity]["close_price"] = fill
                reference = fill
                closed = True
        if closed and not positions:
            low, high = float(asks[instant]), float(bids[instant])
        breached = []
        for side, level in pending.items():
            quote = float(asks[instant] if side is Side.BUY else bids[instant])
            excursion = quote - level if side is Side.BUY else level - quote
            if excursion >= -1e-9:
                breached.append((excursion, side is Side.BUY, side))
        for _, _, side in sorted(breached, reverse=True):
            if side not in pending or side in positions:
                continue
            level = pending.pop(side)
            entry = level if config.entry_fill_mode == "level" else float(asks[instant] if side is Side.BUY else bids[instant])
            close, fill = first_stop(times, bids, asks, instant, side, entry, config.execution, chunk_size, config.require_valid_trail)
            identity = len(results)
            results.append({"open_ms": int(times[instant]), "close_ms": None, "side": side.value,
                            "volume": config.execution.volume, "open_price": entry, "close_price": None})
            positions[side] = (identity, close, fill)
            if config.opposite_policy == "oco":
                pending.clear()
        place(instant)
        index = instant + 1
    return results
