"""Paper pending chronology, gap fills, hedge lifecycle and causal parity."""

import copy
import unittest
from datetime import datetime, timedelta, timezone

import numpy as np

from replay_pending_vector import replay_pending
from strategy_scalping456 import PendingStopConfig, PendingStopStrategy, Scalping456Config, Side, Tick
from test_candle_grid_replay import censor


def reference_pending(times, bids, asks, config):
    strategy = PendingStopStrategy(config)
    predictions = []
    for instant, bid, ask in zip(times, bids, asks):
        events = strategy.on_tick(Tick(datetime.fromtimestamp(int(instant) / 1000, timezone.utc), float(bid), float(ask)))
        for event in events:
            if event.action == "entry":
                assert event.position_id == len(predictions)
                predictions.append({"open_ms": int(instant), "close_ms": None, "side": event.side.value,
                                    "volume": event.volume, "open_price": event.price, "close_price": None})
            else:
                predictions[event.position_id]["close_ms"] = int(instant)
                predictions[event.position_id]["close_price"] = event.price
    return predictions


def candidates():
    for anchor in ("fixed_close", "rolling_extrema"):
        for policy in ("oco", "retain"):
            for entry_fill in ("level", "quote"):
                for stop_fill in ("level", "quote"):
                    for activation, distance in ((40, 30), (16, 16)):
                        execution = Scalping456Config(trailing_activation_points=activation, trailing_distance_points=distance,
                                                       stop_fill_mode=stop_fill)
                        yield PendingStopConfig(anchor, policy, entry_fill_mode=entry_fill, execution=execution)


