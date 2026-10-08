"""Narrow scope controls, causal replay, past-quote and predecessor boundaries."""

import unittest

import numpy as np

from diagnose_quote_paths import QuoteIndex
from first001_components import controls, entry_record, predecessor_index
from replay_pending_vector import replay_pending
from test_candle_grid_replay import censor
from test_pending_stop import reference_pending


def row(ticket=1, opening=2, closing=5, price="100.3", side="buy", close_price="100"):
    return {"ticket": ticket, "symbol": "XAUUSD+", "trade_type": side, "volume": ".01",
            "open_time": f"1970-01-01T03:00:{opening:02d}+00:00", "close_time": f"1970-01-01T03:00:{closing:02d}+00:00",
            "open_price": price, "close_price": close_price}


def observe(r, times, bids, asks, previous=()):
    closes, close_times = predecessor_index(list(previous))
    return entry_record(r, times, bids, asks, closes, close_times, (QuoteIndex(bids), QuoteIndex(asks)))


class First001Tests(unittest.TestCase):
    def test_four_frozen_configs_first_lot_guard_and_fields(self):
        configs = list(controls())
        self.assertEqual(len(configs), 4)
        self.assertEqual({(c.entry_fill_mode, c.execution.stop_fill_mode) for c in configs},
                         {("level", "level"), ("level", "quote"), ("quote", "level"), ("quote", "quote")})
        self.assertTrue(all(c.execution.volume == .01 and c.require_valid_trail and c.anchor_mode == "fixed_close"
                            and c.opposite_policy == "oco" and c.execution.trailing_activation_points == 16 for c in configs))

    def test_all_four_reference_parity_and_changed_future_prefix(self):
        rng = np.random.default_rng(1000)
        times = np.arange(5000, dtype=np.int64) * 1000
        bids = np.round(1000 + np.cumsum(rng.normal(0, .3, len(times))), 2)
        asks = bids + .22
        for c in controls():
            actual = replay_pending(times, bids, asks, c, chunk_size=37)
            self.assertEqual(actual, reference_pending(times, bids, asks, c))
            past = replay_pending(times[:2000], bids[:2000], asks[:2000], c)
            altered = bids.copy()
            altered[2000:] += 100
            changed = replay_pending(times, altered, altered + .22, c)
            self.assertEqual(past, censor(actual, 2000000))
            self.assertEqual(past, censor(changed, 2000000))

    def test_buy_bid_match_is_not_executable_ask_match(self):
        times = np.array([0, 1000, 2000, 2500, 3000])
        bids = np.array([100, 100.1, 100.3, 100.4, 200])
        asks = bids + .2
        result = observe(row(), times, bids, asks)
        self.assertTrue(result["source_price_seen_on_bid_in_reported_second"])
        self.assertFalse(result["source_price_seen_on_executable_side_in_reported_second"])
        self.assertEqual(result["past_quote"]["time_ms"], 1000)
        self.assertAlmostEqual(result["past_signed_returns"]["1"], .1)

    def test_past_quote_excludes_same_second_even_duplicate_milliseconds(self):
        times = np.array([0, 1000, 2000, 2000, 3000])
        bids = np.array([100, 100.1, 900, 1000, 2000])
        result = observe(row(), times, bids, bids + .2)
        self.assertEqual(result["past_quote"]["bid"], 100.1)
        self.assertEqual(result["opening_second_quote_count"], 2)

    def test_same_second_and_future_closes_never_become_strict_predecessor(self):
        times = np.arange(5) * 1000
        bids = np.array([100, 100, 100, 100, 100])
        previous = [row(2, 0, 0, close_price="99"), row(3, 1, 2, close_price="999"), row(4, 1, 4, close_price="9999")]
        result = observe(row(), times, bids, bids + .2, previous)
        self.assertEqual(result["latest_strict_source_predecessor"]["distinct_prices"], ["99"])

    def test_distinct_simultaneous_close_prices_are_not_selected_by_ticket(self):
        times = np.arange(5) * 1000
        bids = np.array([100, 100, 100, 100, 100])
        previous = [row(2, 0, 0, close_price="99"), row(3, 0, 0, close_price="101")]
        result = observe(row(), times, bids, bids + .2, previous)
        self.assertTrue(result["latest_strict_source_predecessor"]["price_ambiguous"])
        self.assertIsNone(result["nominal_price1_cross_before_entry"])

    def test_threshold_witness_is_conditional_and_future_extension_no_change(self):
        times = np.arange(6) * 1000
        bids = np.array([100, 100.3, 101.1, 100.2, 102, 999])
        previous = [row(2, 0, 0)]
        first = observe(row(opening=4), times[:5], bids[:5], bids[:5] + .2, previous)
        second = observe(row(opening=4), times, bids, bids + .2, previous)
        self.assertEqual(first, second)
        witness = first["nominal_price1_cross_before_entry"]
        self.assertEqual(witness["first_cross_ms"], 2000)
        self.assertTrue(witness["conditional_actual_predecessor_NOT_causal_prediction"])

    def test_empty_open_second_remains_record_with_unknown_quote(self):
        times = np.array([0, 1000, 5000])
        bids = np.array([100, 100.1, 102])
        result = observe(row(), times, bids, bids + .2)
        self.assertEqual(result["opening_second_quote_count"], 0)
        self.assertIsNone(result["first_quote_of_reported_second"])
        self.assertTrue(result["not_strategy_prediction"])


if __name__ == "__main__":
    unittest.main()
