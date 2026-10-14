"""Does a richer EA-processing model beat the busy/effect trailing model?

Conditional on the observed entry tick (diagnostic, not a prediction).  The EA
is modelled as processing a tick, then ignoring ticks for ``process_ms``; a SL
modify blocks it for an extra ``modify_busy_ms`` and reaches the server
``effect_ms`` after the decision.  Only development rows (opened before
2026-09-21, 10 lots) are scored, so the choice of grid winner never sees the
later rows.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone

import numpy as np

from analyze_decoded_evidence import trigger_tick
from decoded_common import ROOT, SOURCE_SHA256, SPLIT_MS, load_gold_ticks, load_source, ms
from probe_vantage_feed import sha, write_json

PARAMS = (6, -5)


def simulate(times, bids, asks, row, k, process_ms, effect_ms, busy_ms):
    buy = row["trade_type"] == "buy"
    entry = row["E"]
    stop = entry - 100 if buy else entry + 100
    next_ok, pending = -1, []
    for i in range(k + 1, min(len(times), k + 20000)):
        t = int(times[i])
        q = int(bids[i]) + PARAMS[0] if buy else int(asks[i]) + PARAMS[1]
        while pending and pending[0][0] <= t:
            c = pending.pop(0)[1]
            stop = max(stop, c) if buy else min(stop, c)
        if (buy and q <= stop) or ((not buy) and q >= stop):
            return stop, t
        if t < next_ok:
            continue
        next_ok = t + process_ms
        gain = q - entry if buy else entry - q
        if gain > 20:
            cand = q - 20 if buy else q + 20
            if (buy and cand > stop) or ((not buy) and cand < stop):
                pending.append((t + effect_ms, cand))
                next_ok = t + process_ms + busy_ms
        if t - int(times[k]) > 400_000:
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
    (times, bids, asks), _ = load_gold_ticks()
    pool = [r for r in load_source() if r["symbol"] == "XAUUSD+" and r["volume"] == 10 and r["comment"].startswith("[sl ")
            and r["clms"] - r["opms"] <= 300_000 and ms("2026-09-02T00:00:00") <= r["opms"] < SPLIT_MS]
    rng = np.random.default_rng(7)
    rows = [pool[i] for i in rng.choice(len(pool), 1500, replace=False)]
    prepared = [(row, trigger_tick(times, bids, asks, row, PARAMS)) for row in rows]
    prepared = [x for x in prepared if x[1] >= 0]
    table = []
    for process_ms in (0, 40, 80, 120, 160, 200, 300, 400, 600):
        for effect_ms in (0, 100, 200, 400):
            for busy_ms in (0, 400, 800):
                stop_ok = both = 0
                for row, k in prepared:
                    stop, t = simulate(times, bids, asks, row, k, process_ms, effect_ms, busy_ms)
                    if stop is None:
                        continue
                    a = stop == row["X"]
                    b = row["clms"] <= t < row["clms"] + 1000
                    stop_ok += a
                    both += a and b
                table.append({"process_ms": process_ms, "effect_ms": effect_ms, "modify_busy_ms": busy_ms,
                              "final_stop_exact": stop_ok / len(prepared), "stop_and_close_second_exact": both / len(prepared)})
    table.sort(key=lambda x: -x["stop_and_close_second_exact"])
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_sha256": SOURCE_SHA256,
              "code_sha256": {"analyze_decoded_processing.py": sha(ROOT / "analyze_decoded_processing.py")},
              "development_rows": len(prepared), "best_first": table[:10], "full_grid": table,
              "comparison": "busy800/effect400 with process 0 is the model used by strategy_scalping456_decoded.py"}
    write_json(folder / "report.json", report)
    for row in table[:5]:
        print(row)


if __name__ == "__main__":
    main()
