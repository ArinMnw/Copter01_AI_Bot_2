"""Independent QA of a decoded replay folder (no reuse of strict_source_matcher.match_exact).

Recomputes the exact multiset match from predictions.jsonl and the raw ledger
with a separate key builder, then cross-checks report counts, artifact hashes,
source population and that every exact match really equals the source row.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from decoded_common import ROOT, SOURCE_SHA256
from probe_vantage_feed import sha


def q(value, unit):
    return Decimal(str(value)).quantize(Decimal(unit), rounding=ROUND_HALF_UP)


def source_key(row):
    xau = row["symbol"] == "XAUUSD+"
    comment = row["comment"]
    behavior = "sl" if comment.startswith("[sl ") else "tp" if comment.startswith("[tp ") else "close_by" if comment.startswith("#") else None
    if behavior is None:
        return None
    seconds = lambda text: int(datetime.fromisoformat(text).timestamp()) - 10800
    return (row["symbol"], row["trade_type"], Decimal(str(row["volume"])), seconds(row["open_time"]), seconds(row["close_time"]),
            q(row["open_price"], ".01" if xau else ".001"), q(row["close_price"], ".01" if xau else ".001"),
            q(row["pips"], "1" if xau else ".1"), q(row["profit"], ".01"), behavior)


def prediction_key(row):
    if row["close_ms"] is None:
        return None
    xau = row["symbol"] == "XAUUSD+"
    unit = ".01" if xau else ".001"
    opening, closing = q(row["open_price"], unit), q(row["close_price"], unit)
    delta = (closing - opening) * (1 if row["side"] == "buy" else -1)
    gross = (delta * Decimal(str(row["volume"])) * (100 if xau else 1)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    return (row["symbol"], row["side"], Decimal(str(row["volume"])), row["open_ms"] // 1000, row["close_ms"] // 1000,
            opening, closing, (delta * 100).quantize(Decimal("1" if xau else ".1"), rounding=ROUND_HALF_UP), gross, row["close_behavior"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    folder = ROOT / "data" / args.tag
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    source_path = ROOT / "data/orders_35462.jsonl"
    assert sha(source_path) == SOURCE_SHA256 == report["source_sha256"]
    source = [json.loads(line, parse_float=Decimal) for line in source_path.read_text(encoding="utf-8").splitlines()]
    assert len(source) == len({r["ticket"] for r in source}) == 35462
    for name, digest in report["artifact_sha256"].items():
        assert sha(folder / name) == digest, name
    predictions = [json.loads(line) for line in (folder / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    start = min(round(datetime.fromisoformat(r["open_time"]).timestamp() * 1000) - 10_800_000 for r in source)
    end = max(round(datetime.fromisoformat(r["close_time"]).timestamp() * 1000) - 10_800_000 for r in source) + 1000
    kept = [p for p in predictions if p["open_ms"] < end and (p["close_ms"] is None or p["close_ms"] >= start)]
    assert len(kept) == report["predictions_in_source_window"]
    pool = Counter(k for k in map(prediction_key, kept) if k is not None)
    exact = defaultdict(int)
    matched_rows = 0
    results = {json.loads(l)["ticket"]: json.loads(l) for l in (folder / "all_source_results.jsonl").read_text(encoding="utf-8").splitlines()}
    assert len(results) == 35462
    for row in source:
        key = source_key(row)
        hit = key is not None and pool[key] > 0
        if hit:
            pool[key] -= 1
            matched_rows += 1
        # the saved per-order flag must agree with the independent recomputation
        assert results[row["ticket"]]["exact_all_observable_fields"] == hit, row["ticket"]
        exact[row["symbol"]] += hit
    still_open = sum(1 for p in kept if p["close_ms"] is None)
    extras = len(kept) - matched_rows
    assert matched_rows == report["exact_all_observable_fields"], (matched_rows, report["exact_all_observable_fields"])
    assert extras == report["extra"], (extras, report["extra"])
    assert report["missing"] == 35462 - matched_rows
    unknown = sum(1 for r in source if source_key(r) is None)
    assert unknown == report["unknown_source_close_behavior"]
    assert not report["complete"]
    out = {"verified": True, "tag": args.tag, "exact": matched_rows, "missing": 35462 - matched_rows, "extra": extras,
           "exact_by_symbol": dict(exact), "still_open_predictions": still_open, "unknown_source_close_behavior": unknown}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
