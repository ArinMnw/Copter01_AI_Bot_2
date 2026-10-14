"""Mechanics-given-the-start diagnostic (NOT a causal replay).

Each trial restarts a decoded engine from the OBSERVED close of the previous
source order/basket and checks whether the engine alone reproduces the next
source order(s).  It isolates rule correctness from the loss of synchronisation
that the continuous replay suffers, and uses ledger-observed starting points,
so it must never be quoted as a replay score.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone

import numpy as np

from analyze_decoded_evidence import trigger_tick
from decoded_common import ROOT, SOURCE_SHA256, SPLIT_MS, load_fixed_ticks, load_gold_ticks, load_source, ms
from decoded_schedule import FIXED_REGIMES, GOLD_REGIMES
from probe_vantage_feed import sha, write_json
from strategy_scalping456_decoded import FixedParams, GoldParams, GoldRegime, simulate_fixed, simulate_gold

PARAMS = (6, -5)


def close_instants(times, bids, asks, rows):
    """Exact close-tick time for stop-outs (calibrated source crossing) else the middle of the reported second."""
    instants = []
    for row in rows:
        instant = row["clms"] + 500
        if row["comment"].startswith("[sl ") and row["clms"] - row["opms"] <= 600_000:
            i = int(np.searchsorted(times, row["opms"]))
            j = int(np.searchsorted(times, row["clms"] + 1000))
            if row["trade_type"] == "buy":
                hit = np.flatnonzero((bids[i:j] + PARAMS[0] <= row["X"]) & (times[i:j] >= row["clms"]))
            else:
                hit = np.flatnonzero((asks[i:j] + PARAMS[1] >= row["X"]) & (times[i:j] >= row["clms"]))
            if len(hit):
                instant = int(times[i + int(hit[0])])
        instants.append(instant)
    return np.array(sorted(instants), dtype=np.int64)


def gold_conditional(times, bids, asks, source, per_era):
    everything = [r for r in source if r["symbol"] == "XAUUSD+"]
    gold = [r for r in everything if r["volume"] == 10]
    ends = close_instants(times, bids, asks, everything)
    out = {}
    for era, lo, hi, distance in per_era:
        regime = (GoldRegime(lo - 3_600_000, True, distance, "10", place_offset=1 if distance == 100 else 0),)
        rows = [r for r in gold if lo <= r["opms"] < hi and r["comment"].startswith("[sl ")]
        rng = np.random.default_rng(20261009)
        rows = [rows[i] for i in sorted(rng.choice(len(rows), min(1500, len(rows)), replace=False))]
        counts = Counter()
        for row in rows:
            p = int(np.searchsorted(ends, row["opms"], side="left")) - 1   # latest close before the open second
            if p < 0 or row["opms"] - ends[p] > 300_000:
                counts["no_predecessor_within_300s"] += 1
                continue
            begin = int(np.searchsorted(times, ends[p]))
            trades = simulate_gold(times, bids, asks, regime, GoldParams(), begin=begin, end=min(len(times), begin + 400_000),
                                   initial_close_ms=int(ends[p]), stop_after_trades=1)
            counts["trials"] += 1
            if not trades or trades[0]["close_ms"] is None:
                counts["no_trade"] += 1
                continue
            t = trades[0]
            same_open = t["open_ms"] // 1000 == row["opms"] // 1000
            same_side = t["side"] == row["trade_type"]
            same_price = round(t["open_price"] * 100) == row["E"]
            counts["open_second_and_side"] += same_open and same_side
            counts["open_price_and_side"] += same_side and same_price
            counts["open_second_price_side"] += same_open and same_side and same_price
            exit_ok = t["close_ms"] // 1000 == row["clms"] // 1000 and round(t["close_price"] * 100) == row["X"]
            counts["all_fields"] += same_open and same_side and same_price and exit_ok
            counts["exit_exact_given_entry_exact"] += same_open and same_side and same_price and exit_ok
        out[era] = dict(counts)
    return out


def fixed_conditional(times, bids, asks, source):
    rows = [r for r in source if r["symbol"] == "FixedVol20"]
    baskets, end = [], -1
    for row in rows:
        if row["opms"] > end:
            baskets.append([row])
            end = row["clms"]
        else:
            baskets[-1].append(row)
            end = max(end, row["clms"])
    counts = Counter()
    by_legs = {}
    for previous, basket in zip(baskets[:-1], baskets[1:]):
        opened = basket[0]["opms"]
        if not basket[-1]["comment"].startswith("[tp ") or not (ms("2026-09-06T06:00:00") <= opened < ms("2026-09-27T04:00:00")):
            continue
        close_tick = int(np.searchsorted(times, max(r["clms"] for r in previous)))
        trades = simulate_fixed(times, bids, asks, FIXED_REGIMES, FixedParams(), begin=close_tick + 1,
                                end=min(len(times), close_tick + 1 + 300_000), max_baskets=1)
        if not trades:
            counts["no_basket"] += 1
            continue
        first_close = trades[0]["close_ms"]
        simulated = {(t["open_ms"] // 1000, t["side"], round(t["volume"], 1), round(t["open_price"], 3),
                      t["close_ms"] // 1000, round(t["close_price"], 3)) for t in trades if t["close_ms"] == first_close}
        real = {(r["opms"] // 1000, r["trade_type"], round(float(r["volume"]), 1), round(float(r["open_price"]), 3),
                 r["clms"] // 1000, round(float(r["close_price"]), 3)) for r in basket}
        counts["baskets"] += 1
        counts["orders"] += len(real)
        counts["orders_exact"] += len(real & simulated)
        counts["baskets_exact"] += real == simulated
        first_real = min(real)
        first_sim = min(simulated)
        counts["first_leg_exact"] += first_real[:4] == first_sim[:4]
        slot = by_legs.setdefault(min(len(basket), 6), Counter())
        slot["baskets"] += 1
        slot["baskets_exact"] += real == simulated
        slot["first_leg_exact"] += first_real[:4] == first_sim[:4]
    return {"totals": dict(counts), "by_real_legs_6_means_6plus": {str(k): dict(v) for k, v in sorted(by_legs.items())}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    source = load_source()
    (gt, gb, ga), _ = load_gold_ticks()
    (ft, fb, fa), _ = load_fixed_ticks()
    eras = (("E3_D1.00_lot10_2026-09-02_to_09-30", ms("2026-09-02T00:00:00"), ms("2026-09-30T12:00:00"), 100),
            ("E4_D1.30_2026-10-01_to_10-07", ms("2026-10-01T00:00:00"), ms("2026-10-08T00:00:00"), 130))
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_sha256": SOURCE_SHA256,
              "code_sha256": {name: sha(ROOT / name) for name in ("diagnose_decoded_conditional.py", "strategy_scalping456_decoded.py",
                                                                    "decoded_schedule.py", "analyze_decoded_evidence.py")},
              "warning": "conditional diagnostic starting from observed predecessor closes; not a replay score",
              "gold": gold_conditional(gt, gb, ga, source, eras), "fixed": fixed_conditional(ft, fb, fa, source)}
    write_json(folder / "report.json", report)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
