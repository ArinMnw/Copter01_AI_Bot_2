"""Infer the sequential trigger state machine used by Scalping456.

This script deliberately separates facts available from the public order ledger
from hypotheses that need an external tick proxy.  It reports transition-level
evidence and can replay threshold triggers on the configured MT5 tick symbol.
"""

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
TRANSITIONS_PATH = DATA / "sequential_transitions.csv"
REPORT_PATH = DATA / "state_machine_report.json"


def load_xau() -> pd.DataFrame:
    frame = pd.read_csv(ORDERS_PATH)
    frame["actual_open_utc"] = pd.to_datetime(frame["actual_open_utc"], utc=True)
    frame["actual_close_utc"] = pd.to_datetime(frame["actual_close_utc"], utc=True)
    core = frame[frame["symbol"] == "XAUUSD+"].copy()
    core["is_core"] = core["comment"].fillna("").str.startswith("[sl ")
    return core.sort_values(["actual_open_utc", "ticket"]).reset_index(drop=True)


def build_transitions(core: pd.DataFrame) -> pd.DataFrame:
    current = core.iloc[1:].reset_index(drop=True).copy()
    previous = core.iloc[:-1].reset_index(drop=True)
    result = pd.DataFrame(
        {
            "ticket": current["ticket"],
            "open_utc": current["actual_open_utc"],
            "side": current["trade_type"],
            "volume": current["volume"],
            "open_price": current["open_price"],
            "is_core": current["is_core"],
            "previous_ticket": previous["ticket"],
            "previous_side": previous["trade_type"],
            "previous_volume": previous["volume"],
            "previous_open_utc": previous["actual_open_utc"],
            "previous_close_utc": previous["actual_close_utc"],
            "previous_open_price": previous["open_price"],
            "previous_close_price": previous["close_price"],
            "previous_is_core": previous["is_core"],
        }
    )
    result["gap_sec"] = (
        result["open_utc"] - result["previous_close_utc"]
    ).dt.total_seconds()
    result["move_from_previous_close_points"] = (
        result["open_price"] - result["previous_close_price"]
    ) * 100.0
    result["move_from_previous_open_points"] = (
        result["open_price"] - result["previous_open_price"]
    ) * 100.0
    result["expected_sign"] = np.where(result["side"].eq("buy"), 1, -1)
    result["direction_matches_previous_close"] = (
        np.sign(result["move_from_previous_close_points"]) == result["expected_sign"]
    )
    result["abs_move_previous_close_points"] = result[
        "move_from_previous_close_points"
    ].abs()
    result["same_volume"] = result["volume"].eq(result["previous_volume"])
    result["non_overlapping"] = result["gap_sec"].ge(0)
    result.to_csv(TRANSITIONS_PATH, index=False, lineterminator="\n")
    return result


def describe(values: pd.Series) -> dict[str, float | int | None]:
    clean = values.dropna()
    if clean.empty:
        return {"count": 0}
    return {
        "count": int(len(clean)),
        "p01": round(float(clean.quantile(0.01)), 6),
        "p05": round(float(clean.quantile(0.05)), 6),
        "p10": round(float(clean.quantile(0.10)), 6),
        "p25": round(float(clean.quantile(0.25)), 6),
        "median": round(float(clean.median()), 6),
        "p75": round(float(clean.quantile(0.75)), 6),
        "p90": round(float(clean.quantile(0.90)), 6),
        "p95": round(float(clean.quantile(0.95)), 6),
        "p99": round(float(clean.quantile(0.99)), 6),
    }


def ledger_report(transitions: pd.DataFrame) -> dict:
    eligible = transitions[
        transitions["non_overlapping"] & transitions["gap_sec"].lt(600)
    ].copy()
    eligible["open_day"] = eligible["open_utc"].dt.strftime("%Y-%m-%d")
    mismatch = eligible[~eligible["direction_matches_previous_close"]]
    thresholds = {}
    for threshold in range(50, 151):
        passed = eligible["abs_move_previous_close_points"].ge(threshold)
        thresholds[str(threshold)] = {
            "coverage_pct": round(100 * float(passed.mean()), 6),
            "direction_accuracy_pct": round(
                100 * float(eligible.loc[passed, "direction_matches_previous_close"].mean()), 6
            ) if passed.any() else None,
        }
    by_volume = []
    for volume, group in eligible.groupby("volume", sort=True):
        by_volume.append(
            {
                "volume": float(volume),
                "orders": int(len(group)),
                "direction_accuracy_pct": round(
                    100 * float(group["direction_matches_previous_close"].mean()), 6
                ),
                "distance_points": describe(group["abs_move_previous_close_points"]),
            }
        )
    by_day = []
    for day, group in eligible.groupby("open_day", sort=True):
        by_day.append(
            {
                "day": day,
                "orders": int(len(group)),
                "mismatches": int((~group["direction_matches_previous_close"]).sum()),
                "direction_accuracy_pct": round(
                    100 * float(group["direction_matches_previous_close"].mean()), 6
                ),
                "distance_median_points": round(
                    float(group["abs_move_previous_close_points"].median()), 6
                ),
            }
        )
    return {
        "all_transitions": int(len(transitions)),
        "eligible_nonoverlap_gap_under_600s": int(len(eligible)),
        "overlapping": int((~transitions["non_overlapping"]).sum()),
        "gap_600s_or_more": int(transitions["gap_sec"].ge(600).sum()),
        "direction_accuracy_pct": round(
            100 * float(eligible["direction_matches_previous_close"].mean()), 6
        ),
        "distance_points": describe(eligible["abs_move_previous_close_points"]),
        "matching_distance_points": describe(
            eligible.loc[
                eligible["direction_matches_previous_close"],
                "abs_move_previous_close_points",
            ]
        ),
        "mismatch_distance_points": describe(mismatch["abs_move_previous_close_points"]),
        "mismatch_count": int(len(mismatch)),
        "mismatch_examples": mismatch.head(30).assign(
            open_utc=lambda x: x["open_utc"].astype(str),
            previous_close_utc=lambda x: x["previous_close_utc"].astype(str),
        )[
            [
                "ticket", "previous_ticket", "open_utc", "previous_close_utc",
                "gap_sec", "side", "volume", "open_price", "previous_close_price",
                "move_from_previous_close_points",
            ]
        ].to_dict("records"),
        "threshold_sweep": thresholds,
        "by_volume": by_volume,
        "by_day": by_day,
    }


