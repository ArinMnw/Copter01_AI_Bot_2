"""Full continuous causal research replay: 20 candle +16 grid +2 trial models.

Generates all predictions before parsing source outcomes, then scores every
source row with zero time tolerance. Presets are research hypotheses, not EA.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np

from probe_vantage_feed import ROOT, group, sha, stamp, write_json
from replay_candle_grid_vector import replay_closed_candidate, replay_grid_candidate
from replay_vector import replay_candidate
from strategy_scalping456 import (ClosedBar, ClosedCandleConfig, FixedVol20Config, Scalping456Config)
from strict_source_matcher import enrich_prediction, match_exact
from test_candle_grid_replay import reference_closed, reference_grid


UTC = timezone.utc
START = datetime(2026, 8, 18, 21, tzinfo=UTC)
END = datetime(2026, 10, 8, 1, 17, 56, tzinfo=UTC)
SPLIT_MS = round(datetime(2026, 9, 21, tzinfo=UTC).timestamp() * 1000)


def load_ticks(tag, symbol):
    cache = ROOT / "data" / ("proxy_ticks_" + tag)
    t, b, a, provenance = [], [], [], []
    day = START.replace(hour=0)
    while day < END:
        path = cache / f"{day:%Y-%m-%d}.npz"
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        if sha(path) != meta["sha256"] or meta["symbol"] != symbol or meta["query_shift_ms"] != 10800000:
            raise RuntimeError("Wrong cache/hash/clock")
        if meta["invalid_quotes"]:
            raise RuntimeError("Invalid quotes: refuse silently discarding")
        with np.load(path) as archive:
            keep = ((archive["time_msc"] >= round(START.timestamp() * 1000))
                    & (archive["time_msc"] < round(END.timestamp() * 1000)))
            if len(archive["time_msc"]) != meta["ticks"]:
                raise RuntimeError("Tick count mismatch")
            t.append(archive["time_msc"][keep]); b.append(archive["bid"][keep]); a.append(archive["ask"][keep])
        provenance.append(meta)
        day += timedelta(days=1)
    arrays = tuple(np.concatenate(parts) for parts in (t, b, a))
    if np.any(np.diff(arrays[0]) < 0):
        raise RuntimeError("Non-chronological cache")
    return arrays, provenance


def load_bars(minutes, tag):
    folder = ROOT / "data" / tag
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    path = folder / f"XAUUSD_M{minutes}_inferred.npz"
    if sha(path) != report["feeds"][f"XAUUSD_M{minutes}_raw"]["inferred_sha256"]:
        raise RuntimeError("Broker bars digest differs")
    with np.load(path) as archive:
        arrays = {name: archive[name] for name in ("open_ms", "close_ms", "open", "high", "low", "close")}
    reference = [ClosedBar(datetime.fromtimestamp(int(t) / 1000, UTC), minutes, float(o), float(h), float(l), float(c))
                 for t, o, h, l, c in zip(arrays["open_ms"], arrays["open"], arrays["high"], arrays["low"], arrays["close"])]
    return arrays, reference, {"file": str(path), "sha256": sha(path), "bars": len(reference)}


def phase(open_ms, close_ms):
    if open_ms >= SPLIT_MS:
        return "chronological_validation_not_unseen"
    if close_ms is None or close_ms >= SPLIT_MS:
        return "cross_split_not_parameter_selection"
    return "development_closed_before_split"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True, help="Fresh result snapshot name, existing outputs never overwritten")
    parser.add_argument("--bars-tag", default="vantage_broker_bars_20261008")
    args = parser.parse_args()
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", value) for value in (args.tag, args.bars_tag)):
        parser.error("Invalid tag")
    target = ROOT / "data" / args.tag
    target.mkdir(exist_ok=False)
    script_names = ("strategy_scalping456.py", "replay_candle_grid_vector.py", "replay_vector.py",
                    "strict_source_matcher.py", "replay_vantage_candle_grid.py", "EXPERIMENT_CANDLE_GRID_PLAN.md")
    hashes = {name: sha(ROOT / name) for name in script_names}
    report = {"created_utc": datetime.now(UTC).isoformat(), "code_plan_sha256": hashes,
              "start_inferred_utc": START.isoformat(), "end_exclusive_inferred_utc": END.isoformat(),
              "source_feed_identity_verified": False, "full_source_clone_complete": False,
              "method": "continuous_first_warmup_tick_unknown_initial_state_no_ledger_resets_no_day_resets",
              "parameters": "frozen in prior plan, no tuning from replay scores; not unseen holdout",
              "source_parse_order": "after all candidate predictions generated",
              "development_split_utc": "2026-09-21T00:00:00+00:00",
              "cross_boundary_positions": "retained; not used for pre-split parameter selection",
              "cache_provenance": {}, "bars_provenance": [], "parity_checks": [], "models": []}
    write_json(target / "run_manifest.json", report)
    generated = {}
    configs = {}

    def save_predictions(name, raw, symbol, reason, config):
        enriched = [enrich_prediction(row, symbol, reason) for row in raw]
        path = target / f"{name}_predictions.jsonl"
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            for index, row in enumerate(enriched):
                stream.write(json.dumps({"prediction_index": index, "engine_label": name, **row}) + "\n")
        generated[name], configs[name] = enriched, config
        print(json.dumps({"generated": name, "predictions_including_warmup": len(raw)}), flush=True)

    arrays, provenance = load_ticks("vantage_gold_shift3", "XAUUSD")
    times, bids, asks = arrays
    report["cache_provenance"]["XAUUSD"] = provenance
    sample = ((times >= round(datetime(2026, 9, 7, tzinfo=UTC).timestamp() * 1000))
              & (times < round(datetime(2026, 9, 7, 1, tzinfo=UTC).timestamp() * 1000)))
    for minutes in (1, 5, 15, 30, 60):
        bars, reference, bar_meta = load_bars(minutes, args.bars_tag)
        report["bars_provenance"].append(bar_meta)
        for mode in ("body", "engulf", "breakout"):
            for fill in (("level", "quote") if mode == "breakout" else ("level",)):
                candle = ClosedCandleConfig(minutes, mode)
                execution = Scalping456Config(stop_fill_mode=fill)
                # Actual-feed parity checks precede each full candidate run.
                expected = reference_closed(times[sample], bids[sample], asks[sample], reference, candle, execution)
                actual = replay_closed_candidate(times[sample], bids[sample], asks[sample], bars, candle, execution)
                if expected != actual:
                    raise RuntimeError("Actual closed-bar reference parity failed")
                name = f"xau_M{minutes}_{mode}_{fill}"
                report["parity_checks"].append({"model": name, "ticks": int(sample.sum()), "predictions": len(actual), "all_fields_equal": True})
                raw = replay_closed_candidate(times, bids, asks, bars, candle, execution)
                save_predictions(name, raw, "XAUUSD+", "sl", {"candle": asdict(candle), "execution": asdict(execution)})
    del arrays, times, bids, asks
    arrays, provenance = load_ticks("vantage_fixed_shift3", "FixedVol20")
    times, bids, asks = arrays
    report["cache_provenance"]["FixedVol20"] = provenance
    sample = ((times >= round(datetime(2026, 9, 7, tzinfo=UTC).timestamp() * 1000))
              & (times < round(datetime(2026, 9, 8, tzinfo=UTC).timestamp() * 1000)))
    for step in (3, 15):
        for fixed in (False, True):
            for mode in ("fixed_close", "rolling_extrema"):
                for fill in ("quote", "level"):
                    config = FixedVol20Config(grid_step_price=step, basket_target_price=step,
                                             fixed_volume=fixed, entry_mode=mode, grid_fill_mode=fill, target_rounding="half_up")
                    expected = reference_grid(times[sample], bids[sample], asks[sample], config)
                    actual = replay_grid_candidate(times[sample], bids[sample], asks[sample], config)
                    if expected != actual:
                        raise RuntimeError("Actual grid reference parity failed")
                    name = f"fixed_grid{step}_{'fixed' if fixed else 'progressive'}_{mode}_{fill}"
                    report["parity_checks"].append({"model": name, "ticks": int(sample.sum()), "predictions": len(actual), "all_fields_equal": True})
                    raw = replay_grid_candidate(times, bids, asks, config)
                    save_predictions(name, raw, "FixedVol20", "tp", asdict(config))
    for fill in ("level", "quote"):
        config = Scalping456Config.fixedvol20_trial(entry_reversal_points=300, trailing_activation_points=0,
                                                  trailing_distance_points=1000, stop_fill_mode=fill)
        raw = replay_candidate(times, bids, asks, config)
        save_predictions(f"fixed_trial_a0d1000_{fill}", raw, "FixedVol20", "sl", asdict(config))
    del arrays, times, bids, asks
    if len(generated) != 38:
        raise RuntimeError("Not all 38 frozen candidates were generated")
    if hashes != {name: sha(ROOT / name) for name in script_names}:
        raise RuntimeError("Code/plan changed during replay")
    # Source outcomes are first parsed here, never used for candidate signals.
    source_path = ROOT / "data/orders_35462.jsonl"
    source = [json.loads(line, parse_float=Decimal) for line in source_path.read_text(encoding="utf-8").splitlines()]
    report["source_sha256"], report["source_orders"] = sha(source_path), len(source)
    start_ms = round((min(stamp(row["open_time"]) for row in source) - 10800) * 1000)
    end_ms = round((max(stamp(row["close_time"]) for row in source) - 10800 + 1) * 1000)
    source_phases = {row["ticket"]: phase(round((stamp(row["open_time"]) - 10800) * 1000),
                                        round((stamp(row["close_time"]) - 10800) * 1000)) for row in source}
    source_groups = {name: [row for row in source if source_phases[row["ticket"]] == name]
                     for name in sorted(set(source_phases.values()))}
    # Prespecified independent prototypes, not original equity/margin coupling.
    portfolios = {
        "portfolio_M1_grid3_level_trial_level": ("xau_M1_breakout_level", "fixed_grid3_progressive_fixed_close_level", "fixed_trial_a0d1000_level"),
        "portfolio_M5_grid15_quote_trial_quote": ("xau_M5_breakout_quote", "fixed_grid15_progressive_rolling_extrema_quote", "fixed_trial_a0d1000_quote"),
    }
    for name, components in portfolios.items():
        generated[name] = [{"component": component, **row} for component in components for row in generated[component]]
        configs[name] = {"components": components, "independent_prototypes_not_verified_original_portfolio": True}
    for name, predicted in generated.items():
        kept = [row for row in predicted if row["open_ms"] < end_ms and (row["close_ms"] is None or row["close_ms"] >= start_ms)]
        matches, extra, score = match_exact(source, kept)
        with (target / f"{name}_all_source_results.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for row in matches:
                row["phase"] = source_phases[row["ticket"]]
                stream.write(json.dumps(row) + "\n")
        # Includes every unmatched prediction, not just an extra count.
        with (target / f"{name}_extras.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for index in extra:
                stream.write(json.dumps({"comparison_prediction_index": index, **kept[index]}) + "\n")
        by_cohort = Counter(group(row) for row, matched in zip(source, matches) if matched["exact_all_observable_fields"])
        phases = {}
        for label, subset in source_groups.items():
            selected = [row for row in kept if phase(row["open_ms"], row["close_ms"]) == label]
            _, _, phases[label] = match_exact(subset, selected)
        model = {"name": name, "config": configs[name], "predictions_including_warmup": len(predicted),
                 "outside_comparison_window": len(predicted) - len(kept), "phases": phases,
                 "cohorts": {c: {"source_orders": sum(group(row) == c for row in source), "exact": by_cohort[c]}
                             for c in sorted({group(row) for row in source})}, **score}
        report["models"].append(model)
        print(json.dumps({"scored": name, **score}), flush=True)
    write_json(target / "report.json", report)


if __name__ == "__main__":
    main()
