import unittest
from datetime import datetime, timezone

import numpy as np

from replay_vector import replay_candidate
from strategy_scalping456 import EntrySignal, ExitSignal, Scalping456Config, Scalping456Strategy, Tick
from test_candle_grid_replay import censor
from test_vantage_readonly import FakeConnector
from vantage_readonly import attach


class BrokerBarsTrialTests(unittest.TestCase):
    def test_timeframes_read_through_same_account_guard_without_selection(self):
        connector = FakeConnector()
        for name, value in (("TIMEFRAME_M5", 5), ("TIMEFRAME_M15", 15), ("TIMEFRAME_M30", 30), ("TIMEFRAME_H1", 16385)):
            setattr(connector, name, value)
        def rates(*args):
            connector.calls.append(("copy_rates_range", args))
            return []
        connector.copy_rates_range = rates
        with attach(connector=connector, process_check=lambda _: [123]) as reader:
            for minutes in (1, 5, 15, 30, 60):
                self.assertEqual(reader.rates("XAUUSD", minutes, None, None), [])
            with self.assertRaises(ValueError):
                reader.rates("XAUUSD", 2, None, None)
        self.assertEqual(sum(call[0] == "copy_rates_range" for call in connector.calls), 5)
        self.assertEqual(connector.calls[-1], ("shutdown",))

    def test_fixed_trial_both_fills_reference_parity_and_future_prefix(self):
        rng = np.random.default_rng(456)
        times = 1788739200000 + np.arange(30000, dtype=np.int64) * 1000
        bids = np.round(1000 + np.cumsum(rng.normal(0, .3, len(times))), 3)
        asks = bids + .585
        for fill in ("level", "quote"):
            config = Scalping456Config.fixedvol20_trial(entry_reversal_points=300, trailing_activation_points=0,
                                                       trailing_distance_points=1000, stop_fill_mode=fill)
            strategy = Scalping456Strategy(config)
            expected, pending = [], None
            for instant, bid, ask in zip(times, bids, asks):
                signal = strategy.on_tick(Tick(datetime.fromtimestamp(int(instant) / 1000, timezone.utc), float(bid), float(ask)))
                if isinstance(signal, EntrySignal):
                    pending = {"open_ms": int(instant), "side": signal.side.value, "volume": signal.volume, "open_price": signal.price}
                elif isinstance(signal, ExitSignal):
                    expected.append({**pending, "close_ms": int(instant), "close_price": signal.price})
                    pending = None
            if pending:
                expected.append({**pending, "close_ms": None, "close_price": None})
            actual = replay_candidate(times, bids, asks, config, chunk_size=37)
            with self.subTest(fill=fill):
                self.assertEqual(actual, expected)
                prefix = replay_candidate(times[:10100], bids[:10100], asks[:10100], config)
                self.assertEqual(prefix, censor(actual, int(times[10100])))


if __name__ == "__main__":
    unittest.main()
