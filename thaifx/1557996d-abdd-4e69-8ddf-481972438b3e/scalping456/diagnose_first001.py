"""All 7312 first-lot entry witnesses and archived exit observations, not signals."""

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from diagnose_quote_paths import QuoteIndex, describe
from first001_components import entry_record, load_quotes, load_source_scope, predecessor_index
from probe_vantage_feed import ROOT, sha, write_json
from replay_first001 import save_jsonl


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid output tag")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    source, scope = load_source_scope()
    (times, bids, asks), provenance = load_quotes()
    indices = QuoteIndex(bids), QuoteIndex(asks)
    closes, close_times = predecessor_index(scope)
    records = [entry_record(r, times, bids, asks, closes, close_times, indices) for r in scope]
    path_folder = ROOT / "data/vantage_path_constraints_20261008"
    old_report = json.loads((path_folder / "report.json").read_text(encoding="utf-8"))
    path_source = path_folder / "all_source_quote_paths.jsonl"
    assert sha(path_source) == old_report["all_source_paths_sha256"]
    assert old_report["source_sha256"] == sha(ROOT / "data/orders_35462.jsonl")
    scope_ids = {r["ticket"] for r in scope}
    paths = [json.loads(line) for line in path_source.read_text(encoding="utf-8").splitlines()
             if json.loads(line)["ticket"] in scope_ids]
    assert len(paths) == len({r["ticket"] for r in paths}) == 7312
    path_index = {r["ticket"]: r for r in paths}
    for r in records:
        r["archived_exit_observation"] = path_index[r["ticket"]]
    target = folder / "all_component_entry_exit_observations.jsonl"
    save_jsonl(target, records)
    stats, values = defaultdict(Counter), defaultdict(lambda: defaultdict(list))
    for r, observed in zip(scope, records):
        side = observed["source_side"]
        stat = stats[side]
        stat["source_rows"] += 1
        stat["with_opening_second_quotes"] += observed["opening_second_quote_count"] > 0
        for name in ("source_price_seen_on_bid_in_reported_second", "source_price_seen_on_ask_in_reported_second",
                     "source_price_seen_on_executable_side_in_reported_second"):
            stat[name] += observed[name]
        quote = observed["past_quote"]
        if quote:
            values[side]["spread_before_entry"].append(quote["spread"])
            values[side]["past_quote_age_ms"].append(quote["age_before_open_second_ms"])
        if observed["first_quote_of_reported_second"]:
            values[side]["source_minus_first_executable_quote"].append(observed["first_quote_of_reported_second"]["source_minus_executable_price"])
        previous = observed["latest_strict_source_predecessor"]
        stat["has_strict_predecessor"] += previous is not None
        stat["ambiguous_predecessor_price"] += previous is not None and previous["price_ambiguous"]
        if previous and not previous["price_ambiguous"]:
            values[side]["signed_displacement_from_strict_source_close"].append(float(previous["signed_displacement_prices"][0]))
            values[side]["seconds_from_strict_source_close"].append(previous["seconds_to_entry"])
        hit = observed["nominal_price1_cross_before_entry"]
        if hit and hit["first_cross_ms"] is not None:
            stat["price1_threshold_crossed_before_open_second"] += 1
            stat["price1_threshold_crossed_at_least5s_before"] += hit["lead_before_open_second_seconds"] >= 5
        for lookback, change in observed["past_signed_returns"].items():
            if change is not None:
                stat[f"return{lookback}s_positive"] += change > 1e-9
                stat[f"return{lookback}s_negative"] += change < -1e-9
                stat[f"return{lookback}s_zero"] += abs(change) <= 1e-9
    exit_counts, peak_modes = defaultdict(Counter), defaultdict(Counter)
    for r in scope:
        path = path_index[r["ticket"]]
        kind = "sl" if r["comment"].startswith("[sl ") else "close_by" if r["comment"].startswith("#") else "other"
        c = exit_counts[kind]
        c["source_rows"] += 1
        c["with_definite_interior_quotes"] += path["interior_quotes"] > 0
        c["sl1_plus10pct_cross_at_least5s_before_close"] += path["initial_stop_benchmark"]["strict_beyond_nominal_plus10pct"]["at_least5s_early"]
        c["old_trail40_30_barrier_at_least5s_before_close"] += path["ratchet_barrier_benchmark"]["at_least5s_before_reported_close"]
        peak = path["implied_peak_minus_close_price_observed"]
        if peak is not None and float(r["pips"]) > 0:
            peak_modes[kind][f"{peak:.2f}"] += 1
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_orders": len(source), "component_rows": len(scope),
              "source_sha256": sha(ROOT / "data/orders_35462.jsonl"), "script_sha256": sha(__file__),
              "component_helpers_sha256": sha(ROOT / "first001_components.py"),
              "plan_sha256": sha(ROOT / "EXPERIMENT_FIRST001_PLAN.md"), "archived_path_sha256": sha(path_source),
              "cache_provenance": provenance, "consumed_ticks": len(times),
              "entry_by_side": {s: {**dict(c), "distributions": {k: describe(v) for k, v in values[s].items()}} for s, c in stats.items()},
              "exit_by_kind": {k: {**dict(c), "price_positive_observed_peak_minus_close_modes_NOT_inputs": dict(peak_modes[k].most_common(10))}
                               for k, c in exit_counts.items()},
              "artifact_sha256": {target.name: sha(target)}, "source_feed_identity_verified": False,
              "forensic_observations_NOT_predictions": True, "full_source_clone_complete": False}
    write_json(folder / "report.json", report)
    assert {r["ticket"] for r in records} == scope_ids
    assert sum(r["source_rows"] for r in stats.values()) == sum(r["source_rows"] for r in exit_counts.values()) == 7312
    write_json(folder / "qa_population.json", {"all7312_scope_tickets_and_archived_paths_verified": True,
              "report_sha256": sha(folder / "report.json"), "artifact_sha256": sha(target), "not_strategy_success": True})
    print(json.dumps({"component_rows": len(records), "entry_by_side": report["entry_by_side"], "exit_by_kind": report["exit_by_kind"]}), flush=True)


if __name__ == "__main__":
    main()
