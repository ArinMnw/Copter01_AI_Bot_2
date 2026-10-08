"""Save raw M1/tick witnesses and score clock alignment, not strategy accuracy.

Reads JSONL source without pandas/decimal coercion. Raw server-looking order
timestamps are compared on a numeric axis; their +00:00 label is not trusted.
M1 contains bid OHLC; spread-adjusted containment is diagnostic only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from vantage_readonly import attach


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
FEEDS = {"XAUUSD": "XAUUSD+", "XAUUSD.crp": "XAUUSD+", "FixedVol20": "FixedVol20"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp(value):
    return datetime.fromisoformat(value).timestamp()


def write_json(path, value):
    # Generated research data; exclusive create preserves any previous evidence.
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def group(row):
    if row["symbol"] == "XAUUSD+":
        return "xau_sl" if row["comment"].startswith("[sl ") else "xau_other"
    if row["comment"].startswith("[tp "):
        return "fixed_tp"
    return "fixed_trial" if row["comment"].startswith("[sl ") else "fixed_other"


def score_offsets(rows, rates, point):
    """Include every source row; do not treat close-by reciprocal price as a quote."""
    if not len(rates):
        return []
    times = rates["time"]
    witnesses = []
    for row in rows:
        witnesses.append((stamp(row["open_time"]), float(row["open_price"]), row["trade_type"] == "buy"))
        if not row["comment"].startswith("#"):
            witnesses.append((stamp(row["close_time"]), float(row["close_price"]), row["trade_type"] == "sell"))
    source_time, prices, uses_ask = (np.array(x) for x in zip(*witnesses))
    result = []
    for offset in range(-8, 4):
        minute = np.floor((source_time + offset * 3600) / 60).astype(np.int64) * 60
        index = np.searchsorted(times, minute)
        safe = np.minimum(index, len(times) - 1)
        covered = (index < len(times)) & (times[safe] == minute)
        r = rates[safe]
        low, high = r["low"], r["high"]
        distance = np.maximum(np.maximum(low - prices, prices - high), 0)
        adjusted_prices = prices - np.where(uses_ask, r["spread"] * point, 0)
        adjusted_distance = np.maximum(np.maximum(low - adjusted_prices, adjusted_prices - high), 0)
        result.append({
            "raw_to_query_hours": offset, "source_rows": len(rows),
            "witnesses": len(witnesses), "covered_witnesses": int(covered.sum()),
            "bid_range_containment_count": int(((distance <= 1e-6) & covered).sum()),
            "spread_adjusted_containment_count": int(((adjusted_distance <= 1e-6) & covered).sum()),
            "bid_range_containment_pct_all": round(float(((distance <= 1e-6) & covered).mean() * 100), 6),
            "spread_adjusted_containment_pct_all": round(float(((adjusted_distance <= 1e-6) & covered).mean() * 100), 6),
            "median_adjusted_distance_covered": float(np.median(adjusted_distance[covered])) if covered.any() else None,
        })
    return result


def select_witnesses(rows):
    result = []
    for cohort in sorted({group(row) for row in rows}):
        subset = sorted((row for row in rows if group(row) == cohort), key=lambda row: row["open_time"])
        # Prespecified, chronological stratification, no selection by matching score.
        indices = set(np.linspace(0, len(subset) - 1, min(16, len(subset))).astype(int))
        indices.update(range(max(0, len(subset) - 4), len(subset)))
        for index in sorted(indices):
            row = subset[index]
            for event in ("open", "close"):
                if event == "close" and row["comment"].startswith("#"):
                    continue
                result.append((row, event))
    return result


def score_tick(row, event, ticks, offset, digits):
    second = int(stamp(row[f"{event}_time"]) + offset * 3600)
    quote_side = "ask" if (row["trade_type"] == "buy") == (event == "open") else "bid"
    expected = float(row[f"{event}_price"])
    same_second = ticks["time_msc"] // 1000 == second
    source_digits = 2 if row["symbol"] == "XAUUSD+" else 3
    precision = 0.5 * 10 ** (-source_digits)
    error = abs(ticks[quote_side] - expected)
    exact = same_second & (error < precision + 1e-9)
    return {
        "ticket": row["ticket"], "source_symbol": row["symbol"], "cohort": group(row), "event": event,
        "source_raw_time": row[f"{event}_time"], "raw_to_query_hours": offset,
        "query_second": second, "quote_side": quote_side, "source_price": expected,
        "source_digits": source_digits, "feed_digits": digits,
        "ticks_in_saved_window": len(ticks), "ticks_same_reported_second": int(same_second.sum()),
        "exact_price_ticks_same_second": int(exact.sum()),
        "min_abs_error_same_second": float(error[same_second].min()) if same_second.any() else None,
        "min_abs_error_window": float(error.min()) if len(error) else None,
        "quote_match_does_not_prove_execution_or_causal_trigger": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="vantage_initial")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    target = ROOT / "data" / args.tag
    target.mkdir(exist_ok=False)
    source = ROOT / "data/orders_35462.jsonl"
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    lower = min(stamp(row["open_time"]) for row in rows)
    upper = max(stamp(row["close_time"]) for row in rows)
    start = datetime.fromtimestamp(lower, UTC) - timedelta(days=5, hours=8)
    end = datetime.fromtimestamp(upper, UTC) + timedelta(hours=4)
    report = {
        "created_utc": datetime.now(UTC).isoformat(), "script_sha256": sha(Path(__file__)),
        "guard_sha256": sha(ROOT / "vantage_readonly.py"), "source_sha256": sha(source),
        "source_rows": len(rows), "query_start_utc": start.isoformat(), "query_end_utc": end.isoformat(),
        "raw_timestamps_preserved": True, "source_feed_identity_verified": False,
        "interpretation": "Alignment/provenance diagnostics only, no strategy success claim",
        "account": {}, "feeds": {},
    }
    with attach() as reader:
        report["account"] = reader.verify()
        names = reader.symbols()
        report["source_symbol_available"] = {symbol: symbol in names for symbol in ("XAUUSD+", "FixedVol20")}
        for feed, source_symbol in FEEDS.items():
            selected = [row for row in rows if row["symbol"] == source_symbol]
            specs = reader.specs(feed)
            rates = reader.rates_m1(feed, start, end)
            rate_path = target / f"{feed}_m1_raw.npz"
            np.savez_compressed(rate_path, rates=rates)
            scores = score_offsets(selected, rates, specs["point"])
            if not scores:
                raise RuntimeError(f"No M1 history for {feed}; raw query metadata is retained")
            best = max(scores, key=lambda x: x["spread_adjusted_containment_count"])
            offset = best["raw_to_query_hours"]
            record = {
                "source_symbol": source_symbol, "specs": specs, "m1_rows": len(rates),
                "raw_m1_sha256": sha(rate_path), "m1_first_raw_epoch": int(rates["time"][0]),
                "m1_last_raw_epoch": int(rates["time"][-1]),
                "offset_scores": scores, "best_diagnostic_raw_to_query_hours": offset,
                "cohort_offset_scores": {cohort: score_offsets([row for row in selected if group(row) == cohort], rates, specs["point"])
                                         for cohort in sorted({group(row) for row in selected})},
                "tick_witnesses": [],
            }
            for row, event in select_witnesses(selected):
                second = stamp(row[f"{event}_time"]) + offset * 3600
                tick_start = datetime.fromtimestamp(second - 2, UTC)
                tick_end = datetime.fromtimestamp(second + 3, UTC)
                ticks = reader.ticks(feed, tick_start, tick_end)
                tick_path = target / f"{feed}_{row['ticket']}_{event}_raw.npz"
                np.savez_compressed(tick_path, ticks=ticks)
                witness = score_tick(row, event, ticks, offset, specs["digits"])
                witness.update({"raw_ticks_file": tick_path.name, "raw_ticks_sha256": sha(tick_path),
                                "query_start_utc": tick_start.isoformat(), "query_end_utc": tick_end.isoformat()})
                record["tick_witnesses"].append(witness)
            report["feeds"][feed] = record
            write_json(target / f"{feed}_probe.json", record)
            print(json.dumps({"feed": feed, "m1_rows": len(rates), "best_offset": offset,
                              "best_score": best, "tick_witnesses": len(record["tick_witnesses"]),
                              "exact_same_second_witnesses": sum(x["exact_price_ticks_same_second"] > 0 for x in record["tick_witnesses"])}, ensure_ascii=False), flush=True)
    write_json(target / "report.json", report)
    print(f"Saved {target}", flush=True)


if __name__ == "__main__":
    main()
