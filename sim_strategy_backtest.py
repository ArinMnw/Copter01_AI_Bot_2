# -*- coding: utf-8 -*-
"""Generic conservative two-month backtest for standalone strategy modules.

Example:
    python sim_strategy_backtest.py --strategy 116 --months 2 --tf M5
"""

from __future__ import annotations

import argparse
import calendar
import csv
import importlib
import json
import math
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5

import config


BKK = timezone(timedelta(hours=7))
TF_MAP = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
          "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
          "H1": mt5.TIMEFRAME_H1}
TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600}


def subtract_months(value, months):
    index = value.year * 12 + value.month - 1 - months
    year, month_zero = divmod(index, 12)
    month = month_zero + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def parse_bkk(value):
    parsed = datetime.fromisoformat(value) if value else datetime.now(BKK)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BKK)
    return parsed.astimezone(BKK)


def validate_signal(signal, strategy_id):
    if signal.get("signal") == "WAIT":
        if "reason" not in signal:
            raise AssertionError(f"S{strategy_id} WAIT has no reason")
        return
    required = {"signal", "entry", "sl", "tp", "order_type", "pattern",
                "reason", "be_rr", "cancel_bars"}
    missing = required - set(signal)
    if missing:
        raise AssertionError(f"S{strategy_id} payload missing {sorted(missing)}")
    if signal["signal"] not in ("BUY", "SELL"):
        raise AssertionError(f"invalid signal {signal['signal']}")
    if signal["order_type"] not in ("limit", "market"):
        raise AssertionError(f"invalid order_type {signal['order_type']}")
    if not str(signal["pattern"]).startswith(f"S{strategy_id} "):
        raise AssertionError(f"invalid pattern {signal['pattern']}")
    entry, sl, tp = map(float, (signal["entry"], signal["sl"], signal["tp"]))
    risk = entry - sl if signal["signal"] == "BUY" else sl - entry
    reward = tp - entry if signal["signal"] == "BUY" else entry - tp
    if risk <= 0.0 or reward / risk < 1.5 - 1e-9:
        raise AssertionError("risk invalid or quoted RR below 1.5")


def prepare_rates(months, tf_name, end_bkk, lookback):
    """Fetch one immutable price set reusable across parameter trials."""
    start_bkk = subtract_months(end_bkk, months)
    history_days = math.ceil(lookback * TF_SECONDS[tf_name] / 86400.0) + 7
    fetch_start = start_bkk - timedelta(days=history_days)
    if not config.mt5_initialize(mt5):
        raise RuntimeError("MT5 initialization failed")
    rates = mt5.copy_rates_range(config.SYMBOL, TF_MAP[tf_name], fetch_start, end_bkk)
    mt5.shutdown()
    if rates is None or len(rates) <= lookback:
        raise RuntimeError("not enough MT5 rates")
    bars = list(rates)
    start_index = next(
        (index for index, bar in enumerate(bars)
         if int(bar["time"]) >= int(start_bkk.timestamp())),
        None,
    )
    if start_index is None or start_index < lookback:
        raise RuntimeError("lookback history does not cover requested start")
    return bars, start_bkk, start_index


