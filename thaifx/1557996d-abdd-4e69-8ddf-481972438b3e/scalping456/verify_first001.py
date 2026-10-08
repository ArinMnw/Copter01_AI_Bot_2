"""Audit four component replays plus all original source rows and quote evidence."""

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict
from decimal import Decimal

import numpy as np

from diagnose_quote_paths import QuoteIndex
from first001_components import FIRST_MS, END_MS, controls, load_quotes, load_source_scope, entry_record, predecessor_index
from probe_vantage_feed import ROOT, sha, stamp, write_json
from replay_vantage_pending import entry_key
from strict_source_matcher import enrich_prediction, match_exact, source_record


def read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def verify_replay(tag, source, scope):
    folder = ROOT / "data" / tag
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    assert len(report["models"]) == len(report["parity_checks"]) == 4
    assert all(r["all_fields_equal"] for r in report["parity_checks"])
    assert len(report["artifact_sha256"]) == 25
    assert report["source_sha256"] == sha(ROOT / "data/orders_35462.jsonl")
    for name, digest in report["code_plan_sha256"].items():
        assert sha(ROOT / name) == digest
    for name, digest in report["artifact_sha256"].items():
        assert sha(folder / name) == digest
    ids = {r["ticket"] for r in scope}
    inventory = read_lines(folder / "all_original_source_scope_inventory.jsonl")
    assert len(inventory) == len({r["ticket"] for r in inventory}) == 35462
    assert inventory == [{"ticket": r["ticket"], "symbol": r["symbol"], "in_component": r["ticket"] in ids,
                          "outside_component_not_parent_goal_complete": r["ticket"] not in ids} for r in source]
    for model, config in zip(report["models"], controls()):
        name = model["name"]
        assert model["config"] == asdict(config)
        predicted = read_lines(folder / f"{name}_predictions.jsonl")
        assert len(predicted) == model["predictions_including_warmup"]
        assert [r["prediction_index"] for r in predicted] == list(range(len(predicted)))
        for p in predicted:
            assert Decimal(str(p["volume"])) == Decimal(".01")
            raw = {key: p[key] for key in ("open_ms", "close_ms", "side", "volume", "open_price", "close_price")}
            expected = enrich_prediction(raw, "XAUUSD+", "sl")
            assert {k: v for k, v in p.items() if k != "prediction_index"} == expected
        kept = [{k: v for k, v in p.items() if k != "prediction_index"} for p in predicted
                if p["open_ms"] < END_MS and (p["close_ms"] is None or p["close_ms"] >= FIRST_MS)]
        results, extra, score = match_exact(scope, kept)
        assert results == read_lines(folder / f"{name}_component_results.jsonl")
        assert score == model["component_score"]
        full, full_extra, full_score = match_exact(source, kept)
        assert full == read_lines(folder / f"{name}_all_original_source_results.jsonl")
        assert full_score == model["original35462_parent_score"] and full_extra == extra
        assert read_lines(folder / f"{name}_extras.jsonl") == [{"comparison_prediction_index": i, **kept[i]} for i in extra]
        entries = read_lines(folder / f"{name}_entry_component_results.jsonl")
        assert len(entries) == len({r["ticket"] for r in entries}) == 7312
        used = set()
        for r, entry in zip(scope, entries):
            assert r["ticket"] == entry["ticket"] and entry["not_full_order_success"]
            index = entry["entry_prediction_index"]
            if index is not None:
                assert index not in used and 0 <= index < len(kept)
                assert entry_key(source_record(r)) == entry_key(kept[index])
                used.add(index)
        a = Counter(entry_key(source_record(r)) for r in scope)
        b = Counter(entry_key(r) for r in kept)
        assert len(used) == sum(min(n, b[k]) for k, n in a.items())
        assert model["entry_only_not_success"] == {"matched": len(used), "missing": 7312 - len(used), "extra": len(kept) - len(used)}
        assert read_lines(folder / f"{name}_entry_extras.jsonl") == [{"comparison_prediction_index": i, **r}
                                                                    for i, r in enumerate(kept) if i not in used]
        print(name, "component/all-original/entry uniqueness/extras/hashes verified", flush=True)
    write_json(folder / "qa_full_audit.json", {"all4_models_and25_artifacts_verified": True,
               "report_sha256": sha(folder / "report.json"), "verifier_sha256": sha(__file__),
               "full_source_clone_complete": False, "component_score_not_parent_goal_success": True})


