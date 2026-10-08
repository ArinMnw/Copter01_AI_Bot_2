"""Find the timestamp offset that aligns public orders with an MT5 M1 feed."""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

import MetaTrader5 as mt5
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ORDERS_PATH = DATA / "orders_35462_normalized.csv"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--terminal")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--min-offset", type=int, default=-8)
    parser.add_argument("--max-offset", type=int, default=8)
    args = parser.parse_args()

    orders = pd.read_csv(ORDERS_PATH)
    orders = orders[
        orders["symbol"].eq("XAUUSD+")
        & orders["comment"].fillna("").str.startswith("[sl ")
    ].copy()
    orders["time"] = pd.to_datetime(orders["actual_open_utc"], utc=True)
    initialized = (
        mt5.initialize(args.terminal, portable=True)
        if args.terminal
        else mt5.initialize()
    )
    if not initialized:
        raise RuntimeError(mt5.last_error())
    try:
        mt5.symbol_select(args.symbol, True)
        start = orders["time"].min().to_pydatetime() + timedelta(hours=args.min_offset - 1)
        end = orders["time"].max().to_pydatetime() + timedelta(hours=args.max_offset + 1)
        rates = mt5.copy_rates_range(args.symbol, mt5.TIMEFRAME_M1, start, end)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"No M1 rates: {mt5.last_error()}")
    finally:
        mt5.shutdown()

    bars = pd.DataFrame(rates)
    bars["minute"] = pd.to_datetime(bars["time"], unit="s", utc=True).dt.floor("min")
    bars = bars.drop_duplicates("minute").set_index("minute")
    rows = []
    for offset in range(args.min_offset, args.max_offset + 1):
        minute = (orders["time"] + pd.to_timedelta(offset, unit="h")).dt.floor("min")
        aligned = bars.reindex(minute).reset_index(drop=True)
        valid = aligned["high"].notna().to_numpy()
        price = orders["open_price"].to_numpy(float)
        low = aligned["low"].to_numpy(float)
        high = aligned["high"].to_numpy(float)
        close = aligned["close"].to_numpy(float)
        inside = valid & (price >= low) & (price <= high)
        distance = np.where(price < low, low - price, np.where(price > high, price - high, 0.0))
        rows.append(
            {
                "offset_hours_from_actual_open_utc": offset,
                "bars_found": int(valid.sum()),
                "coverage_pct": round(100 * float(valid.mean()), 6),
                "inside_m1_range": int(inside.sum()),
                "inside_m1_range_pct_all": round(100 * float(inside.mean()), 6),
                "inside_m1_range_pct_found": round(
                    100 * float(inside.sum() / valid.sum()), 6
                ) if valid.any() else None,
                "median_distance_to_m1_range": round(float(np.nanmedian(distance[valid])), 6),
                "median_abs_difference_to_close": round(
                    float(np.nanmedian(np.abs(price[valid] - close[valid]))), 6
                ),
            }
        )
    rows.sort(key=lambda row: (row["inside_m1_range_pct_found"] or 0), reverse=True)
    report = {"symbol": args.symbol, "orders": int(len(orders)), "offset_tests": rows}
    output = DATA / f"time_alignment_{args.tag}.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
