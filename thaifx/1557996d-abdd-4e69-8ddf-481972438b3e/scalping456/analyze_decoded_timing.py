"""EA reaction-latency evidence for the gold pending-stop placement.

For entries whose predecessor close tick is observable, the pending level
equals ``source_ask + D`` (BUY) / ``source_bid - D`` (SELL) on the quote the EA
read after the close.  A constant reaction delay X reads the last tick at or
before ``close_tick_time + X``.  We report, per delay, the share of entries
whose observed level is explained, separately for development (opened before
2026-09-21) and later rows.  Conditional forensics, not a prediction.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone

import numpy as np

from analyze_decoded_evidence import trigger_tick
from decoded_common import ROOT, SOURCE_SHA256, SPLIT_MS, load_gold_ticks, load_source, ms
from probe_vantage_feed import sha, write_json

PARAMS = (6, -5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    source = [r for r in load_source() if r["symbol"] == "XAUUSD+"]
    (times, bids, asks), _ = load_gold_ticks()
    closes = []
    for row in source:
        if not row["comment"].startswith("[sl ") or row["clms"] - row["opms"] > 600_000:
            continue
        i = int(np.searchsorted(times, row["opms"]))
        j = int(np.searchsorted(times, row["clms"] + 1000))
        level = row["X"]
        if row["trade_type"] == "buy":
            hit = np.flatnonzero((bids[i:j] + PARAMS[0] <= level) & (times[i:j] >= row["clms"]))
        else:
            hit = np.flatnonzero((asks[i:j] + PARAMS[1] >= level) & (times[i:j] >= row["clms"]))
        if len(hit):
            closes.append(i + int(hit[0]))
    close_ticks = np.array(sorted(closes), dtype=np.int64)
    eras = {"D100_2026-09-02..09-30": (ms("2026-09-02T00:00:00"), ms("2026-09-30T12:50:00"), 100),
            "D130_2026-10-01..10-07": (ms("2026-10-01T00:00:00"), ms("2026-10-08T00:00:00"), 130)}
    delays = list(range(0, 1001, 10))
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_sha256": SOURCE_SHA256,
              "code_sha256": {"analyze_decoded_timing.py": sha(ROOT / "analyze_decoded_timing.py")},
              "split_ms": SPLIT_MS, "delays_ms": delays, "eras": {}}
    for era, (lo, hi, distance) in eras.items():
        for label, test in (("development", lambda r: r["opms"] < SPLIT_MS), ("later_not_unseen", lambda r: r["opms"] >= SPLIT_MS)):
            rows = [r for r in source if lo <= r["opms"] < hi and r["volume"] == 10 and test(r)]
            intervals = []
            j_sets = []
            for row in rows:
                k = trigger_tick(times, bids, asks, row, PARAMS)
                if k < 0:
                    continue
                p = int(np.searchsorted(close_ticks, k, side="left")) - 1
                if p < 0:
                    continue
                c0 = int(close_ticks[p])
                spans, matched = [], set()
                for j in range(0, 12):
                    ref = asks[c0 + j] + PARAMS[1] if row["trade_type"] == "buy" else bids[c0 + j] + PARAMS[0]
                    value = row["E"] - ref if row["trade_type"] == "buy" else ref - row["E"]
                    if value == distance:
                        spans.append((int(times[c0 + j] - times[c0]), int(times[c0 + j + 1] - times[c0])))
                        matched.add(j)
                intervals.append(spans)
                j_sets.append(matched)
            coverage = []
            for delay in delays:
                ok = sum(any(lo_ <= delay < hi_ for lo_, hi_ in spans) for spans in intervals)
                coverage.append(ok / max(len(intervals), 1))
            best = int(np.argmax(coverage))
            n_entries = max(len(j_sets), 1)
            report["eras"][f"{era}/{label}"] = {
                "reference_is_close_tick_plus_j_share": {str(j): sum(j in m for m in j_sets) / n_entries for j in range(0, 4)},
                "entries": len(intervals), "explained_by_any_tick_0_to_11": sum(bool(s) for s in intervals) / max(len(intervals), 1),
                "coverage_by_delay": coverage, "best_delay_ms": delays[best], "best_coverage": coverage[best]}
    write_json(folder / "report.json", report)
    for name, block in report["eras"].items():
        print(name, block["entries"], round(block["explained_by_any_tick_0_to_11"], 3), block["best_delay_ms"], round(block["best_coverage"], 3))


if __name__ == "__main__":
    main()
