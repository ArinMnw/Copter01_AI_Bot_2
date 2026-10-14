"""Oracle-ceiling diagnostic for the decoded gold engine (NOT a replay score).

Same conditional trials as ``diagnose_decoded_conditional.py`` (restart from the
OBSERVED close of the previous source order, same random sample), but an
"oracle" may pick the hidden variable from a small pre-declared set:
  (a) reference-tick offset j of the placement,
  (b) trailing / SL-request parameter set.
An order is "explained" if some oracle choice reproduces (open second, side,
open price, close second, close price) exactly.  The result is a structural
ceiling per hidden variable; it uses the ledger to choose values, so it must
never be quoted as a replay score.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone

import numpy as np

from decoded_common import ROOT, SOURCE_SHA256, SPLIT_MS, load_gold_ticks, load_source, ms
from diagnose_decoded_conditional import close_instants
from probe_vantage_feed import sha, write_json
from strategy_scalping456_decoded import GoldParams, GoldRegime, simulate_gold

J_VALUES = (0, 1, 2, 3, 4)
TRAIL_VARIANTS = (  # (latency=block ms, trail_step, first_delay ms); first entry is the frozen engine
    (270, 1, 900), (0, 0, 0), (100, 1, 900), (200, 1, 900), (400, 1, 900), (270, 0, 900), (270, 1, 0), (270, 1, 1500))
ERAS = (("E3_D1.00_dev_2026-09-02_to_09-20", ms("2026-09-02T00:00:00"), ms("2026-09-21T00:00:00"), 100, 1),
        ("E4_D1.30_2026-10-01_to_10-07", ms("2026-10-01T00:00:00"), ms("2026-10-08T00:00:00"), 130, 0))


def trial(times, bids, asks, begin, close_ms, distance, j, params):
    regime = (GoldRegime(close_ms - 3_600_000, True, distance, "10", place_offset=j),)
    trades = simulate_gold(times, bids, asks, regime, params, begin=begin, end=min(len(times), begin + 400_000),
                           initial_close_ms=int(close_ms), stop_after_trades=1)
    return trades[0] if trades and trades[0]["close_ms"] is not None else None


def entry_exact(t, row):
    return (t is not None and t["open_ms"] // 1000 == row["opms"] // 1000 and t["side"] == row["trade_type"]
            and round(t["open_price"] * 100) == row["E"])


def exit_exact(t, row):
    return t["close_ms"] // 1000 == row["clms"] // 1000 and round(t["close_price"] * 100) == row["X"]


def run_era(times, bids, asks, source, era, limit):
    name, lo, hi, distance, base_j = era
    everything = [r for r in source if r["symbol"] == "XAUUSD+"]
    gold = [r for r in everything if r["volume"] == 10]
    ends = close_instants(times, bids, asks, everything)
    rows = [r for r in gold if lo <= r["opms"] < hi and r["comment"].startswith("[sl ")]
    rng = np.random.default_rng(20261009)
    rows = [rows[i] for i in sorted(rng.choice(len(rows), min(1500, len(rows)), replace=False))]
    if limit:
        rows = rows[:limit]
    counts, j_hits, trail_hits = Counter(), Counter(), Counter()
    base_params = GoldParams()
    for row in rows:
        p = int(np.searchsorted(ends, row["opms"], side="left")) - 1
        if p < 0 or row["opms"] - ends[p] > 300_000:
            counts["no_predecessor_within_300s"] += 1
            continue
        begin = int(np.searchsorted(times, ends[p]))
        counts["trials"] += 1
        explained_entry = explained_base_exit = explained_any_exit = False
        base_all = False
        entry_second_only = entry_price_only = False
        for j in J_VALUES:
            t = trial(times, bids, asks, begin, ends[p], distance, j, base_params)
            if t is None:
                continue
            if entry_exact(t, row):
                if not explained_entry:
                    j_hits[j] += 1
                explained_entry = True
                if exit_exact(t, row):
                    explained_base_exit = True
                    explained_any_exit = True
                    base_all = base_all or j == base_j
                elif not explained_any_exit:
                    for latency, step, delay in TRAIL_VARIANTS[1:]:
                        variant = GoldParams(trail_latency_ms=latency, trail_block_ms=latency, trail_step=step,
                                             trail_first_delay_ms=delay)
                        v = trial(times, bids, asks, begin, ends[p], distance, j, variant)
                        if v is not None and entry_exact(v, row) and exit_exact(v, row):
                            explained_any_exit = True
                            trail_hits[(latency, step, delay)] += 1
                            break
            else:
                entry_second_only |= (t["side"] == row["trade_type"] and round(t["open_price"] * 100) == row["E"])
                entry_price_only |= (t["side"] == row["trade_type"] and t["open_ms"] // 1000 == row["opms"] // 1000)
        counts["baseline_frozen_all_fields"] += base_all
        counts["oracle_j_entry_exact"] += explained_entry
        counts["oracle_j_all_fields_frozen_trailing"] += explained_base_exit
        counts["oracle_j_and_trailing_all_fields"] += explained_any_exit
        if not explained_entry:
            counts["entry_unexplained_but_price_side_match_other_second"] += entry_second_only
            counts["entry_unexplained_but_second_side_match_other_price"] += entry_price_only
    return {"era": name, "counts": dict(counts), "first_j_that_explains_entry": {str(k): v for k, v in sorted(j_hits.items())},
            "first_trailing_variant_that_rescues_exit": {str(k): v for k, v in trail_hits.items()}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--limit", type=int, default=0, help="debug: first N sampled rows per era")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    source = load_source()
    (gt, gb, ga), _ = load_gold_ticks()
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_sha256": SOURCE_SHA256,
              "warning": "oracle-ceiling diagnostic; ledger chooses hidden variables; NOT a replay score",
              "j_values": J_VALUES, "trailing_variants_latency_step_delay": TRAIL_VARIANTS,
              "code_sha256": {name: sha(ROOT / name) for name in (
                  "diagnose_decoded_oracle.py", "diagnose_decoded_conditional.py", "strategy_scalping456_decoded.py",
                  "EXPERIMENT_DECODED_PLAN.md")},
              "eras": []}
    for era in ERAS:
        result = run_era(gt, gb, ga, source, era, args.limit)
        report["eras"].append(result)
        print(json.dumps(result), flush=True)
    write_json(folder / "report.json", report)


if __name__ == "__main__":
    main()
