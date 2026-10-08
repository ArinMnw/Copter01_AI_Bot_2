import unittest
from datetime import datetime

from strict_source_matcher import enrich_prediction, match_exact


class StrictMatcherTests(unittest.TestCase):
    def setUp(self):
        self.source = {"ticket": 1, "symbol": "XAUUSD+", "trade_type": "buy", "volume": 10,
                       "open_time": "2026-10-08T01:04:15+00:00", "close_time": "2026-10-08T01:04:20+00:00",
                       "open_price": 100., "close_price": 100.1, "pips": 10, "profit": 100., "comment": "[sl 100.10]"}
        opening = int(datetime.fromisoformat(self.source["open_time"]).timestamp()) - 10800
        self.prediction = enrich_prediction({"open_ms": opening * 1000 + 50, "close_ms": (opening + 5) * 1000 + 100,
                                             "side": "buy", "volume": 10, "open_price": 100., "close_price": 100.1},
                                            "XAUUSD+", "sl")

    def test_exact_complete_observable_fields_only(self):
        matched, extra, summary = match_exact([self.source], [self.prediction])
        self.assertEqual(matched[0]["exact_prediction_index"], 0)
        self.assertEqual(extra, [])
        self.assertTrue(summary["complete"])

    def test_every_field_mismatch_counts_missing_and_extra(self):
        for field, value in (("symbol", "FixedVol20"), ("side", "sell"), ("volume", 1),
                             ("open_second", self.prediction["open_second"] + 1),
                             ("close_second", self.prediction["close_second"] + 1),
                             ("open_price", "100.01"), ("close_price", "100.11"),
                             ("pips", "11"), ("gross_profit", "100.01"), ("close_behavior", "tp")):
            predicted = {**self.prediction, field: value}
            _, _, summary = match_exact([self.source], [predicted])
            with self.subTest(field=field):
                self.assertEqual(summary["exact_all_observable_fields"], 0)
                self.assertEqual(summary["missing"], 1)
                self.assertEqual(summary["extra"], 1)

    def test_duplicate_prediction_is_not_reused(self):
        _, extra, summary = match_exact([self.source], [self.prediction, self.prediction])
        self.assertEqual(summary["missing"], 0)
        self.assertEqual(summary["extra"], 1)
        self.assertFalse(summary["complete"])
        self.assertEqual(extra, [1])

    def test_all_symbols_stay_in_denominator(self):
        fixed = {**self.source, "ticket": 2, "symbol": "FixedVol20", "volume": .1, "profit": .01}
        matches, _, summary = match_exact([self.source, fixed], [self.prediction])
        self.assertEqual(len(matches), 2)
        self.assertEqual(summary["missing"], 1)
        self.assertEqual(summary["source_orders"], 2)

    def test_unknown_source_behavior_cannot_be_certified(self):
        unknown = {**self.source, "comment": ""}
        predicted = {**self.prediction, "close_behavior": "unverified_source_behavior"}
        _, _, summary = match_exact([unknown], [predicted])
        self.assertEqual(summary["exact_all_observable_fields"], 0)
        self.assertEqual(summary["unknown_source_close_behavior"], 1)
        self.assertFalse(summary["complete"])


if __name__ == "__main__":
    unittest.main()
