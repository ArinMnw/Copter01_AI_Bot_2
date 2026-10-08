"""Fixed first-lot component boundaries, read-only cached quotes and forensics."""

import json
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np

from analyze_lot_scope import SOURCE_SHA
from diagnose_quote_paths import QuoteIndex
from probe_vantage_feed import ROOT, sha, stamp
from strategy_scalping456 import PendingStopConfig, Scalping456Config


UTC = timezone.utc
WARMUP = datetime(2026, 8, 18, 21, tzinfo=UTC)
SOURCE_START = datetime(2026, 8, 23, 22, 5, 2, tzinfo=UTC)
END = datetime(2026, 8, 31, 5, 12, 19, tzinfo=UTC)
FIRST_MS, END_MS = round(SOURCE_START.timestamp() * 1000), round(END.timestamp() * 1000)


def controls():
    for entry in ("level", "quote"):
        for stop in ("level", "quote"):
            yield PendingStopConfig(anchor_mode="fixed_close", opposite_policy="oco", entry_fill_mode=entry,
                                    require_valid_trail=True, execution=Scalping456Config(volume=.01,
                                    trailing_activation_points=16, trailing_distance_points=16, stop_fill_mode=stop))


def load_quotes(cache=None, start=WARMUP, end=END):
    cache = Path(cache) if cache is not None else ROOT / "data/proxy_ticks_vantage_gold_shift3"
    if start.utcoffset() is None or end.utcoffset() is None or end <= start:
        raise ValueError("Aware increasing cache bounds required")
    day = start.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    parts, provenance = ([], [], []), []
    while day < end:
        path = cache / f"{day:%Y-%m-%d}.npz"
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        if sha(path) != meta["sha256"] or meta["symbol"] != "XAUUSD" or meta["query_shift_ms"] != 10800000 or meta["invalid_quotes"]:
            raise ValueError("Wrong quote provenance/hash/clock/validity")
        with np.load(path) as archive:
            times, bids, asks = (archive[name] for name in ("time_msc", "bid", "ask"))
            if len(times) != meta["ticks"] or len(times) != len(bids) or len(times) != len(asks):
                raise ValueError("Wrong quote counts")
            keep = (times >= round(start.timestamp() * 1000)) & (times < round(end.timestamp() * 1000))
            for target, values in zip(parts, (times, bids, asks)):
                target.append(values[keep])
        provenance.append({**meta, "consumed_ticks": int(keep.sum())})
        day += timedelta(days=1)
    arrays = tuple(np.concatenate(values) for values in parts)
    times, bids, asks = arrays
    if np.any(np.diff(times) < 0) or np.any(~np.isfinite(bids)) or np.any(~np.isfinite(asks)) or np.any(bids <= 0) or np.any(asks < bids):
        raise ValueError("Invalid chronological executable quotes")
    return arrays, provenance


def load_source_scope():
    path = ROOT / "data/orders_35462.jsonl"
    if sha(path) != SOURCE_SHA:
        raise ValueError("Original ledger changed")
    source = [json.loads(line, parse_float=Decimal) for line in path.read_text(encoding="utf-8").splitlines()]
    gold = sorted((r for r in source if r["symbol"] == "XAUUSD+"), key=lambda r: (r["open_time"], r["ticket"]))
    scope = []
    for r in gold:
        if Decimal(str(r["volume"])) != Decimal(".01"):
            break
        scope.append(r)
    assert len(source) == len({r["ticket"] for r in source}) == 35462
    assert len(scope) == len({r["ticket"] for r in scope}) == 7312
    assert round((min(stamp(r["open_time"]) for r in scope) - 10800) * 1000) == FIRST_MS
    assert round((max(stamp(r["close_time"]) for r in scope) - 10800 + 1) * 1000) == END_MS
    return source, scope


def entry_record(row, times, bids, asks, closes, close_times, indices):
    opening = round((stamp(row["open_time"]) - 10800) * 1000)
    entry, buy = float(row["open_price"]), row["trade_type"] == "buy"
    sign = 1 if buy else -1
    lo, hi = (int(x) for x in np.searchsorted(times, (opening, opening + 1000)))
    before = lo - 1
    record = {"ticket": row["ticket"], "source_side": row["trade_type"], "source_open_price": str(row["open_price"]),
              "source_open_raw": row["open_time"], "source_volume": str(row["volume"]),
              "opening_second_quote_count": hi - lo, "quote_side_executable": "ask" if buy else "bid",
              "source_price_seen_on_bid_in_reported_second": bool(np.any(np.isclose(bids[lo:hi], entry, atol=1e-6, rtol=0))),
              "source_price_seen_on_ask_in_reported_second": bool(np.any(np.isclose(asks[lo:hi], entry, atol=1e-6, rtol=0))),
              "source_price_seen_on_executable_side_in_reported_second": bool(np.any(np.isclose((asks if buy else bids)[lo:hi], entry, atol=1e-6, rtol=0))),
              "past_quote": None, "first_quote_of_reported_second": None, "past_signed_returns": {},
              "latest_strict_source_predecessor": None, "nominal_price1_cross_before_entry": None,
              "not_strategy_prediction": True, "source_feed_identity_verified": False}
    if before >= 0:
        record["past_quote"] = {"time_ms": int(times[before]), "bid": float(bids[before]), "ask": float(asks[before]),
                                "age_before_open_second_ms": opening - int(times[before]), "spread": float(asks[before] - bids[before])}
        current = asks[before] if buy else bids[before]
        for lookback in (1, 5, 10):
            at = int(np.searchsorted(times, opening - lookback * 1000, side="left")) - 1
            record["past_signed_returns"][str(lookback)] = float(sign * (current - (asks[at] if buy else bids[at]))) if at >= 0 else None
    if lo < hi:
        record["first_quote_of_reported_second"] = {"time_ms": int(times[lo]), "bid": float(bids[lo]), "ask": float(asks[lo]),
            "source_minus_executable_price": float(entry - (asks[lo] if buy else bids[lo]))}
    previous = bisect_left(close_times, opening) - 1
    if previous >= 0:
        closing = close_times[previous]
        anchors = sorted({Decimal(str(r["close_price"])) for r in closes[closing]})
        displacements = [sign * (Decimal(str(row["open_price"])) - price) for price in anchors]
        record["latest_strict_source_predecessor"] = {"close_ms": closing, "closed_rows": len(closes[closing]),
            "distinct_prices": [str(v) for v in anchors], "price_ambiguous": len(anchors) != 1,
            "signed_displacement_prices": [str(v) for v in displacements], "seconds_to_entry": (opening - closing) / 1000}
        if len(anchors) == 1:
            a, b = (int(v) for v in np.searchsorted(times, (closing + 1000, opening)))
            level = float(anchors[0]) + sign
            index = indices[1] if buy else indices[0]
            hit = index.first_crossing(a, b, level, upper=buy)
            record["nominal_price1_cross_before_entry"] = {"level": level, "first_cross_ms": int(times[hit]) if hit is not None else None,
                "lead_before_open_second_seconds": (opening - int(times[hit])) / 1000 if hit is not None else None,
                "conditional_actual_predecessor_NOT_causal_prediction": True}
    return record


def predecessor_index(scope):
    closes = defaultdict(list)
    for r in scope:
        closes[round((stamp(r["close_time"]) - 10800) * 1000)].append(r)
    return closes, sorted(closes)
