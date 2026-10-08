"""32 preregistered paper pending candidates; all-source strict/entry diagnostics."""

import argparse
import json
import re
from collections import Counter, defaultdict, deque
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal

from diagnose_quote_paths import QuoteIndex
from probe_vantage_feed import ROOT, group, sha, stamp, write_json
from replay_pending_vector import replay_pending
from replay_vantage_candle_grid import START, END, load_ticks, phase
from strict_source_matcher import decimal, enrich_prediction, match_exact, source_record
from test_pending_stop import candidates, reference_pending


def candidate_name(config):
    execution = config.execution
    return f"pending_{config.anchor_mode}_{config.opposite_policy}_entry{config.entry_fill_mode}_stop{execution.stop_fill_mode}_a{execution.trailing_activation_points}d{execution.trailing_distance_points}"


def entry_key(row, without_lot=False):
    return (row["symbol"], row["side"], row["open_second"],
            decimal(row["open_price"], ".01" if row["symbol"] == "XAUUSD+" else ".001"),
            None if without_lot else decimal(row["volume"]))


def entry_diagnostics(source, predictions):
    outputs, used_sets = [], []
    for without_lot in (False, True):
        buckets = defaultdict(deque)
        for i, row in enumerate(predictions):
            buckets[entry_key(row, without_lot)].append(i)
        indices, used = [], set()
        for row in source:
            eligible = buckets[entry_key(source_record(row), without_lot)]
            matched = eligible.popleft() if eligible else None
            indices.append(matched)
            if matched is not None:
                used.add(matched)
        outputs.append(indices)
        used_sets.append(used)
    return outputs, used_sets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--chunk-size", type=int, default=256)
    parser.add_argument("--require-valid-trail", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag) or args.chunk_size <= 0:
        parser.error("Invalid tag/chunk size")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    files = ("strategy_scalping456.py", "replay_pending_vector.py", "replay_vantage_pending.py",
             "strict_source_matcher.py", "test_pending_stop.py", "EXPERIMENT_PENDING_STOP_PLAN.md")
    if args.require_valid_trail:
        files += ("EXPERIMENT_PENDING_TRAIL_GUARD_PLAN.md", "test_pending_trail_guard.py")
    hashes = {name: sha(ROOT / name) for name in files}
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "code_plan_sha256": hashes,
              "start_inferred_utc": START.isoformat(), "end_exclusive_inferred_utc": END.isoformat(),
              "chunk_size": args.chunk_size, "source_parse_order": "after all32 trajectories generated",
              "require_valid_trail": args.require_valid_trail,
              "full_source_clone_complete": False, "source_feed_identity_verified": False,
              "method": "continuous_unknown_startup_no_source_actions_no_day_or_split_resets",
              "validation_not_unseen": True, "lot_and_engines": "fixedlot10 XAU prototypes; every Fixed source row remains missing",
              "parity_checks": [], "models": [], "artifact_sha256": {}}
    write_json(folder / "run_manifest.json", report)
    (times, bids, asks), provenance = load_ticks("vantage_gold_shift3", "XAUUSD")
    report["cache_provenance"] = provenance
    indices = QuoteIndex(bids), QuoteIndex(asks)
    start = round(datetime(2026, 9, 7, tzinfo=timezone.utc).timestamp() * 1000)
    sample = (times >= start) & (times < start + 3600000)
    configurations = {}
    for config in candidates():
        config = replace(config, require_valid_trail=args.require_valid_trail)
        name = candidate_name(config)
        expected = reference_pending(times[sample], bids[sample], asks[sample], config)
        actual = replay_pending(times[sample], bids[sample], asks[sample], config, chunk_size=args.chunk_size)
        if actual != expected:
            raise RuntimeError("Actual-feed reference parity failed: " + name)
        report["parity_checks"].append({"model": name, "sample_ticks": int(sample.sum()), "all_fields_equal": True,
                                        "sample_predictions": len(actual)})
        predicted = replay_pending(times, bids, asks, config, indices=indices, chunk_size=args.chunk_size)
        path = folder / f"{name}_predictions.jsonl"
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            for i, row in enumerate(predicted):
                stream.write(json.dumps({"prediction_index": i, **enrich_prediction(row, "XAUUSD+", "sl")}) + "\n")
        report["artifact_sha256"][path.name] = sha(path)
        configurations[name] = {"config": asdict(config), "predictions_including_warmup": len(predicted)}
        print(json.dumps({"generated": name, "predictions": len(predicted)}), flush=True)
        del predicted
    del times, bids, asks, indices
    assert len(configurations) == 32
    if hashes != {name: sha(ROOT / name) for name in files}:
        raise RuntimeError("Code/plan changed during replay")
    source_path = ROOT / "data/orders_35462.jsonl"
    if sha(source_path) != "b8f5f75de07ba335ba607855167b5c77600954561c7c740621a335fa1b9825f1":
        raise RuntimeError("Source snapshot changed")
    source = [json.loads(line, parse_float=Decimal) for line in source_path.read_text(encoding="utf-8").splitlines()]
    assert len(source) == len({row["ticket"] for row in source}) == 35462
    report["source_sha256"] = sha(source_path)
    phases = {row["ticket"]: phase(round((stamp(row["open_time"]) - 10800) * 1000), round((stamp(row["close_time"]) - 10800) * 1000)) for row in source}
    start_ms = round((min(stamp(row["open_time"]) for row in source) - 10800) * 1000)
    end_ms = round((max(stamp(row["close_time"]) for row in source) - 10800 + 1) * 1000)
    for name, configuration in configurations.items():
        predicted = [json.loads(line) for line in (folder / f"{name}_predictions.jsonl").read_text(encoding="utf-8").splitlines()]
        kept = [{k: v for k, v in row.items() if k != "prediction_index"} for row in predicted
                if row["open_ms"] < end_ms and (row["close_ms"] is None or row["close_ms"] >= start_ms)]
        matches, extra, score = match_exact(source, kept)
        paths = {}
        paths["all_source_results"] = [{"phase": phases[row["ticket"]], **row} for row in matches]
        paths["extras"] = [{"comparison_prediction_index": i, **kept[i]} for i in extra]
        diagnostic, used = entry_diagnostics(source, kept)
        paths["entry_all_source_results"] = [{"ticket": row["ticket"], "symbol": row["symbol"], "phase": phases[row["ticket"]],
            "entry_with_lot_index": diagnostic[0][i], "entry_without_lot_index": diagnostic[1][i],
            "not_full_order_success": True} for i, row in enumerate(source)]
        paths["entry_extras"] = [{"comparison_prediction_index": i, "entry_with_lot_unmatched": i not in used[0],
            "entry_without_lot_unmatched": i not in used[1], **kept[i]} for i in range(len(kept)) if i not in used[0] or i not in used[1]]
        for label, rows in paths.items():
            path = folder / f"{name}_{label}.jsonl"
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                for row in rows:
                    stream.write(json.dumps(row) + "\n")
            report["artifact_sha256"][path.name] = sha(path)
        phase_scores = {}
        for label in sorted(set(phases.values())):
            subset = [row for row in source if phases[row["ticket"]] == label]
            selected = [row for row in kept if phase(row["open_ms"], row["close_ms"]) == label]
            _, _, phase_scores[label] = match_exact(subset, selected)
        exact = Counter(group(row) for row, result in zip(source, matches) if result["exact_all_observable_fields"])
        cohorts = Counter(group(row) for row in source)
        model = {"name": name, **configuration, **score, "phases": phase_scores,
            "cohorts": {c: {"source_rows": n, "exact": exact[c]} for c, n in cohorts.items()},
            "entry_diagnostics_not_success": {"with_lot": {"matched": len(used[0]), "missing": 35462 - len(used[0]), "extra": len(kept) - len(used[0])},
                                               "without_lot": {"matched": len(used[1]), "missing": 35462 - len(used[1]), "extra": len(kept) - len(used[1])}}}
        report["models"].append(model)
        print(json.dumps({"scored": name, **score, "entry_diagnostics": model["entry_diagnostics_not_success"]}), flush=True)
    write_json(folder / "report.json", report)


if __name__ == "__main__":
    main()
