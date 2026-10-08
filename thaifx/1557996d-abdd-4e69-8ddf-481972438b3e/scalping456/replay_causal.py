"""Continuous proxy replay: no observed entry/exit resets and no future prices.

The order ledger is used only by the scorer after signal generation. Missing
source orders and extra predictions are both counted. This is a cross-broker
diagnostic, never proof of a 100% source-feed clone.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from audit_ledger import category, distribution, dt, read_csv
from strategy_scalping456 import EntrySignal, ExitSignal, Scalping456Config, Scalping456Strategy, Tick


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def candidates() -> dict[str, Scalping456Config]:
    models = {}
    for threshold in (100, 120, 130):
        models[f"fixed_{threshold}_a40_d30"] = Scalping456Config(entry_reversal_points=threshold)
    models["fixed_100_a0_d100"] = Scalping456Config(trailing_activation_points=0, trailing_distance_points=100)
    models["fixed_100_a50_d50"] = Scalping456Config(trailing_activation_points=50, trailing_distance_points=50)
    models["fixed_100_a40_d30_quote"] = Scalping456Config(stop_fill_mode="quote")
    for threshold in (100, 160):
        models[f"rolling_{threshold}_a40_d30"] = Scalping456Config(entry_mode="rolling_extrema", entry_reversal_points=threshold)
    for window, threshold in ((5, 50), (10, 50), (60, 100), (300, 100), (900, 100), (1800, 100), (3600, 100)):
        models[f"momentum_{window}s_{threshold}_a40_d30"] = Scalping456Config(
            entry_mode="lookback_momentum", momentum_window_seconds=window,
            entry_reversal_points=threshold,
        )
    return models


def match_orders(source: list[dict], predicted: list[dict], *, tolerance_seconds=3.0):
    """Deterministic nearest-time, one-to-one scoring, without side cherry-picking.

    Several nearby predictions are flagged as ambiguous. This matcher alone
    cannot establish an exact clone when ambiguity exists.
    """
    times = [row["open_ms"] for row in predicted]
    used = set()
    result = []
    tolerance_ms = round(tolerance_seconds * 1000)
    for row in source:
        opened = round(dt(row["actual_open_utc"]).timestamp() * 1000)
        closed = round(dt(row["actual_close_utc"]).timestamp() * 1000)
        left = bisect.bisect_left(times, opened - tolerance_ms)
        right = bisect.bisect_right(times, opened + tolerance_ms)
        available = [i for i in range(left, right) if i not in used]
        item = {
            "ticket": row["ticket"], "category": category(row),
            "expected_open_utc": row["actual_open_utc"],
            "expected_close_utc": row["actual_close_utc"],
            "expected_side": row["trade_type"],
            "expected_volume": row["volume"], "expected_open_price": row["open_price"],
            "expected_close_price": row["close_price"],
            "prediction_index": "", "nearby_unused_predictions": len(available),
            "predicted_open_utc": "", "predicted_close_utc": "", "predicted_side": "",
            "predicted_volume": "", "predicted_open_price": "", "predicted_close_price": "",
            "open_error_seconds": "", "close_error_seconds": "",
            "open_price_error": "", "close_price_error": "",
            "direction_match": False, "volume_match": False,
            "open_same_source_second": False, "close_same_source_second": False,
            "joint_direction_open_close_within_3s": False,
            "joint_source_fields_at_reported_precision": False,
            "status": "missing_prediction_near_open", "source_clone_verified": False,
        }
        if available:
            index = min(available, key=lambda i: (abs(times[i] - opened), i))
            used.add(index)
            prediction = predicted[index]
            open_error = (prediction["open_ms"] - opened) / 1000
            close_error = (prediction["close_ms"] - closed) / 1000 if prediction["close_ms"] is not None else None
            direction_match = prediction["side"] == row["trade_type"]
            volume_match = abs(prediction["volume"] - float(row["volume"])) < 1e-9
            open_same_second = prediction["open_ms"] // 1000 == opened // 1000
            close_same_second = prediction["close_ms"] is not None and prediction["close_ms"] // 1000 == closed // 1000
            open_price_error = prediction["open_price"] - float(row["open_price"])
            close_price_error = prediction["close_price"] - float(row["close_price"]) if prediction["close_price"] is not None else None
            joint_time = direction_match and abs(open_error) <= 3 and close_error is not None and abs(close_error) <= 3
            fields_match = (direction_match and volume_match and open_same_second and close_same_second
                            and abs(open_price_error) < .005 + 1e-9 and close_price_error is not None
                            and abs(close_price_error) < .005 + 1e-9)
            item.update({
                "prediction_index": index,
                "predicted_open_utc": datetime.fromtimestamp(prediction["open_ms"] / 1000, timezone.utc).isoformat(),
                "predicted_close_utc": datetime.fromtimestamp(prediction["close_ms"] / 1000, timezone.utc).isoformat() if prediction["close_ms"] is not None else "",
                "predicted_side": prediction["side"], "predicted_volume": prediction["volume"],
                "predicted_open_price": prediction["open_price"], "predicted_close_price": prediction["close_price"],
                "open_error_seconds": open_error,
                "close_error_seconds": close_error if close_error is not None else "",
                "open_price_error": open_price_error,
                "close_price_error": close_price_error if close_price_error is not None else "",
                "direction_match": direction_match, "volume_match": volume_match,
                "open_same_source_second": open_same_second, "close_same_source_second": close_same_second,
                "joint_direction_open_close_within_3s": joint_time,
                "joint_source_fields_at_reported_precision": fields_match,
                "status": "proxy_fields_match_only" if fields_match else "matched_near_open_but_fields_differ",
            })
        result.append(item)
    matched = len(used)
    count = len(source)
    joint = sum(r["joint_direction_open_close_within_3s"] for r in result)
    exact = sum(r["joint_source_fields_at_reported_precision"] for r in result)
    summary = {
        "source_orders": count, "predicted_orders": len(predicted),
        "matched_open_near_3s": matched, "missing_source_orders": count - matched,
        "extra_predictions": len(predicted) - matched,
        "direction_matches": sum(r["direction_match"] for r in result),
        "joint_direction_open_close_within_3s": joint,
        "joint_direction_open_close_within_3s_pct_all_source": round(100 * joint / count, 6) if count else None,
        "joint_source_fields_at_reported_precision": exact,
        "joint_source_fields_pct_all_source": round(100 * exact / count, 6) if count else None,
        "ambiguous_nearby_prediction_rows": sum(r["nearby_unused_predictions"] > 1 for r in result),
        "open_error_seconds": distribution([r["open_error_seconds"] for r in result if r["open_error_seconds"] != ""]),
        "close_error_seconds": distribution([r["close_error_seconds"] for r in result if r["close_error_seconds"] != ""]),
        "full_source_clone_verified": False,
    }
    return result, summary


def replay(cache: Path, start: datetime, end: datetime, models: dict):
    strategies = {name: Scalping456Strategy(config) for name, config in models.items()}
    predicted = {name: [] for name in models}
    entries = {name: None for name in models}
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    provenance = []
    invalid = 0
    seen = 0
    while day < end:
        file = cache / f"{day:%Y-%m-%d}.npz"
        meta_file = file.with_suffix(".json")
        if not file.exists() or not meta_file.exists():
            raise FileNotFoundError(f"Required cache day missing: {file.name}")
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if hashlib.sha256(file.read_bytes()).hexdigest() != meta["sha256"]:
            raise ValueError(f"Cache changed: {file.name}")
        provenance.append(meta)
        with np.load(file, allow_pickle=False) as ticks:
            times, bids, asks = ticks["time_msc"], ticks["bid"], ticks["ask"]
            if not (len(times) == len(bids) == len(asks) == meta["ticks"]):
                raise ValueError(f"Cache shape differs: {file.name}")
            for instant, bid, ask in zip(times, bids, asks):
                if int(instant) < round(start.timestamp() * 1000) or int(instant) >= round(end.timestamp() * 1000):
                    continue
                if not np.isfinite(bid) or not np.isfinite(ask) or bid <= 0 or ask < bid:
                    invalid += 1
                    continue
                current = Tick(datetime.fromtimestamp(int(instant) / 1000, timezone.utc), float(bid), float(ask))
                for name, strategy in strategies.items():
                    signal = strategy.on_tick(current)
                    if isinstance(signal, EntrySignal):
                        entries[name] = signal
                    elif isinstance(signal, ExitSignal):
                        entry = entries[name]
                        if entry is None:
                            raise AssertionError("Exit without causal entry")
                        predicted[name].append({
                            "open_ms": round(entry.time.timestamp() * 1000),
                            "close_ms": round(signal.time.timestamp() * 1000),
                            "side": entry.side.value, "volume": entry.volume,
                            "open_price": entry.price, "close_price": signal.price,
                        })
                        entries[name] = None
                seen += 1
                if seen % 200_000 == 0:
                    print(f"replay {day.date()} ticks={seen:,}", flush=True)
        print(f"replay day finished {day.date()} ticks={len(times):,}", flush=True)
        day += timedelta(days=1)
    for name, entry in entries.items():
        if entry is not None:
            predicted[name].append({"open_ms": round(entry.time.timestamp() * 1000),
                                    "close_ms": None, "side": entry.side.value,
                                    "volume": entry.volume, "open_price": entry.price,
                                    "close_price": None})
    return predicted, provenance, seen, invalid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--cache-tag", default="iux_shift1")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--models", help="Comma-separated candidate names; default all")
    parser.add_argument("--engine", choices=("reference", "vector"), default="reference")
    args = parser.parse_args()
    for value in (args.tag, args.cache_tag):
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", value):
            parser.error("Invalid tag")
    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
    if end <= start:
        parser.error("End must be later than start")
    models = candidates()
    if args.models:
        names = args.models.split(",")
        if any(name not in models for name in names):
            parser.error("Unknown candidate model")
        models = {name: models[name] for name in names}
    strategy_hash = hashlib.sha256((ROOT / "strategy_scalping456.py").read_bytes()).hexdigest()
    if args.engine == "vector":
        from replay_vector import replay_vector
        runner = replay_vector
    else:
        runner = replay
    prediction, provenance, tick_count, invalid = runner(DATA / f"proxy_ticks_{args.cache_tag}", start, end, models)
    if hashlib.sha256((ROOT / "strategy_scalping456.py").read_bytes()).hexdigest() != strategy_hash:
        raise RuntimeError("Strategy file changed during replay; evidence provenance is ambiguous")
    # No source orders were consulted during signal generation above.
    all_source = read_csv(DATA / "orders_35462_normalized.csv")
    source = sorted([r for r in all_source if r["symbol"] == "XAUUSD+" and start <= dt(r["actual_open_utc"]) < end],
                    key=lambda r: (dt(r["actual_open_utc"]), int(r["ticket"])))
    source_matches = []
    scores = []
    for name, predicted in prediction.items():
        rows, summary = match_orders(source, predicted)
        source_matches.extend({"model": name, **row} for row in rows)
        scores.append({"model": name, "config": asdict(models[name]), **summary})
    scores.sort(key=lambda row: (row["joint_source_fields_at_reported_precision"], row["joint_direction_open_close_within_3s"], -row["extra_predictions"]), reverse=True)
    report = {
        "start_utc": start.isoformat(), "end_utc_exclusive": end.isoformat(),
        "method": "continuous_causal_tick_replay_no_ledger_resets",
        "engine": args.engine,
        "proxy_not_source": True,
        "parameter_selection": "research_candidates_some_previously_fitted_on_full_proxy_dataset_not_unseen_holdout",
        "source_total_all_symbols": len(all_source), "source_xau_in_replay_window": len(source),
        "tick_count": tick_count, "invalid_quote_ticks_skipped": invalid,
        "startup_state": "flat_first_tick_midpoint_unknown_original_EA_state",
        "end_state": "open_positions_not_force_closed",
        "no_resets_at_day_boundaries": True,
        "strategy_sha256": strategy_hash,
        "source_ledger_sha256": hashlib.sha256((DATA / "orders_35462_normalized.csv").read_bytes()).hexdigest(),
        "cache_provenance": provenance, "models": scores,
        "full_35462_source_clone_complete": False,
        "uncovered": "FixedVol20/source broker ticks/manual settings and actions remain unverified",
    }
    prefix = DATA / f"causal_replay_{args.tag}"
    prefix.with_suffix(".json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    if source_matches:
        with prefix.with_suffix(".csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(source_matches[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(source_matches)
    with (DATA / f"causal_predictions_{args.tag}.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["model", "open_ms", "close_ms", "side", "volume", "open_price", "close_price"], lineterminator="\n")
        writer.writeheader()
        for name, predicted in prediction.items():
            writer.writerows({"model": name, **row} for row in predicted)
    print(json.dumps([{key: score[key] for key in ("model", "source_orders", "predicted_orders", "missing_source_orders", "extra_predictions", "joint_direction_open_close_within_3s_pct_all_source", "joint_source_fields_at_reported_precision")} for score in scores], indent=2), flush=True)


if __name__ == "__main__":
    main()
