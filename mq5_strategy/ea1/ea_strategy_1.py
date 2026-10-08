# -*- coding: utf-8 -*-
"""Python research port of Heaven's Reach SMC Matrix Engine v3.37.

The MQ5 source is an ``OnTick`` BUY-only grid EA.  This runner evaluates zones
on the requested signal timeframe, then executes every strategy on completed
M1 bars.  Ambiguous M1 bars use adverse-first ordering, and a basket receiving
any fill may use only that bar's close as subsequent favorable movement.

Two zone modes are supported:

* ``research`` (default): apply the source's 50-bar lowest-low zone to the
  timeframe under test.  This makes the requested multi-timeframe comparison
  meaningful.
* ``source``: keep the original EA's hard-coded M15 zone/execution logic.  The
  source never reads the chart timeframe, so every requested chart TF is
  intentionally the same run in this mode.

Defaults mirror the source EA: 0.01 lot, 2,500-point single-order TP,
500-point first grid gap, widening by 250 points per level, 25 positions,
09:00-23:00 Bangkok local time, and the $1,000 profit collector enabled.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import MetaTrader5 as mt5


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config


BKK = timezone(timedelta(hours=7))
TF_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "H12": mt5.TIMEFRAME_H12,
    "D1": mt5.TIMEFRAME_D1,
}
TF_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1_800,
    "H1": 3_600,
    "H4": 14_400,
    "H12": 43_200,
    "D1": 86_400,
}
TF_ORDER = tuple(TF_MAP)

DEFAULTS = {
    "lot_size": 0.01,
    "normal_tp_points": 2_500,
    "grid_distance_points": 500,
    "max_orders": 25,
    "use_level_spacing": True,
    "level_step_points": 250,
    "max_spacing_points": 3_000,
    "grid_down_only": True,
    "ob_period": 50,
    "zone_size_points": 500,
    "recovery_distance_points": 5_000,
    "collect_profit": True,
    "profit_target": 1_000.0,
    "stop_after_collect": True,
    "target_use_equity": False,
    "start_hour": 9,
    "end_hour": 23,
    "simulate_stop_out": True,
    "slippage_points": 2.0,
    "commission_per_lot_side": 0.0,
    "swap_long_per_lot_day": 0.0,
    "swap_rollover_weekday": 3,
    "daily_profit_target": 0.0,
    "weekly_profit_target": 0.0,
}


@dataclass
class Position:
    entry: float
    volume: float
    opened_at: str
    opened_bar: int
    tp: float = 0.0


def _fmt_time(raw_time: int) -> str:
    return datetime.fromtimestamp(int(raw_time), tz=BKK).strftime("%Y-%m-%d %H:%M:%S")


def _in_session(raw_time: int, start_hour: int, end_hour: int) -> bool:
    hour = datetime.fromtimestamp(int(raw_time), tz=BKK).hour
    if start_hour <= end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def _grid_gap(order_count: int, cfg: dict[str, Any]) -> float:
    gap = float(cfg["grid_distance_points"])
    if cfg["use_level_spacing"] and order_count > 1:
        gap += (order_count - 1) * float(cfg["level_step_points"])
    max_gap = float(cfg["max_spacing_points"])
    if cfg["use_level_spacing"] and max_gap > 0:
        gap = min(gap, max_gap)
    return gap


def _smart_tp(positions: list[Position], bid: float, point: float, cfg: dict[str, Any]) -> float:
    volume = sum(pos.volume for pos in positions)
    cost = sum(pos.entry * pos.volume for pos in positions)
    top = max(pos.entry for pos in positions)
    bottom = min(pos.entry for pos in positions)
    breakeven = cost / volume
    if len(positions) == 1:
        tp = top + float(cfg["normal_tp_points"]) * point
    else:
        tp = bottom + (top - bottom) * 0.66
        if tp < breakeven:
            tp = breakeven + 50 * point
    # IUX reports zero stops/freeze level for XAUUSD.iux.  One point mirrors
    # the source's final minimum-distance guard in that case.
    return max(tp, bid + point)


def _profit(positions: Iterable[Position], exit_bid: float, contract_size: float) -> float:
    return sum((exit_bid - pos.entry) * pos.volume * contract_size for pos in positions)


def _drawdown(balance: float, positions: list[Position], bid: float, contract_size: float, peak: float) -> tuple[float, float]:
    equity = balance + _profit(positions, bid, contract_size)
    peak = max(peak, equity)
    return peak, max(0.0, peak - equity)


def _build_zone_schedule(
    signal_bars: list[Any], point: float, cfg: dict[str, Any]
) -> list[tuple[int, float]]:
    """Create zones that become visible only when the next TF bar opens."""
    period = int(cfg["ob_period"])
    size = float(cfg["zone_size_points"]) * point
    schedule = []
    for index in range(period, len(signal_bars)):
        lowest = min(float(signal_bars[j]["low"]) for j in range(index - period, index))
        schedule.append((int(signal_bars[index]["time"]), lowest + size))
    return schedule


def run_backtest(
    signal_bars: list[Any],
    execution_bars: list[Any],
    *,
    tf: str,
    point: float,
    contract_size: float,
    leverage: float,
    stop_out_level: float,
    start_index: int,
    start_balance: float,
    cfg: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run TF zones on completed M1 execution bars with conservative ordering."""
    settings = dict(DEFAULTS)
    if cfg:
        settings.update(cfg)

    positions: list[Position] = []
    trades: list[dict[str, Any]] = []
    balance = float(start_balance)
    target_base = balance
    equity_peak = balance
    max_dd = 0.0
    max_open = 0
    entries = 0
    cycles = 0
    collected = 0
    terminated = False
    stopped_out = False
    commissions = 0.0
    swaps = 0.0
    slippage_cost = 0.0
    cycle_start_balance: float | None = None
    last_bid = float(execution_bars[start_index]["open"])
    last_date = None
    previous_raw_time = None
    previous_close = None
    weekend_gaps_seen = 0
    weekend_gaps_held = 0
    max_weekend_adverse_gap = 0.0
    current_trade_date = None
    daily_base_balance = balance
    daily_paused = False
    daily_targets_hit = 0
    daily_target_dates: list[str] = []
    current_trade_week = None
    weekly_base_balance = balance
    weekly_paused = False
    weekly_targets_hit = 0
    weekly_target_dates: list[str] = []
    zones = _build_zone_schedule(signal_bars, point, settings)
    zone_index = -1
    zone_top = None

    def refresh_tp(bid: float) -> None:
        if not positions:
            return
        tp = _smart_tp(positions, bid, point, settings)
        for pos in positions:
            pos.tp = tp

    def open_buy(trigger_bid: float, spread: float, bar_index: int) -> None:
        nonlocal balance, commissions, cycle_start_balance, entries, max_open, slippage_cost
        if not positions:
            cycle_start_balance = balance
        slip = float(settings["slippage_points"]) * point
        ask = trigger_bid + spread + slip
        fee = float(settings["commission_per_lot_side"]) * float(settings["lot_size"])
        balance -= fee
        commissions += fee
        slippage_cost += slip * float(settings["lot_size"]) * contract_size
        pos = Position(
            entry=ask,
            volume=float(settings["lot_size"]),
            opened_at=_fmt_time(int(execution_bars[bar_index]["time"])),
            opened_bar=bar_index,
        )
        positions.append(pos)
        entries += 1
        max_open = max(max_open, len(positions))
        refresh_tp(trigger_bid)

    def close_all(exit_bid: float, bar_index: int, reason: str, market_exit: bool = False) -> None:
        nonlocal balance, commissions, cycle_start_balance, cycles, slippage_cost
        if not positions:
            return
        effective_bid = exit_bid
        if market_exit:
            slip = float(settings["slippage_points"]) * point
            effective_bid -= slip
            slippage_cost += slip * sum(pos.volume for pos in positions) * contract_size
        gross = _profit(positions, effective_bid, contract_size)
        exit_fee = float(settings["commission_per_lot_side"]) * sum(pos.volume for pos in positions)
        balance += gross - exit_fee
        commissions += exit_fee
        net = balance - (cycle_start_balance if cycle_start_balance is not None else balance - gross + exit_fee)
        trades.append(
            {
                "exit_time": _fmt_time(int(execution_bars[bar_index]["time"])),
                "reason": reason,
                "positions": len(positions),
                "first_entry": positions[0].entry,
                "last_entry": positions[-1].entry,
                "exit_price": effective_bid,
                "profit": net,
                "balance": balance,
            }
        )
        positions.clear()
        cycle_start_balance = None
        cycles += 1

    def stop_out_bid() -> float | None:
        if not settings["simulate_stop_out"] or not positions or leverage <= 0:
            return None
        exposure = sum(pos.volume * contract_size for pos in positions)
        entry_cost = sum(pos.entry * pos.volume * contract_size for pos in positions)
        denominator = exposure * (1.0 - stop_out_level / 100.0 / leverage)
        if denominator <= 0:
            return None
        return (entry_cost - balance) / denominator

    def check_stop_out(bid: float, bar_index: int, *, gap: bool = False) -> bool:
        nonlocal stopped_out, terminated
        if not settings["simulate_stop_out"] or not positions or leverage <= 0:
            return False
        liquidation_bid = stop_out_bid()
        equity_now = balance + _profit(positions, bid, contract_size)
        margin = sum(bid * pos.volume * contract_size / leverage for pos in positions)
        if margin <= 0:
            if equity_now > 0:
                return False
        elif equity_now / margin * 100.0 > stop_out_level + 1e-7:
            return False
        # A gap is filled at the actual open, never at an unavailable synthetic
        # threshold.  Inside a continuous M1 bar, use the threshold plus adverse
        # market slippage.
        exit_bid = bid if gap or liquidation_bid is None else max(bid, liquidation_bid)
        close_all(exit_bid, bar_index, "STOP_OUT_GAP" if gap else "STOP_OUT", market_exit=True)
        stopped_out = True
        terminated = True
        return True

    def charge_swap(raw_time: int) -> None:
        nonlocal balance, last_date, swaps
        current_date = datetime.fromtimestamp(raw_time, tz=BKK).date()
        if last_date is None:
            last_date = current_date
            return
        if current_date == last_date:
            return
        if positions:
            multiplier = 3 if current_date.weekday() == int(settings["swap_rollover_weekday"]) else 1
            amount = float(settings["swap_long_per_lot_day"]) * sum(pos.volume for pos in positions) * multiplier
            balance += amount
            swaps += amount
        last_date = current_date

    def check_daily_target(mark_bid: float, bar_index: int) -> bool:
        nonlocal daily_paused, daily_targets_hit
        target = float(settings["daily_profit_target"])
        if target <= 0 or daily_paused:
            return daily_paused
        gauge = balance + (_profit(positions, mark_bid, contract_size) if settings["target_use_equity"] else 0.0)
        if gauge < daily_base_balance + target:
            return False
        if positions:
            close_all(mark_bid, bar_index, "DAILY_PROFIT_COLLECT", market_exit=True)
        daily_paused = True
        daily_targets_hit += 1
        daily_target_dates.append(str(current_trade_date))
        return True

    def check_weekly_target(mark_bid: float, bar_index: int) -> bool:
        nonlocal weekly_paused, weekly_targets_hit
        target = float(settings["weekly_profit_target"])
        if target <= 0 or weekly_paused:
            return weekly_paused
        gauge = balance + (_profit(positions, mark_bid, contract_size) if settings["target_use_equity"] else 0.0)
        if gauge < weekly_base_balance + target:
            return False
        if positions:
            close_all(mark_bid, bar_index, "WEEKLY_PROFIT_COLLECT", market_exit=True)
        weekly_paused = True
        weekly_targets_hit += 1
        weekly_target_dates.append(str(current_trade_week))
        return True

    for bar_index in range(start_index, len(execution_bars)):
        bar = execution_bars[bar_index]
        raw_time = int(bar["time"])
        while zone_index + 1 < len(zones) and zones[zone_index + 1][0] <= raw_time:
            zone_index += 1
            zone_top = zones[zone_index][1]
        if zone_top is None:
            continue

        charge_swap(raw_time)
        bar_date = datetime.fromtimestamp(raw_time, tz=BKK).date()
        if current_trade_date != bar_date:
            current_trade_date = bar_date
            daily_base_balance = balance
            daily_paused = False
        bar_week = bar_date - timedelta(days=bar_date.weekday())
        if current_trade_week != bar_week:
            current_trade_week = bar_week
            weekly_base_balance = balance
            weekly_paused = False
        spread = max(0.0, float(bar["spread"]) * point)
        open_bid = float(bar["open"])
        low_bid = float(bar["low"])
        high_bid = float(bar["high"])
        close_bid = float(bar["close"])
        last_bid = close_bid

        if previous_raw_time is not None and raw_time - previous_raw_time > TF_SECONDS["M1"] * 60:
            previous_dt = datetime.fromtimestamp(previous_raw_time, tz=BKK)
            current_dt = datetime.fromtimestamp(raw_time, tz=BKK)
            if previous_dt.weekday() >= 4 and current_dt.weekday() == 0:
                weekend_gaps_seen += 1
                if positions:
                    weekend_gaps_held += 1
                    max_weekend_adverse_gap = max(
                        max_weekend_adverse_gap,
                        max(0.0, float(previous_close) - open_bid),
                    )
        previous_raw_time = raw_time
        previous_close = close_bid

        # Real weekend/session gaps execute at the first available M1 open.
        if positions and check_stop_out(open_bid, bar_index, gap=True):
            equity_peak, dd = _drawdown(balance, positions, open_bid, contract_size, equity_peak)
            max_dd = max(max_dd, dd)
            break
        if positions and open_bid >= positions[0].tp:
            close_all(open_bid, bar_index, "FULL_TP_GAP")

        check_daily_target(open_bid, bar_index)
        check_weekly_target(open_bid, bar_index)

        gauge = balance + (_profit(positions, open_bid, contract_size) if settings["target_use_equity"] else 0.0)
        periodic_target_enabled = (
            float(settings["daily_profit_target"]) > 0 or float(settings["weekly_profit_target"]) > 0
        )
        if not periodic_target_enabled and settings["collect_profit"] and gauge >= target_base + float(settings["profit_target"]):
            if positions:
                close_all(open_bid, bar_index, "PROFIT_COLLECT", market_exit=True)
            collected += 1
            if settings["stop_after_collect"]:
                terminated = True
                break
            target_base = balance

        had_position_at_bar_open = bool(positions)
        filled_this_bar = False
        in_session = _in_session(raw_time, int(settings["start_hour"]), int(settings["end_hour"]))
        period_paused = daily_paused or weekly_paused
        if in_session and not period_paused and not positions:
            if open_bid <= zone_top:
                open_buy(open_bid, spread, bar_index)
                filled_this_bar = True
            elif low_bid <= zone_top:
                open_buy(zone_top, spread, bar_index)
                filled_this_bar = True

        # Pessimistic M1 ordering for BUY: adverse Low/grid/stop-out first.
        if positions and in_session and not period_paused:
            cursor_bid = open_bid if had_position_at_bar_open else min(open_bid, zone_top)
            while len(positions) < int(settings["max_orders"]):
                low_entry = min(pos.entry for pos in positions)
                last_entry = positions[-1].entry
                gap_price = _grid_gap(len(positions), settings) * point
                trigger_ask = low_entry - gap_price if settings["grid_down_only"] else last_entry - gap_price
                trigger_bid = trigger_ask - spread
                liquidation_bid = stop_out_bid()
                if liquidation_bid is not None and low_bid <= liquidation_bid <= cursor_bid:
                    if trigger_bid < liquidation_bid:
                        check_stop_out(liquidation_bid, bar_index)
                        break
                if trigger_bid < low_bid or trigger_bid > cursor_bid:
                    break
                first_entry = positions[0].entry
                in_zone = trigger_bid <= zone_top
                recovery = abs(first_entry - trigger_ask) >= float(settings["recovery_distance_points"]) * point
                if not (in_zone or recovery):
                    break
                open_buy(trigger_bid, spread, bar_index)
                filled_this_bar = True
                cursor_bid = trigger_bid

        if terminated:
            equity_peak, dd = _drawdown(balance, positions, balance, contract_size, equity_peak)
            max_dd = max(max_dd, dd)
            break
        if positions and check_stop_out(low_bid, bar_index):
            equity_peak, dd = _drawdown(balance, positions, low_bid, contract_size, equity_peak)
            max_dd = max(max_dd, dd)
            break

        equity_peak, dd = _drawdown(balance, positions, low_bid, contract_size, equity_peak)
        max_dd = max(max_dd, dd)

        # Existing baskets may use the completed M1 range.  If any order filled
        # this bar, checklist rule #5 limits favorable movement to Close only.
        favorable_bid = close_bid if filled_this_bar else high_bid
        if positions and favorable_bid >= positions[0].tp:
            close_all(positions[0].tp, bar_index, "FULL_TP")

        check_daily_target(close_bid, bar_index)
        check_weekly_target(close_bid, bar_index)

        equity_peak, dd = _drawdown(balance, positions, close_bid, contract_size, equity_peak)
        max_dd = max(max_dd, dd)

        gauge = balance + (_profit(positions, close_bid, contract_size) if settings["target_use_equity"] else 0.0)
        if not periodic_target_enabled and settings["collect_profit"] and gauge >= target_base + float(settings["profit_target"]):
            if positions:
                close_all(close_bid, bar_index, "PROFIT_COLLECT", market_exit=True)
            collected += 1
            if settings["stop_after_collect"]:
                terminated = True
                break
            target_base = balance
            equity_peak = max(equity_peak, balance)
        if terminated:
            break

    estimated_exit_fee = float(settings["commission_per_lot_side"]) * sum(pos.volume for pos in positions)
    open_pnl = _profit(positions, last_bid, contract_size) - estimated_exit_fee
    equity = balance + open_pnl
    gross_profit = sum(max(0.0, row["profit"]) for row in trades)
    gross_loss = -sum(min(0.0, row["profit"]) for row in trades)
    wins = sum(row["profit"] > 0 for row in trades)
    summary = {
        "strategy": "EA1_Heavens_Reach_v3.37",
        "tf": tf,
        "bars": len(execution_bars) - start_index,
        "start": _fmt_time(int(execution_bars[start_index]["time"])),
        "end": _fmt_time(int(execution_bars[-1]["time"])),
        "start_balance": start_balance,
        "realized_pnl": balance - start_balance,
        "open_pnl": open_pnl,
        "net_pnl": equity - start_balance,
        "end_balance": balance,
        "end_equity": equity,
        "entries": entries,
        "closed_cycles": len(trades),
        "wins": wins,
        "win_rate": wins / len(trades) * 100.0 if trades else None,
        "profit_factor": gross_profit / gross_loss if gross_loss else (math.inf if gross_profit else None),
        "max_drawdown_usd": max_dd,
        "max_open_positions": max_open,
        "open_positions": len(positions),
        "profit_collections": collected,
        "terminated_on_target": terminated,
        "stopped_out": stopped_out,
        "commission_paid": commissions,
        "swap_paid": swaps,
        "estimated_slippage_cost": slippage_cost,
        "execution_tf": "M1",
        "execution_model": "completed M1; adverse-first; fill-bar favorable move capped at close",
        "weekend_gaps_seen": weekend_gaps_seen,
        "weekend_gaps_held": weekend_gaps_held,
        "max_weekend_adverse_gap": max_weekend_adverse_gap,
        "daily_profit_target": float(settings["daily_profit_target"]),
        "daily_targets_hit": daily_targets_hit,
        "daily_target_dates": daily_target_dates,
        "weekly_profit_target": float(settings["weekly_profit_target"]),
        "weekly_targets_hit": weekly_targets_hit,
        "weekly_target_dates": weekly_target_dates,
    }
    summary["terminated_on_target"] = terminated and not stopped_out
    return summary, trades


