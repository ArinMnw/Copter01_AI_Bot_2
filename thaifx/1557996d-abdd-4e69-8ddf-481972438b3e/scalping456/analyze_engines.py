"""Decompose every public order into the EA's distinct operating regimes."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ORDERS_PATH = DATA / "orders_35462_normalized.csv"
BASKETS_PATH = DATA / "fixedvol20_baskets.csv"
REPORT_PATH = DATA / "engine_decomposition.json"


def load_orders() -> pd.DataFrame:
    frame = pd.read_csv(ORDERS_PATH)
    frame["actual_open_utc"] = pd.to_datetime(frame["actual_open_utc"], utc=True)
    frame["actual_close_utc"] = pd.to_datetime(frame["actual_close_utc"], utc=True)
    return frame


def classify_orders(frame: pd.DataFrame) -> pd.Series:
    comment = frame["comment"].fillna("")
    conditions = [
        frame["symbol"].eq("XAUUSD+") & comment.str.startswith("[sl "),
        frame["symbol"].eq("XAUUSD+"),
        frame["symbol"].eq("FixedVol20") & comment.str.startswith("[sl "),
        frame["symbol"].eq("FixedVol20") & comment.str.startswith("[tp "),
        frame["symbol"].eq("FixedVol20"),
    ]
    labels = [
        "xau_core_trailing",
        "xau_recovery_or_manual",
        "fixedvol20_scalp_trial",
        "fixedvol20_grid_tp",
        "fixedvol20_forced_or_manual",
    ]
    return pd.Series(np.select(conditions, labels, default="unclassified"), index=frame.index)


def cluster_tp_baskets(frame: pd.DataFrame, close_gap_sec: float = 10.0) -> list[pd.DataFrame]:
    """Cluster legs whose common TP closes over adjacent server seconds."""
    clusters: list[pd.DataFrame] = []
    for _, same_target in frame.groupby("comment", sort=False):
        same_target = same_target.sort_values(["actual_close_utc", "ticket"])
        cluster_indexes: list[int] = []
        previous_close: pd.Timestamp | None = None
        for index, row in same_target.iterrows():
            close = row["actual_close_utc"]
            if previous_close is not None and (close - previous_close).total_seconds() > close_gap_sec:
                clusters.append(frame.loc[cluster_indexes].copy())
                cluster_indexes = []
            cluster_indexes.append(index)
            previous_close = close
        if cluster_indexes:
            clusters.append(frame.loc[cluster_indexes].copy())
    return clusters


def basket_table(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for basket_id, basket in enumerate(cluster_tp_baskets(frame), start=1):
        basket = basket.sort_values(["actual_open_utc", "ticket"])
        side = basket["trade_type"].iloc[0]
        sign = 1 if side == "buy" else -1
        total_volume = float(basket["volume"].sum())
        weighted_entry = float((basket["open_price"] * basket["volume"]).sum() / total_volume)
        target = float(basket["close_price"].iloc[0])
        target_distance = sign * (target - weighted_entry)
        volumes = basket["volume"].astype(float).tolist()
        prices = basket["open_price"].astype(float).tolist()
        adverse_steps = [
            sign * (prices[index - 1] - prices[index])
            for index in range(1, len(prices))
        ]
        expected_progressive = [
            min(174.0, int(volumes[index - 1] * 1.68 * 10 + 0.5 + 1e-9) / 10)
            for index in range(1, len(volumes))
        ]
        progression_matches = [
            abs(volumes[index] - expected_progressive[index - 1]) < 1e-9
            for index in range(1, len(volumes))
        ]
        fixed_matches = [abs(value - volumes[0]) < 1e-9 for value in volumes]
        if all(fixed_matches):
            sizing_mode = "fixed"
        elif all(progression_matches):
            sizing_mode = "x1.68_capped_174"
        else:
            sizing_mode = "mixed_or_exception"
        if abs(target_distance - 3.0) <= 0.002:
            target_mode = "3.0"
        elif abs(target_distance - 15.0) <= 0.002:
            target_mode = "15.0"
        else:
            target_mode = "exception"
        rows.append(
            {
                "basket_id": basket_id,
                "first_ticket": int(basket["ticket"].iloc[0]),
                "first_open_utc": basket["actual_open_utc"].iloc[0],
                "last_open_utc": basket["actual_open_utc"].iloc[-1],
                "first_close_utc": basket["actual_close_utc"].min(),
                "last_close_utc": basket["actual_close_utc"].max(),
                "side": side,
                "legs": int(len(basket)),
                "first_price": prices[0],
                "close_price": target,
                "weighted_entry": weighted_entry,
                "target_distance": target_distance,
                "target_mode": target_mode,
                "total_volume": total_volume,
                "max_volume": max(volumes),
                "sizing_mode": sizing_mode,
                "median_adverse_step": float(np.median(adverse_steps)) if adverse_steps else None,
                "profit": float(basket["profit"].sum()),
                "comment": basket["comment"].iloc[0],
            }
        )
    result = pd.DataFrame(rows).sort_values(["first_open_utc", "basket_id"]).reset_index(drop=True)
    result["previous_close_utc"] = result["last_close_utc"].shift()
    result["previous_close_price"] = result["close_price"].shift()
    result["flat_gap_sec"] = (
        result["first_open_utc"] - result["previous_close_utc"]
    ).dt.total_seconds()
    result["move_from_previous_close"] = result["first_price"] - result["previous_close_price"]
    expected_sign = np.where(result["side"].eq("buy"), 1, -1)
    result["direction_matches_previous_close"] = (
        np.sign(result["move_from_previous_close"]) == expected_sign
    )
    result.to_csv(BASKETS_PATH, index=False, lineterminator="\n")
    return result


def percentile_summary(values: pd.Series) -> dict:
    values = values.dropna().astype(float)
    return {
        "count": int(len(values)),
        "p01": round(float(values.quantile(0.01)), 6),
        "p25": round(float(values.quantile(0.25)), 6),
        "median": round(float(values.median()), 6),
        "p75": round(float(values.quantile(0.75)), 6),
        "p99": round(float(values.quantile(0.99)), 6),
    }


def build_report(frame: pd.DataFrame, baskets: pd.DataFrame) -> dict:
    frame = frame.copy()
    frame["engine"] = classify_orders(frame)
    comments = frame["comment"].fillna("")
    xau_core = frame[frame["engine"].eq("xau_core_trailing")].copy()
    fixed_sl = frame[frame["engine"].eq("fixedvol20_scalp_trial")].copy()
    xau_core["comment_price"] = pd.to_numeric(
        xau_core["comment"].str.extract(r"\[sl\s+([0-9.]+)\]")[0]
    )
    fixed_sl["comment_price"] = pd.to_numeric(
        fixed_sl["comment"].str.extract(r"\[sl\s+([0-9.]+)\]")[0]
    )
    eligible = baskets[
        baskets["flat_gap_sec"].between(0, 600)
    ].copy()
    progressive_or_fixed = baskets[~baskets["sizing_mode"].eq("mixed_or_exception")]
    report = {
        "order_count": int(len(frame)),
        "classification": {
            key: int(value)
            for key, value in frame["engine"].value_counts().sort_index().items()
        },
        "classification_sum": int(frame["engine"].value_counts().sum()),
        "xau_core": {
            "orders": int(len(xau_core)),
            "close_equals_sl_comment": int(
                np.isclose(xau_core["close_price"], xau_core["comment_price"]).sum()
            ),
            "tp_zero": int(xau_core["tp"].eq(0).sum()),
            "loss_exact_minus_100_points": int(xau_core["pips"].eq(-100).sum()),
            "loss_orders": int(xau_core["pips"].lt(0).sum()),
        },
        "fixedvol20_scalp_trial": {
            "orders": int(len(fixed_sl)),
            "close_equals_sl_comment": int(
                np.isclose(fixed_sl["close_price"], fixed_sl["comment_price"]).sum()
            ),
            "loss_exact_minus_1000_points": int(fixed_sl["pips"].eq(-1000).sum()),
            "first_open_utc": str(fixed_sl["actual_open_utc"].min()),
            "last_close_utc": str(fixed_sl["actual_close_utc"].max()),
        },
        "fixedvol20_grid": {
            "tp_orders": int(comments.str.startswith("[tp ").sum()),
            "baskets": int(len(baskets)),
            "target_modes_baskets": {
                key: int(value)
                for key, value in baskets["target_mode"].value_counts().sort_index().items()
            },
            "target_modes_orders": {
                key: int(value)
                for key, value in baskets.groupby("target_mode")["legs"].sum().sort_index().items()
            },
            "sizing_modes_baskets": {
                key: int(value)
                for key, value in baskets["sizing_mode"].value_counts().sort_index().items()
            },
            "sizing_exact_baskets": int(len(progressive_or_fixed)),
            "entry_transitions_under_600s": int(len(eligible)),
            "entry_direction_matches_previous_close": int(
                eligible["direction_matches_previous_close"].sum()
            ),
            "entry_direction_accuracy_pct": round(
                100 * float(eligible["direction_matches_previous_close"].mean()), 6
            ),
            "entry_abs_move_from_previous_close": percentile_summary(
                eligible["move_from_previous_close"].abs()
            ),
            "max_legs": int(baskets["legs"].max()),
            "max_volume": float(baskets["max_volume"].max()),
            "worst_basket_profit": round(float(baskets["profit"].min()), 6),
        },
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> None:
    frame = load_orders()
    fixed_tp = frame[
        frame["symbol"].eq("FixedVol20")
        & frame["comment"].fillna("").str.startswith("[tp ")
    ].copy()
    baskets = basket_table(fixed_tp)
    print(json.dumps(build_report(frame, baskets), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
