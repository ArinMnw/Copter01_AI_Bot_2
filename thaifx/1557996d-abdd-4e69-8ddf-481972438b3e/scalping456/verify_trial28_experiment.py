"""Audit both trial experiments' entire source/extra populations, not goal success."""

import argparse
import json
import re
from decimal import Decimal

from probe_vantage_feed import ROOT, sha, stamp, write_json
from replay_vantage_candle_grid import phase
from strict_source_matcher import key, match_exact, source_record
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
    assert len(source) == 35462 and len({row["ticket"] for row in source}) == 35462
    assert sha(source_path) == report["source_sha256"]
    by_ticket = {row["ticket"]: row for row in source}
    assert len(report["models"]) == len(report["parity_checks"]) == 2
    assert all(check["all_fields_equal"] for check in report["parity_checks"])
    assert report["trial_validation_source_rows"] == 0
    for name, expected in report["code_plan_sha256"].items():
        assert sha(ROOT / name) == expected, name
    for name, expected in report["artifact_sha256"].items():
        assert sha(folder / name) == expected, name
    start_ms = round((min(stamp(row["open_time"]) for row in source) - 10800) * 1000)
    end_ms = round((max(stamp(row["close_time"]) for row in source) - 10800 + 1) * 1000)
    for model in report["models"]:
        name = model["name"]
        predicted = read_jsonl(folder / f"{name}_predictions.jsonl")
        assert [row["prediction_index"] for row in predicted] == list(range(len(predicted)))
        predicted = [{k: v for k, v in row.items() if k != "prediction_index"} for row in predicted]
        assert len(predicted) == model["predictions_including_warmup"]
        kept = [row for row in predicted if row["open_ms"] < end_ms and (row["close_ms"] is None or row["close_ms"] >= start_ms)]
        results = read_jsonl(folder / f"{name}_all_source_results.jsonl")
        assert len(results) == len({row["ticket"] for row in results}) == 35462
        assert {row["ticket"] for row in results} == set(by_ticket)
        expected, indices, score = match_exact(source, kept)
        assert [{k: v for k, v in row.items() if k != "phase"} for row in results] == expected
        assert all(model[k] == v for k, v in score.items())
        used = set()
        for result in results:
            actual = by_ticket[result["ticket"]]
            expected_phase = phase(round((stamp(actual["open_time"]) - 10800) * 1000), round((stamp(actual["close_time"]) - 10800) * 1000))
            assert result["phase"] == expected_phase
            if result["exact_prediction_index"] is not None:
                index = result["exact_prediction_index"]
                assert index not in used
                used.add(index)
                assert key(source_record(actual)) == key(kept[index])
        extras = read_jsonl(folder / f"{name}_extras.jsonl")
        assert [row["comparison_prediction_index"] for row in extras] == indices
        for row in extras:
            assert {k: v for k, v in row.items() if k != "comparison_prediction_index"} == kept[row["comparison_prediction_index"]]
        assert sum(p["source_orders"] for p in model["phases"].values()) == 35462
        assert sum(p["predicted_orders"] for p in model["phases"].values()) == len(kept)
        assert sum(p["exact_all_observable_fields"] for p in model["phases"].values()) == len(used)
        assert not model["complete"] and model["timing_tolerance_seconds"] == 0
        print(name, "all-source/extras/hashes/matcher verified", flush=True)
    write_json(folder / "qa_audit.json", {"source_sha256": sha(source_path), "report_sha256": sha(report_path),
        "verifier_sha256": sha(__file__), "all_two_model_artifacts_verified": True,
        "full_source_clone_complete": False, "interpretation": "Experiment evidence is complete; neither model passes the goal"})


if __name__ == "__main__":
    main()
