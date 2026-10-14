"""Conditional diagnostic on the FORWARD holdout rows (NOT a replay score; no tuning).

Restarts the frozen gold / Fixed engines from the OBSERVED close of the
previous forward order/basket (as ``diagnose_decoded_conditional.py`` does on the
development data) and asks whether the engine alone reproduces the next
order(s).  Also reports the run-13 oracle ceilings on the same rows.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone

import numpy as np

from decoded_common import ROOT, SERVER_OFFSET_MS, SOURCE_SHA256, load_fixed_ticks, load_gold_ticks
from decoded_schedule import FIXED_REGIMES
from diagnose_decoded_conditional import close_instants
from diagnose_decoded_oracle import J_VALUES, TRAIL_VARIANTS, entry_exact, exit_exact, trial
from probe_vantage_feed import sha, write_json
from replay_forward import FORWARD_START, join, load_forward_cache
from strategy_scalping456_decoded import FixedParams, GoldParams, simulate_fixed

UTC = timezone.utc


def forward_rows(tag):
    frozen = {json.loads(l)["ticket"] for l in (ROOT / "data/orders_35462.jsonl").read_text(encoding="utf-8").splitlines()}
    rows = {}
    for file in sorted((ROOT / "data" / tag).glob("new_orders_*.jsonl")):
        for line in file.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["ticket"] not in frozen:
                rows.setdefault(row["ticket"], row)
    out = []
    for row in rows.values():
        scale = 100 if row["symbol"] == "XAUUSD+" else 1000
        row["opms"] = round(datetime.fromisoformat(row["open_time"]).timestamp() * 1000) - SERVER_OFFSET_MS
        row["clms"] = round(datetime.fromisoformat(row["close_time"]).timestamp() * 1000) - SERVER_OFFSET_MS
        row["E"], row["X"] = round(float(row["open_price"]) * scale), round(float(row["close_price"]) * scale)
        out.append(row)
    return sorted(out, key=lambda r: (r["opms"], r["ticket"]))


def gold(times, bids, asks, rows, horizon_ms, resume_ms):
    everything = [r for r in rows if r["symbol"] == "XAUUSD+" and r["clms"] < horizon_ms]
    ends = close_instants(times, bids, asks, everything)
    sample = [r for r in everything if r["volume"] == 10 and r["comment"].startswith("[sl ") and r["opms"] >= resume_ms]
    counts, j_hits = Counter(), Counter()
    for row in sample:
        p = int(np.searchsorted(ends, row["opms"], side="left")) - 1
        if p < 0 or row["opms"] - ends[p] > 300_000:
            counts["no_predecessor_within_300s"] += 1
            continue
        begin = int(np.searchsorted(times, ends[p]))
        counts["trials"] += 1
        entry = rescued = base_all = False
        for j in J_VALUES:
            t = trial(times, bids, asks, begin, ends[p], 130, j, GoldParams())
            if t is None or not entry_exact(t, row):
                continue
            if not entry:
                j_hits[j] += 1
            entry = True
            if exit_exact(t, row):
                rescued = True
                base_all = base_all or j == 0
            elif not rescued:
                for latency, step, delay in TRAIL_VARIANTS[1:]:
                    v = trial(times, bids, asks, begin, ends[p], 130, j,
                              GoldParams(trail_latency_ms=latency, trail_block_ms=latency, trail_step=step,
                                         trail_first_delay_ms=delay))
                    if v is not None and entry_exact(v, row) and exit_exact(v, row):
                        rescued = True
                        break
        counts["baseline_frozen_all_fields_j0"] += base_all
        counts["oracle_j_entry_exact"] += entry
        counts["oracle_j_and_trailing_all_fields"] += rescued
    return {"counts": dict(counts), "first_j_that_explains_entry": {str(k): v for k, v in sorted(j_hits.items())}}


def fixed(times, bids, asks, rows, horizon_ms):
    rows = [r for r in rows if r["symbol"] == "FixedVol20" and r["clms"] < horizon_ms]
    baskets, end = [], -1
    for row in rows:
        if row["opms"] > end:
            baskets.append([row])
            end = row["clms"]
        else:
            baskets[-1].append(row)
            end = max(end, row["clms"])
    counts, detail = Counter(), []
    for previous, basket in zip(baskets[:-1], baskets[1:]):
        close_tick = int(np.searchsorted(times, max(r["clms"] for r in previous)))
        trades = simulate_fixed(times, bids, asks, FIXED_REGIMES, FixedParams(), begin=close_tick + 1,
                                end=min(len(times), close_tick + 1 + 300_000), max_baskets=1)
        counts["baskets"] += 1
        counts["orders"] += len(basket)
        if not trades:
            counts["no_basket"] += 1
            continue
        first_close = trades[0]["close_ms"]
        simulated = {(t["open_ms"] // 1000, t["side"], round(t["volume"], 1), round(t["open_price"], 3),
                      t["close_ms"] // 1000, round(t["close_price"], 3)) for t in trades if t["close_ms"] == first_close}
        real = {(r["opms"] // 1000, r["trade_type"], round(float(r["volume"]), 1), round(float(r["open_price"]), 3),
                 r["clms"] // 1000, round(float(r["close_price"]), 3)) for r in basket}
        counts["orders_exact"] += len(real & simulated)
        counts["baskets_exact"] += real == simulated
        counts["first_leg_exact"] += min(real)[:4] == min(simulated)[:4]
        detail.append({"legs": len(basket), "basket_exact": real == simulated,
                       "first_leg_exact": min(real)[:4] == min(simulated)[:4]})
    return {"totals": dict(counts), "baskets": detail}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--forward-tag", default="forward_watch_20261009")
    parser.add_argument("--horizon", default="2026-10-09T02:00:00")
    parser.add_argument("--resume", default="2026-10-08T10:55:00",
                        help="first inferred instant of normal EA operation (ledger-derived)")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    horizon = datetime.fromisoformat(args.horizon).replace(tzinfo=UTC)
    horizon_ms = round(horizon.timestamp() * 1000)
    resume_ms = round(datetime.fromisoformat(args.resume).replace(tzinfo=UTC).timestamp() * 1000)
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    old_gold, _ = load_gold_ticks()
    old_fixed, _ = load_fixed_ticks()
    gt, gb, ga = join(old_gold, load_forward_cache("vantage_gold_fwd1", "XAUUSD", 100, FORWARD_START, horizon)[0], "gold")
    ft, fb, fa = join(old_fixed, load_forward_cache("vantage_fixed_fwd1", "FixedVol20", 1000, FORWARD_START, horizon)[0],
                      "fixed")
    rows = forward_rows(args.forward_tag)
    report = {"created_utc": datetime.now(UTC).isoformat(), "source_sha256": SOURCE_SHA256,
              "warning": "conditional diagnostic on forward rows; not a replay score; no tuning",
              "resume_instant_ledger_derived": args.resume,
              "code_sha256": {n: sha(ROOT / n) for n in ("diagnose_forward_conditional.py", "diagnose_decoded_oracle.py",
                                                        "strategy_scalping456_decoded.py", "decoded_schedule.py")},
              "gold": gold(gt, gb, ga, rows, horizon_ms, resume_ms), "fixed": fixed(ft, fb, fa, rows, horizon_ms)}
    write_json(folder / "report.json", report)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
