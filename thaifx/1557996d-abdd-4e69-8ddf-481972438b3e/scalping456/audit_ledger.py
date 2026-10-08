"""Reconcile every source order and audit predecessors without dropping exits.

The CSV output is an analysis intermediate, not a claim of strategy fidelity.
UTC normalization follows the documented, inferred source-clock offset.
No entry is declared reproduced from a direction-only or post-hoc check.
"""

from __future__ import annotations

import csv
import hashlib
import heapq
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
NUMERIC_FIELDS = {"volume", "profit", "open_price", "close_price", "pips", "sl", "tp"}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def dt(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError(f"Missing timezone: {value}")
    return result


def category(row: dict) -> str:
    comment = str(row.get("comment") or "")
    if row["symbol"] == "XAUUSD+":
        return "xau_sl_core" if comment.startswith("[sl ") else "xau_other_exit"
    if row["symbol"] == "FixedVol20":
        if comment.startswith("[tp "):
            return "fixedvol_tp_basket"
        if comment.startswith("[sl "):
            return "fixedvol_sl_trial"
        return "fixedvol_other_exit"
    return "unclassified_symbol"


def distribution(values: list[float]) -> dict:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0}
    result = {"count": len(ordered)}
    for label, fraction in (("p10", .1), ("p25", .25), ("median", .5), ("p75", .75), ("p90", .9)):
        index = (len(ordered) - 1) * fraction
        lower = int(index)
        upper = min(lower + 1, len(ordered) - 1)
        value = ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)
        result[label] = round(value, 6)
    return result


def displacement(row: dict, previous: dict | None) -> dict:
    if previous is None:
        return {"ticket": "", "gap_sec": "", "move_points": "", "direction_match": ""}
    movement = (Decimal(row["open_price"]) - Decimal(previous["close_price"])) * 100
    expected = 1 if row["trade_type"] == "buy" else -1
    sign = (movement > 0) - (movement < 0)
    return {
        "ticket": previous["ticket"],
        "gap_sec": (row["_open"] - previous["_close"]).total_seconds(),
        "move_points": float(movement),
        "direction_match": sign == expected,
    }


def build_audit(rows: list[dict]) -> list[dict]:
    """Half-open positions; close/open ties are explicitly ambiguous.

    Only rows already opened can contribute a completed predecessor. A final
    ledger is required for this diagnostic; the strategy never reads it.
    """
    by_symbol = defaultdict(list)
    for original in rows:
        row = dict(original)
        row["_open"] = dt(row["actual_open_utc"])
        row["_close"] = dt(row["actual_close_utc"])
        by_symbol[row["symbol"]].append(row)
    output = []
    for symbol_rows in by_symbol.values():
        symbol_rows.sort(key=lambda row: (row["_open"], int(row["ticket"])))
        active = []
        previous = None
        previous_core = None
        latest_closed = None
        previous_open_time = None
        for row in symbol_rows:
            close_tie = False
            while active and active[0][0] <= row["_open"]:
                close_time, _, completed = heapq.heappop(active)
                close_tie |= close_time == row["_open"]
                latest_closed = completed
            current_category = category(row)
            adjacent = displacement(row, previous)
            completed = displacement(row, latest_closed)
            core_only = displacement(row, previous_core)
            item = {
                "id": row["id"], "ticket": row["ticket"], "symbol": row["symbol"],
                "category": current_category, "side": row["trade_type"],
                "volume": row["volume"], "profit": row["profit"], "pips": row["pips"],
                "open_utc_inferred": row["actual_open_utc"],
                "close_utc_inferred": row["actual_close_utc"],
                "web_open_display_derived": row.get("web_open_display_derived", ""),
                "web_close_display_derived": row.get("web_close_display_derived", ""),
                "open_price": row["open_price"], "close_price": row["close_price"],
                "comment": row["comment"],
                "duration_sec": (row["_close"] - row["_open"]).total_seconds(),
                "active_same_symbol_before_open": len(active),
                "close_open_second_tie": close_tie,
                "same_open_second_as_previous": row["_open"] == previous_open_time,
                "previous_opened_category": category(previous) if previous else "",
                "previous_opened_side": previous["trade_type"] if previous else "",
                "previous_completed_category": category(latest_closed) if latest_closed else "",
                "predecessor_changed_by_including_other_exits": bool(
                    current_category == "xau_sl_core" and previous and previous_core
                    and previous["ticket"] != previous_core["ticket"]
                ),
                "full_causal_clone_verified": False,
                "source_tick_validation": "source_feed_unavailable",
            }
            for prefix, values in (("previous_opened", adjacent), ("previous_completed", completed), ("previous_core_only", core_only)):
                for name, value in values.items():
                    item[f"{prefix}_{name}"] = value
            output.append(item)
            heapq.heappush(active, (row["_close"], int(row["ticket"]), row))
            previous = row
            previous_open_time = row["_open"]
            if current_category == "xau_sl_core":
                previous_core = row
    return sorted(output, key=lambda row: (row["open_utc_inferred"], int(row["ticket"])))


