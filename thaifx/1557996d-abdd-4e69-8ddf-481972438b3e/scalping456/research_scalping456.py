"""Forensic feature extraction for the Scalping456 XAU engine.

This module aligns every public order with an independent MT5 tick feed.  It is
not the live strategy: its job is to measure which entry/exit hypotheses are
actually supported by all orders, and to emit compact evidence that the live
strategy can use without embedding hindsight ticket data.

The ThaiFXBook timestamps require a correction before this script is used; run
``analyze_orders.py`` first and consume ``orders_35462_normalized.csv``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import MetaTrader5 as mt5
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ORDERS_PATH = DATA / "orders_35462_normalized.csv"
FEATURES_PATH = DATA / "order_tick_features.csv"
REPORT_PATH = DATA / "tick_hypothesis_report.json"

ENTRY_HORIZONS_SEC = (1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 120, 300, 900, 1800, 3600)
MAX_CORE_EXIT_SEC = 30 * 60


@dataclass(frozen=True)
class TickDay:
    time_msc: np.ndarray
    mid: np.ndarray
    bid: np.ndarray
    ask: np.ndarray


def _to_millis(values: Iterable[pd.Timestamp]) -> np.ndarray:
    return np.asarray([int(value.timestamp() * 1000) for value in values], dtype=np.int64)


def _load_orders(feed_time_shift_hours: float = 0.0) -> pd.DataFrame:
    frame = pd.read_csv(ORDERS_PATH)
    frame["actual_open_utc"] = pd.to_datetime(frame["actual_open_utc"], utc=True)
    frame["actual_close_utc"] = pd.to_datetime(frame["actual_close_utc"], utc=True)
    if feed_time_shift_hours:
        frame["canonical_actual_open_utc"] = frame["actual_open_utc"]
        frame["canonical_actual_close_utc"] = frame["actual_close_utc"]
        shift = pd.to_timedelta(feed_time_shift_hours, unit="h")
        frame["actual_open_utc"] = frame["actual_open_utc"] + shift
        frame["actual_close_utc"] = frame["actual_close_utc"] + shift
    frame["duration_sec"] = (frame["actual_close_utc"] - frame["actual_open_utc"]).dt.total_seconds()
    return frame[
        (frame["symbol"] == "XAUUSD+")
        & frame["comment"].fillna("").str.startswith("[sl")
    ].copy()


def _fetch_tick_day(symbol: str, day: pd.Timestamp) -> TickDay:
    start = day.to_pydatetime().replace(tzinfo=timezone.utc) - timedelta(minutes=10)
    end = start + timedelta(days=1, minutes=20)
    ticks = mt5.copy_ticks_range(symbol, start, end, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) == 0:
        raise RuntimeError(f"No ticks for {symbol} on {day.date()}: {mt5.last_error()}")
    return TickDay(
        time_msc=ticks["time_msc"].astype(np.int64),
        mid=(ticks["bid"].astype(float) + ticks["ask"].astype(float)) / 2.0,
        bid=ticks["bid"].astype(float),
        ask=ticks["ask"].astype(float),
    )


def _price_at_or_before(ticks: TickDay, timestamp_msc: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    indexes = np.searchsorted(ticks.time_msc, timestamp_msc, side="right") - 1
    clipped = np.clip(indexes, 0, len(ticks.time_msc) - 1)
    age_msc = timestamp_msc - ticks.time_msc[clipped]
    valid = (indexes >= 0) & (age_msc >= 0) & (age_msc <= 10_000)
    return clipped, valid


def _extract_day_features(day_orders: pd.DataFrame, ticks: TickDay) -> pd.DataFrame:
    result = day_orders[
        [
            "ticket", "trade_type", "volume", "profit", "pips", "open_price",
            "close_price", "actual_open_utc", "actual_close_utc", "duration_sec",
        ]
    ].copy()
    open_msc = _to_millis(result["actual_open_utc"])
    close_msc = _to_millis(result["actual_close_utc"])
    entry_idx, entry_valid = _price_at_or_before(ticks, open_msc)
    result["entry_tick_valid"] = entry_valid
    result["entry_tick_age_ms"] = open_msc - ticks.time_msc[entry_idx]
    result["proxy_entry_mid"] = ticks.mid[entry_idx]
    result["source_minus_proxy_entry"] = result["open_price"].to_numpy() - ticks.mid[entry_idx]
    result["spread_points"] = (ticks.ask[entry_idx] - ticks.bid[entry_idx]) * 100.0

    for seconds in ENTRY_HORIZONS_SEC:
        prior_msc = open_msc - seconds * 1000
        prior_idx, prior_valid = _price_at_or_before(ticks, prior_msc)
        valid = entry_valid & prior_valid
        values = np.full(len(result), np.nan)
        values[valid] = (ticks.mid[entry_idx[valid]] - ticks.mid[prior_idx[valid]]) * 100.0
        result[f"ret_{seconds}s_points"] = values
        counts = np.full(len(result), np.nan)
        counts[valid] = entry_idx[valid] - prior_idx[valid]
        result[f"ticks_{seconds}s"] = counts

    mfe = np.full(len(result), np.nan)
    mae = np.full(len(result), np.nan)
    proxy_exit = np.full(len(result), np.nan)
    sides = result["trade_type"].to_numpy()
    durations = result["duration_sec"].to_numpy()
    for pos, (start, stop) in enumerate(zip(open_msc, close_msc)):
        if not entry_valid[pos] or durations[pos] < 0 or durations[pos] > MAX_CORE_EXIT_SEC:
            continue
        first = int(np.searchsorted(ticks.time_msc, start, side="left"))
        last = int(np.searchsorted(ticks.time_msc, stop, side="right"))
        if last <= first:
            continue
        path = ticks.mid[first:last]
        base = path[0]
        proxy_exit[pos] = path[-1]
        if sides[pos] == "buy":
            mfe[pos] = (path.max() - base) * 100.0
            mae[pos] = (base - path.min()) * 100.0
        else:
            mfe[pos] = (base - path.min()) * 100.0
            mae[pos] = (path.max() - base) * 100.0
    result["proxy_exit_mid"] = proxy_exit
    result["mfe_points_proxy"] = mfe
    result["mae_points_proxy"] = mae
    result["trailing_giveback_points_proxy"] = mfe - result["pips"].to_numpy()
    return result


def extract_features(symbol: str, feed_time_shift_hours: float = 0.0) -> pd.DataFrame:
    orders = _load_orders(feed_time_shift_hours)
    orders["actual_day_utc"] = orders["actual_open_utc"].dt.floor("D")
    frames: list[pd.DataFrame] = []
    days = sorted(orders["actual_day_utc"].unique())
    for number, day_value in enumerate(days, start=1):
        day = pd.Timestamp(day_value)
        day_orders = orders[orders["actual_day_utc"] == day_value]
        ticks = _fetch_tick_day(symbol, day)
        frames.append(_extract_day_features(day_orders, ticks))
        print(f"features {number}/{len(days)} {day.date()} orders={len(day_orders)} ticks={len(ticks.time_msc)}", flush=True)
    features = pd.concat(frames, ignore_index=True).sort_values(["actual_open_utc", "ticket"])
    features.to_csv(FEATURES_PATH, index=False, lineterminator="\n")
    return features


def _direction_accuracy(frame: pd.DataFrame, column: str, min_abs_points: float = 0.0) -> dict:
    values = frame[column]
    valid = values.notna() & (values.abs() >= min_abs_points) & (values != 0)
    actual_buy = frame.loc[valid, "trade_type"].eq("buy")
    predicted_buy = values[valid] > 0
    correct = actual_buy == predicted_buy
    return {
        "feature": column,
        "min_abs_points": min_abs_points,
        "orders": int(valid.sum()),
        "coverage_pct": round(100 * float(valid.mean()), 6),
        "momentum_accuracy_pct": round(100 * float(correct.mean()), 6) if valid.any() else None,
        "reversal_accuracy_pct": round(100 * float((~correct).mean()), 6) if valid.any() else None,
    }


def build_report(features: pd.DataFrame, symbol: str, broker: str) -> dict:
    tests = []
    for seconds in ENTRY_HORIZONS_SEC:
        column = f"ret_{seconds}s_points"
        for threshold in (0.0, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 30.0, 50.0):
            tests.append(_direction_accuracy(features, column, threshold))
    tests.sort(key=lambda row: (row["momentum_accuracy_pct"] or 0, row["coverage_pct"]), reverse=True)

    chronological = features.sort_values(["actual_open_utc", "ticket"]).copy()
    chronological["previous_close"] = chronological["actual_close_utc"].shift()
    chronological["reentry_gap_sec"] = (
        chronological["actual_open_utc"] - chronological["previous_close"]
    ).dt.total_seconds()
    wins = features[features["pips"] > 0]
    losses = features[features["pips"] < 0]
    price_valid = features[features["entry_tick_valid"]]
    report = {
        "feed": {
            "proxy_symbol": symbol,
            "proxy_broker": broker,
            "source_broker": "Vantage Markets (Pty) Ltd",
            "warning": "Proxy ticks can identify structure but cannot prove tick-perfect 100% replay across brokers.",
        },
        "orders": int(len(features)),
        "entry_tick_matches": int(features["entry_tick_valid"].sum()),
        "entry_tick_match_pct": round(100 * float(features["entry_tick_valid"].mean()), 6),
        "source_proxy_price_difference": {
            "median": round(float(price_valid["source_minus_proxy_entry"].median()), 6),
            "median_absolute": round(float(price_valid["source_minus_proxy_entry"].abs().median()), 6),
            "p90_absolute": round(float(price_valid["source_minus_proxy_entry"].abs().quantile(0.90)), 6),
        },
        "best_direction_tests": tests[:30],
        "all_direction_tests": tests,
        "reentry_gap_sec": {
            "median": round(float(chronological["reentry_gap_sec"].median()), 6),
            "p25": round(float(chronological["reentry_gap_sec"].quantile(0.25)), 6),
            "p75": round(float(chronological["reentry_gap_sec"].quantile(0.75)), 6),
            "share_0_to_5_pct": round(
                100 * float(chronological["reentry_gap_sec"].between(0, 5).mean()), 6
            ),
            "share_0_to_30_pct": round(
                100 * float(chronological["reentry_gap_sec"].between(0, 30).mean()), 6
            ),
        },
        "exit_proxy": {
            "eligible_orders": int(features["mfe_points_proxy"].notna().sum()),
            "winning_giveback_points": {
                "p25": round(float(wins["trailing_giveback_points_proxy"].quantile(0.25)), 6),
                "median": round(float(wins["trailing_giveback_points_proxy"].median()), 6),
                "p75": round(float(wins["trailing_giveback_points_proxy"].quantile(0.75)), 6),
            },
            "losing_mfe_points": {
                "p25": round(float(losses["mfe_points_proxy"].quantile(0.25)), 6),
                "median": round(float(losses["mfe_points_proxy"].median()), 6),
                "p75": round(float(losses["mfe_points_proxy"].quantile(0.75)), 6),
                "p90": round(float(losses["mfe_points_proxy"].quantile(0.90)), 6),
            },
        },
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def main() -> None:
    global FEATURES_PATH, REPORT_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSDm")
    parser.add_argument("--broker", default="Exness")
    parser.add_argument("--terminal", help="Optional terminal64.exe path")
    parser.add_argument("--tag", help="Output suffix, for example iux")
    parser.add_argument(
        "--feed-time-shift-hours",
        type=float,
        default=0.0,
        help="Shift canonical UTC before looking up broker-local encoded tick timestamps",
    )
    parser.add_argument("--reuse", action="store_true", help="Reuse order_tick_features.csv")
    args = parser.parse_args()

    if args.tag:
        FEATURES_PATH = DATA / f"order_tick_features_{args.tag}.csv"
        REPORT_PATH = DATA / f"tick_hypothesis_report_{args.tag}.json"

    if args.reuse and FEATURES_PATH.exists():
        features = pd.read_csv(FEATURES_PATH)
        features["actual_open_utc"] = pd.to_datetime(features["actual_open_utc"], utc=True)
        features["actual_close_utc"] = pd.to_datetime(features["actual_close_utc"], utc=True)
    else:
        initialized = (
            mt5.initialize(args.terminal, portable=True)
            if args.terminal
            else mt5.initialize()
        )
        if not initialized:
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        try:
            if not mt5.symbol_select(args.symbol, True):
                raise RuntimeError(f"Cannot select {args.symbol}: {mt5.last_error()}")
            features = extract_features(args.symbol, args.feed_time_shift_hours)
        finally:
            mt5.shutdown()
    report = build_report(features, args.symbol, args.broker)
    report["feed"]["lookup_time_shift_hours"] = args.feed_time_shift_hours
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
