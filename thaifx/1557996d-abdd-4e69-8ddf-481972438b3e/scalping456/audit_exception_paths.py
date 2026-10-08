"""All-order payoff/support audit from the untouched public JSONL snapshot.

Reported [sl ...] is a closing label, not proof of the initial stop or a single
EA engine. Grouping unusual closes is diagnostic, not a recovered basket ID.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import groupby
from pathlib import Path

from strategy_scalping456 import CloseByPosition, Side, settle_close_by


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
D = Decimal


def clock(value):
    return datetime.fromisoformat(value) - timedelta(hours=3)


def number(value):
    return D(str(value))


def stats(values):
    values = sorted(map(float, values))
    if not values:
        return {"count": 0}
    out = {"count": len(values), "min": values[0], "max": values[-1]}
    for label, fraction in (("p25", .25), ("median", .5), ("p75", .75), ("p90", .9)):
        position = (len(values) - 1) * fraction
        lower, upper = int(position), min(int(position) + 1, len(values) - 1)
        out[label] = round(values[lower] + (values[upper] - values[lower]) * (position - lower), 6)
    return out


def summarize_sl(rows, initial_points):
    losses = [r for r in rows if number(r["profit"]) < 0]
    partial = [r for r in losses if -initial_points < number(r["pips"]) < 0]
    beyond = [r for r in losses if number(r["pips"]) < -initial_points]
    small_positive = [r for r in rows if 0 < number(r["pips"]) < 10]
    return {
        "orders": len(rows), "wins": sum(number(r["profit"]) > 0 for r in rows),
        "losses": len(losses), "breakeven_profit": sum(number(r["profit"]) == 0 for r in rows),
        "volumes": sorted({float(r["volume"]) for r in rows}),
        "nominal_initial_stop_points_candidate": initial_points,
        "loss_exact_initial_points": sum(number(r["pips"]) == -initial_points for r in losses),
        "loss_between_initial_and_zero": len(partial), "loss_beyond_initial": len(beyond),
        "loss_points": stats(r["pips"] for r in losses),
        "partial_loss_points": stats(r["pips"] for r in partial),
        "beyond_initial_loss_points": stats(r["pips"] for r in beyond),
        "positive_pips_below_10": len(small_positive),
        "zero_pips": sum(number(r["pips"]) == 0 for r in rows),
        "duration_seconds": stats((clock(r["close_time"]) - clock(r["open_time"])).total_seconds() for r in rows),
        "worst_beyond_initial": sorted(beyond, key=lambda r: number(r["pips"]))[:10],
    }


def unusual_close_groups(rows):
    by_symbol = defaultdict(list)
    for row in rows:
        by_symbol[row["symbol"]].append(row)
    clusters = []
    for symbol, orders in by_symbol.items():
        pending = []
        previous = None
        for row in sorted(orders, key=lambda r: (clock(r["close_time"]), r["ticket"])):
            closed = clock(row["close_time"])
            if previous is not None and (closed - previous).total_seconds() > 15:
                clusters.append((symbol, pending))
                pending = []
            pending.append(row)
            previous = closed
        if pending:
            clusters.append((symbol, pending))
    output = []
    for index, (symbol, orders) in enumerate(clusters, 1):
        ordered = sorted(orders, key=lambda r: (clock(r["open_time"]), r["ticket"]))
        output.append({
            "diagnostic_group": index, "not_verified_ea_basket_id": True,
            "symbol": symbol, "tickets": [r["ticket"] for r in ordered],
            "orders": len(ordered), "sides": sorted({r["trade_type"] for r in ordered}),
            "first_open_utc_inferred": clock(ordered[0]["open_time"]).isoformat(),
            "last_close_utc_inferred": max(clock(r["close_time"]) for r in ordered).isoformat(),
            "total_volume": str(sum((number(r["volume"]) for r in ordered), D(0))),
            "max_volume": str(max(number(r["volume"]) for r in ordered)),
            "gross_profit": str(sum((number(r["profit"]) for r in ordered), D(0))),
            "volumes_by_open": [str(r["volume"]) for r in ordered],
            "close_comments": sorted({r["comment"] or "" for r in ordered}),
            "member_orders": ordered,
        })
    return output


def audit_close_by(rows):
    """Reconcile closing mechanics, not the unknown opening/closing schedule."""
    groups = defaultdict(list)
    for row in rows:
        if " by #" in (row["comment"] or ""):
            groups[(row["symbol"], row["comment"], row["close_time"])].append(row)
    verified, unresolved, expected = [], [], {}
    contracts = {"XAUUSD+": D(100), "FixedVol20": D(1)}
    for (symbol, comment, closed), members in sorted(groups.items()):
        options = []
        if len(members) == 2:
            for first, second in (members, members[::-1]):
                try:
                    positions = [CloseByPosition(symbol, Side(r["trade_type"]),
                                                 clock(r["open_time"]), number(r["open_price"]),
                                                 number(r["volume"])) for r in (first, second)]
                    exits = settle_close_by(*positions, time=clock(closed),
                                            contract_price_multiplier=contracts[symbol], point=D("0.01"))
                    if all(abs(exit.price - number(row["close_price"])) <= D("0.000001")
                           and abs(exit.pips - number(row["pips"])) <= D("0.000001")
                           and abs(exit.gross_profit - number(row["profit"])) <= D("0.005000001")
                           and exit.volume == number(row["volume"])
                           for exit, row in zip(exits, (first, second))):
                        options.append((first, second, exits))
                except (ValueError, KeyError):
                    pass
        if not options:
            unresolved.append({"symbol": symbol, "comment": comment,
                               "tickets": [r["ticket"] for r in members]})
            continue
        first, second, exits = options[0]
        for row, exit in zip((first, second), exits):
            expected[row["ticket"]] = exit.gross_profit
        verified.append({
            "symbol": symbol, "comment": comment,
            "first_position_ticket_inferred": first["ticket"],
            "position_by_ticket_inferred": second["ticket"],
            "allocation_ambiguous": len(options) > 1,
            "request_order_not_directly_observed": True,
            "open_gap_seconds": abs((clock(first["open_time"]) - clock(second["open_time"])).total_seconds()),
            "close_time_utc_inferred": clock(closed).isoformat(),
            "offset_volume": str(exits[0].volume), "mirrored_pips_each": str(exits[0].pips),
            "net_gross_profit": str(exits[0].gross_profit),
            "member_orders": [first, second],
        })
    return {"source_close_by_rows": sum(map(len, groups.values())), "verified_pairs": verified,
            "unresolved_groups": unresolved, "timing_or_hedge_trigger_reproduced": False}, expected


def audit_portfolio(rows):
    """All XAU intervals, including special exits. Equal-second order is unknown."""
    prepared = sorted(((clock(r["open_time"]), clock(r["close_time"]), r)
                       for r in rows if r["symbol"] == "XAUUSD+"),
                      key=lambda value: (value[0], value[2]["ticket"]))
    active, pairs = [], []
    max_concurrent, boundary_rows, same_second_rows, strict_open_overlaps = 0, 0, 0, 0
    boundary_tickets, prior_opposite_at_open = set(), set()

    def pair(a, b):
        opened, closed = max(a[0], b[0]), min(a[1], b[1])
        if closed <= opened:
            return
        first, second = a[2], b[2]
        sign = D(1) if first["trade_type"] == "buy" else D(-1)
        adverse = -sign * (number(second["open_price"]) - number(first["open_price"])) * 100
        pairs.append({
            "earlier_ticket": first["ticket"], "later_ticket": second["ticket"],
            "same_reported_open_second": a[0] == b[0],
            "opposite_sides": first["trade_type"] != second["trade_type"],
            "same_volume": number(first["volume"]) == number(second["volume"]),
            "open_gap_seconds": (b[0] - a[0]).total_seconds(),
            "positive_overlap_seconds": (closed - opened).total_seconds(),
            "overlap_start_utc_inferred": opened.isoformat(),
            "adverse_points_at_later_entry": str(adverse),
            "same_close_second": a[1] == b[1],
            "earlier_close_comment": first["comment"], "later_close_comment": second["comment"],
            "earlier_pips": str(first["pips"]), "later_pips": str(second["pips"]),
        })

    for opened, batch_iterator in groupby(prepared, key=lambda value: value[0]):
        batch = list(batch_iterator)
        boundaries = [value for value in active if value[1] == opened]
        active = [value for value in active if value[1] > opened]
        if boundaries:
            boundary_rows += len(batch)
            boundary_tickets.update(value[2]["ticket"] for value in batch)
        if len(batch) > 1:
            same_second_rows += len(batch)
        if active:
            strict_open_overlaps += len(batch)
        for current in batch:
            for previous in active:
                pair(previous, current)
                if previous[2]["trade_type"] != current[2]["trade_type"]:
                    prior_opposite_at_open.add(current[2]["ticket"])
        for index, first in enumerate(batch):
            for second in batch[index + 1:]:
                pair(first, second)
        active.extend(value for value in batch if value[1] > opened)
        max_concurrent = max(max_concurrent, len(active))

    overlap_tickets, opposed_tickets = set(), set()
    for value in pairs:
        tickets = {value["earlier_ticket"], value["later_ticket"]}
        overlap_tickets.update(tickets)
        if value["opposite_sides"]:
            opposed_tickets.update(tickets)
    below = {r["ticket"] for _, _, r in prepared
             if (r["comment"] or "").startswith("[sl ") and number(r["pips"]) < -100}
    return {
        "xau_rows": len(prepared), "maximum_concurrent_positive_duration_positions": max_concurrent,
        "strict_overlap_order_pairs": len(pairs), "orders_in_strict_overlaps": len(overlap_tickets),
        "opposed_overlap_pairs": sum(value["opposite_sides"] for value in pairs),
        "orders_in_opposed_overlaps": len(opposed_tickets),
        "rows_opened_while_earlier_order_still_active": strict_open_overlaps,
        "rows_with_other_opens_in_same_reported_second": same_second_rows,
        "rows_at_prior_close_same_second_ambiguous": boundary_rows,
        "equal_second_ordering_not_observed": True,
        "sl_label_loss_below_100": len(below),
        "sl_label_loss_below_100_with_any_overlap": len(below & overlap_tickets),
        "sl_label_loss_below_100_with_opposed_overlap": len(below & opposed_tickets),
        "sl_label_loss_below_100_prior_opposed_at_open": len(below & prior_opposite_at_open),
        "sl_label_loss_below_100_with_no_strict_overlap": sorted(below - overlap_tickets),
        "pairs": pairs,
        "overlap_is_not_proof_of_same_EA_or_hedge_logic": True,
    }


def audit_contracts(rows, close_by_profit=None):
    contract_candidates = {"XAUUSD+": D(100), "FixedVol20": D(1)}
    counts = defaultdict(Counter)
    mismatches = []
    for row in rows:
        sign = D(1) if row["trade_type"] == "buy" else D(-1)
        delta = sign * (number(row["close_price"]) - number(row["open_price"]))
        implied_pips = delta * 100
        implied_profit = delta * number(row["volume"]) * contract_candidates[row["symbol"]]
        allocation_profit = (close_by_profit or {}).get(row["ticket"], implied_profit)
        pips_error = implied_pips - number(row["pips"])
        profit_error = implied_profit - number(row["profit"])
        group = counts[row["symbol"]]
        group["orders"] += 1
        group["pips_reconcile_within_0_000001"] += abs(pips_error) <= D("0.000001")
        group["gross_profit_reconcile_within_half_cent"] += abs(profit_error) <= D("0.005") + D("0.000000001")
        group["gross_profit_after_close_by_allocation_reconcile_within_half_cent"] += abs(
            allocation_profit - number(row["profit"])) <= D("0.005000001")
        if abs(pips_error) > D("0.000001") or abs(profit_error) > D("0.005000001"):
            mismatches.append({"ticket": row["ticket"], "symbol": row["symbol"],
                               "pips_error": str(pips_error), "gross_profit_error": str(profit_error),
                               "comment": row["comment"]})
    return {"candidate_contract_price_multipliers": {k: str(v) for k, v in contract_candidates.items()},
            "candidate_not_account_contract_confirmation": True,
            "by_symbol": {k: dict(v) for k, v in counts.items()}, "mismatches": mismatches}


def main():
    source = DATA / "orders_35462.jsonl"
    with source.open(encoding="utf-8") as stream:
        rows = [json.loads(line, parse_float=D) for line in stream if line.strip()]
    xau = [r for r in rows if r["symbol"] == "XAUUSD+" and (r["comment"] or "").startswith("[sl ")]
    trial = [r for r in rows if r["symbol"] == "FixedVol20" and (r["comment"] or "").startswith("[sl ")]
    unusual = [r for r in rows if not (r["comment"] or "").startswith(("[sl ", "[tp "))]
    xau_summary, trial_summary = summarize_sl(xau, 100), summarize_sl(trial, 1000)
    forbidden = []
    for row in xau:
        pips = number(row["pips"])
        # Ideal fills: initial -100, or trailing >= activation-distance=10.
        if abs(pips + 100) > D("0.000001") and pips < D("9.999999"):
            forbidden.append({"ticket": row["ticket"], "pips": str(pips),
                              "reason": "below_initial_stop" if pips < -100 else "below_minimum_trailing_profit_10"})
    groups = unusual_close_groups(unusual)
    close_by, close_by_profit = audit_close_by(rows)
    portfolio = audit_portfolio(rows)
    accounted = [ticket for group in groups for ticket in group["tickets"]]
    assert len(accounted) == len(set(accounted)) == len(unusual)
    report = {
        "source_rows": len(rows), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "audit_implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "strategy_implementation_sha256": hashlib.sha256((ROOT / "strategy_scalping456.py").read_bytes()).hexdigest(),
        "xau_sl_labeled_cohort": xau_summary, "fixedvol20_sl_trial": trial_summary,
        "initial_stop_not_observed_in_source": True,
        "closing_sl_label_not_proof_of_uniform_engine_or_initial_stop": True,
        "ideal_level_a40_d30_cannot_reproduce_xau_orders": len(forbidden),
        "ideal_level_a40_d30_counterexamples": forbidden,
        "exclusion_is_for_ideal_level_fill_not_quote_fill": True,
        "unusual_exit_rows": len(unusual), "unusual_diagnostic_groups": groups,
        "all_unusual_orders_accounted_for_exactly_once": True,
        "close_by": close_by, "xau_portfolio_paths": portfolio,
        "contracts": audit_contracts(rows, close_by_profit),
        "full_source_clone_complete": False,
    }
    target = DATA / "exception_paths_report.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "xau_sl_labeled_cohort": {k: xau_summary[k] for k in ("orders", "loss_beyond_initial", "positive_pips_below_10", "zero_pips")},
        "fixedvol20_sl_trial": {k: trial_summary[k] for k in ("orders", "wins", "losses", "breakeven_profit", "loss_between_initial_and_zero", "duration_seconds")},
        "ideal_level_a40_d30_counterexamples": len(forbidden),
        "unusual_exit_rows": len(unusual), "diagnostic_groups": len(groups),
        "contract_reconciliation": report["contracts"]["by_symbol"],
        "close_by_verified_pairs": len(close_by["verified_pairs"]),
        "close_by_unresolved": len(close_by["unresolved_groups"]),
        "xau_portfolio_paths": {k: v for k, v in portfolio.items() if k not in (
            "pairs", "sl_label_loss_below_100_with_no_strict_overlap")},
    }, indent=2))


if __name__ == "__main__":
    main()
