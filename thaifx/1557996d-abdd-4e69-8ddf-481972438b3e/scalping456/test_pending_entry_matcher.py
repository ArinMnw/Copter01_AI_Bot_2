"""Entry-only diagnostics cannot reuse predictions or become full-order success."""

import unittest
from decimal import Decimal

import numpy as np

from replay_pending_vector import replay_pending
from replay_vantage_pending import entry_diagnostics
from strategy_scalping456 import PendingStopConfig
from strict_source_matcher import source_record


class PendingEntryMatcherTests(unittest.TestCase):
    def row(self, ticket=1, volume=10):
        return {"ticket": ticket, "symbol": "XAUUSD+", "trade_type": "buy", "volume": volume,
                "open_time": "2026-09-07T03:00:00+00:00", "close_time": "2026-09-07T03:00:10+00:00",
                "open_price": Decimal("100.12"), "close_price": 100.2, "pips": 8, "profit": 80, "comment": "[sl 100.2]"}

    def test_duplicate_entry_consumes_prediction_only_once(self):
        first, second = self.row(), self.row(2)
        prediction = source_record(first)
        matched, used = entry_diagnostics([first, second], [prediction])
        self.assertEqual(matched, [[0, None], [0, None]])
        self.assertEqual(used, [{0}, {0}])

    def test_lot_omission_is_explicit_separate_metric(self):
        row = self.row(volume=Decimal(".01"))
        prediction = {**source_record(row), "volume": 10}
        matched, used = entry_diagnostics([row], [prediction])
        self.assertEqual(matched, [[None], [0]])
        self.assertEqual(used, [set(), {0}])

    def test_no_second_tolerance_or_wrong_side_price_matching(self):
        row = self.row()
        predicted = source_record(row)
        for changed in ({"open_second": predicted["open_second"] + 1}, {"side": "sell"}, {"open_price": "100.13"}):
            matched, _ = entry_diagnostics([row], [{**predicted, **changed}])
            self.assertEqual(matched, [[None], [None]])

    def test_vector_rejects_invalid_quotes_instead_of_dropping(self):
        for bids, asks in (([1, np.nan], [1.2, 1.2]), ([1, 2], [1.2, 1.5]), ([1, 0], [1.2, .2])):
            with self.assertRaises(ValueError):
                replay_pending(np.array([0, 1]), np.array(bids), np.array(asks), PendingStopConfig())


if __name__ == "__main__":
    unittest.main()