class PendingStopTests(unittest.TestCase):
    def tick(self, bid, ask, second=0):
        return Tick(datetime(2026, 9, 7, tzinfo=timezone.utc) + timedelta(seconds=second), bid, ask)

    def test_config_validation(self):
        for kwargs in ({"anchor_mode": "source_ticket"}, {"opposite_policy": "future"}, {"entry_fill_mode": "copied"},
                       {"entry_distance_price": 0}, {"price_digits": -1}, {"execution": None}):
            with self.assertRaises(ValueError):
                PendingStopConfig(**kwargs)

    def test_pending_created_before_fill_even_with_duplicate_timestamp(self):
        strategy = PendingStopStrategy(PendingStopConfig())
        self.assertEqual(strategy.on_tick(self.tick(100, 100.2)), [])
        self.assertEqual(len(strategy.pending), 2)
        events = strategy.on_tick(self.tick(101.2, 101.4))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].action, "entry")
        self.assertEqual(events[0].price, 101.1)
        self.assertEqual(len(strategy.pending), 0)

    def test_invalid_placement_never_retroactively_filled(self):
        strategy = PendingStopStrategy(PendingStopConfig())
        self.assertEqual(strategy.on_tick(self.tick(98, 102)), [])
        self.assertEqual(strategy.pending, {})
        self.assertEqual(strategy.on_tick(self.tick(99.5, 100.5, 1)), [])
        self.assertEqual(len(strategy.pending), 2)
        self.assertEqual(strategy.on_tick(self.tick(100.8, 101.2, 2))[0].price, 101)

    def test_oco_and_retained_both_breached_with_deterministic_priority(self):
        for policy in ("oco", "retain"):
            strategy = PendingStopStrategy(PendingStopConfig(opposite_policy=policy))
            strategy.on_tick(self.tick(100, 100.2))
            events = strategy.on_tick(self.tick(98, 102, 1))
            self.assertEqual(events[0].side, Side.SELL)
            self.assertEqual(len(events), 1 if policy == "oco" else 2)
            self.assertTrue(all(event.action == "entry" for event in events))
            self.assertEqual(len(strategy.positions), len(events))
            exits = strategy.on_tick(self.tick(98, 102, 2))
            self.assertEqual(sum(e.action == "exit" for e in exits), len(events))

    def test_retained_opposite_and_freed_side_rearm(self):
        execution = Scalping456Config(trailing_activation_points=9999)
        strategy = PendingStopStrategy(PendingStopConfig(opposite_policy="retain", execution=execution))
        strategy.on_tick(self.tick(100, 100.2))
        strategy.on_tick(self.tick(101, 101.2, 1))
        opposite = strategy.pending[Side.SELL]
        strategy.on_tick(self.tick(100.1, 100.3, 2))
        self.assertEqual(strategy.pending[Side.SELL], opposite)
        self.assertIn(Side.BUY, strategy.pending)
        self.assertEqual(strategy.on_tick(self.tick(99, 99.2, 3))[0].side, Side.SELL)
        events = strategy.on_tick(self.tick(101.2, 101.4, 4))
        self.assertEqual([e.action for e in events], ["exit", "entry"])
        self.assertEqual(events[-1].side, Side.BUY)

    def test_rolling_replacement_is_past_quote_only(self):
        strategy = PendingStopStrategy(PendingStopConfig(anchor_mode="rolling_extrema"))
        strategy.on_tick(self.tick(100, 100.2))
        self.assertEqual(strategy.on_tick(self.tick(99.5, 99.7, 1)), [])
        self.assertEqual(strategy.pending[Side.BUY].price, 100.7)
        self.assertEqual(strategy.pending[Side.BUY].created_quote_sequence, 2)
        self.assertEqual(strategy.on_tick(self.tick(100.5, 100.7, 2))[0].price, 100.7)

    def test_level_entry_gap_does_not_trail_on_opening_quote(self):
        config = PendingStopConfig()
        times = 1788739200000 + np.arange(5) * 1000
        bids = np.array([100, 105, 104, 103.9, 104])
        asks = bids + .2
        expected = reference_pending(times, bids, asks, config)
        self.assertEqual(expected[0]["open_price"], 101.1)
        self.assertEqual(expected[0]["close_ms"], int(times[3]))
        self.assertAlmostEqual(expected[0]["close_price"], 104.7)
        self.assertEqual(replay_pending(times, bids, asks, config, chunk_size=2), expected)

    def test_out_of_order_rejected_without_state_change(self):
        strategy = PendingStopStrategy(PendingStopConfig())
        strategy.on_tick(self.tick(100, 100.2, 2))
        before = copy.deepcopy(strategy.__dict__)
        with self.assertRaises(ValueError):
            strategy.on_tick(self.tick(100, 100.2, 1))
        self.assertEqual(before, strategy.__dict__)

    def test_all32_full_field_reference_parity_synthetic_gaps_spread(self):
        rng = np.random.default_rng(456)
        times = 1788739200000 + np.arange(10000, dtype=np.int64) * 1000
        change = rng.normal(0, .2, len(times))
        change[::197] += rng.choice([-4, 4], len(change[::197]))
        bids = np.round(1000 + np.cumsum(change), 2)
        spread = rng.choice([.1, .2, .3, 2.5], len(times), p=[.1, .6, .29, .01])
        asks = np.round(bids + spread, 2)
        for config in candidates():
            with self.subTest(config=config):
                expected = reference_pending(times, bids, asks, config)
                actual = replay_pending(times, bids, asks, config, chunk_size=37)
                self.assertEqual(actual, expected)

    def test_all32_future_prefix_and_changed_future_quotes(self):
        rng = np.random.default_rng(456)
        times = 1788739200000 + np.arange(5000, dtype=np.int64) * 1000
        bids = np.round(1000 + np.cumsum(rng.normal(0, .2, len(times))), 2)
        asks = np.round(bids + .2, 2)
        cut = 2000
        changed = bids.copy()
        changed[cut:] = np.round(1000 + np.cumsum(rng.normal(0, 2, len(times) - cut)), 2)
        for config in candidates():
            with self.subTest(config=config):
                prefix = replay_pending(times[:cut], bids[:cut], asks[:cut], config, chunk_size=13)
                full = replay_pending(times, bids, asks, config, chunk_size=41)
                altered = replay_pending(times, changed, np.round(changed + .2, 2), config, chunk_size=7)
                self.assertEqual(prefix, censor(full, int(times[cut])))
                self.assertEqual(prefix, censor(altered, int(times[cut])))


if __name__ == "__main__":
    unittest.main()
