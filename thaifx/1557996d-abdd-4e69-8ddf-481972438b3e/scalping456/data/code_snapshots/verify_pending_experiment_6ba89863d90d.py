"""Audit complete pending experiment populations; not certify original strategy."""

import argparse
import json
import re
from collections import Counter
from decimal import Decimal

from probe_vantage_feed import ROOT, sha, stamp, write_json
from replay_vantage_candle_grid import phase
from replay_vantage_pending import entry_key
from strict_source_matcher import match_exact, source_record
from verify_candle_grid_experiment import read_jsonl


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    folder = ROOT / "data" / args.tag
    report_path = folder / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    source_path = ROOT / "data/orders_35462.jsonl"
    source = [json.loads(line, parse_float=Decimal) for line in source_path.read_text(encoding="utf-8").splitlines()]
    assert len(source) == len({row["ticket"] for row in source}) == 35462
    assert sha(source_path) == report["source_sha256"]
    assert len(report["models"]) == len(report["parity_checks"]) == 32
    assert all(row["all_fields_equal"] for row in report["parity_checks"])
    assert len(report["artifact_sha256"]) == 160
    for name, digest in report["code_plan_sha256"].items():
        assert sha(ROOT / name) == digest, name
    for name, digest in report["artifact_sha256"].items():
        assert sha(folder / name) == digest, name
    first = round((min(stamp(row["open_time"]) for row in source) - 10800) * 1000)
    last = round((max(stamp(row["close_time"]) for row in source) - 10800 + 1) * 1000)
    source_records = [source_record(row) for row in source]
    for model in report["models"]:
        name = model["name"]
        predicted = read_jsonl(folder / f"{name}_predictions.jsonl")
        assert [row["prediction_index"] for row in predicted] == list(range(len(predicted)))
        assert len(predicted) == model["predictions_including_warmup"]
        kept = [{k: v for k, v in row.items() if k != "prediction_index"} for row in predicted
                if row["open_ms"] < last and (row["close_ms"] is None or row["close_ms"] >= first)]
        results = read_jsonl(folder / f"{name}_all_source_results.jsonl")
        assert len(results) == len({row["ticket"] for row in results}) == 35462
        expected, extra, score = match_exact(source, kept)
        assert [{k: v for k, v in row.items() if k != "phase"} for row in results] == expected
        assert all(model[key] == value for key, value in score.items())
        extras = read_jsonl(folder / f"{name}_extras.jsonl")
        assert extras == [{"comparison_prediction_index": i, **kept[i]} for i in extra]
        entry_results = read_jsonl(folder / f"{name}_entry_all_source_results.jsonl")
        assert len(entry_results) == len({row["ticket"] for row in entry_results}) == 35462
        used = [set(), set()]
        for i, (row, result, entry) in enumerate(zip(source, results, entry_results)):
            assert row["ticket"] == result["ticket"] == entry["ticket"]
            assert row["symbol"] == result["symbol"] == entry["symbol"]
            split = phase(round((stamp(row["open_time"]) - 10800) * 1000), round((stamp(row["close_time"]) - 10800) * 1000))
            assert entry["phase"] == result["phase"] == split
            assert entry["not_full_order_success"]
            for without_lot, keyname in enumerate(("entry_with_lot_index", "entry_without_lot_index")):
                index = entry[keyname]
                if index is not None:
                    assert 0 <= index < len(kept) and index not in used[without_lot]
                    assert entry_key(source_records[i], bool(without_lot)) == entry_key(kept[index], bool(without_lot))
                    used[without_lot].add(index)
        entry_extras = read_jsonl(folder / f"{name}_entry_extras.jsonl")
        expected_extra = [{"comparison_prediction_index": i, "entry_with_lot_unmatched": i not in used[0],
                           "entry_without_lot_unmatched": i not in used[1], **kept[i]} for i in range(len(kept))
                          if i not in used[0] or i not in used[1]]
        assert entry_extras == expected_extra
        for number, label in enumerate(("with_lot", "without_lot")):
            source_keys = Counter(entry_key(row, bool(number)) for row in source_records)
            predicted_keys = Counter(entry_key(row, bool(number)) for row in kept)
            assert len(used[number]) == sum(min(n, predicted_keys[key]) for key, n in source_keys.items())
            assert model["entry_diagnostics_not_success"][label] == {"matched": len(used[number]), "missing": 35462 - len(used[number]), "extra": len(kept) - len(used[number])}
        assert sum(p["source_orders"] for p in model["phases"].values()) == 35462
        assert sum(p["predicted_orders"] for p in model["phases"].values()) == len(kept)
        assert sum(p["exact_all_observable_fields"] for p in model["phases"].values()) == model["exact_all_observable_fields"]
        assert sum(c["source_rows"] for c in model["cohorts"].values()) == 35462
        assert model["timing_tolerance_seconds"] == 0 and not model["complete"]
        print(name, "all-source/extras/entry uniqueness/hashes verified", flush=True)
    write_json(folder / "qa_audit.json", {"report_sha256": sha(report_path), "verifier_sha256": sha(__file__),
        "source_sha256": sha(source_path), "all32_models_and160_artifacts_verified": True,
        "full_source_clone_complete": False, "diagnostic_counts_not_goal_metrics": True})


if __name__ == "__main__":
    main()
