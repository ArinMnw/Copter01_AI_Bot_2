"""Fit initial-stop, trailing-activation and trailing-distance on proxy ticks."""

from __future__ import annotations

import argparse
import json
from datetime import timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ORDERS_PATH = DATA / "orders_35462_normalized.csv"


def describe(values: list[float]) -> dict:
    series = pd.Series(values, dtype=float)
    if series.empty:
        return {"count": 0}
    return {
        "count": int(len(series)),
        "p25": round(float(series.quantile(0.25)), 6),
        "median": round(float(series.median()), 6),
        "p75": round(float(series.quantile(0.75)), 6),
        "p90": round(float(series.quantile(0.90)), 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD.iux")
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--tag", default="iux_shift1")
    parser.add_argument("--feed-time-shift-hours", type=float, default=1.0)
    parser.add_argument("--max-orders", type=int)
    args = parser.parse_args()

    orders = pd.read_csv(ORDERS_PATH)
    orders = orders[
        orders["symbol"].eq("XAUUSD+")
        & orders["comment"].fillna("").str.startswith("[sl ")
    ].copy()
    orders["open"] = pd.to_datetime(orders["actual_open_utc"], utc=True)
    orders["close"] = pd.to_datetime(orders["actual_close_utc"], utc=True)
    shift = pd.to_timedelta(args.feed_time_shift_hours, unit="h")
    orders["feed_open"] = orders["open"] + shift
    orders["feed_close"] = orders["close"] + shift
    orders["day"] = orders["feed_open"].dt.floor("D")
    if args.max_orders:
        orders = orders.sort_values("feed_open").head(args.max_orders)

    activations = (35, 40, 45, 50, 55, 60, 65)
    distances = (10, 15, 20, 25, 30, 35, 40)
    candidates = [(activation, distance) for activation in activations for distance in distances]
    stats = {
        candidate: {
            "eligible": 0,
            "predicted": 0,
            "time_error": [],
            "pips_error": [],
            "sign_correct": 0,
            "exit_kind_correct": 0,
        }
        for candidate in candidates
    }

    if not mt5.initialize(args.terminal, portable=True):
        raise RuntimeError(mt5.last_error())
    try:
        mt5.symbol_select(args.symbol, True)
        for day_number, (day, day_orders) in enumerate(orders.groupby("day", sort=True), start=1):
            start = day.to_pydatetime().replace(tzinfo=timezone.utc) - timedelta(minutes=10)
            end = start + timedelta(days=1, minutes=20)
            ticks = mt5.copy_ticks_range(args.symbol, start, end, mt5.COPY_TICKS_ALL)
            if ticks is None or len(ticks) == 0:
                continue
            times = ticks["time_msc"].astype(np.int64)
            bids = ticks["bid"].astype(float)
            asks = ticks["ask"].astype(float)
            for row in day_orders.itertuples(index=False):
                open_ms = int(row.feed_open.timestamp() * 1000)
                close_ms = int(row.feed_close.timestamp() * 1000)
                first = int(np.searchsorted(times, open_ms, side="left"))
                last = int(np.searchsorted(times, close_ms + 30_000, side="right"))
                if first >= len(times) or last <= first:
                    continue
                if times[first] - open_ms > 10_000:
                    continue
                if row.trade_type == "buy":
                    entry = asks[first]
                    favorable = (bids[first:last] - entry) * 100.0
                else:
                    entry = bids[first]
                    favorable = (entry - asks[first:last]) * 100.0
                running_best = np.maximum.accumulate(favorable)
                initial_hit = favorable <= -100.0
                actual_initial = row.pips == -100
                for activation, distance in candidates:
                    stat = stats[(activation, distance)]
                    stat["eligible"] += 1
                    trailing_hit = (running_best >= activation) & (
                        favorable <= running_best - distance
                    )
                    hits = np.flatnonzero(initial_hit | trailing_hit)
                    if len(hits) == 0:
                        continue
                    hit = int(hits[0])
                    stat["predicted"] += 1
                    error_sec = (times[first + hit] - close_ms) / 1000.0
                    predicted_pips = float(favorable[hit])
                    stat["time_error"].append(error_sec)
                    stat["pips_error"].append(predicted_pips - float(row.pips))
                    predicted_initial = bool(initial_hit[hit] and not trailing_hit[hit])
                    stat["exit_kind_correct"] += int(predicted_initial == actual_initial)
                    stat["sign_correct"] += int(
                        np.sign(predicted_pips) == np.sign(float(row.pips))
                    )
            print(
                f"exit fit day {day_number} {day.date()} orders={len(day_orders)}",
                flush=True,
            )
    finally:
        mt5.shutdown()

    results = []
    for (activation, distance), stat in stats.items():
        errors = pd.Series(stat.pop("time_error"), dtype=float)
        pips_errors = pd.Series(stat.pop("pips_error"), dtype=float)
        predicted = stat["predicted"]
        results.append(
            {
                "activation_points": activation,
                "distance_points": distance,
                **stat,
                "coverage_pct": round(100 * predicted / stat["eligible"], 6)
                if stat["eligible"] else None,
                "within_1s_pct": round(100 * float(errors.abs().le(1).mean()), 6)
                if len(errors) else None,
                "within_3s_pct": round(100 * float(errors.abs().le(3).mean()), 6)
                if len(errors) else None,
                "within_5s_pct": round(100 * float(errors.abs().le(5).mean()), 6)
                if len(errors) else None,
                "median_abs_time_error_sec": round(float(errors.abs().median()), 6)
                if len(errors) else None,
                "median_time_error_sec": round(float(errors.median()), 6)
                if len(errors) else None,
                "sign_accuracy_pct": round(100 * stat["sign_correct"] / predicted, 6)
                if predicted else None,
                "exit_kind_accuracy_pct": round(
                    100 * stat["exit_kind_correct"] / predicted, 6
                ) if predicted else None,
                "pips_error": describe(pips_errors.tolist()),
            }
        )
    ranked = sorted(
        results,
        key=lambda row: (
            row["within_3s_pct"] or 0,
            -(row["median_abs_time_error_sec"] or 1e9),
            row["exit_kind_accuracy_pct"] or 0,
        ),
        reverse=True,
    )
    report = {
        "feed": args.symbol,
        "feed_time_shift_hours": args.feed_time_shift_hours,
        "orders": int(len(orders)),
        "initial_stop_points": 100,
        "best": ranked[:15],
        "all": results,
    }
    output = DATA / f"exit_model_fit_{args.tag}.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report["best"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
