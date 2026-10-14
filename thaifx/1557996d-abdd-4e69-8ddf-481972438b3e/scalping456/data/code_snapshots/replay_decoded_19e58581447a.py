"""Continuous causal replay of the decoded gold + FixedVol20 engines.

Predictions are generated from ticks and the declared regime schedule only,
before the ledger is parsed.  The strict matcher then compares ALL 35,462
source rows (both symbols) with timing tolerance 0 at source precision.
Eras whose entry mechanism is not identified are inactive, so their source
orders count as missing; nothing is hidden or tolerance-widened.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

import numpy as np

from decoded_common import ROOT, SOURCE_SHA256, SPLIT_MS, load_fixed_ticks, load_gold_ticks, ms
from decoded_schedule import FIXED_REGIMES, GOLD_REGIMES
from probe_vantage_feed import group, sha, write_json
from replay_vantage_candle_grid import END, START
from strategy_scalping456_decoded import FixedParams, GoldParams, simulate_fixed, simulate_gold
from strict_source_matcher import enrich_prediction, match_exact

CODE = ("strategy_scalping456_decoded.py", "decoded_schedule.py", "decoded_common.py", "replay_decoded.py",
        "strict_source_matcher.py", "EXPERIMENT_DECODED_PLAN.md")
GOLD_ERAS = (("E0_D1.05_slow_2026-08-23_to_08-26", None, ms("2026-08-26T08:00:00")),
             ("E1_D1.00_2026-08-26_to_08-27", ms("2026-08-26T08:00:00"), ms("2026-08-27T06:05:00")),
             ("E2_D1.05_2026-08-27_to_08-30", ms("2026-08-27T06:05:00"), ms("2026-08-30T22:00:00")),
             ("E3_D1.00_2026-08-30_to_09-30", ms("2026-08-30T22:00:00"), ms("2026-09-30T14:20:00")),
             ("T1_D1.10_2026-09-30", ms("2026-09-30T14:20:00"), ms("2026-09-30T16:15:00")),
             ("T2_EA_idle_2026-09-30", ms("2026-09-30T16:15:00"), ms("2026-09-30T20:46:00")),
             ("E4_D1.30_2026-09-30_to_10-07", ms("2026-09-30T20:46:00"), None))
FIXED_ERAS = (("F0_pre_2026-09-05_17:40_D5.0_and_SL_trial", None, ms("2026-09-05T17:40:00")),
              ("F1_step3_tp3_2026-09-05_to_09-27", ms("2026-09-05T17:40:00"), ms("2026-09-27T04:38:39")),
              ("F2_step15_tp15_from_2026-09-27", ms("2026-09-27T04:38:39"), None))


def era_of(open_ms, eras):
    for name, lo, hi in eras:
        if (lo is None or open_ms >= lo) and (hi is None or open_ms < hi):
            return name
    return "none"


def to_prediction(trade, symbol):
    row = {key: trade[key] for key in ("open_ms", "close_ms", "side", "volume", "open_price", "close_price")}
    return enrich_prediction(row, symbol, trade["close_behavior"])


def window_filter(predictions, start_ms, end_ms):
    return [p for p in predictions if p["open_ms"] < end_ms and (p["close_ms"] is None or p["close_ms"] >= start_ms)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--flat-only", action="store_true", help="run-2 hypothesis H9: place a pair only when flat")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    hashes = {name: sha(ROOT / name) for name in CODE}
    gold_params = GoldParams(place_only_when_flat=args.flat_only)
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "code_plan_sha256": hashes,
              "start_inferred_utc": START.isoformat(), "end_exclusive_inferred_utc": END.isoformat(),
              "gold_params": gold_params.__dict__, "fixed_params": {k: str(v) for k, v in FixedParams().__dict__.items()},
              "regime_schedule_is_ledger_derived_input": True,
              "method": "continuous_from_first_warmup_tick_no_ledger_actions_no_resets", "source_parse_order": "after predictions",
              "full_source_clone_complete": False, "artifact_sha256": {}}
    write_json(folder / "run_manifest.json", report)
    (gt, gb, ga), gold_provenance = load_gold_ticks()
    (ft, fb, fa), fixed_provenance = load_fixed_ticks()
    report["cache_provenance"] = {"gold_days": len(gold_provenance), "fixed_days": len(fixed_provenance)}
    gold = simulate_gold(gt, gb, ga, GOLD_REGIMES, gold_params)
    fixed = simulate_fixed(ft, fb, fa, FIXED_REGIMES, FixedParams())
    predictions = [to_prediction(t, "XAUUSD+") for t in gold] + [to_prediction(t, "FixedVol20") for t in fixed]
    path = folder / "predictions.jsonl"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for index, row in enumerate(predictions):
            stream.write(json.dumps({"prediction_index": index, **row}, default=str) + "\n")
    report["artifact_sha256"][path.name] = sha(path)
    report["predictions_including_warmup"] = {"XAUUSD+": len(gold), "FixedVol20": len(fixed)}
    if hashes != {name: sha(ROOT / name) for name in CODE}:
        raise RuntimeError("Code/plan changed during replay")
    source_path = ROOT / "data/orders_35462.jsonl"
    if sha(source_path) != SOURCE_SHA256:
        raise RuntimeError("Source snapshot changed")
    source = [json.loads(line, parse_float=Decimal) for line in source_path.read_text(encoding="utf-8").splitlines()]
    report["source_sha256"] = SOURCE_SHA256
    from probe_vantage_feed import stamp
    opens = [round((stamp(r["open_time"]) - 10800) * 1000) for r in source]
    closes = [round((stamp(r["close_time"]) - 10800) * 1000) for r in source]
    start_ms, end_ms = min(opens), max(closes) + 1000
    kept = window_filter(predictions, start_ms, end_ms)
    matches, extra, score = match_exact(source, kept)
    report.update(score)
    report["predictions_in_source_window"] = len(kept)
    # per-order results with era/cohort labels
    labelled = []
    exact_by = Counter()
    total_by = Counter()
    for row, match, opened in zip(source, matches, opens):
        era = era_of(opened, GOLD_ERAS if row["symbol"] == "XAUUSD+" else FIXED_ERAS)
        label = (group(row), era)
        total_by[label] += 1
        exact_by[label] += match["exact_all_observable_fields"]
        labelled.append({"era": era, "cohort": group(row), "development": opened < SPLIT_MS, **match})
    path = folder / "all_source_results.jsonl"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in labelled:
            stream.write(json.dumps(row) + "\n")
    report["artifact_sha256"][path.name] = sha(path)
    path = folder / "extras.jsonl"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for index in extra:
            stream.write(json.dumps({"comparison_prediction_index": index, **kept[index]}, default=str) + "\n")
    report["artifact_sha256"][path.name] = sha(path)
    extras_by = Counter()
    for index in extra:
        p = kept[index]
        extras_by[(p["symbol"], era_of(p["open_ms"], GOLD_ERAS if p["symbol"] == "XAUUSD+" else FIXED_ERAS))] += 1
    report["by_cohort_era"] = {f"{c}|{e}": {"source_rows": total_by[(c, e)], "exact": exact_by[(c, e)]}
                                for (c, e) in sorted(total_by)}
    report["extras_by_symbol_era"] = {f"{s}|{e}": n for (s, e), n in sorted(extras_by.items())}
    dev = [m for m in labelled if m["development"]]
    report["development_before_2026-09-21"] = {"source_rows": len(dev), "exact": sum(m["exact_all_observable_fields"] for m in dev)}
    report["later_not_unseen"] = {"source_rows": len(labelled) - len(dev),
                                  "exact": sum(m["exact_all_observable_fields"] for m in labelled if not m["development"])}
    write_json(folder / "report.json", report)
    print(json.dumps(score))
    for key, value in report["by_cohort_era"].items():
        print(key, value)


if __name__ == "__main__":
    main()
