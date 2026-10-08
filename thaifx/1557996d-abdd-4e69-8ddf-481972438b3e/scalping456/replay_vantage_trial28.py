"""Two evidence-motivated continuous trial candidates, not an EA clone."""

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal

from probe_vantage_feed import ROOT, group, sha, stamp, write_json
from replay_vantage_candle_grid import START, END, load_ticks, phase
from replay_vector import replay_candidate
from strategy_scalping456 import EntrySignal, ExitSignal, Scalping456Config, Scalping456Strategy, Tick
from strict_source_matcher import enrich_prediction, match_exact


def reference_trial(times, bids, asks, config):
    strategy = Scalping456Strategy(config)
    result, pending = [], None
    for instant, bid, ask in zip(times, bids, asks):
        signal = strategy.on_tick(Tick(datetime.fromtimestamp(int(instant) / 1000, timezone.utc), float(bid), float(ask)))
        if isinstance(signal, EntrySignal):
            pending = {"open_ms": int(instant), "side": signal.side.value, "volume": signal.volume, "open_price": signal.price}
        elif isinstance(signal, ExitSignal):
            result.append({**pending, "close_ms": int(instant), "close_price": signal.price})
            pending = None
    if pending:
        result.append({**pending, "close_ms": None, "close_price": None})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    names = ("strategy_scalping456.py", "replay_vector.py", "replay_vantage_trial28.py",
             "strict_source_matcher.py", "replay_vantage_candle_grid.py", "EXPERIMENT_TRIAL28_PLAN.md")
    hashes = {name: sha(ROOT / name) for name in names}
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "code_plan_sha256": hashes,
              "start_inferred_utc": START.isoformat(), "end_exclusive_inferred_utc": END.isoformat(),
              "parameters_chosen_from_development_path_diagnostics": True, "trial_validation_source_rows": 0,
              "validation_not_unseen": True, "source_parse_order": "after all predictions generated",
              "source_feed_identity_verified": False, "full_source_clone_complete": False,
              "method": "continuous_from_first_warmup_tick_no_ledger_actions_no_session_gates_no_resets",
              "models": [], "parity_checks": [], "artifact_sha256": {}}
    write_json(folder / "run_manifest.json", report)
    (times, bids, asks), provenance = load_ticks("vantage_fixed_shift3", "FixedVol20")
    report["cache_provenance"] = provenance
    sample = (times >= 1788739200000) & (times < 1788825600000)  # 2026-09-07 UTC day, not a source entry/close.
    predictions = {}
    for fill in ("level", "quote"):
        name = "fixed_trial_a0d280_" + fill
        config = Scalping456Config.fixedvol20_trial(entry_reversal_points=300, trailing_activation_points=0,
                                                  trailing_distance_points=280, stop_fill_mode=fill)
        expected = reference_trial(times[sample], bids[sample], asks[sample], config)
        actual = replay_candidate(times[sample], bids[sample], asks[sample], config)
        if expected != actual:
            raise RuntimeError("Actual-feed vector/reference parity differs")
        report["parity_checks"].append({"model": name, "ticks": int(sample.sum()), "predictions": len(actual), "all_fields_equal": True})
        predicted = [enrich_prediction(row, "FixedVol20", "sl") for row in replay_candidate(times, bids, asks, config)]
        path = folder / f"{name}_predictions.jsonl"
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            for index, row in enumerate(predicted):
                stream.write(json.dumps({"prediction_index": index, **row}) + "\n")
        predictions[name] = (predicted, asdict(config))
        report["artifact_sha256"][path.name] = sha(path)
        print("Generated", name, len(predicted), flush=True)
    if hashes != {name: sha(ROOT / name) for name in names}:
        raise RuntimeError("Code/plan changed during replay")
    source_path = ROOT / "data/orders_35462.jsonl"
    if sha(source_path) != "b8f5f75de07ba335ba607855167b5c77600954561c7c740621a335fa1b9825f1":
        raise RuntimeError("Source snapshot changed")
    source = [json.loads(line, parse_float=Decimal) for line in source_path.read_text(encoding="utf-8").splitlines()]
    report["source_sha256"] = sha(source_path)
    phases = {row["ticket"]: phase(round((stamp(row["open_time"]) - 10800) * 1000), round((stamp(row["close_time"]) - 10800) * 1000)) for row in source}
    start_ms = round((min(stamp(row["open_time"]) for row in source) - 10800) * 1000)
    end_ms = round((max(stamp(row["close_time"]) for row in source) - 10800 + 1) * 1000)
    for name, (predicted, config) in predictions.items():
        kept = [row for row in predicted if row["open_ms"] < end_ms and (row["close_ms"] is None or row["close_ms"] >= start_ms)]
        matches, extra, score = match_exact(source, kept)
        path = folder / f"{name}_all_source_results.jsonl"
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            for row in matches:
                stream.write(json.dumps({"phase": phases[row["ticket"]], **row}) + "\n")
        report["artifact_sha256"][path.name] = sha(path)
        path = folder / f"{name}_extras.jsonl"
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            for index in extra:
                stream.write(json.dumps({"comparison_prediction_index": index, **kept[index]}) + "\n")
        report["artifact_sha256"][path.name] = sha(path)
        exact = Counter(group(row) for row, match in zip(source, matches) if match["exact_all_observable_fields"])
        cohorts = Counter(group(row) for row in source)
        phase_scores = {}
        for label in sorted(set(phases.values())):
            subset = [row for row in source if phases[row["ticket"]] == label]
            selected = [row for row in kept if phase(row["open_ms"], row["close_ms"]) == label]
            _, _, phase_scores[label] = match_exact(subset, selected)
        report["models"].append({"name": name, "config": config, "predictions_including_warmup": len(predicted),
                                  "outside_comparison_window": len(predicted) - len(kept), "phases": phase_scores,
                                  "cohorts": {c: {"source_rows": n, "exact": exact[c]} for c, n in cohorts.items()}, **score})
        print(name, json.dumps(score), flush=True)
    write_json(folder / "report.json", report)


if __name__ == "__main__":
    main()
