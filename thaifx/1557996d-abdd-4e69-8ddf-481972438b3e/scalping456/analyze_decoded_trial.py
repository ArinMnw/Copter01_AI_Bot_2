"""Evidence for the FixedVol20 single-leg trailing ("SL trial") engine.

Conditional on the observed entry tick (diagnostic, not a prediction): the 143
``[sl`` rows of 5-6 Sep are replayed from their stop-level trigger tick with an
initial stop of 10.000 and a trailing stop 2.800 behind the best executable
quote once the gain reaches ``activation``.  The feed is bit-identical to the
source, so this isolates the exit rule.  All rows precede 2026-09-21, so there
is NO later validation set for this engine.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from datetime import datetime, timezone

import numpy as np

from decoded_common import ROOT, SOURCE_SHA256, load_fixed_ticks, load_source, ms
from probe_vantage_feed import sha, write_json


def trigger(times, bids, asks, row):
    i = int(np.searchsorted(times, row["opms"] - 3000))
    j = int(np.searchsorted(times, row["opms"] + 1000))
    if row["trade_type"] == "buy":
        q = asks[i:j]
        cross = np.flatnonzero((q[:-1] < row["E"]) & (q[1:] >= row["E"]))
    else:
        q = bids[i:j]
        cross = np.flatnonzero((q[:-1] > row["E"]) & (q[1:] <= row["E"]))
    for x in cross:
        k = i + int(x) + 1
        if row["opms"] <= times[k] < row["opms"] + 1000:
            return k
    return i + int(cross[0]) + 1 if len(cross) else -1


def simulate(times, bids, asks, row, k, activation, distance=2800, initial=10000):
    buy = row["trade_type"] == "buy"
    entry = row["E"]
    stop = entry - initial if buy else entry + initial
    for i in range(k + 1, len(times)):
        q = int(bids[i]) if buy else int(asks[i])
        if (buy and q <= stop) or ((not buy) and q >= stop):
            return stop, int(times[i])
        gain = q - entry if buy else entry - q
        if gain >= activation:
            cand = q - distance if buy else q + distance
            if (buy and cand > stop) or ((not buy) and cand < stop):
                stop = cand
        if times[i] - times[k] > 3 * 86400 * 1000:
            break
    return None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    (times, bids, asks), _ = load_fixed_ticks()
    all_rows = load_source("FixedVol20")
    rows = [r for r in all_rows if r["comment"].startswith("[sl ")]
    prepared = [(r, trigger(times, bids, asks, r)) for r in rows]
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_sha256": SOURCE_SHA256,
              "code_sha256": {"analyze_decoded_trial.py": sha(ROOT / "analyze_decoded_trial.py")},
              "rows": len(rows), "rows_with_stop_level_trigger_tick": sum(k >= 0 for _, k in prepared),
              "rows_whose_entry_equals_a_quote_in_the_open_second": 0,
              "validation": "none: every trial row opened before 2026-09-21"}
    equal = 0
    for r, _ in prepared:
        i = int(np.searchsorted(times, r["opms"]))
        j = int(np.searchsorted(times, r["opms"] + 1000))
        q = asks[i:j] if r["trade_type"] == "buy" else bids[i:j]
        equal += bool((q == r["E"]).any())
    report["rows_whose_entry_equals_a_quote_in_the_open_second"] = equal
    grid = {}
    for activation in [-10 ** 9, 0, 500, 1000, 1500, 1700, 1800, 1900, 1950, 2000, 2050, 2100, 2200, 2300, 2500, 2800, 3000]:
        stop_ok = both = 0
        for r, k in prepared:
            stop, t = simulate(times, bids, asks, r, k, activation)
            if stop is None:
                continue
            a = stop == r["X"]
            b = r["clms"] <= t < r["clms"] + 1000
            stop_ok += a
            both += a and b
        grid[str(activation)] = {"final_stop_exact": stop_ok, "stop_and_close_second_exact": both}
    report["activation_grid_points"] = grid
    best = max(grid, key=lambda key: grid[key]["stop_and_close_second_exact"])
    report["best_activation"] = int(best)
    kinds = Counter()
    exact = Counter()
    for r, k in prepared:
        rel = (r["X"] - r["E"]) * (1 if r["trade_type"] == "buy" else -1)
        kind = "initial_stop_-10.000" if rel <= -9990 else "small_loss" if rel < 0 else "zero" if rel == 0 else "profit"
        stop, t = simulate(times, bids, asks, r, k, 2000)
        kinds[kind] += 1
        exact[kind] += stop == r["X"] and stop is not None and r["clms"] <= t < r["clms"] + 1000
    report["by_outcome_kind_activation_2000"] = {kind: {"rows": kinds[kind], "stop_and_second_exact": exact[kind]} for kind in kinds}
    # entry distance (stop order vs quote one tick after the previous close) by period
    periods = Counter()
    previous_close = None
    for r in sorted(all_rows, key=lambda x: x["opms"]):
        if r["opms"] > ms("2026-09-06T04:30:00"):
            break
        if previous_close is not None and r["comment"].startswith("[sl "):
            k = int(np.searchsorted(times, previous_close))
            for j in (1, 0):
                d = r["E"] - asks[k + j] if r["trade_type"] == "buy" else bids[k + j] - r["E"]
                if d in (3000, 5000):
                    periods[("before_14:51" if r["opms"] < ms("2026-09-05T14:51:00") else "from_14:51", int(d), j)] += 1
                    break
        previous_close = r["clms"]
    report["entry_distance_by_period_and_reference_tick"] = {f"{p}|D{d}|j{j}": n for (p, d, j), n in sorted(periods.items())}
    write_json(folder / "report.json", report)
    print({k: v for k, v in report.items() if k not in ("activation_grid_points",)})
    print({k: v["stop_and_close_second_exact"] for k, v in grid.items()})


if __name__ == "__main__":
    main()
