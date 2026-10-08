"""Score immutable predictions in the ledger window, retaining warmup state.

No rerun/reset/refit. Warmup trades closed before the source window are outside
the comparison scope, not extra orders; positions still open at its start stay.
"""

import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

from probe_vantage_feed import ROOT, group, sha, stamp, write_json
from strict_source_matcher import match_exact


def main():
    target = ROOT / "data/vantage_prespecified_source_window_20261008"
    target.mkdir(exist_ok=False)
    prior = ROOT / "data/vantage_prespecified_benchmarks_20261008"
    source_path = ROOT / "data/orders_35462.jsonl"
    source = [json.loads(line, parse_float=Decimal) for line in source_path.read_text(encoding="utf-8").splitlines()]
    start_ms = round((min(stamp(row["open_time"]) for row in source) - 10800) * 1000)
    end_ms = round((max(stamp(row["close_time"]) for row in source) - 10800 + 1) * 1000)
    report = {"source_rows": len(source), "source_sha256": sha(source_path),
              "original_replay_report_sha256": sha(prior / "report.json"), "script_sha256": sha(__file__),
              "source_window_start_inferred_utc": datetime.fromtimestamp(start_ms / 1000, timezone.utc).isoformat(),
              "source_window_end_exclusive_inferred_utc": datetime.fromtimestamp(end_ms / 1000, timezone.utc).isoformat(),
              "selection": "exclude only predictions closed before source start or opening after source end; retain boundary-active positions; no refit/no state resets",
              "all_symbols_scored": True, "parameter_selection": "old prespecified benchmarks, not unseen holdout",
              "source_feed_identity_verified": False, "full_source_clone_complete": False, "models": []}
    for path in sorted(prior.glob("*_predictions.jsonl")):
        model = path.name.removesuffix("_predictions.jsonl")
        predictions = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        kept = [row for row in predictions if row["open_ms"] < end_ms
                and (row["close_ms"] is None or row["close_ms"] >= start_ms)]
        matches, extras, score = match_exact(source, kept)
        write_json(target / f"{model}_kept_original_prediction_indices.json", [row["prediction_index"] for row in kept])
        write_json(target / f"{model}_extra_original_prediction_indices.json", [kept[index]["prediction_index"] for index in extras])
        with (target / f"{model}_all_source_results.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
            for row in matches:
                if row["exact_prediction_index"] is not None:
                    row["original_prediction_index"] = kept[row["exact_prediction_index"]]["prediction_index"]
                handle.write(json.dumps(row) + "\n")
        matched_by_cohort = Counter(group(row) for row, result in zip(source, matches) if result["exact_all_observable_fields"])
        report["models"].append({"model": model, "immutable_prediction_sha256": sha(path),
                                 "predictions_including_warmup": len(predictions), "outside_window_predictions": len(predictions) - len(kept),
                                 "cohorts": {cohort: {"source_orders": sum(group(row) == cohort for row in source),
                                                      "exact": matched_by_cohort[cohort]} for cohort in sorted({group(row) for row in source})}, **score})
    write_json(target / "report.json", report)
    print(json.dumps(report["models"], indent=2), flush=True)


if __name__ == "__main__":
    main()
