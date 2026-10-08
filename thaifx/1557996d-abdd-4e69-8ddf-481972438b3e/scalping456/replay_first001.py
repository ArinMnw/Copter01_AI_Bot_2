"""Four fixed first-0.01 controls, predictions before outcomes, full inventories."""

import argparse
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone

from diagnose_quote_paths import QuoteIndex
from first001_components import WARMUP, END, FIRST_MS, END_MS, controls, load_quotes, load_source_scope
from probe_vantage_feed import ROOT, sha, write_json
from replay_pending_vector import replay_pending
from replay_vantage_pending import entry_diagnostics
from strict_source_matcher import enrich_prediction, match_exact
from test_pending_stop import reference_pending


def save_jsonl(path, rows):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for r in rows:
            handle.write(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid output tag")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    files = ("first001_components.py", "replay_first001.py", "strategy_scalping456.py", "replay_pending_vector.py",
             "strict_source_matcher.py", "replay_vantage_pending.py", "test_pending_stop.py", "EXPERIMENT_FIRST001_PLAN.md")
    sealed = {name: sha(ROOT / name) for name in files}
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "code_plan_sha256": sealed,
              "warmup_start_utc": WARMUP.isoformat(), "end_exclusive_utc": END.isoformat(),
              "source_parse_order": "after all4 prediction trajectories", "validation_not_unseen": True,
              "source_feed_identity_verified": False, "full_source_clone_complete": False,
              "method": "continuous fixedlot0.01 no ledger resets no session changes no forced final close",
              "models": [], "parity_checks": [], "artifact_sha256": {}}
    write_json(folder / "run_manifest.json", report)
    (times, bids, asks), provenance = load_quotes()
    report["cache_provenance"] = provenance
    report["consumed_ticks"] = len(times)
    indices = QuoteIndex(bids), QuoteIndex(asks)
    sample_start = round(datetime(2026, 8, 24, tzinfo=timezone.utc).timestamp() * 1000)
    sample = (times >= sample_start) & (times < sample_start + 3600000)
    configurations = {}
    for config in controls():
        name = f"first001_entry{config.entry_fill_mode}_stop{config.execution.stop_fill_mode}"
        expected = reference_pending(times[sample], bids[sample], asks[sample], config)
        actual = replay_pending(times[sample], bids[sample], asks[sample], config, chunk_size=256)
        assert expected == actual, name
        report["parity_checks"].append({"name": name, "sample_ticks": int(sample.sum()), "all_fields_equal": True})
        raw = replay_pending(times, bids, asks, config, indices=indices, chunk_size=256)
        path = folder / f"{name}_predictions.jsonl"
        save_jsonl(path, ({"prediction_index": i, **enrich_prediction(r, "XAUUSD+", "sl")} for i, r in enumerate(raw)))
        configurations[name] = {"config": asdict(config), "predictions_including_warmup": len(raw)}
        report["artifact_sha256"][path.name] = sha(path)
        print(json.dumps({"generated": name, "predictions": len(raw)}), flush=True)
    del times, bids, asks, indices, raw
    assert sealed == {name: sha(ROOT / name) for name in files}
    source, scope = load_source_scope()
    report["source_sha256"] = sha(ROOT / "data/orders_35462.jsonl")
    scope_ids = {r["ticket"] for r in scope}
    inventory = folder / "all_original_source_scope_inventory.jsonl"
    save_jsonl(inventory, ({"ticket": r["ticket"], "symbol": r["symbol"], "in_component": r["ticket"] in scope_ids,
                           "outside_component_not_parent_goal_complete": r["ticket"] not in scope_ids} for r in source))
    report["artifact_sha256"][inventory.name] = sha(inventory)
    for name, configuration in configurations.items():
        predicted = [json.loads(line) for line in (folder / f"{name}_predictions.jsonl").read_text(encoding="utf-8").splitlines()]
        kept = [{k: v for k, v in r.items() if k != "prediction_index"} for r in predicted
                if r["open_ms"] < END_MS and (r["close_ms"] is None or r["close_ms"] >= FIRST_MS)]
        results, extra, score = match_exact(scope, kept)
        full_results, full_extra, full_score = match_exact(source, kept)
        assert extra == full_extra
        (entries, _), used = entry_diagnostics(scope, kept)
        artifacts = {
            "component_results": results, "all_original_source_results": full_results,
            "extras": [{"comparison_prediction_index": i, **kept[i]} for i in extra],
            "entry_component_results": [{"ticket": r["ticket"], "entry_prediction_index": entries[i], "not_full_order_success": True}
                                         for i, r in enumerate(scope)],
            "entry_extras": [{"comparison_prediction_index": i, **r} for i, r in enumerate(kept) if i not in used[0]],
        }
        for label, values in artifacts.items():
            path = folder / f"{name}_{label}.jsonl"
            save_jsonl(path, values)
            report["artifact_sha256"][path.name] = sha(path)
        model = {"name": name, **configuration, "component_score": score, "original35462_parent_score": full_score,
                 "entry_only_not_success": {"matched": len(used[0]), "missing": 7312 - len(used[0]), "extra": len(kept) - len(used[0])}}
        report["models"].append(model)
        print(json.dumps({"scored": name, "component": score, "entry_only": model["entry_only_not_success"]}), flush=True)
    write_json(folder / "report.json", report)


if __name__ == "__main__":
    main()
