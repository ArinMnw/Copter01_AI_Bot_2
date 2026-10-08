"""Offline checks for analytic observations, not strategy reproduction tests."""

import unittest
from datetime import datetime, timezone
from decimal import Decimal

import numpy as np

from diagnose_quote_paths import QuoteIndex, analytic_barrier, path_record


class QuotePathTests(unittest.TestCase):
    def test_first_crossing_matches_brute_force(self):
        rng = np.random.default_rng(456)
        values = rng.integers(-10, 11, 1003).astype(float)
        for block in (1, 2, 7, 32, 1024):
            index = QuoteIndex(values, block)
            for _ in range(400):
                lo, hi = sorted(rng.integers(0, len(values) + 1, 2))
                level = float(rng.integers(-12, 13))
                for upper in (False, True):
                    for strict in (False, True):
                        q = values[lo:hi]
                        mask = (q > level + 1e-9 if strict else q >= level - 1e-9) if upper else (q < level - 1e-9 if strict else q <= level + 1e-9)
                        hits = np.flatnonzero(mask)
                        expected = int(lo + hits[0]) if len(hits) else None
                        self.assertEqual(index.first_crossing(lo, hi, level, upper, strict), expected)

    def test_empty_invalid_and_strict_equal(self):
        self.assertIsNone(QuoteIndex([]).first_crossing(0, 0, 1))
        index = QuoteIndex([1, 1, 1], 2)
        self.assertEqual(index.first_crossing(0, 3, 1), 0)
        self.assertIsNone(index.first_crossing(0, 3, 1, strict=True))
        self.assertIsNone(index.first_crossing(2, 1, 1))
        with self.assertRaises(ValueError):
            QuoteIndex([1], 0)
        with self.assertRaises(ValueError):
            QuoteIndex([[1]])
        with self.assertRaises(ValueError):
            index.first_crossing(-1, 3, 1)

    def test_barrier_uses_only_prior_extrema_and_stop_before_modify(self):
        self.assertEqual(analytic_barrier(np.array([.5]), 1, .4, .3), (None, None))
        at, level = analytic_barrier(np.array([.5, .21, .2, 10]), 1, .4, .3)
        self.assertEqual(at, 2)
        self.assertAlmostEqual(level, .2)
        self.assertEqual(analytic_barrier(np.array([-1, 100]), 1, .4, .3), (0, -1.0))
        self.assertEqual(analytic_barrier(np.array([]), 1, .4, .3), (None, None))

    def test_barrier_matches_sequential_reference_and_future_prefix(self):
        rng = np.random.default_rng(456)
        for activation, distance in ((.4, .3), (0, 10)):
            for _ in range(50):
                gains = np.cumsum(rng.normal(0, .12, 500))
                stop, best, expected = -1.0, -np.inf, (None, None)
                for i, gain in enumerate(gains):
                    if gain <= stop + 1e-9:
                        expected = (i, stop)
                        break
                    best = max(best, gain)
                    if best >= activation - 1e-9:
                        stop = max(stop, best - distance)
                actual = analytic_barrier(gains, 1, activation, distance)
                self.assertEqual(actual[0], expected[0])
                if actual[0] is not None:
                    self.assertAlmostEqual(actual[1], expected[1])
                prefix = gains[:40]
                before = analytic_barrier(prefix, 1, activation, distance)
                after = analytic_barrier(np.concatenate((prefix, [100, -100])), 1, activation, distance)
                if before[0] is not None:
                    self.assertEqual(before, after)
                else:
                    self.assertTrue(after[0] is None or after[0] >= 40)

    def row(self, symbol="XAUUSD+", side="buy", comment="[sl 99]", close=10):
        return {"ticket": 1, "symbol": symbol, "trade_type": side, "volume": Decimal(".1"),
                "open_time": "2026-09-07T03:00:00+00:00", "close_time": f"2026-09-07T03:00:{close:02d}+00:00",
                "open_price": Decimal("100"), "close_price": Decimal("100"), "pips": 0,
                "sl": Decimal("99"), "tp": Decimal("101"), "comment": comment}

    def record(self, row, seconds, bids, asks):
        start = round(datetime(2026, 9, 7, tzinfo=timezone.utc).timestamp() * 1000)
        times = start + np.array(seconds)
        return path_record(row, times, np.array(bids), np.array(asks), QuoteIndex(bids, 2), QuoteIndex(asks, 2), [])

    def test_interior_excludes_open_and_close_seconds_and_uses_bid(self):
        record = self.record(self.row(), [0, 999, 1000, 2000, 9999, 10000], [90, 90, 100, 98.8, 100.5, 90], [200] * 6)
        self.assertEqual(record["interior_quotes"], 3)
        self.assertAlmostEqual(record["mae_price_observed"], -1.2)
        self.assertEqual(record["quote_side"], "bid")
        self.assertTrue(record["initial_stop_benchmark"]["strict_beyond_nominal_plus10pct"]["at_least5s_early"])
        self.assertFalse(record["source_feed_identity_verified"])

    def test_sell_uses_ask_and_trial_distances_are_not_broker_points(self):
        record = self.record(self.row("FixedVol20", "sell", "[sl 110]"), [1000, 2000, 9000], [0, 0, 0], [100, 111.2, 100])
        self.assertEqual(record["quote_side"], "ask")
        self.assertAlmostEqual(record["mae_price_observed"], -11.2)
        self.assertEqual(record["initial_stop_benchmark"]["distance_price"], 10)
        self.assertTrue(record["initial_stop_benchmark"]["strict_beyond_nominal_plus10pct"]["at_least5s_early"])

    def test_tp_is_observation_not_initial_target_and_other_rows_retained(self):
        record = self.record(self.row("FixedVol20", comment="[tp 101]"), [1000, 2000], [100, 101], [200, 200])
        self.assertIsNone(record["initial_stop_benchmark"])
        self.assertTrue(record["final_reported_tp_witness"]["final_target_not_proven_to_exist_at_entry"])
        closeby = self.record(self.row(comment="#123 by #124"), [1000, 2000], [100, 101], [100, 101])
        self.assertEqual(closeby["source_comment"], "#123 by #124")
        self.assertEqual(closeby["cohort"], "xau_other")
        self.assertTrue(closeby["not_a_prediction_or_goal_success_metric"])

    def test_short_and_zero_duration_have_no_interior(self):
        for close in (0, 1):
            record = self.record(self.row(close=close), [0, 999, 1000], [90, 90, 90], [100, 100, 100])
            self.assertEqual(record["interior_quotes"], 0)
            self.assertIsNone(record["mfe_price_observed"])
            self.assertIsNone(record["initial_stop_benchmark"]["strict_beyond_nominal"]["first_inferred_ms"])


if __name__ == "__main__":
    unittest.main()