def replay_proxy_thresholds(
    transitions: pd.DataFrame, symbol: str, feed_time_shift_hours: float = 0.0
) -> dict:
    eligible = transitions[
        transitions["non_overlapping"]
        & transitions["gap_sec"].between(0, 600)
    ].copy()
    thresholds = tuple(range(80, 121))
    stats = {
        threshold: {"orders": 0, "triggered": 0, "direction_correct": 0, "timing_errors": []}
        for threshold in thresholds
    }
    eligible["day"] = eligible["previous_close_utc"].dt.floor("D")
    for number, (day, group) in enumerate(eligible.groupby("day", sort=True), start=1):
        start = day.to_pydatetime().replace(tzinfo=timezone.utc) - timedelta(minutes=10)
        end = start + timedelta(days=1, minutes=20)
        ticks = mt5.copy_ticks_range(symbol, start, end, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            continue
        times = ticks["time_msc"].astype(np.int64)
        mids = (ticks["bid"].astype(float) + ticks["ask"].astype(float)) / 2.0
        for row in group.itertuples(index=False):
            shift_ms = int(feed_time_shift_hours * 3_600_000)
            close_ms = int(row.previous_close_utc.timestamp() * 1000) + shift_ms
            open_ms = int(row.open_utc.timestamp() * 1000) + shift_ms
            first = int(np.searchsorted(times, close_ms, side="left"))
            last = int(np.searchsorted(times, open_ms + 5000, side="right"))
            if first >= len(times) or last <= first:
                continue
            reference = mids[first]
            delta = (mids[first:last] - reference) * 100.0
            for threshold in thresholds:
                stat = stats[threshold]
                stat["orders"] += 1
                hit = np.flatnonzero(np.abs(delta) >= threshold)
                if len(hit) == 0:
                    continue
                idx = first + int(hit[0])
                stat["triggered"] += 1
                predicted_sign = 1 if mids[idx] > reference else -1
                if predicted_sign == row.expected_sign:
                    stat["direction_correct"] += 1
                stat["timing_errors"].append((times[idx] - open_ms) / 1000.0)
        print(f"replay day {number} {day.date()} orders={len(group)}", flush=True)
    rows = []
    for threshold, stat in stats.items():
        errors = pd.Series(stat.pop("timing_errors"), dtype=float)
        orders = stat["orders"]
        triggered = stat["triggered"]
        rows.append(
            {
                "threshold_points": threshold,
                **stat,
                "trigger_coverage_pct": round(100 * triggered / orders, 6) if orders else None,
                "direction_accuracy_pct": round(
                    100 * stat["direction_correct"] / triggered, 6
                ) if triggered else None,
                "timing_error_sec": describe(errors),
                "within_1s_pct": round(100 * float(errors.abs().le(1).mean()), 6) if len(errors) else None,
                "within_3s_pct": round(100 * float(errors.abs().le(3).mean()), 6) if len(errors) else None,
                "within_5s_pct": round(100 * float(errors.abs().le(5).mean()), 6) if len(errors) else None,
            }
        )
    return {"symbol": symbol, "tests": rows}


def replay_proxy_rolling_extrema(
    transitions: pd.DataFrame, symbol: str, feed_time_shift_hours: float = 0.0
) -> dict:
    """Test a flat-state trailing-entry hypothesis.

    While flat, a BUY fires after price rises D points from the running low and
    a SELL fires after it falls D points from the running high.  This explains
    the rare orders whose direction is opposite to the displacement from the
    previous close, something a fixed two-stop bracket cannot explain.
    """
    eligible = transitions[
        transitions["non_overlapping"]
        & transitions["gap_sec"].between(0, 600)
    ].copy()
    thresholds = tuple(range(70, 161))
    stats = {
        threshold: {"orders": 0, "triggered": 0, "direction_correct": 0, "timing_errors": []}
        for threshold in thresholds
    }
    eligible["day"] = eligible["previous_close_utc"].dt.floor("D")
    for number, (day, group) in enumerate(eligible.groupby("day", sort=True), start=1):
        start = day.to_pydatetime().replace(tzinfo=timezone.utc) - timedelta(minutes=10)
        end = start + timedelta(days=1, minutes=20)
        ticks = mt5.copy_ticks_range(symbol, start, end, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            continue
        times = ticks["time_msc"].astype(np.int64)
        bids = ticks["bid"].astype(float)
        asks = ticks["ask"].astype(float)
        for row in group.itertuples(index=False):
            shift_ms = int(feed_time_shift_hours * 3_600_000)
            close_ms = int(row.previous_close_utc.timestamp() * 1000) + shift_ms
            open_ms = int(row.open_utc.timestamp() * 1000) + shift_ms
            first = int(np.searchsorted(times, close_ms, side="left"))
            last = int(np.searchsorted(times, open_ms + 5000, side="right"))
            if first >= len(times) or last <= first:
                continue
            path_bid = bids[first:last]
            path_ask = asks[first:last]
            running_low_ask = np.minimum.accumulate(path_ask)
            running_high_bid = np.maximum.accumulate(path_bid)
            rise = (path_ask - running_low_ask) * 100.0
            fall = (running_high_bid - path_bid) * 100.0
            for threshold in thresholds:
                stat = stats[threshold]
                stat["orders"] += 1
                buy_hits = np.flatnonzero(rise >= threshold)
                sell_hits = np.flatnonzero(fall >= threshold)
                buy_hit = int(buy_hits[0]) if len(buy_hits) else len(path_bid) + 1
                sell_hit = int(sell_hits[0]) if len(sell_hits) else len(path_bid) + 1
                hit = min(buy_hit, sell_hit)
                if hit > len(path_bid):
                    continue
                predicted_sign = 1 if buy_hit <= sell_hit else -1
                stat["triggered"] += 1
                if predicted_sign == row.expected_sign:
                    stat["direction_correct"] += 1
                stat["timing_errors"].append((times[first + hit] - open_ms) / 1000.0)
        print(f"rolling replay day {number} {day.date()} orders={len(group)}", flush=True)
    rows = []
    for threshold, stat in stats.items():
        errors = pd.Series(stat.pop("timing_errors"), dtype=float)
        orders = stat["orders"]
        triggered = stat["triggered"]
        rows.append(
            {
                "threshold_points": threshold,
                **stat,
                "trigger_coverage_pct": round(100 * triggered / orders, 6) if orders else None,
                "direction_accuracy_pct": round(
                    100 * stat["direction_correct"] / triggered, 6
                ) if triggered else None,
                "timing_error_sec": describe(errors),
                "within_1s_pct": round(100 * float(errors.abs().le(1).mean()), 6) if len(errors) else None,
                "within_3s_pct": round(100 * float(errors.abs().le(3).mean()), 6) if len(errors) else None,
                "within_5s_pct": round(100 * float(errors.abs().le(5).mean()), 6) if len(errors) else None,
            }
        )
    ranked = sorted(
        rows,
        key=lambda row: (
            row["within_3s_pct"] or 0,
            row["direction_accuracy_pct"] or 0,
        ),
        reverse=True,
    )
    return {"symbol": symbol, "tests": rows, "best_by_within_3s": ranked[:15]}


def main() -> None:
    global TRANSITIONS_PATH, REPORT_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSDm")
    parser.add_argument("--terminal", help="Optional terminal64.exe path")
    parser.add_argument("--tag", help="Output suffix, for example iux")
    parser.add_argument("--feed-time-shift-hours", type=float, default=0.0)
    parser.add_argument("--skip-ticks", action="store_true")
    args = parser.parse_args()
    if args.tag:
        TRANSITIONS_PATH = DATA / f"sequential_transitions_{args.tag}.csv"
        REPORT_PATH = DATA / f"state_machine_report_{args.tag}.json"
    all_transitions = build_transitions(load_xau())
    transitions = all_transitions[all_transitions["is_core"]].copy()
    report = {
        "ledger": ledger_report(transitions),
        "all_xau_transitions_saved": len(all_transitions),
        "predecessor_population": "all_XAU_including_special_exits",
        "tick_replay_method": "conditional_on_observed_previous_close_and_actual_entry_horizon_not_full_causal",
        "full_source_clone_verified": False,
    }
    if not args.skip_ticks:
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
            report["proxy_threshold_replay"] = replay_proxy_thresholds(
                transitions, args.symbol, args.feed_time_shift_hours
            )
            report["proxy_rolling_extrema_replay"] = replay_proxy_rolling_extrema(
                transitions, args.symbol, args.feed_time_shift_hours
            )
            report["feed_time_shift_hours"] = args.feed_time_shift_hours
        finally:
            mt5.shutdown()
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