def verify_diagnostics(tag, source, scope):
    folder = ROOT / "data" / tag
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    assert report["source_sha256"] == sha(ROOT / "data/orders_35462.jsonl")
    assert report["script_sha256"] == sha(ROOT / "diagnose_first001.py")
    assert report["component_helpers_sha256"] == sha(ROOT / "first001_components.py")
    assert report["plan_sha256"] == sha(ROOT / "EXPERIMENT_FIRST001_PLAN.md")
    for name, digest in report["artifact_sha256"].items():
        assert sha(folder / name) == digest
    (times, bids, asks), _ = load_quotes()
    indices = QuoteIndex(bids), QuoteIndex(asks)
    closes, close_times = predecessor_index(scope)
    rows = read_lines(folder / "all_component_entry_exit_observations.jsonl")
    assert len(rows) == len({r["ticket"] for r in rows}) == 7312
    archived_path = ROOT / "data/vantage_path_constraints_20261008/all_source_quote_paths.jsonl"
    assert sha(archived_path) == report["archived_path_sha256"]
    ids = {r["ticket"] for r in scope}
    archived = {r["ticket"]: r for r in read_lines(archived_path) if r["ticket"] in ids}
    quote_seen, covered, crossed = 0, 0, 0
    for r, saved in zip(scope, rows):
        expected = entry_record(r, times, bids, asks, closes, close_times, indices)
        expected["archived_exit_observation"] = archived[r["ticket"]]
        assert saved == expected
        opening = round((stamp(r["open_time"]) - 10800) * 1000)
        lo, hi = np.searchsorted(times, (opening, opening + 1000))
        quotes = asks if r["trade_type"] == "buy" else bids
        seen = bool(np.any(np.abs(quotes[lo:hi] - float(r["open_price"])) < 1e-6))
        assert saved["source_price_seen_on_executable_side_in_reported_second"] == seen
        quote_seen += seen
        covered += hi > lo
        witness = saved["nominal_price1_cross_before_entry"]
        if witness:
            start = saved["latest_strict_source_predecessor"]["close_ms"] + 1000
            a, b = np.searchsorted(times, (start, opening))
            level = witness["level"]
            hits = np.flatnonzero(quotes[a:b] >= level - 1e-9 if r["trade_type"] == "buy" else quotes[a:b] <= level + 1e-9)
            actual = int(times[a + hits[0]]) if len(hits) else None
            assert actual == witness["first_cross_ms"]
            crossed += actual is not None
    assert sum(r["source_rows"] for r in report["entry_by_side"].values()) == 7312
    assert sum(r["source_rows"] for r in report["exit_by_kind"].values()) == 7312
    assert quote_seen == sum(r["source_price_seen_on_executable_side_in_reported_second"] for r in report["entry_by_side"].values())
    write_json(folder / "qa_quote_audit.json", {"all7312_quote_records_archived_paths_and_bruteforce_crossings_verified": True,
               "report_sha256": sha(folder / "report.json"), "verifier_sha256": sha(__file__),
               "opening_second_quotes_covered": int(covered), "source_entry_prices_seen_on_executable_quotes": int(quote_seen),
               "unseen_entry_prices_under_direct_quote_fill_assumption": 7312 - int(quote_seen),
               "conditional_nominal_crossings_before_entry": int(crossed), "not_strategy_predictions": True,
               "full_source_clone_complete": False})
    print("all7312 quote records/archived paths/brute-force crossings verified", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-tag", required=True)
    parser.add_argument("--diagnostics-tag", required=True)
    args = parser.parse_args()
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", t) for t in (args.replay_tag, args.diagnostics_tag)):
        parser.error("Invalid output tag")
    source, scope = load_source_scope()
    verify_replay(args.replay_tag, source, scope)
    verify_diagnostics(args.diagnostics_tag, source, scope)


if __name__ == "__main__":
    main()
