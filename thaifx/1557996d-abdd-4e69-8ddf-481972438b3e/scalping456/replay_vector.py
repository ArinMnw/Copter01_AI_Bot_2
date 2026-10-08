"""Chunked replay accelerator, checked against the public strategy class.

It searches the first causal threshold in each chunk. Future values never set
an entry reference or stop. Step trailing is deliberately unsupported here;
use the reference replay for that configuration.
"""

import hashlib
import json
from datetime import timedelta

import numpy as np


def replay_candidate(times, bids, asks, config, chunk_size=4096):
    if config.trailing_step_points != 0:
        raise ValueError("Vector engine does not implement stepped trailing")
    if not len(times):
        return []
    n = len(times)
    index = 1  # The first tick establishes the unknown-startup flat reference.
    reference = (bids[0] + asks[0]) / 2
    low, high = asks[0], bids[0]
    threshold = config.entry_reversal_price
    predictions = []
    momentum_change = None
    if config.entry_mode == "lookback_momentum":
        # Every lookup resolves to time <= current time - window. Precomputing
        # those past-only returns avoids repeated whole-chunk binary searches.
        past = np.searchsorted(times, times - config.momentum_window_seconds * 1000, side="right") - 1
        valid = past >= 0
        past = np.maximum(past, 0)
        momentum_change = (bids + asks) / 2 - (bids[past] + asks[past]) / 2
        momentum_change[~valid] = np.nan
    while index < n:
        entry_index = None
        while index < n:
            last = min(index + chunk_size, n)
            bid, ask = bids[index:last], asks[index:last]
            if config.entry_mode == "fixed_close":
                rise, fall = ask - reference, reference - bid
            elif config.entry_mode == "rolling_extrema":
                lows = np.minimum.accumulate(np.minimum(ask, low))
                highs = np.maximum.accumulate(np.maximum(bid, high))
                rise, fall = ask - lows, highs - bid
            else:
                rise = momentum_change[index:last]
                fall = -rise
            buy = rise >= threshold - 1e-9
            sell = fall >= threshold - 1e-9
            hits = np.flatnonzero(buy | sell)
            if len(hits):
                hit = int(hits[0])
                entry_index = index + hit
                is_buy = bool(buy[hit] and (not sell[hit] or rise[hit] >= fall[hit]))
                break
            low = min(low, float(ask.min()))
            high = max(high, float(bid.max()))
            index = last
        if entry_index is None:
            break
        entry = float(asks[entry_index] if is_buy else bids[entry_index])
        initial_stop = entry - config.initial_stop_price if is_buy else entry + config.initial_stop_price
        best = float(bids[entry_index] if is_buy else asks[entry_index])
        stop = initial_stop
        index = entry_index + 1
        close_index = None
        while index < n:
            last = min(index + chunk_size, n)
            quotes = bids[index:last] if is_buy else asks[index:last]
            favorable_best = (np.maximum.accumulate(np.maximum(quotes, best)) if is_buy
                              else np.minimum.accumulate(np.minimum(quotes, best)))
            gain_points = ((favorable_best - entry) if is_buy else (entry - favorable_best)) / config.point
            active = gain_points >= config.trailing_activation_points - 1e-7
            candidates = (favorable_best - config.trailing_distance_price if is_buy
                          else favorable_best + config.trailing_distance_price)
            levels = (np.maximum(stop, np.where(active, candidates, stop)) if is_buy
                      else np.minimum(stop, np.where(active, candidates, stop)))
            # A new favorable extreme cannot also cross its positive-distance
            # stop on that tick, so this is equivalent to stop-before-modify.
            hits = np.flatnonzero(quotes <= levels if is_buy else quotes >= levels)
            if len(hits):
                hit = int(hits[0])
                close_index = index + hit
                fill = float(levels[hit] if config.stop_fill_mode == "level" else quotes[hit])
                break
            best, stop = float(favorable_best[-1]), float(levels[-1])
            index = last
        predictions.append({
            "open_ms": int(times[entry_index]),
            "close_ms": int(times[close_index]) if close_index is not None else None,
            "side": "buy" if is_buy else "sell", "volume": config.volume,
            "open_price": entry, "close_price": fill if close_index is not None else None,
        })
        if close_index is None:
            break
        reference = fill
        low, high = float(asks[close_index]), float(bids[close_index])
        index = close_index + 1
    return predictions


def replay_vector(cache, start, end, models):
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    provenance, time_parts, bid_parts, ask_parts = [], [], [], []
    start_ms, end_ms = round(start.timestamp() * 1000), round(end.timestamp() * 1000)
    while day < end:
        path = cache / f"{day:%Y-%m-%d}.npz"
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
            raise ValueError(f"Cache digest differs: {path.name}")
        with np.load(path, allow_pickle=False) as stored:
            times, bid, ask = stored["time_msc"], stored["bid"], stored["ask"]
            if not (len(times) == len(bid) == len(ask) == meta["ticks"]):
                raise ValueError(f"Cache shape differs: {path.name}")
            keep = (times >= start_ms) & (times < end_ms)
            time_parts.append(times[keep])
            bid_parts.append(bid[keep])
            ask_parts.append(ask[keep])
        provenance.append(meta)
        day += timedelta(days=1)
    times, bids, asks = map(np.concatenate, (time_parts, bid_parts, ask_parts))
    if np.any(times[1:] < times[:-1]):
        raise ValueError("Cache not globally chronological")
    valid = np.isfinite(bids) & np.isfinite(asks) & (bids > 0) & (asks >= bids)
    invalid = int((~valid).sum())
    times, bids, asks = times[valid], bids[valid], asks[valid]
    results = {}
    for name, config in models.items():
        results[name] = replay_candidate(times, bids, asks, config)
        print(f"vector model finished {name} ticks={len(times):,} trades={len(results[name]):,}", flush=True)
    return results, provenance, len(times), invalid