def transition_stats(rows: list[dict], prefix: str) -> dict:
    available = [r for r in rows if r[f"{prefix}_ticket"] != ""]
    eligible = [r for r in available if 0 <= r[f"{prefix}_gap_sec"] < 600]
    matched = sum(r[f"{prefix}_direction_match"] for r in eligible)
    return {
        "available": len(available), "eligible_nonoverlap_gap_under_600s": len(eligible),
        "matching_direction": matched, "mismatching_direction": len(eligible) - matched,
        "direction_accuracy_pct": round(100 * matched / len(eligible), 6) if eligible else None,
        "overlapping_adjacent_pair": sum(r[f"{prefix}_gap_sec"] < 0 for r in available),
        "gap_600s_or_more": sum(r[f"{prefix}_gap_sec"] >= 600 for r in available),
        "abs_distance_points": distribution([abs(r[f"{prefix}_move_points"]) for r in eligible]),
    }


def reconcile(raw: list[dict], normalized: list[dict], json_rows: list[dict]) -> dict:
    issues = []
    raw_map = {str(r["ticket"]): r for r in raw}
    normalized_map = {str(r["ticket"]): r for r in normalized}
    json_map = {str(r["ticket"]): r for r in json_rows}
    for label, rows, mapped in (("raw_csv", raw, raw_map), ("normalized_csv", normalized, normalized_map), ("jsonl", json_rows, json_map)):
        if len(mapped) != len(rows) or len({r["id"] for r in rows}) != len(rows):
            issues.append({"source": label, "issue": "duplicate_ticket_or_id"})
        if set(mapped) != set(raw_map):
            issues.append({"source": label, "issue": "ticket_population_differs"})
    for ticket, source in raw_map.items():
        normalized_row = normalized_map.get(ticket)
        json_row = json_map.get(ticket)
        if normalized_row is None or json_row is None:
            continue
        for name in source:
            expected = str(source[name] or "")
            actual = str(json_row.get(name) if json_row.get(name) is not None else "")
            same = Decimal(expected) == Decimal(actual) if name in NUMERIC_FIELDS else expected == actual
            if not same:
                issues.append({"ticket": ticket, "field": name, "issue": "raw_csv_jsonl_differs"})
            if name in ("open_time", "close_time"):
                part = name.split("_")[0]
                source_time = dt(expected)
                canonical = dt(normalized_row[f"actual_{part}_utc"])
                expected_utc = source_time - timedelta(hours=3)
                if canonical != expected_utc:
                    issues.append({"ticket": ticket, "field": name, "issue": "inferred_utc_transform_differs"})
                for suffix, offset in (("bkk", 7), ("iux_chart", 6)):
                    key = f"actual_{part}_bkk" if suffix == "bkk" else f"{part}_iux_chart"
                    converted = dt(normalized_row[key])
                    if converted != canonical or converted.utcoffset() != timedelta(hours=offset):
                        issues.append({"ticket": ticket, "field": key, "issue": "instant_or_timezone_label_differs"})
                web_key = f"web_{part}_display_derived"
                expected_web = (source_time.replace(tzinfo=None) + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
                if normalized_row.get(web_key) != expected_web:
                    issues.append({"ticket": ticket, "field": web_key, "issue": "derived_display_differs"})
            elif name in normalized_row:
                value = normalized_row[name] or ""
                same = Decimal(expected) == Decimal(value) if name in NUMERIC_FIELDS else expected == value
                if not same:
                    issues.append({"ticket": ticket, "field": name, "issue": "normalized_source_value_differs"})
    return {
        "raw_rows": len(raw), "normalized_rows": len(normalized), "jsonl_rows": len(json_rows),
        "raw_unique_tickets": len(raw_map), "raw_unique_ids": len({r["id"] for r in raw}),
        "issue_count": len(issues), "issues": issues,
        "exact_population_and_values_reconciled": not issues,
        "utc_offset_status": "inferred_from_cross_broker_price_alignment_not_officially_confirmed",
        "web_display_status": "derived_raw_plus_7h_not_independently_captured_for_every_row",
    }


def main() -> None:
    raw = read_csv(DATA / "orders_35462.csv")
    normalized = read_csv(DATA / "orders_35462_normalized.csv")
    with (DATA / "orders_35462.jsonl").open(encoding="utf-8") as stream:
        json_rows = [json.loads(line) for line in stream if line.strip()]
    audit = build_audit(normalized)
    core = [r for r in audit if r["category"] == "xau_sl_core"]
    classes = Counter(r["category"] for r in audit)
    old_bad = [r for r in core if r["previous_core_only_ticket"] and 0 <= r["previous_core_only_gap_sec"] < 600 and not r["previous_core_only_direction_match"]]
    resolved = [r for r in old_bad if r["predecessor_changed_by_including_other_exits"] and r["previous_opened_direction_match"]]
    by_predecessor_category = defaultdict(list)
    by_side_pair = defaultdict(list)
    for row in core:
        if row["previous_opened_ticket"]:
            by_predecessor_category[row["previous_opened_category"]].append(row)
            by_side_pair[f"{row['previous_opened_side']}_to_{row['side']}"].append(row)
    report = {
        "reconciliation": reconcile(raw, normalized, json_rows),
        "source_file_sha256": {name: hashlib.sha256((DATA / name).read_bytes()).hexdigest() for name in ("orders_35462.csv", "orders_35462.jsonl", "orders_35462_normalized.csv")},
        "all_orders_accounted_for": len(audit), "classification": dict(sorted(classes.items())),
        "classification_sum": sum(classes.values()),
        "gross_profit_decimal": str(sum((Decimal(r["profit"]) for r in raw), Decimal(0))),
        "xau_core_previous_core_only": transition_stats(core, "previous_core_only"),
        "xau_core_previous_all_xau_opened": transition_stats(core, "previous_opened"),
        "xau_core_latest_completed_xau": transition_stats(core, "previous_completed"),
        "predecessor_changed_core_orders": sum(r["predecessor_changed_by_including_other_exits"] for r in core),
        "old_core_only_direction_mismatches_resolved": len(resolved),
        "resolved_tickets": [r["ticket"] for r in resolved],
        "xau_core_opens_with_active_same_symbol": sum(r["active_same_symbol_before_open"] > 0 for r in core),
        "xau_core_close_open_second_ties": sum(r["close_open_second_tie"] for r in core),
        "by_predecessor_category": {key: transition_stats(value, "previous_opened") for key, value in by_predecessor_category.items()},
        "by_side_pair": {key: transition_stats(value, "previous_opened") for key, value in by_side_pair.items()},
        "core_loss_orders": sum(Decimal(r["profit"]) < 0 for r in core),
        "core_loss_exact_minus_100_points": sum(Decimal(r["pips"]) == -100 and Decimal(r["profit"]) < 0 for r in core),
        "full_causal_clone_verified_orders": 0,
        "full_clone_complete": False,
        "remaining": ["Source broker ticks and bid/ask not present", "No causal one-to-one replay has passed for all source orders", "Manual actions/settings/session state not in closed ledger", "FixedVol20 trial and unusual exits must not be dropped"],
    }
    with (DATA / "order_audit_35462.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(audit[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit)
    (DATA / "ledger_audit_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: report[key] for key in ("all_orders_accounted_for", "classification", "predecessor_changed_core_orders", "old_core_only_direction_mismatches_resolved", "xau_core_previous_all_xau_opened", "xau_core_latest_completed_xau", "full_clone_complete")}, ensure_ascii=False, indent=2))
    if not report["reconciliation"]["exact_population_and_values_reconciled"]:
        raise SystemExit("Ledger reconciliation failed; inspect report.")


if __name__ == "__main__":
    main()
