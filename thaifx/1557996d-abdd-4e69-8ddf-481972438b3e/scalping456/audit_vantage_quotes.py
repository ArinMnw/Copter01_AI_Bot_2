"""Full-source feed/coverage audit; not a predictive model or a success scorer.

Every source order remains represented, including non-market close-by prices.
Near-time quotes are reported separately and never substituted for exact seconds.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from probe_vantage_feed import ROOT, group, sha, stamp, write_json


def event_witness(row, event):
    return {
        "ticket": row["ticket"], "source_symbol": row["symbol"], "cohort": group(row),
        "event": event, "source_raw_time": row[f"{event}_time"],
        "source_price": row[f"{event}_price"],
        "inferred_canonical_ms": round((stamp(row[f"{event}_time"]) - 10800) * 1000),
        "quote_side": "ask" if (row["trade_type"] == "buy") == (event == "open") else "bid",
        "market_quote_witness_applicable": not (event == "close" and row["comment"].startswith("#")),
    }


def compare_event(event, times, bids, asks):
    result = dict(event)
    price = float(event["source_price"])
    digits = 2 if event["source_symbol"] == "XAUUSD+" else 3
    # Half a unit at original price precision, not a strategy fitting tolerance.
    precision = .5 * 10 ** (-digits)
    quotes = asks if event["quote_side"] == "ask" else bids
    instant = event["inferred_canonical_ms"]
    for label, lower, upper in (("same_second", instant, instant + 1000),
                                ("window_minus2_plus3_seconds", instant - 2000, instant + 3000)):
        lo, hi = np.searchsorted(times, (lower, upper), side="left")
        selected = quotes[lo:hi]
        errors = selected - price
        closest = int(np.argmin(abs(errors))) if len(errors) else None
        result[label] = {
            "ticks": len(selected), "exact_price_ticks": int((abs(errors) < precision + 1e-9).sum()),
            "min_abs_price_error": float(abs(errors[closest])) if closest is not None else None,
            "nearest_quote_minus_source_price": float(errors[closest]) if closest is not None else None,
            "nearest_quote_canonical_ms": int(times[lo + closest]) if closest is not None else None,
        }
    return result


def load_day(path, expected_symbol):
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    raw = Path(meta["raw_file"])
    if meta["symbol"] != expected_symbol or meta["query_shift_ms"] != 10800000:
        raise RuntimeError("Wrong feed/time normalization " + str(path))
    if sha(path) != meta["sha256"] or sha(raw) != meta["raw_sha256"]:
        raise RuntimeError("Cache hash mismatch " + str(path))
    with np.load(path) as archive:
        return {key: archive[key] for key in ("time_msc", "bid", "ask")}, meta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="vantage_full_quotes_20261008")
    args = parser.parse_args()
    if not args.tag.replace("_", "").replace("-", "").isalnum():
        parser.error("Invalid tag")
    source = ROOT / "data/orders_35462.jsonl"
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    target = ROOT / "data" / args.tag
    target.mkdir(exist_ok=False)
    result_path = target / "all_source_events.jsonl"
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_orders": len(rows),
              "source_sha256": sha(source), "script_sha256": sha(__file__), "counts": {},
              "cache_provenance": [], "data_gaps": [], "source_feed_identity_verified": False,
              "full_source_clone_complete": False, "not_strategy_accuracy": True,
              "clock_inference": "source raw -3h; measured independently on new Vantage live anchors and offset witnesses"}
    events_by_day = defaultdict(list)
    for row in rows:
        for event in ("open", "close"):
            witness = event_witness(row, event)
            day = datetime.fromtimestamp(witness["inferred_canonical_ms"] / 1000, timezone.utc).strftime("%Y-%m-%d")
            events_by_day[(row["symbol"], day)].append(witness)
    stats = defaultdict(Counter)
    # Validate the complete requested export before analysis; partial downloads
    # cannot be silently called a complete full-source feed audit.
    caches = {"XAUUSD+": ("vantage_gold_shift3", "XAUUSD"), "FixedVol20": ("vantage_fixed_shift3", "FixedVol20")}
    for _, (tag, _) in caches.items():
        manifest = json.loads((ROOT / "data" / f"vantage_raw_ticks_{tag}" / "manifest.json").read_text(encoding="utf-8"))
        day = datetime.fromisoformat(manifest["start_inferred"]).date()
        end = (datetime.fromisoformat(manifest["end_inferred"]) - timedelta(microseconds=1)).date()
        while day <= end:
            if not (ROOT / "data" / f"proxy_ticks_{tag}" / f"{day}.json").exists():
                raise RuntimeError("Export not complete: " + str(day))
            day += timedelta(days=1)
    with result_path.open("x", encoding="utf-8", newline="\n") as output:
        for source_symbol, (tag, feed) in caches.items():
            cache = ROOT / "data" / f"proxy_ticks_{tag}"
            total = 0
            prior_last = None
            for path in sorted(cache.glob("*.npz")):
                arrays, meta = load_day(path, feed)
                total += len(arrays["time_msc"])
                report["cache_provenance"].append({"file": str(path), **meta})
                t = arrays["time_msc"]
                if len(t):
                    if prior_last is not None and t[0] - prior_last > 60000:
                        report["data_gaps"].append({"source_symbol": source_symbol, "start_ms": int(prior_last), "end_ms": int(t[0]), "gap_ms": int(t[0] - prior_last)})
                    gaps = np.diff(t)
                    for index in np.flatnonzero(gaps > 60000):
                        report["data_gaps"].append({"source_symbol": source_symbol, "start_ms": int(t[index]), "end_ms": int(t[index + 1]), "gap_ms": int(gaps[index])})
                    prior_last = t[-1]
                events = events_by_day[(source_symbol, path.stem)]
                if not events:
                    continue
                # At midnight, load neighbouring dates too for the labelled ±window.
                pieces = [arrays]
                day = datetime.fromisoformat(path.stem)
                for delta in (-1, 1):
                    nearby = cache / f"{(day + timedelta(days=delta)):%Y-%m-%d}.npz"
                    if nearby.exists():
                        other, _ = load_day(nearby, feed)
                        pieces.append(other)
                times = np.concatenate([p["time_msc"] for p in pieces])
                order = np.argsort(times, kind="stable")
                times = times[order]
                bids = np.concatenate([p["bid"] for p in pieces])[order]
                asks = np.concatenate([p["ask"] for p in pieces])[order]
                for event in sorted(events, key=lambda x: (x["inferred_canonical_ms"], x["ticket"], x["event"])):
                    compared = compare_event(event, times, bids, asks)
                    output.write(json.dumps(compared, ensure_ascii=False, allow_nan=False) + "\n")
                    key = source_symbol + "/" + event["cohort"] + "/" + event["event"]
                    stats[key]["source_events"] += 1
                    if not event["market_quote_witness_applicable"]:
                        stats[key]["close_by_non_market_prices"] += 1
                        continue
                    stats[key]["applicable_quote_events"] += 1
                    for label in ("same_second", "window_minus2_plus3_seconds"):
                        stats[key][label + "_covered"] += compared[label]["ticks"] > 0
                        stats[key][label + "_exact_price"] += compared[label]["exact_price_ticks"] > 0
                print(json.dumps({"symbol": source_symbol, "day": path.stem, "events": len(events)}), flush=True)
            report.setdefault("tick_totals", {})[source_symbol] = total
    report["counts"] = {key: dict(value) for key, value in stats.items()}
    report["source_events_written"] = sum(x["source_events"] for x in stats.values())
    if report["source_events_written"] != len(rows) * 2:
        raise RuntimeError("Not all source events were represented")
    report["all_source_events_sha256"] = sha(result_path)
    write_json(target / "report.json", report)
    print(json.dumps({"source_events": report["source_events_written"], "tick_totals": report["tick_totals"], "counts": report["counts"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
