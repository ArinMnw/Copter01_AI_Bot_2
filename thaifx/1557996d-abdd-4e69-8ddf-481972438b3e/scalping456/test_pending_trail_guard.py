"""Wrong-side modification rejection, existing-stop priority and causal parity."""

import unittest
from dataclasses import replace

import numpy as np

from replay_pending_vector import replay_pending
from strategy_scalping456 import PendingStopConfig
from test_candle_grid_replay import censor
from test_pending_stop import candidates, reference_pending


class PendingTrailGuardTests(unittest.TestCase):
    def test_buy_gap_rejects_invalid_proposal_until_market_allows(self):
        times = 1788739200000 + np.arange(6) * 1000
        bids = np.array([100, 105, 104, 103.9, 105, 104.6])
        asks = bids + .2
        config = PendingStopConfig(require_valid_trail=True)
        expected = reference_pending(times, bids, asks, config)
        self.assertEqual(expected[0]["close_ms"], int(times[5]))
        self.assertAlmostEqual(expected[0]["close_price"], 104.7)
        self.assertEqual(replay_pending(times, bids, asks, config, chunk_size=2), expected)
        legacy = reference_pending(times, bids, asks, replace(config, require_valid_trail=False))
        self.assertEqual(legacy[0]["close_ms"], int(times[3]))

    def test_sell_gap_rejects_invalid_proposal_until_market_allows(self):
        times = 1788739200000 + np.arange(6) * 1000
        bids = np.array([100, 95, 96, 96.1, 95, 95.4])
        asks = bids + .2
        config = PendingStopConfig(require_valid_trail=True)
        expected = reference_pending(times, bids, asks, config)
        self.assertEqual(expected[0]["side"], "sell")
        self.assertEqual(expected[0]["close_ms"], int(times[5]))
        self.assertAlmostEqual(expected[0]["close_price"], 95.5)
        self.assertEqual(replay_pending(times, bids, asks, config, chunk_size=2), expected)

    def test_existing_stop_breach_cannot_be_rescued_by_guard(self):
        times = 1788739200000 + np.arange(4) * 1000
        bids = np.array([100, 105, 105, 104.6])
        asks = bids + .2
        config = PendingStopConfig(require_valid_trail=True)
        expected = reference_pending(times, bids, asks, config)
        self.assertEqual(expected[0]["close_ms"], int(times[3]))
        self.assertEqual(replay_pending(times, bids, asks, config, chunk_size=2), expected)

    def test_guard_config_requires_boolean(self):
        with self.assertRaises(ValueError):
            PendingStopConfig(require_valid_trail="source")

    def test_all32_guarded_full_field_reference_parity(self):
        rng = np.random.default_rng(456)
        times = 1788739200000 + np.arange(5000, dtype=np.int64) * 1000
        changes = rng.normal(0, .2, len(times))
        changes[::97] += rng.choice([-4, 4], len(changes[::97]))
        bids = np.round(1000 + np.cumsum(changes), 2)
        asks = np.round(bids + rng.choice([.1, .2, 2.5], len(times), p=[.2, .79, .01]), 2)
        for config in candidates():
            config = replace(config, require_valid_trail=True)
            with self.subTest(config=config):
                self.assertEqual(replay_pending(times, bids, asks, config, chunk_size=37), reference_pending(times, bids, asks, config))

    def test_all32_guarded_changed_future_prefix(self):
        rng = np.random.default_rng(456)
        times = 1788739200000 + np.arange(3000, dtype=np.int64) * 1000
        bids = np.round(1000 + np.cumsum(rng.normal(0, .3, len(times))), 2)
        asks = np.round(bids + .2, 2)
        cut = 1000
        altered = bids.copy()
        altered[cut:] = np.round(1000 + np.cumsum(rng.normal(0, 2, len(times) - cut)), 2)
        for config in candidates():
            config = replace(config, require_valid_trail=True)
            with self.subTest(config=config):
                prefix = replay_pending(times[:cut], bids[:cut], asks[:cut], config, chunk_size=11)
                full = replay_pending(times, bids, asks, config, chunk_size=37)
                changed = replay_pending(times, altered, np.round(altered + .2, 2), config, chunk_size=5)
                self.assertEqual(prefix, censor(full, int(times[cut])))
                self.assertEqual(prefix, censor(changed, int(times[cut])))


if __name__ == "__main__":
    unittest.main()
