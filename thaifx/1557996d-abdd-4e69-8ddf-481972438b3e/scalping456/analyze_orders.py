"""Create reproducible descriptive statistics for the Scalping456 snapshot."""

from __future__ import annotations

import argparse
import json
import re
from datetime import timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SOURCE = DATA / "orders_35462.csv"
COMMISSION_TOTAL = -1_320_571.32  # Public profile headline at snapshot time.
STARTING_DEPOSIT = 1_000.00
BKK_TZ = "Asia/Bangkok"
# ThaiFXBook serialised the Vantage MT5 server clock as if it were UTC.  Price
# alignment against an independent XAUUSD tick feed supports a -3 hour correction
# throughout this snapshot (95.26% of sampled entries fall inside the matching
# M1 bar after correction, versus 4.33% without it). This is an inferred offset,
# not an official broker timezone confirmation.
VANTAGE_SERVER_UTC_OFFSET_HOURS = 3
IUX_CHART_TZ = timezone(timedelta(hours=6))


def scalar(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def describe(group: pd.DataFrame) -> dict:
    wins = group[group["profit"] > 0]
    losses = group[group["profit"] < 0]
    durations = group["duration_sec"]
    gross_profit = float(wins["profit"].sum())
    gross_loss = float(losses["profit"].sum())
    return {
        "orders": len(group),
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": int((group["profit"] == 0).sum()),
        "win_rate_pct": round(100 * len(wins) / len(group), 6),
        "gross_profit_usd": round(float(group["profit"].sum()), 2),
        "profit_factor": round(gross_profit / abs(gross_loss), 6) if gross_loss else None,
        "avg_profit_usd": round(float(group["profit"].mean()), 6),
        "median_profit_usd": round(float(group["profit"].median()), 6),
        "avg_win_usd": round(float(wins["profit"].mean()), 6),
        "avg_loss_usd": round(float(losses["profit"].mean()), 6),
        "payoff_ratio_abs": round(float(wins["profit"].mean() / abs(losses["profit"].mean())), 6),
        "total_pips": round(float(group["pips"].sum()), 6),
        "avg_pips": round(float(group["pips"].mean()), 6),
        "total_lots": round(float(group["volume"].sum()), 6),
        "avg_lots": round(float(group["volume"].mean()), 6),
        "duration_sec": {
            "mean": round(float(durations.mean()), 3),
            "median": round(float(durations.median()), 3),
            "p25": round(float(durations.quantile(0.25)), 3),
            "p75": round(float(durations.quantile(0.75)), 3),
            "p90": round(float(durations.quantile(0.90)), 3),
            "p95": round(float(durations.quantile(0.95)), 3),
            "p99": round(float(durations.quantile(0.99)), 3),
            "max": round(float(durations.max()), 3),
        },
        "best_trade_usd": round(float(group["profit"].max()), 2),
        "worst_trade_usd": round(float(group["profit"].min()), 2),
    }


def streaks(values: list[bool]) -> list[int]:
    result: list[int] = []
    run = 0
    for value in values:
        if value:
            run += 1
        elif run:
            result.append(run)
            run = 0
    if run:
        result.append(run)
    return result


def concurrency_metrics(group: pd.DataFrame) -> dict:
    events: list[tuple[pd.Timestamp, int, str]] = []
    for row in group.itertuples():
        events.append((row.open_time, 1, row.trade_type))
        events.append((row.close_time, -1, row.trade_type))
    # Close before open at an identical timestamp.
    events.sort(key=lambda item: (item[0], item[1]))
    active = {"buy": 0, "sell": 0}
    maximum = 0
    opens_with_existing = 0
    opens_while_hedged = 0
    for _, delta, side in events:
        other = "sell" if side == "buy" else "buy"
        if delta == 1:
            if active["buy"] + active["sell"]:
                opens_with_existing += 1
            if active[other]:
                opens_while_hedged += 1
            active[side] += 1
            maximum = max(maximum, active["buy"] + active["sell"])
        else:
            active[side] -= 1
    return {
        "max_simultaneous_positions": maximum,
        "opens_with_existing_position": opens_with_existing,
        "opens_with_existing_pct": round(100 * opens_with_existing / len(group), 6),
        "opens_while_opposite_side_active": opens_while_hedged,
        "opens_while_opposite_side_active_pct": round(100 * opens_while_hedged / len(group), 6),
    }


def records(frame: pd.DataFrame, columns: list[str]) -> list[dict]:
    return [{key: scalar(value) for key, value in row.items()} for row in frame[columns].to_dict("records")]


def load_normalized() -> pd.DataFrame:
    df = pd.read_csv(SOURCE)
    for col in ("open_time", "close_time"):
        df[col] = pd.to_datetime(df[col], utc=True)
    df["source_open_time"] = df["open_time"]
    df["source_close_time"] = df["close_time"]
    correction = pd.Timedelta(hours=VANTAGE_SERVER_UTC_OFFSET_HOURS)
    df["open_time"] = df["source_open_time"] - correction
    df["close_time"] = df["source_close_time"] - correction
    df["open_bkk"] = df["open_time"].dt.tz_convert(BKK_TZ)
    df["close_bkk"] = df["close_time"].dt.tz_convert(BKK_TZ)
    df["open_iux_chart"] = df["open_time"].dt.tz_convert(IUX_CHART_TZ)
    df["close_iux_chart"] = df["close_time"].dt.tz_convert(IUX_CHART_TZ)
    # Preserve the website clock separately. These are derived display strings,
    # not independently captured page values and not validated market instants.
    for part in ("open", "close"):
        displayed = df[f"source_{part}_time"].dt.tz_localize(None) + pd.Timedelta(hours=7)
        df[f"web_{part}_display_derived"] = displayed.dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


def write_normalized(df: pd.DataFrame) -> None:
    normalized_columns = [
        "id", "ticket", "symbol", "trade_type", "volume", "profit",
        "source_open_time", "source_close_time", "open_time", "close_time",
        "web_open_display_derived", "web_close_display_derived",
        "open_bkk", "close_bkk", "open_iux_chart", "close_iux_chart",
        "open_price", "close_price", "pips", "sl", "tp", "comment",
    ]
    normalized = df[normalized_columns].rename(
        columns={
            "source_open_time": "source_server_open_time_mislabeled_utc",
            "source_close_time": "source_server_close_time_mislabeled_utc",
            "open_time": "actual_open_utc",
            "close_time": "actual_close_utc",
            "open_bkk": "actual_open_bkk",
            "close_bkk": "actual_close_bkk",
        }
    )
    # Do not round source numeric values through pandas' float parser/exporter.
    # Joins are ticket-keyed so sorting the working frame cannot mix records.
    raw = pd.read_csv(SOURCE, dtype=str, keep_default_na=False).set_index("ticket")
    tickets = normalized["ticket"].astype(str)
    if not raw.index.is_unique or len(raw) != len(normalized):
        raise ValueError("Source population changed or contains duplicate tickets")
    for column in ("id", "ticket", "symbol", "trade_type", "volume", "profit",
                   "open_price", "close_price", "pips", "sl", "tp", "comment"):
        if column == "ticket":
            normalized[column] = tickets
        else:
            normalized[column] = tickets.map(raw[column])
    normalized.to_csv(DATA / "orders_35462_normalized.csv", index=False, lineterminator="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalize-only", action="store_true")
    args = parser.parse_args()
    df = load_normalized()
    DATA.mkdir(parents=True, exist_ok=True)
    if args.normalize_only:
        write_normalized(df)
        print(json.dumps({"normalized_rows": len(df), "source_offset_inferred_hours": 3}))
        return
    df["duration_sec"] = (df["close_time"] - df["open_time"]).dt.total_seconds()
    df["exit_reason"] = df["comment"].fillna("").str.extract(r"^\[([a-zA-Z]+)", expand=False).fillna("other").str.lower()
    df["result"] = np.select([df["profit"] > 0, df["profit"] < 0], ["win", "loss"], default="breakeven")
    chronological = df.sort_values(["open_time", "ticket"]).reset_index(drop=True)

    gross = float(df["profit"].sum())
    total_lots = float(df["volume"].sum())
    commission_per_lot = COMMISSION_TOTAL / total_lots
    net_after_commission = gross + COMMISSION_TOTAL
    overall = describe(df)
    overall.update(
        {
            "first_open_utc": df["open_time"].min().isoformat(),
            "last_close_utc": df["close_time"].max().isoformat(),
            "first_open_bkk": df["open_bkk"].min().isoformat(),
            "last_close_bkk": df["close_bkk"].max().isoformat(),
            "source_clock_correction": "ThaiFXBook value - 3 hours = actual UTC",
            "vantage_server_utc_offset_hours": VANTAGE_SERVER_UTC_OFFSET_HOURS,
            "public_commission_total_usd": COMMISSION_TOTAL,
            "implied_commission_per_lot_usd": round(commission_per_lot, 8),
            "net_after_public_commission_usd": round(net_after_commission, 2),
            "ending_balance_reconstructed_usd": round(STARTING_DEPOSIT + net_after_commission, 2),
            "net_after_commission_per_order_usd": round(net_after_commission / len(df), 6),
        }
    )

    symbol_stats = {name: describe(group) for name, group in df.groupby("symbol", sort=False)}
    side_stats = {name: describe(group) for name, group in df.groupby("trade_type", sort=True)}
    symbol_side_stats = {
        f"{symbol}|{side}": describe(group)
        for (symbol, side), group in df.groupby(["symbol", "trade_type"], sort=False)
    }
    exit_stats = {
        f"{symbol}|{reason}": describe(group)
        for (symbol, reason), group in df.groupby(["symbol", "exit_reason"], sort=False)
    }

    profit_seq = chronological["profit"].tolist()
    win_runs = streaks([value > 0 for value in profit_seq])
    loss_runs = streaks([value < 0 for value in profit_seq])
    chronological["previous_profit"] = chronological["profit"].shift(1)
    chronological["previous_volume"] = chronological["volume"].shift(1)
    after_loss = chronological[chronological["previous_profit"] < 0]
    revenge_2x = after_loss[after_loss["volume"] > 2 * after_loss["previous_volume"]]

    xau = chronological[chronological["symbol"] == "XAUUSD+"].copy()
    xau["gap_from_prev_open_sec"] = xau["open_time"].diff().dt.total_seconds()
    xau["open_minute"] = xau["open_bkk"].dt.floor("min")
    minute_counts = xau.groupby("open_minute").size()
    xau_win = xau[xau["profit"] > 0]
    xau_loss = xau[xau["profit"] < 0]
    xau_direction_change_pct = 100 * (xau["trade_type"] != xau["trade_type"].shift(1)).iloc[1:].mean()

    common_loss_pips = (
        xau_loss.groupby("pips").size().sort_values(ascending=False).head(20).rename("orders").reset_index()
    )
    common_win_pips = (
        xau_win.groupby("pips").size().sort_values(ascending=False).head(20).rename("orders").reset_index()
    )
    volume_stats = (
        df.groupby(["symbol", "volume"])
        .agg(orders=("ticket", "size"), profit_usd=("profit", "sum"), win_rate_pct=("profit", lambda s: 100 * (s > 0).mean()))
        .reset_index()
        .sort_values(["symbol", "orders"], ascending=[True, False])
    )

    daily = (
        df.assign(date_bkk=df["open_bkk"].dt.strftime("%Y-%m-%d"))
        .groupby(["date_bkk", "symbol"])
        .agg(
            orders=("ticket", "size"),
            wins=("profit", lambda s: int((s > 0).sum())),
            losses=("profit", lambda s: int((s < 0).sum())),
            gross_profit_usd=("profit", "sum"),
            pips=("pips", "sum"),
            lots=("volume", "sum"),
            median_volume=("volume", "median"),
            max_volume=("volume", "max"),
            median_duration_sec=("duration_sec", "median"),
        )
        .reset_index()
    )
    daily["win_rate_pct"] = 100 * daily["wins"] / daily["orders"]

    hourly = (
        df.assign(hour_bkk=df["open_bkk"].dt.hour)
        .groupby(["symbol", "hour_bkk"])
        .agg(
            orders=("ticket", "size"),
            wins=("profit", lambda s: int((s > 0).sum())),
            gross_profit_usd=("profit", "sum"),
            pips=("pips", "sum"),
            lots=("volume", "sum"),
        )
        .reset_index()
    )
    hourly["win_rate_pct"] = 100 * hourly["wins"] / hourly["orders"]

    second_stats = (
        xau.assign(second=xau["open_bkk"].dt.second)
        .groupby("second")
        .agg(orders=("ticket", "size"), wins=("profit", lambda s: int((s > 0).sum())), gross_profit_usd=("profit", "sum"))
        .reset_index()
        .sort_values("orders", ascending=False)
    )
    second_stats["share_pct"] = 100 * second_stats["orders"] / len(xau)
    second_stats["win_rate_pct"] = 100 * second_stats["wins"] / second_stats["orders"]

    metrics = {
        "overall": overall,
        "by_symbol": symbol_stats,
        "by_side": side_stats,
        "by_symbol_side": symbol_side_stats,
        "by_symbol_exit_reason": exit_stats,
        "sequence": {
            "max_win_streak_chronological_open_order": max(win_runs),
            "max_loss_streak_chronological_open_order": max(loss_runs),
            "orders_after_a_loss": len(after_loss),
            "volume_gt_2x_previous_after_loss": len(revenge_2x),
        },
        "xau_microstructure": {
            "direction_change_vs_previous_order_pct": round(float(xau_direction_change_pct), 6),
            "gap_between_opens_sec": {
                "median": round(float(xau["gap_from_prev_open_sec"].median()), 6),
                "p25": round(float(xau["gap_from_prev_open_sec"].quantile(0.25)), 6),
                "p75": round(float(xau["gap_from_prev_open_sec"].quantile(0.75)), 6),
                "p90": round(float(xau["gap_from_prev_open_sec"].quantile(0.90)), 6),
                "share_le_5s_pct": round(float(100 * (xau["gap_from_prev_open_sec"] <= 5).mean()), 6),
                "share_le_60s_pct": round(float(100 * (xau["gap_from_prev_open_sec"] <= 60).mean()), 6),
            },
            "orders_per_active_minute": {
                "active_minutes": int(len(minute_counts)),
                "mean": round(float(minute_counts.mean()), 6),
                "median": round(float(minute_counts.median()), 6),
                "p90": round(float(minute_counts.quantile(0.90)), 6),
                "p99": round(float(minute_counts.quantile(0.99)), 6),
                "max": int(minute_counts.max()),
                "orders_in_minutes_with_2plus_pct": round(float(100 * minute_counts[minute_counts >= 2].sum() / len(xau)), 6),
            },
            "loss_pips": {
                "median": round(float(xau_loss["pips"].median()), 6),
                "p25": round(float(xau_loss["pips"].quantile(0.25)), 6),
                "p75": round(float(xau_loss["pips"].quantile(0.75)), 6),
                "exact_minus_100_count": int((xau_loss["pips"] == -100).sum()),
                "exact_minus_100_pct_of_losses": round(float(100 * (xau_loss["pips"] == -100).mean()), 6),
            },
            "win_pips": {
                "median": round(float(xau_win["pips"].median()), 6),
                "p25": round(float(xau_win["pips"].quantile(0.25)), 6),
                "p75": round(float(xau_win["pips"].quantile(0.75)), 6),
            },
            "concurrency": concurrency_metrics(xau),
            "common_loss_pips": records(common_loss_pips, ["pips", "orders"]),
            "common_win_pips": records(common_win_pips, ["pips", "orders"]),
            "open_second_top10": records(second_stats.head(10), ["second", "orders", "share_pct", "win_rate_pct", "gross_profit_usd"]),
        },
    }

    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "analysis_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=scalar) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_normalized(df)
    daily.to_csv(DATA / "daily_stats.csv", index=False, lineterminator="\n")
    hourly.to_csv(DATA / "hourly_stats_bkk.csv", index=False, lineterminator="\n")
    volume_stats.to_csv(DATA / "volume_stats.csv", index=False, lineterminator="\n")
    second_stats.to_csv(DATA / "xau_open_second_stats.csv", index=False, lineterminator="\n")
    print(json.dumps(metrics, ensure_ascii=False, indent=2, default=scalar))


if __name__ == "__main__":
    main()
