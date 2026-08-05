# -*- coding: utf-8 -*-
"""Cached cross-window release-shape sweep for optimized S311."""

from __future__ import annotations

from datetime import datetime
import json
import math
import re

from sim_strategy_backtest import BKK, parse_bkk, prepare_rates
from strategy119 import _atr, _bars
from strategy311 import detect_s311


WINDOWS = (
    ("2m", 2, "2026-07-20T00:00:00+07:00"),
    ("6m", 6, "2026-07-20T00:00:00+07:00"),
    ("wf", 6, "2026-01-20T00:00:00+07:00"),
)
BODY_VALUES = (0.45, 0.50, 0.575, 0.65, 0.70)
RANGE_VALUES = (0.70, 0.8375, 1.00, 1.15)
CLOSE_VALUES = (0.75, 0.80, 0.8325, 0.875, 0.90)
BASE_SHAPE = (0.575, 0.8375, 0.8325)
OFFICIAL_BASE = {
    "2m": {"closed": 10, "net": 70.91},
    "6m": {"closed": 18, "net": 196.41},
    "wf": {"closed": 22, "net": 90.31},
}
_REASON_RE = re.compile(
    r"CvM=(?P<cvm>[-+0-9.eE]+), median shift=(?P<shift>[-+0-9.eE]+)MAD"
)


def _candidate_cache(bars, start_index):
    permissive = {
        "ALLOW_BUY": False,
        "ALLOW_SELL": True,
        "CVM_MIN": 0.0,
        "MEDIAN_SHIFT_MAD_MIN": 0.0,
        "RELEASE_BODY_ATR_MIN": 0.0,
        "RELEASE_RANGE_ATR_MIN": 0.0,
        "RELEASE_CLOSE_FRACTION": 0.0,
    }
    wait = {"signal": "WAIT", "reason": "shape filter"}
    signals, features = {}, {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - 299:index + 1]
        moment = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s311(window, "M5", moment, permissive)
        signals[index] = wait
        if signal.get("signal") != "SELL":
            continue
        match = _REASON_RE.search(signal["reason"])
        if match is None:
            raise AssertionError(signal["reason"])
        normalized = _bars(window)
        atr = _atr(normalized[:-1], 14)
        event = normalized[-1]
        event_range = event["high"] - event["low"]
        if atr <= 0.0 or event_range <= 0.0:
            continue
        signals[index] = signal
        features[index] = {
            "cvm": float(match.group("cvm")),
            "shift": abs(float(match.group("shift"))),
            "body": abs(event["close"] - event["open"]) / atr,
            "range": event_range / atr,
            "close": (event["high"] - event["close"]) / event_range,
        }
    return signals, features, wait


def _summary_sparse(rr, be_rr, bars, candidates, spread=0.20, lot=0.01):
    """Replay only candidate indices; WAIT bars cannot affect one-position state."""
    trades = []
    invalid = 0
    next_free = 0
    for index, signal in candidates:
        if index < next_free:
            continue
        side = 1 if signal["signal"] == "BUY" else -1
        quoted_entry = float(signal["entry"])
        sl = float(signal["sl"])
        fill_index = index + 1
        entry = float(bars[fill_index]["open"])
        quoted_risk = side * (quoted_entry - sl)
        actual_risk = side * (entry - sl)
        if quoted_risk <= 0.0 or actual_risk <= 0.0:
            invalid += 1
            next_free = fill_index + 1
            continue
        raw_tp = quoted_entry + side * rr * quoted_risk
        tp = (
            math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
            if side > 0
            else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
        )
        be_trigger = entry + side * actual_risk * be_rr
        active_sl, be_armed = sl, False
        outcome = exit_price = None
        for cursor in range(fill_index, len(bars)):
            low = float(bars[cursor]["low"])
            high = float(bars[cursor]["high"])
            if side > 0:
                if low <= active_sl:
                    outcome, exit_price = ("BE" if be_armed else "SL"), active_sl
                elif high >= tp:
                    outcome, exit_price = "TP", tp
                elif high >= be_trigger:
                    be_armed, active_sl = True, entry
            else:
                if high >= active_sl:
                    outcome, exit_price = ("BE" if be_armed else "SL"), active_sl
                elif low <= tp:
                    outcome, exit_price = "TP", tp
                elif low <= be_trigger:
                    be_armed, active_sl = True, entry
            if outcome:
                next_free = cursor + 1
                break
        if outcome is None:
            break
        pnl = round(
            (side * (exit_price - entry) - spread) * (100.0 * lot), 2
        )
        trades.append((outcome, pnl))

    profits = [pnl for _, pnl in trades]
    gross_profit = sum(max(0.0, pnl) for pnl in profits)
    gross_loss = -sum(min(0.0, pnl) for pnl in profits)
    equity = peak = max_dd = 0.0
    for pnl in profits:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    wins = sum(outcome == "TP" for outcome, _ in trades)
    return {
        "closed": len(trades),
        "invalid": invalid,
        "wins": wins,
        "win_rate": 100.0 * wins / len(trades) if trades else 0.0,
        "net": sum(profits),
        "pf": gross_profit / gross_loss if gross_loss else math.inf,
        "max_dd": max_dd,
    }


