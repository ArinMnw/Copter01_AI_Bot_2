"""Does the real `XAUUSD+` tick stream beat demo `XAUUSD` + offsets on SL-crossing timing? (read-only analysis)

Rows: gold stop-outs that lost exactly 100 pips (close price = the SL level the EA used).  For each row the
first tick at/after the reported open instant whose source-side quote crosses the SL level is compared with the
reported close second.  Demo ticks get the calibrated bid+0.06 / ask-0.05; `XAUUSD+` ticks get no offset.
Rows are split into development (opened before 2026-09-21) and later (not unseen).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone

import numpy as np

from decoded_common import ROOT, SOURCE_SHA256, SPLIT_MS, load_gold_plus_ticks, load_gold_ticks, load_source
from probe_vantage_feed import sha, write_json


def first_crossing(times, bids, asks, row, bid_add, ask_add):
    i = int(np.searchsorted(times, row["opms"]))
    j = int(np.searchsorted(times, row["clms"] + 5000))
    if row["trade_type"] == "buy":
        hit = np.flatnonzero(bids[i:j] + bid_add <= row["X"])
    else:
        hit = np.flatnonzero(asks[i:j] + ask_add >= row["X"])
    return int(times[i + int(hit[0])]) if len(hit) else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    rows = [r for r in load_source("XAUUSD+") if r["comment"].startswith("[sl ") and float(r["pips"]) == -100]
    demo, _ = load_gold_ticks()
    plus, _ = load_gold_plus_ticks()
    feeds = {"demo_offset": (demo, 6, -5), "xauusd_plus": (plus, 0, 0), "demo_no_offset": (demo, 0, 0)}
    counts = {name: Counter() for name in feeds}
    for row in rows:
        phase = "dev" if row["opms"] < SPLIT_MS else "later"
        for name, ((t, b, a), badd, aadd) in feeds.items():
            hit = first_crossing(t, b, a, row, badd, aadd)
            counts[name][phase + "_rows"] += 1
            counts[name][phase + "_same_second"] += hit is not None and hit // 1000 == row["clms"] // 1000
            counts[name][phase + "_no_cross"] += hit is None
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_sha256": SOURCE_SHA256, "rows": len(rows),
              "code_sha256": sha(ROOT / "analyze_goldplus_feed.py"), "counts": {k: dict(v) for k, v in counts.items()}}
    write_json(folder / "report.json", report)
    for name, c in counts.items():
        print(name, {k: v for k, v in c.items()},
              "dev %.1f%% later %.1f%%" % (100 * c["dev_same_second"] / c["dev_rows"], 100 * c["later_same_second"] / c["later_rows"]))


if __name__ == "__main__":
    main()