def backtest(strategy_id, months, tf_name, spread, lot, end_bkk, lookback,
             cfg=None, prepared=None):
    module = importlib.import_module(f"strategy{strategy_id}")
    detector = getattr(module, f"detect_s{strategy_id}")
    if prepared is None:
        bars, start_bkk, start_index = prepare_rates(months, tf_name, end_bkk, lookback)
    else:
        bars, start_bkk, start_index = prepared
    detector_cfg = dict(cfg or {})

    trades, signals, expired, invalid = [], 0, 0, 0
    next_free = start_index
    for index in range(start_index, len(bars) - 1):
        if index < next_free:
            continue
        window = bars[index - lookback + 1:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detector(window, tf_name, dt_bkk, detector_cfg)
        validate_signal(signal, strategy_id)
        if signal["signal"] not in ("BUY", "SELL"):
            continue
        signals += 1
        direction = signal["signal"]
        side = 1 if direction == "BUY" else -1
        quoted_entry = float(signal["entry"])
        sl, tp = float(signal["sl"]), float(signal["tp"])
        order_type = signal["order_type"]

        if order_type == "market":
            fill_index = index + 1
            entry = float(bars[fill_index]["open"])
        else:
            entry = quoted_entry
            cancel_bars = int(signal["cancel_bars"] or 1)
            pending_end = min(len(bars) - 1, index + cancel_bars)
            fill_index = None
            for pending_index in range(index + 1, pending_end + 1):
                low, high = float(bars[pending_index]["low"]), float(bars[pending_index]["high"])
                if ((side > 0 and low <= entry - spread)
                        or (side < 0 and high >= entry + spread)):
                    fill_index = pending_index
                    break
            if fill_index is None:
                expired += 1
                next_free = pending_end + 1
                continue

        risk = side * (entry - sl)
        if risk <= 0.0:
            invalid += 1
            next_free = fill_index + 1
            continue
        be_rr = signal.get("be_rr")
        be_trigger = entry + side * risk * float(be_rr) if be_rr is not None else None
        active_sl, be_armed = sl, False
        outcome = exit_index = exit_price = None
        for cursor in range(fill_index, len(bars)):
            low, high = float(bars[cursor]["low"]), float(bars[cursor]["high"])
            # Conservative OHLC ordering: active SL first, TP second. A BE
            # trigger becomes active on the next bar only.
            if side > 0:
                if low <= active_sl:
                    outcome, exit_price = ("BE" if be_armed else "SL"), active_sl
                elif high >= tp:
                    outcome, exit_price = "TP", tp
                elif be_trigger is not None and high >= be_trigger:
                    be_armed, active_sl = True, entry
            else:
                if high >= active_sl:
                    outcome, exit_price = ("BE" if be_armed else "SL"), active_sl
                elif low <= tp:
                    outcome, exit_price = "TP", tp
                elif be_trigger is not None and low <= be_trigger:
                    be_armed, active_sl = True, entry
            if outcome:
                exit_index = cursor
                break
        if outcome is None:
            break

        contract_multiplier = 100.0 * lot
        pnl = (side * (exit_price - entry) - spread) * contract_multiplier
        trades.append({
            "signal_time": dt_bkk.isoformat(),
            "exit_time": datetime.fromtimestamp(int(bars[exit_index]["time"]), tz=BKK).isoformat(),
            "direction": direction,
            "entry": round(entry, 2), "sl": sl, "tp": tp,
            "outcome": outcome, "profit": round(pnl, 2),
            "pattern": signal["pattern"], "reason": signal["reason"],
        })
        next_free = exit_index + 1

    profits = [trade["profit"] for trade in trades]
    wins = sum(profit > 0.0 for profit in profits)
    gross_win = sum(profit for profit in profits if profit > 0.0)
    gross_loss = -sum(profit for profit in profits if profit < 0.0)
    net = sum(profits)
    equity = peak = max_drawdown = 0.0
    for profit in profits:
        equity += profit
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    calendar_days = max(1.0, (end_bkk - start_bkk).total_seconds() / 86400.0)
    summary = {
        "strategy": f"S{strategy_id}", "tf": tf_name,
        "start": start_bkk.isoformat(), "end": end_bkk.isoformat(),
        "months": months, "spread": spread, "lot": lot,
        "signals": signals, "closed": len(trades), "expired": expired,
        "invalid": invalid, "wins": wins,
        "win_rate": wins / len(trades) * 100.0 if trades else None,
        "net_profit": net,
        "pnl_per_day": net / calendar_days,
        "pnl_per_month": net / months,
        "profit_factor": gross_win / gross_loss if gross_loss else (math.inf if gross_win else None),
        "max_drawdown": max_drawdown,
    }
    return summary, trades


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", type=int, required=True)
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--tf", choices=tuple(TF_MAP), default="M5")
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--lot", type=float, default=0.01)
    parser.add_argument("--end", help="BKK ISO datetime; default now")
    parser.add_argument("--lookback", type=int, default=300)
    parser.add_argument("--cfg-json", default="{}",
                        help="JSON object passed to the detector cfg")
    parser.add_argument("--csv")
    args = parser.parse_args()
    try:
        detector_cfg = json.loads(args.cfg_json)
        if not isinstance(detector_cfg, dict):
            raise ValueError("cfg must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        parser.error(f"invalid --cfg-json: {exc}")
    summary, trades = backtest(
        args.strategy, args.months, args.tf, args.spread, args.lot,
        parse_bkk(args.end), args.lookback, detector_cfg,
    )
    print(summary)
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=(trades[0].keys() if trades else (
                "signal_time", "exit_time", "direction", "entry", "sl", "tp",
                "outcome", "profit", "pattern", "reason",
            )))
            writer.writeheader()
            writer.writerows(trades)


if __name__ == "__main__":
    main()
