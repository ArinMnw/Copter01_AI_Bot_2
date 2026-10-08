"""Old, prespecified tick hypotheses on the new feed; no new parameter fitting.

All 35,462 source rows are scored, so uncovered FixedVol/manual/special paths
remain missing rather than disappearing from the denominator. No CSV required.
"""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal

from probe_vantage_feed import ROOT, sha, write_json
from replay_vector import replay_vector
from strategy_scalping456 import Scalping456Config
from strict_source_matcher import enrich_prediction, match_exact


def main():
    target = ROOT / "data/vantage_prespecified_benchmarks_20261008"
    target.mkdir(exist_ok=False)
    models = {
        "fixed100_a40_d30_level": Scalping456Config(),
        "fixed100_a40_d30_quote": Scalping456Config(stop_fill_mode="quote"),
        "rolling100_a40_d30_level": Scalping456Config(entry_mode="rolling_extrema"),
        "momentum10s50_a40_d30_level": Scalping456Config(entry_mode="lookback_momentum", momentum_window_seconds=10, entry_reversal_points=50),
    }
    start = datetime(2026, 8, 18, 21, tzinfo=timezone.utc)
    end = datetime(2026, 10, 8, 1, 17, 56, tzinfo=timezone.utc)
    hashes = {name: sha(ROOT / name) for name in ("strategy_scalping456.py", "replay_vector.py", "strict_source_matcher.py")}
    predictions, provenance, ticks, invalid = replay_vector(ROOT / "data/proxy_ticks_vantage_gold_shift3", start, end, models)
    if hashes != {name: sha(ROOT / name) for name in hashes}:
        raise RuntimeError("Code changed during replay")
    source_path = ROOT / "data/orders_35462.jsonl"
    source = [json.loads(line, parse_float=Decimal) for line in source_path.read_text(encoding="utf-8").splitlines()]
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "start_inferred_utc": start.isoformat(),
              "end_exclusive_inferred_utc": end.isoformat(), "code_sha256": hashes,
              "script_sha256": sha(__file__), "source_sha256": sha(source_path),
              "tick_count_including_warmup": ticks, "invalid_quotes_skipped": invalid,
              "cache_provenance": provenance, "source_feed_identity_verified": False,
              "parameter_selection": "old fixed hypotheses, no new Vantage fitting; not unseen holdout",
              "method": "continuous_no_ledger_resets_no_day_resets_state_seed_first_warmup_tick_midpoint",
              "symbol_mapping_unverified": {"XAUUSD+": "XAUUSD"},
              "full_source_clone_complete": False, "models": []}
    for name, predicted in predictions.items():
        enriched = [enrich_prediction(row, "XAUUSD+", "sl") for row in predicted]
        matches, extras, score = match_exact(source, enriched)
        with (target / f"{name}_predictions.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
            for index, row in enumerate(enriched):
                handle.write(json.dumps({"prediction_index": index, **row}, ensure_ascii=False) + "\n")
        with (target / f"{name}_all_source_results.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
            for row in matches:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        write_json(target / f"{name}_extras.json", extras)
        report["models"].append({"name": name, "config": asdict(models[name]), **score,
                                 "source_xau": 31210, "source_fixed_uncovered_missing": 4252})
        print(json.dumps(report["models"][-1], ensure_ascii=False), flush=True)
    write_json(target / "report.json", report)


if __name__ == "__main__":
    main()
