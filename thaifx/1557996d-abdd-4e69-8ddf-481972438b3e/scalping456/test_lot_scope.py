"""Past-gross chronology, lot scope and explicit reconstruction boundaries."""

import unittest
from decimal import Decimal

from analyze_lot_scope import analyze


def row(ticket, opening, closing, volume="0.01", profit="1", symbol="XAUUSD+"):
    return {"ticket": ticket, "open_time": f"2026-08-24T01:00:{opening:02d}+00:00",
            "close_time": f"2026-08-24T01:00:{closing:02d}+00:00", "volume": Decimal(volume),
            "profit": Decimal(profit), "symbol": symbol, "comment": "[sl 100]"}


class LotScopeTests(unittest.TestCase):
    def test_future_profit_cannot_enter_preentry_gross(self):
        data = [row(1, 0, 20, profit="999"), row(2, 10, 11, profit="2"), row(3, 12, 13)]
        states, _ = analyze(data)
        self.assertEqual(Decimal(states[1]["starting_capital_plus_past_gross_NOT_balance"]), 1000)
        self.assertEqual(Decimal(states[2]["starting_capital_plus_past_gross_NOT_balance"]), 1002)
        self.assertEqual(states[1]["strict_active_before_entry_all_symbols"], 1)

    def test_same_second_close_is_not_arbitrarily_consumed(self):
        states, _ = analyze([row(1, 0, 10, profit="10"), row(2, 10, 20)])
        self.assertEqual(states[1]["past_closed_gross_all_symbols"], "0")
        self.assertEqual(states[1]["other_closes_same_second_ambiguous_count"], 1)
        self.assertEqual(states[1]["other_closes_same_second_gross_NOT_consumed"], "10")
        self.assertEqual(states[1]["strict_active_before_entry_all_symbols"], 0)

    def test_zero_duration_own_close_never_seeds_entry_or_negative_active(self):
        states, _ = analyze([row(1, 0, 0, profit="7"), row(2, 0, 10), row(3, 11, 12)])
        self.assertEqual(states[0]["other_closes_same_second_ambiguous_count"], 0)
        self.assertEqual(states[1]["other_closes_same_second_ambiguous_count"], 1)
        self.assertEqual(states[0]["past_closed_gross_all_symbols"], "0")
        self.assertEqual(states[0]["strict_active_before_entry_all_symbols"], 0)
        self.assertEqual(states[2]["past_closed_gross_all_symbols"], "8")

    def test_symbol_separation_and_account_includes_fixed(self):
        states, report = analyze([row(1, 0, 1, symbol="FixedVol20", volume="0.1", profit="3"), row(2, 2, 3)])
        self.assertNotIn("0.1", report["volume_counts_by_symbol"]["XAUUSD+"])
        self.assertEqual(states[1]["past_closed_gross_xau_only"], "0")
        self.assertEqual(states[1]["past_closed_gross_all_symbols"], "3")

    def test_rollback_preserved_but_component_is_first_run_only(self):
        states, report = analyze([row(1, 0, 1), row(2, 2, 3, volume="1"), row(3, 4, 5)])
        self.assertEqual([r["volume"] for r in report["xau_chronological_adjacent_volume_runs"]], ["0.01", "1", "0.01"])
        self.assertEqual([r["first_xau_lot_run_component_scope_NOT_goal_completion"] for r in states], [True, False, False])
        self.assertFalse(report["actual_balance_equity_identified"])
        self.assertFalse(report["recovered_lot_formula"])

    def test_future_extension_preserves_states_and_ties_have_no_fake_order(self):
        data = [row(3, 0, 10), row(1, 0, 20), row(2, 12, 13)]
        initial, _ = analyze(data)
        extended, _ = analyze(data + [row(4, 30, 40, profit="999999")])
        self.assertEqual(initial, extended[:len(initial)])
        self.assertEqual(initial[0]["other_entries_same_second_ambiguous_count"], 1)
        self.assertEqual(initial[0]["strict_active_before_entry_all_symbols"], 0)
        self.assertEqual(initial[1]["strict_active_before_entry_all_symbols"], 0)

    def test_invalid_population_lifecycle_and_numbers_rejected(self):
        for data in ([row(1, 10, 9)], [row(1, 0, 1, volume="0")], [row(1, 0, 1, profit="NaN")],
                     [row(1, 0, 1), row(1, 2, 3)]):
            with self.assertRaises(ValueError):
                analyze(data)
        with self.assertRaises(ValueError):
            analyze([], starting_capital=0)


if __name__ == "__main__":
    unittest.main()
