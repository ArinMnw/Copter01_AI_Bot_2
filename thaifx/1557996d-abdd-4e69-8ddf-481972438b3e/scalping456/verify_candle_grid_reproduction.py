"""Require identical every prediction/source-result/extra row across two runs."""

import argparse
import json
import re

from probe_vantage_feed import ROOT, sha, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", required=True)
    parser.add_argument("--second", required=True)
    args = parser.parse_args()
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", value) for value in (args.first, args.second)) or args.first == args.second:
        parser.error("Two distinct valid snapshot tags required")
    first, second = (ROOT / "data" / value for value in (args.first, args.second))
    left = json.loads((first / "report.json").read_text(encoding="utf-8"))
    right = json.loads((second / "report.json").read_text(encoding="utf-8"))
    assert len(left["models"]) == len(right["models"]) == 40
    for field in ("source_sha256", "models", "cache_provenance", "bars_provenance", "parity_checks"):
        assert left[field] == right[field], field
    filenames = sorted(path.name for path in first.glob("*.jsonl"))
    assert len(filenames) == 118
    assert filenames == sorted(path.name for path in second.glob("*.jsonl"))
    hashes = {}
    for name in filenames:
        digest = sha(first / name)
        assert digest == sha(second / name), name
        hashes[name] = digest
    result = {"first_report_sha256": sha(first / "report.json"), "second_report_sha256": sha(second / "report.json"),
              "verifier_sha256": sha(__file__), "source_sha256": right["source_sha256"],
              "data_file_sha256": hashes, "identical_data_files": len(hashes),
              "all_38_predictions_identical": True, "all_40_source_and_extra_outputs_identical": True,
              "model_config_scores_phases_identical": True, "full_source_clone_complete": False,
              "interpretation": "Reproducible rejected hypotheses, not original EA recovered"}
    write_json(second / "reproduction_audit.json", result)
    print("Reproduction passed: 118 identical files, all prediction/result/extra fields; NOT 100% clone", flush=True)


if __name__ == "__main__":
    main()
