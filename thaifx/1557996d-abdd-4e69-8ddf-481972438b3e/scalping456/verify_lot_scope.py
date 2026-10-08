"""Independent sequential past-gross audit and population checks, not cloning."""

import argparse
import json
import re
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from decimal import Decimal

from analyze_lot_scope import ROOT, SOURCE_SHA, digest, second, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid output tag")
    folder = ROOT / "data" / args.tag
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    source_path = ROOT / "data/orders_35462.jsonl"
    assert digest(source_path) == report["source_sha256"] == SOURCE_SHA
    assert digest(ROOT / "analyze_lot_scope.py") == report["code_sha256"]
    assert digest(ROOT / "NARROW_RESEARCH_PLAN.md") == report["plan_sha256"]
    for name, value in report["artifact_sha256"].items():
        assert digest(folder / name) == value
    source = [json.loads(line, parse_float=Decimal) for line in source_path.read_text(encoding="utf-8").splitlines()]
    states = [json.loads(line) for line in (folder / "all_source_lot_states.jsonl").read_text(encoding="utf-8").splitlines()]
    by_ticket = {r["ticket"]: r for r in source}
    assert len(source) == len(states) == len(by_ticket) == 35462
    assert set(by_ticket) == {r["ticket"] for r in states}
    assert [r["ticket"] for r in states] == [r["ticket"] for r in sorted(source, key=lambda r: (second(r["open_time"]), r["ticket"]))]
    closed = sorted(source, key=lambda r: second(r["close_time"]))
    opens_by_symbol, closes_by_symbol, zero_by_symbol = defaultdict(list), defaultdict(list), defaultdict(Counter)
    for r in source:
        symbol, opening, closing = r["symbol"], second(r["open_time"]), second(r["close_time"])
        opens_by_symbol[symbol].append(opening)
        closes_by_symbol[symbol].append(closing)
        if opening == closing:
            zero_by_symbol[symbol][opening] += 1
    for values in (opens_by_symbol, closes_by_symbol):
        for symbol in values:
            values[symbol].sort()
    index, gross, gold = 0, Decimal(0), Decimal(0)
    for state in states:
        t = second(state["open_raw"])
        while index < len(closed) and second(closed[index]["close_time"]) < t:
            r = closed[index]
            gross += Decimal(str(r["profit"]))
            if r["symbol"] == "XAUUSD+":
                gold += Decimal(str(r["profit"]))
            index += 1
        assert Decimal(state["past_closed_gross_all_symbols"]) == gross
        assert Decimal(state["past_closed_gross_xau_only"]) == gold
        assert Decimal(state["starting_capital_plus_past_gross_NOT_balance"]) == Decimal(report["starting_capital_assumption"]) + gross
        assert Decimal(state["volume"]) == Decimal(str(by_ticket[state["ticket"]]["volume"]))
        active = {s: bisect_left(opens_by_symbol[s], t) - bisect_right(closes_by_symbol[s], t) + zero_by_symbol[s][t]
                  for s in opens_by_symbol}
        assert all(n >= 0 for n in active.values())
        assert {s: n for s, n in active.items() if n} == state["strict_active_before_entry_by_symbol"]
        assert sum(active.values()) == state["strict_active_before_entry_all_symbols"]
        assert state["not_strategy_prediction"] and state["fee_swap_floating_cashflow_not_reconstructed"]
    assert sum(r["first_xau_lot_run_component_scope_NOT_goal_completion"] for r in states) == 7312
    assert not report["actual_balance_equity_identified"] and not report["recovered_lot_formula"] and not report["full_source_clone_complete"]
    write_json(folder / "qa_independent.json", {"all35462_sequential_gross_and_active_counts_verified": True,
               "source_sha256": digest(source_path), "report_sha256": digest(folder / "report.json"),
               "verifier_sha256": digest(__file__), "actual_balance_equity_identified": False,
               "full_source_clone_complete": False})
    print("Independent sequential gross/active/population/hash audit passed for all 35462 entries")


if __name__ == "__main__":
    main()
