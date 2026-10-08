"""All-row diagnostic QA and split-aware constraints; no fitted entry/exit rules."""

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from probe_vantage_feed import ROOT, sha, stamp, write_json
from replay_vantage_candle_grid import phase


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    folder = ROOT / "data" / args.tag
    report_path = folder / "report.json"
    manifest = json.loads(report_path.read_text(encoding="utf-8"))
    path = folder / "all_source_quote_paths.jsonl"
    source_path = ROOT / "data/orders_35462.jsonl"
    if sha(source_path) != manifest["source_sha256"] or sha(path) != manifest["all_source_paths_sha256"]:
        raise RuntimeError("Data digest differs")
    source = {r["ticket"]: r for r in (json.loads(line, parse_float=Decimal) for line in source_path.read_text(encoding="utf-8").splitlines())}
    observations = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    tickets = [r["ticket"] for r in observations]
    if len(source) != 35462 or len(tickets) != 35462 or len(set(tickets)) != 35462 or set(source) != set(tickets):
        raise RuntimeError("Missing/duplicate/extra diagnostic source rows")
    counts = defaultdict(Counter)
    distances = defaultdict(Counter)
    closeby_counts = Counter()
    worst = None
    for observed in observations:
        row = source[observed["ticket"]]
        for key, original in (("symbol", "symbol"), ("source_open_raw", "open_time"), ("source_close_raw", "close_time"), ("source_comment", "comment")):
            if observed[key] != row[original]:
                raise RuntimeError("Diagnostic/source identity differs")
        if Decimal(observed["source_volume"]) != row["volume"] or Decimal(observed["source_pips"]) != row["pips"]:
            raise RuntimeError("Diagnostic source numeric values differ")
        if not observed["not_a_prediction_or_goal_success_metric"] or observed["source_feed_identity_verified"]:
            raise RuntimeError("Incorrect diagnostic certification")
        split = phase(round((stamp(row["open_time"]) - 10800) * 1000), round((stamp(row["close_time"]) - 10800) * 1000))
        cohort = observed["cohort"]
        stat = counts[split + ":" + cohort]
        stat["source_rows"] += 1
        stat["interior_quotes_available"] += bool(observed["interior_quotes"])
        stat["gaps_over60s"] += bool(observed["gaps_over60s_intersecting_interior"])
        if observed["initial_stop_benchmark"]:
            stat["nominal_plus10pct_at_least5s_early"] += observed["initial_stop_benchmark"]["strict_beyond_nominal_plus10pct"]["at_least5s_early"]
        if row["comment"].startswith("#"):
            closeby_counts["source_rows_retained"] += 1
            closeby_counts["interior_quotes_available"] += bool(observed["interior_quotes"])
        outcome = "positive" if row["pips"] > 0 else "zero" if row["pips"] == 0 else "nominal_loss" if row["pips"] == (-100 if cohort == "xau_sl" else -1000) else "other_loss"
        distance = observed["implied_peak_minus_close_price_observed"]
        if distance is not None and cohort in ("xau_sl", "fixed_trial"):
            unit = Decimal(".01") if cohort == "xau_sl" else Decimal(".001")
            rounded = str(Decimal(str(distance)).quantize(unit))
            distances[split + ":" + cohort + ":" + outcome][rounded] += 1
        if cohort == "fixed_trial":
            stat["implied_distance_equal2_8_at_feed_resolution"] += distance is not None and abs(distance - 2.8) < .0000001
            stat["loss_below_minus2_8_price"] += row["pips"] < -280
        if cohort == "xau_sl" and (worst is None or Decimal(observed["source_pips"]) < Decimal(worst["source_pips"])):
            worst = observed
    result = {"created_utc": datetime.now(timezone.utc).isoformat(), "script_sha256": sha(__file__),
              "path_report_sha256": sha(report_path), "source_rows_verified": 35462, "unique_tickets_verified": 35462,
              "missing_or_extra_source_rows": 0, "full_clone_complete": False,
              "phase_counts": {key: dict(value) for key, value in sorted(counts.items())},
              "implied_distance_mode_counts_not_recovered_parameters": {key: value.most_common(12) for key, value in sorted(distances.items())},
              "closeby": dict(closeby_counts), "worst_xau_sl_path": worst,
              "lot_segment_counts": {symbol: len(rows) for symbol, rows in manifest["lot_segments"].items()},
              "xau_lot_segments_observed_not_settings": manifest["lot_segments"]["XAUUSD+"],
              "sparse_public_equity_not_used_for_live_risk_sizing": True}
    write_json(folder / "qa_constraints.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
