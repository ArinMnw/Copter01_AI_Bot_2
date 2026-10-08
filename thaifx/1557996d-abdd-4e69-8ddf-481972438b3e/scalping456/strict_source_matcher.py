"""One-to-one exact multiset matching at source precision; no timing tolerance.

Predictions must already contain pips/gross P&L/close behavior. This scorer
never copies outcomes from the source to a prediction. Unknown source behavior
is not certified by assigning an invented manual/EA label.
"""

from collections import defaultdict, deque
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime


def decimal(value, quantum=None):
    result = Decimal(str(value))
    return result.quantize(Decimal(quantum), rounding=ROUND_HALF_UP) if quantum else result


def source_behavior(row):
    comment = row["comment"]
    if comment.startswith("[sl "):
        return "sl"
    if comment.startswith("[tp "):
        return "tp"
    if comment.startswith("#"):
        return "close_by"
    return "unverified_source_behavior"


def key(row):
    price_unit = ".01" if row["symbol"] == "XAUUSD+" else ".001"
    pip_unit = "1" if row["symbol"] == "XAUUSD+" else ".1"
    return (row["symbol"], row["side"], decimal(row["volume"]), row["open_second"], row["close_second"],
            decimal(row["open_price"], price_unit),
            decimal(row["close_price"], price_unit) if row["close_price"] is not None else None,
            decimal(row["pips"], pip_unit) if row["pips"] is not None else None,
            decimal(row["gross_profit"], ".01") if row["gross_profit"] is not None else None,
            row["close_behavior"])


def source_record(row):
    return {"symbol": row["symbol"], "side": row["trade_type"], "volume": row["volume"],
            "open_second": int(datetime.fromisoformat(row["open_time"]).timestamp()) - 10800,
            "close_second": int(datetime.fromisoformat(row["close_time"]).timestamp()) - 10800,
            "open_price": row["open_price"], "close_price": row["close_price"],
            "pips": row["pips"], "gross_profit": row["profit"], "close_behavior": source_behavior(row)}


def enrich_prediction(row, symbol, close_behavior):
    price_unit = ".01" if symbol == "XAUUSD+" else ".001"
    opening = decimal(row["open_price"], price_unit)
    closing = decimal(row["close_price"], price_unit) if row["close_price"] is not None else None
    delta = (closing - opening) * (1 if row["side"] == "buy" else -1) if closing is not None else None
    return {**row, "symbol": symbol, "open_second": row["open_ms"] // 1000,
            "close_second": row["close_ms"] // 1000 if row["close_ms"] is not None else None,
            "open_price": str(opening), "close_price": str(closing) if closing is not None else None,
            "pips": str(delta * 100) if delta is not None else None,
            "gross_profit": str((delta * decimal(row["volume"]) * (100 if symbol == "XAUUSD+" else 1)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)) if delta is not None else None,
            "close_behavior": close_behavior if closing is not None else "still_open"}


def match_exact(source, predictions):
    buckets = defaultdict(deque)
    for index, predicted in enumerate(predictions):
        buckets[key(predicted)].append(index)
    matches = []
    used = set()
    unknown = 0
    for row in source:
        record = source_record(row)
        if record["close_behavior"] == "unverified_source_behavior":
            unknown += 1
            index = None
        else:
            candidates = buckets[key(record)]
            index = candidates.popleft() if candidates else None
        if index is not None:
            used.add(index)
        matches.append({"ticket": row["ticket"], "symbol": row["symbol"],
                        "exact_prediction_index": index, "exact_all_observable_fields": index is not None,
                        "source_close_behavior_verified": record["close_behavior"] != "unverified_source_behavior"})
    matched = len(used)
    extra = [index for index in range(len(predictions)) if index not in used]
    return matches, extra, {"source_orders": len(source), "predicted_orders": len(predictions),
                           "exact_all_observable_fields": matched, "missing": len(source) - matched,
                           "extra": len(extra), "unknown_source_close_behavior": unknown,
                           "timing_tolerance_seconds": 0, "source_field_precision_only": True,
                           "complete": matched == len(source) and not extra and unknown == 0}
