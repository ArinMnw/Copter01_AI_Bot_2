"""Reference parity and causality checks, entirely offline."""

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import numpy as np

from replay_candle_grid_vector import replay_closed_candidate, replay_grid_candidate
from strategy_scalping456 import (BasketEntrySignal, BasketExitSignal, ClosedBar, ClosedCandleConfig,
                                   ClosedCandleStrategy, EntrySignal, ExitSignal, FixedVol20Config,
                                   FixedVol20GridStrategy, Scalping456Config, Tick)


BASE = datetime(2026, 9, 7, tzinfo=timezone.utc)


def bar_arrays(bars):
    return {"open_ms": np.array([round(bar.open_time.timestamp() * 1000) for bar in bars]),
            "close_ms": np.array([round(bar.close_time.timestamp() * 1000) for bar in bars]),
            **{name: np.array([getattr(bar, name) for bar in bars]) for name in ("open", "high", "low", "close")}}


def reference_closed(times, bids, asks, bars, candle, execution):
    strategy = ClosedCandleStrategy(candle, execution)
    results, pending, index = [], None, 0
    for time_ms, bid, ask in zip(times, bids, asks):
        current = Tick(datetime.fromtimestamp(int(time_ms) / 1000, timezone.utc), float(bid), float(ask))
        available = []
        while index < len(bars) and bars[index].close_time <= current.time:
            available.append(bars[index])
            index += 1
        signal = strategy.on_tick(current, tuple(available))
        if isinstance(signal, EntrySignal):
            pending = {"open_ms": int(time_ms), "side": signal.side.value, "volume": signal.volume, "open_price": signal.price}
        elif isinstance(signal, ExitSignal):
            results.append({**pending, "close_ms": int(time_ms), "close_price": signal.price})
            pending = None
    if pending:
        results.append({**pending, "close_ms": None, "close_price": None})
    return results


def reference_grid(times, bids, asks, config):
    strategy = FixedVol20GridStrategy(config)
    results, pending = [], []
    for time_ms, bid, ask in zip(times, bids, asks):
        signal = strategy.on_tick(Tick(datetime.fromtimestamp(int(time_ms) / 1000, timezone.utc), float(bid), float(ask)))
        if isinstance(signal, BasketEntrySignal):
            pending.append({"open_ms": int(time_ms), "side": signal.side.value, "volume": signal.volume, "open_price": signal.price})
        elif isinstance(signal, BasketExitSignal):
            results.extend({**leg, "close_ms": int(time_ms), "close_price": signal.price} for leg in pending)
            pending = []
    results.extend({**leg, "close_ms": None, "close_price": None} for leg in pending)
    return results


def censor(results, end_ms):
    return [{**row, **({"close_ms": None, "close_price": None} if row["close_ms"] is not None and row["close_ms"] >= end_ms else {})}
            for row in results if row["open_ms"] < end_ms]


class CandleGridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(456)
        cls.times = round(BASE.timestamp() * 1000) + np.arange(20000, dtype=np.int64) * 1000
        cls.bids = np.round(1000 + np.cumsum(rng.normal(0, .25, len(cls.times))), 2)
        cls.asks = cls.bids + .2

    def synthetic_bars(self, minutes):
        bars = []
        length = minutes * 60
        for index in range(0, len(self.times), length):
            prices = self.bids[index:index + length]
            bars.append(ClosedBar(BASE + timedelta(seconds=index), minutes, float(prices[0]),
                                  float(prices.max()), float(prices.min()), float(prices[-1])))
        return bars

    def test_all_five_timeframes_three_modes_reference_parity(self):
        for minutes in (1, 5, 15, 30, 60):
            bars = self.synthetic_bars(minutes)
            arrays = bar_arrays(bars)
            for mode in ("body", "engulf", "breakout"):
                for fill in ("level", "quote"):
                    candle = ClosedCandleConfig(minutes, mode)
                    execution = Scalping456Config(stop_fill_mode=fill)
                    expected = reference_closed(self.times, self.bids, self.asks, bars, candle, execution)
                    actual = replay_closed_candidate(self.times, self.bids, self.asks, arrays, candle, execution, chunk_size=37)
                    with self.subTest(minutes=minutes, mode=mode, fill=fill):
                        self.assertEqual(expected, actual)

    def test_future_bar_rejected_without_consuming_batch(self):
        strategy = ClosedCandleStrategy()
        ready = ClosedBar(BASE - timedelta(minutes=1), 1, 100, 102, 99, 101)
        future = ClosedBar(BASE, 1, 101, 103, 100, 102)
        with self.assertRaises(ValueError):
            strategy.on_tick(Tick(BASE, 100, 100.2), (ready, future))
        self.assertEqual(list(strategy.closed_bars), [])
        self.assertIsNone(strategy.last_tick_time)

    def test_future_extension_and_changed_future_ohlc_do_not_change_prefix(self):
        cut = 5100
        end = int(self.times[cut])
        for minutes in (1, 5, 15, 30, 60):
            bars = self.synthetic_bars(minutes)
            changed = [replace(bar, high=bar.high + 100, close=bar.close + 100) if bar.close_time.timestamp() * 1000 >= end else bar for bar in bars]
            for mode in ("body", "engulf", "breakout"):
                candle, execution = ClosedCandleConfig(minutes, mode), Scalping456Config()
                prefix = replay_closed_candidate(self.times[:cut], self.bids[:cut], self.asks[:cut], bar_arrays(bars), candle, execution)
                extended = replay_closed_candidate(self.times, self.bids, self.asks, bar_arrays(changed), candle, execution)
                self.assertEqual(prefix, censor(extended, end))

    def test_body_one_entry_per_closed_bar_and_no_same_tick_reentry(self):
        strategy = ClosedCandleStrategy()
        closed = ClosedBar(BASE - timedelta(minutes=1), 1, 100, 102, 99, 101)
        self.assertIsInstance(strategy.on_tick(Tick(BASE, 100, 100.2), (closed,)), EntrySignal)
        self.assertIsInstance(strategy.on_tick(Tick(BASE + timedelta(seconds=1), 99, 99.2)), ExitSignal)
        self.assertIsNone(strategy.on_tick(Tick(BASE + timedelta(seconds=2), 101, 101.2)))

    def test_grid_all_sixteen_configurations_parity_and_prefix(self):
        for step in (3., 15.):
            for fixed in (False, True):
                for mode in ("fixed_close", "rolling_extrema"):
                    for fill in ("quote", "level"):
                        config = FixedVol20Config(grid_step_price=step, basket_target_price=step,
                                                 fixed_volume=fixed, entry_mode=mode, grid_fill_mode=fill, target_rounding="half_up")
                        expected = reference_grid(self.times, self.bids, self.asks, config)
                        actual = replay_grid_candidate(self.times, self.bids, self.asks, config, chunk_size=37)
                        with self.subTest(step=step, fixed=fixed, mode=mode, fill=fill):
                            self.assertEqual(expected, actual)
                            cut = 5100
                            prefix = replay_grid_candidate(self.times[:cut], self.bids[:cut], self.asks[:cut], config)
                            self.assertEqual(prefix, censor(actual, int(self.times[cut])))

    def test_pending_grid_level_preexists_crossing_and_tp_priority(self):
        config = FixedVol20Config(grid_step_price=3, basket_target_price=3, grid_fill_mode="level", target_rounding="half_up")
        strategy = FixedVol20GridStrategy(config)
        strategy.on_tick(Tick(BASE, 100, 100.2))
        self.assertEqual(strategy.on_tick(Tick(BASE + timedelta(seconds=1), 103, 103.2)).price, 103.2)
        add = strategy.on_tick(Tick(BASE + timedelta(seconds=2), 98, 98.2))
        self.assertAlmostEqual(add.price, 100.2)
        self.assertEqual(add.volume, .2)
        self.assertAlmostEqual(add.basket_take_profit, 104.2)
        self.assertIsInstance(strategy.on_tick(Tick(BASE + timedelta(seconds=3), 105, 105.2)), BasketExitSignal)

    def test_wrong_timeframe_duplicate_bar_and_invalid_ohlc_rejected(self):
        with self.assertRaises(ValueError):
            ClosedBar(BASE, 1, 100, 99, 98, 100)
        strategy = ClosedCandleStrategy()
        wrong = ClosedBar(BASE - timedelta(minutes=5), 5, 100, 102, 99, 101)
        with self.assertRaises(ValueError):
            strategy.on_tick(Tick(BASE, 100, 100.2), (wrong,))
        ready = replace(wrong, open_time=BASE - timedelta(minutes=1), minutes=1)
        strategy.on_tick(Tick(BASE, 100, 100.2), (ready,))
        with self.assertRaises(ValueError):
            strategy.on_tick(Tick(BASE + timedelta(seconds=1), 100, 100.2), (ready,))


if __name__ == "__main__":
    unittest.main()
