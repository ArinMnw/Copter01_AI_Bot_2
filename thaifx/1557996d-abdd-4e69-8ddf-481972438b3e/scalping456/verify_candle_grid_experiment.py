"""Verify completed artifacts: all rows, uniqueness, extras, phases and hashes.

This is a completion audit of the experiment, not of the 100% cloning goal.
"""

import argparse
import json
import re
from decimal import Decimal

from probe_vantage_feed import ROOT, sha, stamp, write_json
from strict_source_matcher import key, source_record


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid snapshot tag")
    folder = ROOT / "data" / args.tag
    report_path = folder / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    source_path = ROOT / "data/orders_35462.jsonl"
    source = [json.loads(line, parse_float=Decimal) for line in source_path.read_text(encoding="utf-8").splitlines()]
    assert len(source) == 35462 and sha(source_path) == report["source_sha256"]
    by_ticket = {row["ticket"]: row for row in source}
    assert len(by_ticket) == 35462
    assert len(report["models"]) == 40 and len(report["parity_checks"]) == 36
    assert all(check["all_fields_equal"] for check in report["parity_checks"])
    for name, expected in report["code_plan_sha256"].items():
        assert sha(ROOT / name) == expected, name
    start_ms = round((min(stamp(row["open_time"]) for row in source) - 10800) * 1000)
    end_ms = round((max(stamp(row["close_time"]) for row in source) - 10800 + 1) * 1000)
    for model in report["models"]:
        name = model["name"]
        if "components" in model["config"]:
            predictions = []
            for component in model["config"]["components"]:
                predictions.extend({"component": component, **{k: v for k, v in row.items() if k not in ("prediction_index", "engine_label")}}
                                   for row in read_jsonl(folder / f"{component}_predictions.jsonl"))
        else:
            predictions = [{k: v for k, v in row.items() if k not in ("prediction_index", "engine_label")}
                           for row in read_jsonl(folder / f"{name}_predictions.jsonl")]
        assert len(predictions) == model["predictions_including_warmup"]
        kept = [row for row in predictions if row["open_ms"] < end_ms and (row["close_ms"] is None or row["close_ms"] >= start_ms)]
        assert len(kept) == model["predicted_orders"]
        results = read_jsonl(folder / f"{name}_all_source_results.jsonl")
        assert len(results) == 35462 and {r["ticket"] for r in results} == set(by_ticket)
        used = set()
        for result in results:
            actual = by_ticket[result["ticket"]]
            assert result["symbol"] == actual["symbol"]
            assert result["exact_all_observable_fields"] == (result["exact_prediction_index"] is not None)
            if result["exact_prediction_index"] is not None:
                index = result["exact_prediction_index"]
                assert index not in used and 0 <= index < len(kept)
                used.add(index)
                assert result["source_close_behavior_verified"]
                assert key(source_record(actual)) == key(kept[index])
        assert len(used) == model["exact_all_observable_fields"]
        assert model["missing"] == 35462 - len(used)
        extras = read_jsonl(folder / f"{name}_extras.jsonl")
        assert len(extras) == model["extra"] == len(kept) - len(used)
        indices = {row["comparison_prediction_index"] for row in extras}
        assert len(indices) == len(extras) and indices == set(range(len(kept))) - used
        for extra in extras:
            index = extra["comparison_prediction_index"]
            assert {k: v for k, v in extra.items() if k != "comparison_prediction_index"} == kept[index]
        assert sum(p["source_orders"] for p in model["phases"].values()) == 35462
        assert sum(p["predicted_orders"] for p in model["phases"].values()) == len(kept)
        assert model["timing_tolerance_seconds"] == 0 and not model["complete"]
        print(name, "all source rows/extras/hash scope verified", flush=True)
    qa = {"experiment_report_sha256": sha(report_path), "verifier_sha256": sha(__file__),
          "source_sha256": sha(source_path), "all_40_model_artifacts_verified": True,
          "unit_test_module_sha256": {name: sha(ROOT / name) for name in ("test_reconstruction.py", "test_vantage_readonly.py", "test_strict_source_matcher.py", "test_candle_grid_replay.py", "test_broker_bars_trial.py")},
          "output_sha256": {path.name: sha(path) for path in sorted(folder.glob("*")) if path.is_file()},
          "full_source_clone_complete": False,
          "interpretation": "Experiment artifacts reconciled; all models still fail original goal"}
    write_json(folder / "qa_audit.json", qa)
    print("Full experiment QA passed, not strategy clone", flush=True)


if __name__ == "__main__":
    main()
