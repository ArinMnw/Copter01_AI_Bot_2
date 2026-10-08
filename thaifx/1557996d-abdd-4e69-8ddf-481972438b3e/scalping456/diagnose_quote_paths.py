"""All-order analytic quote-path constraints, NEVER source-seeded predictions.

No strategy instance, orders, entry/exit actions or parameter fitting. Source
times bound observations for forensics only; every row remains represented.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal

import numpy as np

from probe_vantage_feed import ROOT, group, sha, stamp, write_json
from replay_vantage_candle_grid import load_ticks


class QuoteIndex:
    """Block extrema and first-crossing queries without an N log N table."""

    def __init__(self, quotes, block=1024):
        self.quotes = np.asarray(quotes)
        if self.quotes.ndim != 1 or not isinstance(block, int) or block <= 0:
            raise ValueError("Expected one-dimensional quotes and a positive block size")
        self.block = block
        starts = np.arange(0, len(quotes), block)
        self.minimum = np.minimum.reduceat(self.quotes, starts) if len(quotes) else np.array([])
        self.maximum = np.maximum.reduceat(self.quotes, starts) if len(quotes) else np.array([])

    def first_crossing(self, lo, hi, level, upper=False, strict=False):
        if lo < 0 or hi < 0 or lo > len(self.quotes) or hi > len(self.quotes):
            raise ValueError("Quote interval outside the array")
        if hi <= lo:
            return None
        def mask(values):
            if upper:
                return values > level + 1e-9 if strict else values >= level - 1e-9
            return values < level - 1e-9 if strict else values <= level + 1e-9
        cursor = lo
        boundary = min(hi, ((lo // self.block) + 1) * self.block)
        hits = np.flatnonzero(mask(self.quotes[cursor:boundary]))
        if len(hits):
            return cursor + int(hits[0])
        cursor = boundary
        end_blocks = hi // self.block
        if cursor // self.block < end_blocks:
            start_block = cursor // self.block
            extrema = self.maximum if upper else self.minimum
            blocks = np.flatnonzero(mask(extrema[start_block:end_blocks]))
            if len(blocks):
                at = (start_block + int(blocks[0])) * self.block
                hit = np.flatnonzero(mask(self.quotes[at:at + self.block]))[0]
                return at + int(hit)
            cursor = end_blocks * self.block
        hits = np.flatnonzero(mask(self.quotes[cursor:hi]))
        return cursor + int(hits[0]) if len(hits) else None


def analytic_barrier(gain, initial_stop, activation, distance):
    """First violation of a past-extrema barrier, not a simulated exit/fill."""
    if not len(gain):
        return None, None
    best = np.maximum.accumulate(gain)
    prior_best = np.concatenate(([-np.inf], best[:-1]))
    level = np.maximum(-initial_stop, np.where(prior_best >= activation - 1e-9, prior_best - distance, -initial_stop))
    hits = np.flatnonzero(gain <= level + 1e-9)
    if not len(hits):
        return None, None
    first = int(hits[0])
    return first, float(level[first])


def describe(values):
    if not values:
        return {"count": 0}
    values = np.array(values, dtype=float)
    return {"count": len(values), "min": float(values.min()), "max": float(values.max()),
            **{name: float(np.percentile(values, p)) for name, p in (("p10", 10), ("p25", 25), ("median", 50), ("p75", 75), ("p90", 90))}}


def path_record(row, times, bids, asks, bid_index, ask_index, gaps):
    opening = round((stamp(row["open_time"]) - 10800) * 1000)
    closing = round((stamp(row["close_time"]) - 10800) * 1000)
    lo, hi = np.searchsorted(times, (opening + 1000, closing), side="left")
    buy = row["trade_type"] == "buy"
    sign = 1 if buy else -1
    quotes = bids if buy else asks
    index = bid_index if buy else ask_index
    entry = float(row["open_price"])
    gain = sign * (quotes[lo:hi] - entry)
    record = {"ticket": row["ticket"], "symbol": row["symbol"], "cohort": group(row),
              "source_open_raw": row["open_time"], "source_close_raw": row["close_time"],
              "source_volume": str(row["volume"]), "source_pips": str(row["pips"]),
              "source_comment": row["comment"], "holding_seconds": (closing - opening) / 1000,
              "interior_start_inferred_ms": opening + 1000, "interior_end_exclusive_inferred_ms": closing,
              "interior_quotes": len(gain), "quote_side": "bid" if buy else "ask",
              "gaps_over60s_intersecting_interior": sum(g["start_ms"] < closing and g["end_ms"] > opening + 1000 for g in gaps),
              "mfe_price_observed": float(gain.max()) if len(gain) else None,
              "mae_price_observed": float(gain.min()) if len(gain) else None,
              "implied_peak_minus_close_price_observed": float(gain.max() - sign * (float(row["close_price"]) - entry)) if len(gain) else None,
              "source_feed_identity_verified": False, "not_a_prediction_or_goal_success_metric": True,
              "initial_stop_benchmark": None, "ratchet_barrier_benchmark": None,
              "final_reported_tp_witness": None}
    nominal = 1 if row["symbol"] == "XAUUSD+" else 10 if group(row) == "fixed_trial" else None
    if nominal is not None:
        hits = {}
        for label, margin in (("strict_beyond_nominal", 0), ("strict_beyond_nominal_plus10pct", nominal * .1)):
            level = entry - sign * (nominal + margin)
            at = index.first_crossing(lo, hi, level, upper=not buy, strict=True)
            hits[label] = {"first_inferred_ms": int(times[at]) if at is not None else None,
                           "lead_before_reported_close_seconds": (closing - int(times[at])) / 1000 if at is not None else None,
                           "at_least5s_early": at is not None and closing - int(times[at]) >= 5000}
        record["initial_stop_benchmark"] = {"distance_price": nominal, **hits}
        activation, distance = (.4, .3) if row["symbol"] == "XAUUSD+" else (0, 10)
        at, level = analytic_barrier(gain, nominal, activation, distance)
        record["ratchet_barrier_benchmark"] = {
            "activation_price": activation, "distance_price": distance,
            "first_violation_inferred_ms": int(times[lo + at]) if at is not None else None,
            "gain_barrier_price": level,
            "at_least5s_before_reported_close": at is not None and closing - int(times[lo + at]) >= 5000,
            "not_a_source_seeded_exit_signal": True}
    if group(row) == "fixed_tp":
        target = float(row["tp"])
        at = index.first_crossing(lo, hi, target, upper=buy)
        record["final_reported_tp_witness"] = {
            "target_price": target, "first_crossing_inferred_ms": int(times[at]) if at is not None else None,
            "lead_before_reported_close_seconds": (closing - int(times[at])) / 1000 if at is not None else None,
            "final_target_not_proven_to_exist_at_entry": True}
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid snapshot tag")
    target = ROOT / "data" / args.tag
    target.mkdir(exist_ok=False)
    source_path = ROOT / "data/orders_35462.jsonl"
    if sha(source_path) != "b8f5f75de07ba335ba607855167b5c77600954561c7c740621a335fa1b9825f1":
        raise RuntimeError("The original source snapshot changed")
    source = [json.loads(line, parse_float=Decimal) for line in source_path.read_text(encoding="utf-8").splitlines()]
    if len(source) != 35462 or len({r["ticket"] for r in source}) != 35462:
        raise RuntimeError("Source population/uniqueness differs")
    gap_path = ROOT / "data/vantage_full_quotes_20261008/report.json"
    gaps = json.loads(gap_path.read_text(encoding="utf-8"))["data_gaps"]
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_rows": len(source),
              "source_sha256": sha(source_path), "script_sha256": sha(__file__),
              "plan_sha256": sha(ROOT / "PATH_DIAGNOSTIC_PLAN.md"), "gap_report_sha256": sha(gap_path),
              "method": "all_source_analytic_intervals_not_strategy_replay_no_source_derived_actions_no_fitting",
              "full_source_clone_complete": False, "source_feed_identity_verified": False,
              "cache_provenance": {}, "cohorts": {}, "lot_segments": {}, "xau_tail_details": []}
    counts = defaultdict(Counter)
    distances = defaultdict(list)
    with (target / "all_source_quote_paths.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for symbol, feed, tag in (("XAUUSD+", "XAUUSD", "vantage_gold_shift3"), ("FixedVol20", "FixedVol20", "vantage_fixed_shift3")):
            arrays, provenance = load_ticks(tag, feed)
            times, bids, asks = arrays
            report["cache_provenance"][symbol] = provenance
            bid_index, ask_index = QuoteIndex(bids), QuoteIndex(asks)
            rows = sorted((r for r in source if r["symbol"] == symbol), key=lambda r: (r["open_time"], r["ticket"]))
            symbol_gaps = [g for g in gaps if g["source_symbol"] == symbol]
            segments = []
            for number, row in enumerate(rows, 1):
                record = path_record(row, times, bids, asks, bid_index, ask_index, symbol_gaps)
                stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                cohort = record["cohort"]
                stat = counts[cohort]
                stat["source_rows"] += 1
                stat["with_definite_interior_quotes"] += record["interior_quotes"] > 0
                stat["with_intersecting_gaps_over60s"] += record["gaps_over60s_intersecting_interior"] > 0
                if record["initial_stop_benchmark"]:
                    for label in ("strict_beyond_nominal", "strict_beyond_nominal_plus10pct"):
                        stat[label + "_any"] += record["initial_stop_benchmark"][label]["first_inferred_ms"] is not None
                        stat[label + "_at_least5s_early"] += record["initial_stop_benchmark"][label]["at_least5s_early"]
                    stat["ratchet_barrier_at_least5s_early"] += record["ratchet_barrier_benchmark"]["at_least5s_before_reported_close"]
                if record["final_reported_tp_witness"]:
                    witness = record["final_reported_tp_witness"]
                    stat["final_tp_crossed_in_definite_interior"] += witness["first_crossing_inferred_ms"] is not None
                    stat["final_tp_crossed_at_least5s_early"] += witness["lead_before_reported_close_seconds"] is not None and witness["lead_before_reported_close_seconds"] >= 5
                if record["implied_peak_minus_close_price_observed"] is not None:
                    distances[cohort].append(record["implied_peak_minus_close_price_observed"])
                volume = str(row["volume"])
                if segments and Decimal(segments[-1]["volume"]) == row["volume"]:
                    segments[-1]["last_open_raw"] = row["open_time"]
                    segments[-1]["orders"] += 1
                else:
                    segments.append({"volume": volume, "first_open_raw": row["open_time"],
                                     "last_open_raw": row["open_time"], "orders": 1,
                                     "not_proven_EA_parameter_change": True})
                if symbol == "XAUUSD+" and float(row["pips"]) < -100 and cohort == "xau_sl":
                    report["xau_tail_details"].append(record)
                if number % 5000 == 0:
                    print(symbol, "paths", number, flush=True)
            report["lot_segments"][symbol] = segments
            print(symbol, "all paths finished", len(rows), flush=True)
            del arrays, times, bids, asks, bid_index, ask_index
    report["cohorts"] = {c: {**dict(stat), "implied_peak_minus_close_price": describe(distances[c])} for c, stat in counts.items()}
    assert sum(v["source_rows"] for v in report["cohorts"].values()) == 35462
    report["all_source_paths_sha256"] = sha(target / "all_source_quote_paths.jsonl")
    write_json(target / "report.json", report)
    print(json.dumps(report["cohorts"], indent=2), flush=True)


if __name__ == "__main__":
    main()
