"""Reproducible evidence tables behind the decoded gold / FixedVol20 mechanics.

Read-only: uses the hash-verified Vantage caches and the untouched public
snapshot, writes one exclusive JSON report.  Every table is conditional
forensics (ledger rows used as probes), NOT a causal prediction; the replay is
in replay_decoded.py.  Parameter selections use only rows opened before
2026-09-21 (development); the later rows are reported separately but, because
the whole ledger was read earlier in this research, they are not unseen data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone

import numpy as np

from decoded_common import (ROOT, SOURCE_SHA256, SPLIT_MS, load_fixed_ticks, load_gold_ticks, load_source, ms)
from probe_vantage_feed import sha, write_json

SEED = 20261009
ERA_10LOT_START = ms("2026-09-02T00:00:00")
ERA_130_START = ms("2026-10-01T00:00:00")


def sample(rows, count, seed=SEED):
    rng = np.random.default_rng(seed)
    if len(rows) <= count:
        return list(rows)
    return [rows[i] for i in sorted(rng.choice(len(rows), count, replace=False))]


# ---------------------------------------------------------------- gold feed
def sl_crossing_rate(times, bids, asks, rows, bid_add, ask_add):
    """Share of -100pip stop-outs whose first source-quote stop crossing falls in the reported close second."""
    hits = total = 0
    for row in rows:
        i = int(np.searchsorted(times, row["opms"]))
        j = int(np.searchsorted(times, row["clms"] + 1000))
        level = row["X"]
        if row["trade_type"] == "buy":
            crossing = np.flatnonzero(bids[i:j] + bid_add <= level)
        else:
            crossing = np.flatnonzero(asks[i:j] + ask_add >= level)
        total += 1
        if len(crossing) and row["clms"] <= times[i + crossing[0]] < row["clms"] + 1000:
            hits += 1
    return hits / total, total


def gold_feed_calibration(times, bids, asks, source):
    rows = [r for r in source if r["symbol"] == "XAUUSD+" and r["comment"].startswith("[sl ") and r["pips"] == -100
            and r["clms"] - r["opms"] <= 600_000]
    result = {"rows": len(rows), "offset_grid_cents": list(range(-20, 21))}
    for label, subset in (("development_before_2026-09-21", [r for r in rows if r["opms"] < SPLIT_MS]),
                          ("later_not_unseen", [r for r in rows if r["opms"] >= SPLIT_MS])):
        block = {}
        for side in ("buy", "sell"):
            part = [r for r in subset if r["trade_type"] == side]
            curve = {}
            for c in range(-20, 21):
                curve[c] = sl_crossing_rate(times, bids, asks, part, c if side == "buy" else 0, c if side == "sell" else 0)[0]
            block[side] = {"rows": len(part), "rate_by_offset_cents": curve, "rate_at_zero": curve[0],
                           "best_offset_cents": max(curve, key=curve.get), "best_rate": max(curve.values())}
        result[label] = block
    return result


# --------------------------------------------------------------- gold entries
def trigger_tick(times, bids, asks, row, params):
    """Index of the tick where the source stop level was crossed near the open second (or -1)."""
    level = row["E"]
    i = int(np.searchsorted(times, row["opms"] - 1500))
    j = int(np.searchsorted(times, row["opms"] + 1000))
    if j - i < 2:
        return -1
    if row["trade_type"] == "buy":
        quote = asks[i:j] + params[1]
        crossing = np.flatnonzero((quote[:-1] < level) & (quote[1:] >= level))
    else:
        quote = bids[i:j] + params[0]
        crossing = np.flatnonzero((quote[:-1] > level) & (quote[1:] <= level))
    for x in crossing:
        k = i + x + 1
        if row["opms"] <= times[k] < row["opms"] + 1000:
            return k
    return i + crossing[0] + 1 if len(crossing) else -1


def gold_entry_mechanics(times, bids, asks, source, params):
    gold = [r for r in source if r["symbol"] == "XAUUSD+"]
    out = {}
    probe = sample(gold, 6000)
    for shift in (0, 37_000, -23_000, 91_000):
        found = 0
        for row in probe:
            shifted = dict(row, opms=row["opms"] + shift)
            found += trigger_tick(times, bids, asks, shifted, params) >= 0
        out[f"stop_level_crossing_near_open_shift_{shift}ms"] = found / len(probe)
    # close ticks for -100pip stop-outs define "predecessor close" anchors
    closes = []
    for row in gold:
        if row["comment"].startswith("[sl ") and row["clms"] - row["opms"] <= 600_000:
            i = int(np.searchsorted(times, row["opms"]))
            j = int(np.searchsorted(times, row["clms"] + 1000))
            level = row["X"]
            if row["trade_type"] == "buy":
                hit = np.flatnonzero((bids[i:j] + params[0] <= level) & (times[i:j] >= row["clms"]))
            else:
                hit = np.flatnonzero((asks[i:j] + params[1] >= level) & (times[i:j] >= row["clms"]))
            if len(hit):
                closes.append((i + int(hit[0]), row["ticket"]))
    close_ticks = np.array(sorted(k for k, _ in closes), dtype=np.int64)
    out["exact_close_ticks"] = len(close_ticks)
    scale = {}
    for era, (lo, hi) in {"E1_2026-08-26..08-27": (ms("2026-08-26T00:00:00"), ms("2026-08-27T06:05:00")),
                          "E3_2026-08-30..09-30": (ms("2026-08-30T22:00:00"), ms("2026-09-30T12:50:00")),
                          "E4_2026-10-01..10-07": (ms("2026-10-01T00:00:00"), ms("2026-10-08T00:00:00")),
                          "E0_2026-08-23..08-25": (ms("2026-08-23T00:00:00"), ms("2026-08-26T00:00:00"))}.items():
        counter, total = Counter(), 0
        for row in sample([r for r in gold if lo <= r["opms"] < hi], 3000):
            k = trigger_tick(times, bids, asks, row, params)
            if k < 0:
                continue
            p = int(np.searchsorted(close_ticks, k, side="left")) - 1
            if p < 0:
                continue
            total += 1
            c0 = int(close_ticks[p])
            matched = None
            for j in (1, 0, 2, 3, 4):
                ref = asks[c0 + j] + params[1] if row["trade_type"] == "buy" else bids[c0 + j] + params[0]
                distance = row["E"] - ref if row["trade_type"] == "buy" else ref - row["E"]
                if distance in (100, 130):
                    matched = (distance, j)
                    break
            counter[matched[0] if matched else 0] += 1
        scale[era] = {"entries_probed": total, "distance_found_cents": {str(k): v for k, v in counter.items()},
                      "share_100": counter[100] / max(total, 1), "share_130": counter[130] / max(total, 1)}
    out["placement_distance_after_predecessor_close_by_era"] = scale
    # control scan around the 10-lot era to show 100 is a specific spike
    control = {}
    era_rows = sample([r for r in gold if ERA_10LOT_START <= r["opms"] < ERA_130_START and r["volume"] == 10], 3000)
    for distance in (80, 90, 95, 98, 99, 100, 101, 102, 105, 110, 120, 130, 140, 150):
        hits = total = 0
        for row in era_rows:
            k = trigger_tick(times, bids, asks, row, params)
            if k < 0:
                continue
            p = int(np.searchsorted(close_ticks, k, side="left")) - 1
            if p < 0:
                continue
            total += 1
            c0 = int(close_ticks[p])
            for j in range(0, 4):
                ref = asks[c0 + j] + params[1] if row["trade_type"] == "buy" else bids[c0 + j] + params[0]
                if (row["E"] - ref if row["trade_type"] == "buy" else ref - row["E"]) == distance:
                    hits += 1
                    break
        control[str(distance)] = hits / max(total, 1)
    out["distance_scan_10lot_era_within_3_ticks_of_predecessor_close"] = control
    return out


# ---------------------------------------------------------------- gold exits
def stops_level_trailing_grid(times, bids, asks, source, params):
    """Server-side stops-level validation model (trade_stops_level 20 points for XAUUSD).

    The EA requests SL = best quote -/+ 0.20 (exactly the minimum allowed distance); the request reaches
    the server ``latency`` ms later and is accepted only if that distance is still respected against the
    quote then (otherwise rejected, EA retries on a later tick); the EA is unavailable for ``block`` ms.
    """
    pool = [r for r in source if r["symbol"] == "XAUUSD+" and r["volume"] == 10 and r["comment"].startswith("[sl ")
            and r["clms"] - r["opms"] <= 300_000]
    prepared = []
    for row in pool:
        k = trigger_tick(times, bids, asks, row, params)
        if k >= 0:
            prepared.append((row, k))
    rng = np.random.default_rng(SEED)
    dev = [x for x in prepared if x[0]["opms"] < SPLIT_MS]
    later = [x for x in prepared if x[0]["opms"] >= SPLIT_MS]
    dev = [dev[i] for i in sorted(rng.choice(len(dev), min(1500, len(dev)), replace=False))]
    later = [later[i] for i in sorted(rng.choice(len(later), min(1500, len(later)), replace=False))]

    def quote_at(buy, instant):
        i = int(np.searchsorted(times, instant, side="right")) - 1
        return int(bids[i]) + params[0] if buy else int(asks[i]) + params[1]

    def simulate(row, k, latency, block, activation):
        buy = row["trade_type"] == "buy"
        entry = row["E"]
        stop = entry - 100 if buy else entry + 100
        free_at, pending = -1, None
        for i in range(k + 1, min(len(times), k + 20000)):
            t = int(times[i])
            q = int(bids[i]) + params[0] if buy else int(asks[i]) + params[1]
            if pending and pending[0] <= t:
                arrival, cand = pending
                qa = quote_at(buy, arrival)
                if (cand <= qa - 20) if buy else (cand >= qa + 20):
                    stop = max(stop, cand) if buy else min(stop, cand)
                pending = None
            if (buy and q <= stop) or ((not buy) and q >= stop):
                return stop, t
            if t < free_at:
                continue
            gain = q - entry if buy else entry - q
            if gain > activation:
                cand = q - 20 if buy else q + 20
                if (buy and cand > stop) or ((not buy) and cand < stop):
                    pending, free_at = (t + latency, cand), t + block
            if t - int(times[k]) > 400_000:
                break
        return None, None

    table = {}
    for latency in (0, 60, 120, 180, 240, 270, 300, 360, 450):
        for block in sorted({latency, latency + 60, latency + 150, 600}):
            if block < latency:
                continue
            entry = {}
            for label, group in (("development", dev), ("later_not_unseen", later)):
                stop_ok = both = 0
                for row, k in group:
                    stop, t = simulate(row, k, latency, block, 20)
                    if stop is None:
                        continue
                    a = stop == row["X"]
                    b = row["clms"] <= t < row["clms"] + 1000
                    stop_ok += a
                    both += a and b
                entry[label] = {"rows": len(group), "final_stop_exact": stop_ok / len(group), "both": both / len(group)}
            table[f"latency{latency}_block{block}"] = entry
    best = max(table, key=lambda name: table[name]["development"]["both"])
    return {"grid": table, "best_on_development": best}


def stops_level_refinement(times, bids, asks, source, params):
    """Selection on dev sample A; the same settings are then scored on independent dev sample B and later sample C."""
    pool = [r for r in source if r["symbol"] == "XAUUSD+" and r["volume"] == 10 and r["comment"].startswith("[sl ")
            and r["clms"] - r["opms"] <= 300_000]
    prepared = [(row, trigger_tick(times, bids, asks, row, params)) for row in pool]
    prepared = [x for x in prepared if x[1] >= 0]
    dev = [x for x in prepared if x[0]["opms"] < SPLIT_MS]
    later = [x for x in prepared if x[0]["opms"] >= SPLIT_MS]
    pick = lambda group, seed: [group[i] for i in np.random.default_rng(seed).choice(len(group), 1500, replace=False)]
    sample_a, sample_b, sample_c = pick(dev, 7), pick(dev, 8), pick(later, 9)

    def quote_at(buy, instant):
        i = int(np.searchsorted(times, instant, side="right")) - 1
        return int(bids[i]) + params[0] if buy else int(asks[i]) + params[1]

    def simulate(row, k, latency, block, step, first_delay):
        buy = row["trade_type"] == "buy"
        entry = row["E"]
        stop = entry - 100 if buy else entry + 100
        free_at, pending = int(times[k]) + first_delay, None
        for i in range(k + 1, min(len(times), k + 20000)):
            t = int(times[i])
            q = int(bids[i]) + params[0] if buy else int(asks[i]) + params[1]
            if pending and pending[0] <= t:
                arrival, cand = pending
                qa = quote_at(buy, arrival)
                if (cand <= qa - 20) if buy else (cand >= qa + 20):
                    stop = max(stop, cand) if buy else min(stop, cand)
                pending = None
            if (buy and q <= stop) or ((not buy) and q >= stop):
                return stop, t
            if t < free_at:
                continue
            gain = q - entry if buy else entry - q
            if gain > 20:
                cand = q - 20 if buy else q + 20
                if (buy and cand > stop + step) or ((not buy) and cand < stop - step):
                    pending, free_at = (t + latency, cand), t + block
            if t - int(times[k]) > 400_000:
                break
        return None, None

    def score(group, **kw):
        stop_ok = both = 0
        for row, k in group:
            stop, t = simulate(row, k, **kw)
            if stop is None:
                continue
            a = stop == row["X"]
            b = row["clms"] <= t < row["clms"] + 1000
            stop_ok += a
            both += a and b
        return {"final_stop_exact": stop_ok / len(group), "both": both / len(group)}

    table = {}
    for step in (0, 1, 2):
        for first_delay in (0, 300, 600, 900):
            for latency, block in ((270, 270), (300, 300), (330, 330)):
                kw = dict(latency=latency, block=block, step=step, first_delay=first_delay)
                table[f"step{step}_firstdelay{first_delay}_latency{latency}_block{block}"] = {
                    "selection_dev_A": score(sample_a, **kw), "dev_B": score(sample_b, **kw), "later_C_not_unseen": score(sample_c, **kw)}
    best = max(table, key=lambda name: table[name]["selection_dev_A"]["both"])
    return {"grid": table, "best_on_selection_sample": best,
            "previous_engine": "step0_firstdelay0_latency300_block300"}


def gold_overlaps(source):
    rows = [r for r in source if r["symbol"] == "XAUUSD+" and r["volume"] == 10]
    rows.sort(key=lambda r: r["opms"])
    pairs = Counter()
    entries_with_other_open = 0
    for n, row in enumerate(rows):
        others = [x for x in rows[max(0, n - 200):n] if x["opms"] <= row["opms"] < x["clms"]]
        if others:
            entries_with_other_open += 1
            pairs[abs(row["E"] - others[-1]["E"])] += 1
    return {"ten_lot_entries": len(rows), "entries_while_another_position_open": entries_with_other_open,
            "entry_price_gap_cents_distribution": {str(k): v for k, v in sorted(pairs.items())}}


def gold_exit_mechanics(times, bids, asks, source, params):
    wins = [r for r in source if r["symbol"] == "XAUUSD+" and r["comment"].startswith("[sl ") and r["pips"] > 0
            and r["clms"] - r["opms"] <= 300_000]
    probe = sample(wins, 5000)
    edge = {}
    for bid_add, ask_add in ((4, -3), (5, -4), (6, -5), (7, -6), (8, -7)):
        gaps = []
        for row in probe:
            i = int(np.searchsorted(times, row["opms"]))
            j = int(np.searchsorted(times, row["clms"] + 1000))
            level = row["X"]
            if row["trade_type"] == "buy":
                q = bids[i:j] + bid_add
                hit = np.flatnonzero((q <= level) & (times[i:j] >= row["clms"]))
                if len(hit) and hit[0] > 0:
                    gaps.append(int(q[:hit[0]].max() - level))
            else:
                q = asks[i:j] + ask_add
                hit = np.flatnonzero((q >= level) & (times[i:j] >= row["clms"]))
                if len(hit) and hit[0] > 0:
                    gaps.append(int(level - q[:hit[0]].min()))
        gaps = np.array(gaps)
        edge[f"bid{bid_add:+d}_ask{ask_add:+d}"] = {
            "rows": int(len(gaps)), "peak_minus_final_stop_min_cents": int(gaps.min()),
            "share_below_20": float((gaps < 20).mean()), "share_exactly_20": float((gaps == 20).mean())}
    tick_value = {}
    sample_rows = probe[:3000]
    for add in (18, 19, 20, 21, 22, 25):
        hits = total = 0
        for row in sample_rows:
            i = int(np.searchsorted(times, row["opms"]))
            j = int(np.searchsorted(times, row["clms"] + 1000))
            level = row["X"]
            if row["trade_type"] == "buy":
                q = bids[i:j] + params[0]
                hit = np.flatnonzero((q <= level) & (times[i:j] >= row["clms"]))
                if len(hit) and hit[0] > 0:
                    total += 1
                    hits += bool((q[:hit[0]] == level + add).any())
            else:
                q = asks[i:j] + params[1]
                hit = np.flatnonzero((q >= level) & (times[i:j] >= row["clms"]))
                if len(hit) and hit[0] > 0:
                    total += 1
                    hits += bool((q[:hit[0]] == level - add).any())
        tick_value[str(add)] = hits / max(total, 1)
    return {"trailing_distance_edge_by_feed_offset": edge,
            "final_stop_plus_distance_is_a_source_tick_value_share": tick_value}


def trail_exit_grid(times, bids, asks, source, params):
    """Exit model fit conditional on the observed entry tick (diagnostic, not prediction)."""
    pool = [r for r in source if r["symbol"] == "XAUUSD+" and r["volume"] == 10 and r["comment"].startswith("[sl ")
            and r["clms"] - r["opms"] <= 300_000]
    prepared = []
    for row in pool:
        k = trigger_tick(times, bids, asks, row, params)
        if k >= 0:
            prepared.append((row, k))
    rng = np.random.default_rng(SEED)
    dev = [x for x in prepared if x[0]["opms"] < SPLIT_MS]
    later = [x for x in prepared if x[0]["opms"] >= SPLIT_MS]
    dev = [dev[i] for i in sorted(rng.choice(len(dev), min(2500, len(dev)), replace=False))]
    later = [later[i] for i in sorted(rng.choice(len(later), min(2500, len(later)), replace=False))]

    def simulate(row, k, busy, effect, minimum_gain):
        buy = row["trade_type"] == "buy"
        entry = row["E"]
        stop = entry - 100 if buy else entry + 100
        blocked, pending = -1, None
        for i in range(k + 1, min(len(times), k + 20000)):
            t = int(times[i])
            q = int(bids[i]) + params[0] if buy else int(asks[i]) + params[1]
            if pending and pending[0] <= t:
                stop = max(stop, pending[1]) if buy else min(stop, pending[1])
                pending = None
            if (buy and q <= stop) or ((not buy) and q >= stop):
                return stop, t
            if t < blocked:
                continue
            gain = q - entry if buy else entry - q
            if gain >= minimum_gain:
                cand = q - 20 if buy else q + 20
                if (buy and cand > stop) or ((not buy) and cand < stop):
                    blocked, pending = t + busy, (t + effect, cand)
            if t - int(times[k]) > 400_000:
                break
        return None, None

    table = {}
    configs = [(busy, effect, gain) for gain in (20, 21)
               for busy, effect in ((0, 0), (100, 50), (200, 100), (300, 150), (400, 200), (600, 300), (800, 400), (1000, 500), (1500, 750))]
    for busy, effect, minimum_gain in configs:
        entry = {}
        for label, group in (("development", dev), ("later_not_unseen", later)):
            stop_ok = second_ok = both = 0
            for row, k in group:
                stop, t = simulate(row, k, busy, effect, minimum_gain)
                if stop is None:
                    continue
                a = stop == row["X"]
                b = row["clms"] <= t < row["clms"] + 1000
                stop_ok += a
                second_ok += b
                both += a and b
            n = len(group)
            entry[label] = {"rows": n, "final_stop_exact": stop_ok / n, "close_second_exact": second_ok / n, "both": both / n}
        table[f"gain_min{minimum_gain}_busy{busy}_effect{effect}"] = entry
    best = max(table, key=lambda name: table[name]["development"]["both"])
    return {"grid": table, "best_on_development": best}


# ------------------------------------------------------------------- fixed
def fixed_mechanics(times, bids, asks, source):
    rows = [r for r in source if r["symbol"] == "FixedVol20"]
    out = {"orders": len(rows), "ticks_per_second": len(times) / ((times[-1] - times[0]) / 1000),
           "tick_phase_ms_quantiles_1_50_99": np.percentile(times % 1000, [1, 50, 99]).tolist()}
    probe = sample([r for r in rows if r["comment"].startswith("[tp ")], 1500)
    for label, value in (("entry_price_equals_executable_quote_offset_0", 0), ("offset_+0.075", 75), ("offset_-0.135", -135)):
        hit = 0
        for row in probe:
            i = int(np.searchsorted(times, row["opms"]))
            j = int(np.searchsorted(times, row["opms"] + 1000))
            quote = asks[i:j] if row["trade_type"] == "buy" else bids[i:j]
            hit += bool((quote + value == row["E"]).any())
        out[label] = hit / len(probe)
    # baskets by lifetime overlap
    baskets, current, end = [], None, -1
    for row in rows:
        if row["opms"] > end:
            current = []
            baskets.append(current)
            end = row["clms"]
        else:
            end = max(end, row["clms"])
        current.append(row)
    first_distance, race = Counter(), Counter()
    previous_legs = None
    previous_close = None
    for basket in baskets:
        first = basket[0]
        if previous_close is not None and first["opms"] >= ms("2026-09-06T06:00:00") and first["opms"] < ms("2026-09-27T04:00:00"):
            k = int(np.searchsorted(times, previous_close))
            found = []
            for j in range(0, 4):
                distance = first["E"] - asks[k + j] if first["trade_type"] == "buy" else bids[k + j] - first["E"]
                if distance == 3000:
                    found.append(j)
            label = found[0] if len(found) == 1 else ("none" if not found else "ambiguous")
            race[(min(previous_legs, 5), str(label))] += 1
        previous_legs = len(basket)
        previous_close = max(r["clms"] for r in basket)
    totals = {}
    for (legs, label), count in race.items():
        totals.setdefault(legs, Counter())[label] += count
    out["reference_tick_after_previous_close_by_previous_legs"] = {
        str(k): {kk: vv for kk, vv in v.items()} for k, v in sorted(totals.items())}
    # grid step consistency
    consistent = total = 0
    for basket in baskets:
        for a, b in zip(basket[:-1], basket[1:]):
            i = int(np.searchsorted(times, b["opms"]))
            j = int(np.searchsorted(times, b["opms"] + 1000))
            quote = bids[i:j] if b["trade_type"] == "sell" else asks[i:j]
            if not len(quote) or not (quote == b["E"]).any():
                continue
            k = i + int(np.flatnonzero(quote == b["E"])[0])
            adverse = bids[k] - a["E"] if b["trade_type"] == "sell" else a["E"] - asks[k]
            previous = bids[k - 1] - a["E"] if b["trade_type"] == "sell" else a["E"] - asks[k - 1]
            if b["opms"] < ms("2026-09-27T04:00:00"):
                total += 1
                consistent += adverse >= 3000 and previous < 3000
    out["grid_add_is_first_tick_with_adverse_3000_share"] = consistent / max(total, 1)
    # basket TP rounding rule: volume-weighted entry (exact fraction) +/- distance vs the reported close level
    from fractions import Fraction
    import math
    rules = Counter()
    checked = 0
    for basket in baskets:
        if len(basket) < 2 or not basket[-1]["comment"].startswith("[tp "):
            continue
        sign = 1 if basket[0]["trade_type"] == "buy" else -1
        volumes = [round(float(r["volume"]) * 10) for r in basket]
        weighted = Fraction(sum(r["E"] * v for r, v in zip(basket, volumes)), sum(volumes))
        distance = 3000 if basket[0]["opms"] < ms("2026-09-27T04:00:00") else 15000
        target = basket[-1]["X"]
        checked += 1
        rules["round_half_up"] += math.floor(weighted + Fraction(1, 2)) + sign * distance == target
        rules["floor"] += math.floor(weighted) + sign * distance == target
        rules["ceil"] += math.ceil(weighted) + sign * distance == target
    out["multi_leg_tp_rounding_rule"] = {"baskets": checked, **dict(rules)}
    # first-leg entry distance by period, using the tick right after the previous basket closed
    regimes = Counter()
    previous_close = None
    for basket in baskets:
        first = basket[0]
        if previous_close is not None:
            k = int(np.searchsorted(times, previous_close))
            for j in (1, 0):
                distance = first["E"] - asks[k + j] if first["trade_type"] == "buy" else bids[k + j] - first["E"]
                if distance in (2802, 3000, 5000):
                    period = "before_2026-09-05T17:40" if first["opms"] < ms("2026-09-05T17:40:00") else (
                        "2026-09-05..09-27" if first["opms"] < ms("2026-09-27T04:38:39") else "from_2026-09-27T04:38")
                    regimes[(period, int(distance))] += 1
                    break
        previous_close = max(r["clms"] for r in basket)
    out["first_leg_distance_by_period_thousandths"] = {f"{p}|{d}": n for (p, d), n in sorted(regimes.items())}
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    if sha(ROOT / "data/orders_35462.jsonl") != SOURCE_SHA256:
        raise RuntimeError("Source snapshot changed")
    source = load_source()
    (gt, gb, ga), gold_provenance = load_gold_ticks()
    (ft, fb, fa), fixed_provenance = load_fixed_ticks()
    params = (6, -5)   # cents added to demo bid / ask (calibrated below on the development rows)
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_sha256": SOURCE_SHA256,
              "code_sha256": {"analyze_decoded_evidence.py": sha(ROOT / "analyze_decoded_evidence.py"),
                              "decoded_common.py": sha(ROOT / "decoded_common.py")},
              "gold_ticks": len(gt), "fixed_ticks": len(ft), "split_ms": SPLIT_MS,
              "seed": SEED, "note": "conditional ledger probes; not predictions; later rows are not unseen"}
    report["gold_feed_calibration"] = gold_feed_calibration(gt, gb, ga, source)
    report["gold_entry_mechanics"] = gold_entry_mechanics(gt, gb, ga, source, params)
    report["gold_exit_mechanics"] = gold_exit_mechanics(gt, gb, ga, source, params)
    report["gold_trailing_timing_grid"] = trail_exit_grid(gt, gb, ga, source, params)
    report["gold_overlapping_positions"] = gold_overlaps(source)
    report["gold_stops_level_trailing_grid"] = stops_level_trailing_grid(gt, gb, ga, source, params)
    report["gold_stops_level_refinement"] = stops_level_refinement(gt, gb, ga, source, params)
    report["fixed_mechanics"] = fixed_mechanics(ft, fb, fa, source)
    write_json(folder / "report.json", report)
    print(json.dumps({k: (v if not isinstance(v, dict) else "...") for k, v in report.items()}, indent=1)[:600])


if __name__ == "__main__":
    main()