def _parse_bkk(value: str | None) -> datetime:
    if not value:
        return datetime.now(BKK)
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=BKK) if parsed.tzinfo is None else parsed.astimezone(BKK)


def _fetch_rates(
    symbol: str,
    tf: str,
    start: datetime,
    end: datetime,
    warmup: int,
    *,
    completed_only: bool = False,
) -> tuple[list[Any], int]:
    pad_days = math.ceil(warmup * TF_SECONDS[tf] / 86_400 * 7 / 5) + 10
    rates = mt5.copy_rates_range(symbol, TF_MAP[tf], start - timedelta(days=pad_days), end)
    if rates is None:
        raise RuntimeError(f"copy_rates_range failed: {mt5.last_error()}")
    end_ts = int(end.timestamp())
    bars = [
        bar for bar in rates
        if not completed_only or int(bar["time"]) + TF_SECONDS[tf] <= end_ts
    ]
    start_ts = int(start.timestamp())
    start_index = next((i for i, bar in enumerate(bars) if int(bar["time"]) >= start_ts), None)
    if start_index is None or start_index < warmup:
        raise RuntimeError(f"not enough history: bars={len(bars)}, warmup_before_start={start_index}")
    return bars, start_index


def _csv_name(tf: str, suffix: str = "") -> Path:
    return HERE / f"ea1_trades_{tf}{suffix}.csv"