def main():
    prepared = {}
    candidates = {}
    for label, months, end_text in WINDOWS:
        end = parse_bkk(end_text)
        bars, start_bkk, start_index = prepare_rates(months, "M5", end, 300)
        signals, features, wait = _candidate_cache(bars, start_index)
        prepared[label] = (months, end, bars, start_bkk, start_index)
        candidates[label] = (signals, features, wait)

    rows = []
    for body_floor in BODY_VALUES:
        for range_floor in RANGE_VALUES:
            for close_floor in CLOSE_VALUES:
                windows = {}
                for label, _, _ in WINDOWS:
                    months, end, bars, start_bkk, start_index = prepared[label]
                    signals, features, wait = candidates[label]
                    selected = [
                        (index, signals[index])
                        for index, feature in features.items()
                        if feature["cvm"] >= 0.2875
                        and feature["shift"] >= 0.225
                        and feature["body"] >= body_floor
                        and feature["range"] >= range_floor
                        and feature["close"] >= close_floor
                    ]
                    windows[label] = _summary_sparse(
                        10.1, 0.25, bars, selected
                    )
                long_net = windows["6m"]["net"] + windows["wf"]["net"]
                worst_dd = max(windows["6m"]["max_dd"], windows["wf"]["max_dd"])
                rows.append({
                    "body": body_floor,
                    "range": range_floor,
                    "close": close_floor,
                    "2m": windows["2m"],
                    "6m": windows["6m"],
                    "wf": windows["wf"],
                    "long_net": long_net,
                    "long_ratio": long_net / worst_dd if worst_dd else float("inf"),
                    "worst_pf": min(windows["6m"]["pf"], windows["wf"]["pf"]),
                })

    base = next(
        row for row in rows
        if (row["body"], row["range"], row["close"]) == BASE_SHAPE
    )
    for label, expected in OFFICIAL_BASE.items():
        cached_result = base[label]
        if (
            cached_result["closed"] != expected["closed"]
            or abs(cached_result["net"] - expected["net"]) > 1e-7
        ):
            raise AssertionError({
                "window": label,
                "cached": cached_result,
                "official": expected,
            })

    survivors = [
        row for row in rows
        if row["2m"]["net"] > 0.0
        and row["6m"]["net"] > 0.0
        and row["wf"]["net"] > 0.0
    ]
    survivors.sort(
        key=lambda row: (
            row["long_ratio"],
            row["worst_pf"],
            row["2m"]["net"],
        ),
        reverse=True,
    )
    print("BASE", json.dumps(base, allow_nan=True))
    print("SURVIVORS", len(survivors), "OF", len(rows))
    for row in survivors[:30]:
        print(json.dumps(row, allow_nan=True))


if __name__ == "__main__":
    main()
