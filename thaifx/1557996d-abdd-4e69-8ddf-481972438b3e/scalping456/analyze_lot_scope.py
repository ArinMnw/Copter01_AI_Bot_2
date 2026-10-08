"""Forensic lot timeline and past realized GROSS ledger, never risk signals.

No MT5, live account, candles, fee invention, balance/equity reconstruction or
source-clock lot switches. Same-second event ordering stays explicitly unknown.
"""

import argparse
import hashlib
import heapq
import json
import re
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import groupby
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_SHA = "b8f5f75de07ba335ba607855167b5c77600954561c7c740621a335fa1b9825f1"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite ledger number")
    return result


def second(value):
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None or parsed.microsecond:
        raise ValueError("Source needs timezone-aware second precision")
    return int(parsed.timestamp())


def analyze(rows, starting_capital=Decimal("1000")):
    starting_capital = number(starting_capital)
    if starting_capital <= 0 or len({r["ticket"] for r in rows}) != len(rows):
        raise ValueError("Positive capital and unique source tickets required")
    ordered = sorted(rows, key=lambda r: (second(r["open_time"]), r["ticket"]))
    closes, opened = defaultdict(list), defaultdict(list)
    for r in ordered:
        opening, closing = second(r["open_time"]), second(r["close_time"])
        if closing < opening or number(r["volume"]) <= 0:
            raise ValueError("Invalid trade lifecycle/volume")
        number(r["profit"])
        closes[closing].append(r)
        opened[opening].append(r)
    close_times = sorted(closes)
    cumulative, cumulative_gold = [Decimal(0)], [Decimal(0)]
    for t in close_times:
        cumulative.append(cumulative[-1] + sum((number(r["profit"]) for r in closes[t]), Decimal(0)))
        cumulative_gold.append(cumulative_gold[-1] + sum((number(r["profit"]) for r in closes[t]
                                                         if r["symbol"] == "XAUUSD+"), Decimal(0)))
    outputs, active = [], []
    active_symbols = Counter()
    for t in sorted(opened):
        while active and active[0][0] <= t:
            _, _, symbol = heapq.heappop(active)
            active_symbols[symbol] -= 1
        before = bisect_left(close_times, t)
        same_profit = sum((number(r["profit"]) for r in closes[t]), Decimal(0))
        for r in opened[t]:
            closes_now = second(r["close_time"]) == t
            inferred = datetime.fromtimestamp(t - 10800, timezone.utc)
            outputs.append({
                "ticket": r["ticket"], "symbol": r["symbol"], "volume": str(number(r["volume"])),
                "open_raw": r["open_time"], "close_raw": r["close_time"],
                "open_inferred_utc": inferred.isoformat(),
                "web_open_display_derived": (datetime.fromisoformat(r["open_time"]) + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S"),
                "past_closed_gross_all_symbols": str(cumulative[before]),
                "starting_capital_plus_past_gross_NOT_balance": str(starting_capital + cumulative[before]),
                "past_closed_gross_xau_only": str(cumulative_gold[before]),
                "other_closes_same_second_ambiguous_count": len(closes[t]) - int(closes_now),
                "other_closes_same_second_gross_NOT_consumed": str(same_profit - (number(r["profit"]) if closes_now else 0)),
                "other_entries_same_second_ambiguous_count": len(opened[t]) - 1,
                "strict_active_before_entry_all_symbols": sum(active_symbols.values()),
                "strict_active_before_entry_by_symbol": {s: n for s, n in active_symbols.items() if n},
                "not_strategy_prediction": True, "fee_swap_floating_cashflow_not_reconstructed": True,
            })
        # Entries in this second cannot be presumed earlier than another entry.
        for r in opened[t]:
            close = second(r["close_time"])
            if close > t:
                heapq.heappush(active, (close, r["ticket"], r["symbol"]))
                active_symbols[r["symbol"]] += 1
    by_ticket = {r["ticket"]: r for r in outputs}
    gold = [r for r in ordered if r["symbol"] == "XAUUSD+"]
    runs = []
    for volume, values in groupby(gold, key=lambda r: number(r["volume"])):
        values = list(values)
        first, last = values[0], values[-1]
        runs.append({"volume": str(volume), "source_rows": len(values),
                     "first_ticket": first["ticket"], "last_entry_ticket": last["ticket"],
                     "first_entry_raw": first["open_time"], "last_entry_raw": last["open_time"],
                     "last_close_raw": max(r["close_time"] for r in values),
                     "first_entry_state": by_ticket[first["ticket"]]})
    first_scope = []
    if gold:
        for r in gold:
            if number(r["volume"]) != number(gold[0]["volume"]):
                break
            first_scope.append(r)
    scope_tickets = {r["ticket"] for r in first_scope}
    for r in outputs:
        r["first_xau_lot_run_component_scope_NOT_goal_completion"] = r["ticket"] in scope_tickets
    counts = {s: dict(Counter(str(number(r["volume"])) for r in ordered if r["symbol"] == s))
              for s in sorted({r["symbol"] for r in ordered})}
    report = {"source_orders": len(rows), "starting_capital_assumption": str(starting_capital),
              "volume_counts_by_symbol": counts, "xau_chronological_adjacent_volume_runs": runs,
              "gross_total_all_symbols": str(cumulative[-1]), "gross_total_xau_only": str(cumulative_gold[-1]),
              "first_xau_lot_run_component_scope": {"source_rows": len(first_scope),
                  "volume": str(number(first_scope[0]["volume"])) if first_scope else None,
                  "close_comment_types": dict(Counter("close_by" if r["comment"].startswith("#") else
                                                       "sl" if r["comment"].startswith("[sl ") else "other"
                                                       for r in first_scope)),
                  "strict_preentry_active_distribution": dict(Counter(str(by_ticket[r["ticket"]]["strict_active_before_entry_all_symbols"])
                                                                      for r in first_scope))},
              "actual_balance_equity_identified": False, "recovered_lot_formula": False,
              "full_source_clone_complete": False, "source_ledger_is_forensic_input_not_signals": True}
    return outputs, report


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid output tag")
    source = ROOT / "data/orders_35462.jsonl"
    if digest(source) != SOURCE_SHA:
        raise ValueError("Source snapshot hash changed")
    rows = [json.loads(line, parse_float=Decimal) for line in source.read_text(encoding="utf-8").splitlines()]
    if len(rows) != 35462:
        raise ValueError("Source population changed")
    outputs, report = analyze(rows)
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    path = folder / "all_source_lot_states.jsonl"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for r in outputs:
            handle.write(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n")
    report.update({"created_utc": datetime.now(timezone.utc).isoformat(), "source_sha256": digest(source),
                   "code_sha256": digest(__file__), "plan_sha256": digest(ROOT / "NARROW_RESEARCH_PLAN.md"),
                   "artifact_sha256": {path.name: digest(path)}})
    write_json(folder / "report.json", report)
    saved = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert saved == outputs
    assert len(saved) == len({r["ticket"] for r in saved}) == 35462
    assert {r["ticket"] for r in saved} == {r["ticket"] for r in rows}
    assert sum(report["volume_counts_by_symbol"]["XAUUSD+"].values()) == 31210
    assert sum(report["volume_counts_by_symbol"]["FixedVol20"].values()) == 4252
    assert sum(r["source_rows"] for r in report["xau_chronological_adjacent_volume_runs"]) == 31210
    assert sum(r["first_xau_lot_run_component_scope_NOT_goal_completion"] for r in saved) == 7312
    write_json(folder / "qa_lot_scope.json", {"all35462_tickets_and_populations_verified": True,
              "report_sha256": digest(folder / "report.json"), "artifact_sha256": digest(path),
              "actual_balance_equity_identified": False, "full_source_clone_complete": False})
    print(json.dumps({"tag": args.tag, "source_orders": len(saved), "xau_runs": len(report["xau_chronological_adjacent_volume_runs"]),
                      "first_component_rows": 7312, "actual_balance_equity_identified": False}))


if __name__ == "__main__":
    main()