def _write_trades(path: Path, trades: list[dict[str, Any]]) -> None:
    fields = ("exit_time", "reason", "positions", "first_entry", "last_entry", "exit_price", "profit", "balance")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(trades)


def _display(results: dict[str, dict[str, Any]], days: int) -> None:
    print(f"\n===== EA1 {days}-DAY SUMMARY =====")
    print(f"{'TF':<5}{'Net PnL':>12}{'Realized':>12}{'Open PnL':>12}{'Cycles':>9}{'Entries':>9}{'Max DD':>12}{'Status':>11}")
    for tf, row in results.items():
        status = "STOP-OUT" if row["stopped_out"] else (
            "TARGET" if row["terminated_on_target"] else ("OPEN" if row["open_positions"] else "END")
        )
        print(
            f"{tf:<5}{row['net_pnl']:>12.2f}{row['realized_pnl']:>12.2f}{row['open_pnl']:>12.2f}"
            f"{row['closed_cycles']:>9}{row['entries']:>9}{row['max_drawdown_usd']:>12.2f}{status:>11}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--end", help="Bangkok ISO datetime; default now")
    parser.add_argument("--tf", choices=TF_ORDER + ("all",), default="all")
    parser.add_argument("--mode", choices=("research", "source"), default="research")
    parser.add_argument("--balance", type=float, default=10_000.0)
    parser.add_argument("--lot", type=float, default=0.01)
    parser.add_argument("--slippage-points", type=float, default=2.0)
    parser.add_argument("--commission-per-lot-side", type=float, default=0.0)
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument("--daily-profit-target", type=float, default=0.0)
    target_group.add_argument("--weekly-profit-target", type=float, default=0.0)
    parser.add_argument("--no-collect-profit", action="store_true")
    parser.add_argument("--keep-running-after-collect", action="store_true")
    parser.add_argument("--summary-json")
    args = parser.parse_args()

    end = _parse_bkk(args.end)
    start = end - timedelta(days=args.days)
    settings = dict(DEFAULTS)
    settings["lot_size"] = args.lot
    settings["collect_profit"] = not args.no_collect_profit
    settings["stop_after_collect"] = not args.keep_running_after_collect
    settings["slippage_points"] = max(0.0, args.slippage_points)
    settings["commission_per_lot_side"] = max(0.0, args.commission_per_lot_side)
    settings["daily_profit_target"] = max(0.0, args.daily_profit_target)
    settings["weekly_profit_target"] = max(0.0, args.weekly_profit_target)
    if settings["daily_profit_target"] > 0 or settings["weekly_profit_target"] > 0:
        settings["collect_profit"] = False
        settings["stop_after_collect"] = False
    run_tag = (
        f"daily_{settings['daily_profit_target']:g}" if settings["daily_profit_target"] > 0
        else f"weekly_{settings['weekly_profit_target']:g}" if settings["weekly_profit_target"] > 0
        else "no_collect" if args.no_collect_profit
        else "continue_collect" if args.keep_running_after_collect
        else args.mode
    )

    if not config.mt5_initialize(mt5):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        symbol = config.profile_symbol(mt5_module=mt5, set_runtime=False)
        info = mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"symbol info unavailable: {symbol}")
        point = float(info.point)
        contract_size = float(info.trade_contract_size)
        account = mt5.account_info()
        leverage = float(getattr(account, "leverage", 0.0) or 0.0)
        stop_out_level = float(getattr(account, "margin_so_so", 0.0) or 0.0)
        swap_mode = int(getattr(info, "swap_mode", 0) or 0)
        if swap_mode == 1:
            tick_size = float(getattr(info, "trade_tick_size", 0.0) or point)
            tick_value = float(getattr(info, "trade_tick_value_loss", 0.0) or 0.0)
            settings["swap_long_per_lot_day"] = float(info.swap_long) * point / tick_size * tick_value
        else:
            # SYMBOL_SWAP_MODE_DISABLED=0.  Other interest/currency modes need
            # broker-specific conversion and are intentionally not guessed.
            settings["swap_long_per_lot_day"] = 0.0
        settings["swap_rollover_weekday"] = int(getattr(info, "swap_rollover3days", 3) or 3)
        tf_list = TF_ORDER if args.tf == "all" else (args.tf,)
        results: dict[str, dict[str, Any]] = {}
        execution_bars, execution_start = _fetch_rates(
            symbol, "M1", start, end, 1, completed_only=True
        )
        print(
            f"EA1 Heaven's Reach v3.37 | mode={args.mode} | {start.isoformat()} -> {end.isoformat()} | "
            f"symbol={symbol} lot={args.lot:.2f} balance={args.balance:.2f}"
        )

        if args.mode == "source":
            # The source uses M15 unconditionally; run it once and copy the
            # result to requested chart TFs because chart TF is not consulted.
            signal_bars, _ = _fetch_rates(symbol, "M15", start, end, int(settings["ob_period"]) + 5)
            base, trades = run_backtest(
                signal_bars,
                execution_bars,
                tf="M15",
                point=point,
                contract_size=contract_size,
                leverage=leverage,
                stop_out_level=stop_out_level,
                start_index=execution_start,
                start_balance=args.balance,
                cfg=settings,
            )
            for tf in tf_list:
                row = dict(base)
                row["tf"] = tf
                row["signal_tf"] = "M15"
                row["note"] = "Source EA is hard-coded to PERIOD_M15; M1 is used only for verified execution."
                results[tf] = row
                _write_trades(_csv_name(tf, f"_{run_tag}"), trades)
        else:
            for tf in tf_list:
                started = time.perf_counter()
                try:
                    signal_bars, _ = _fetch_rates(symbol, tf, start, end, int(settings["ob_period"]) + 5)
                    row, trades = run_backtest(
                        signal_bars,
                        execution_bars,
                        tf=tf,
                        point=point,
                        contract_size=contract_size,
                        leverage=leverage,
                        stop_out_level=stop_out_level,
                        start_index=execution_start,
                        start_balance=args.balance,
                        cfg=settings,
                    )
                except RuntimeError as exc:
                    print(f"{tf}: SKIP - {exc}")
                    continue
                row["signal_tf"] = tf
                row["elapsed_sec"] = round(time.perf_counter() - started, 3)
                row["model"] = "completed M1 execution; adverse-first; dynamic spread; friction enabled"
                results[tf] = row
                _write_trades(_csv_name(tf, f"_{run_tag}" if run_tag != "research" else ""), trades)
                print(
                    f"{tf}: net={row['net_pnl']:.2f} realized={row['realized_pnl']:.2f} "
                    f"open={row['open_pnl']:.2f} cycles={row['closed_cycles']} entries={row['entries']} "
                    f"maxDD={row['max_drawdown_usd']:.2f} stopout={row['stopped_out']}"
                )

        _display(results, args.days)
        for row in results.values():
            if row["profit_factor"] == math.inf:
                row["profit_factor"] = None
        summary_path = Path(args.summary_json) if args.summary_json else HERE / f"ea1_summary_{args.days}d_{run_tag}.json"
        with summary_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {
                    "generated_at_bkk": datetime.now(BKK).isoformat(),
                    "mode": args.mode,
                    "symbol": symbol,
                    "point": point,
                    "contract_size": contract_size,
                    "leverage": leverage,
                    "stop_out_level_percent": stop_out_level,
                    "swap_mode": swap_mode,
                    "settings": settings,
                    "results": results,
                },
                handle,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            handle.write("\n")
        print(f"\nSummary JSON: {summary_path}")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
