import copy
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mq5_strategy" / "ea2.1"))
from ea_strategy_2_1 import DEFAULT_CFG, advance_live_state
from ea_strategy_2 import run_backtest
import live_ea2_1 as adapter


class LiveParityTest(unittest.TestCase):
    def test_adapter_filters_before_cycle_commit(self):
        bars = [dict(time=1700000100 + i * 300, open=9, high=12, low=8, close=11)
                for i in range(512)]
        initial = dict(version=2, last_bar_time=bars[-2]["time"], trend=1,
                       awaiting_confirm=True, bos_count=0, entry_done_cycle=False,
                       ref_high=10, ref_low=1, last_bear_ob_high=1000,
                       last_bull_ob_low=1, swing_highs=[], swing_lows=[], order_blocks=[])
        mt5 = NS(symbol_info_tick=lambda symbol: NS(ask=11.01, bid=11),
                 symbol_info=lambda symbol: NS(point=.01, digits=2, volume_min=.01,
                    volume_max=100, volume_step=.01, trade_tick_size=.01, trade_tick_value=1),
                 account_info=lambda: NS(balance=10000), positions_get=lambda **kw: [])
        for allowed in (False, True):
            with self.subTest(allowed=allowed), \
                    patch.object(adapter, "_load_state", return_value=copy.deepcopy(initial)), \
                    patch.object(adapter, "_atomic_save") as save, \
                    patch.object(adapter, "make_entry_filter", return_value=lambda *args: allowed):
                signal = adapter.detect_ea2_1(bars, tf="M5", mt5=mt5, cfg=NS(),
                                               symbol="XAUUSDm", htf_rates=bars[-200:])
                self.assertEqual(signal["signal"], "BUY" if allowed else "WAIT")
                saved = save.call_args.args[1]
                self.assertEqual(saved["entry_done_cycle"], allowed)
                self.assertEqual(saved["ea21_last_accepted_time"], bars[-1]["time"] if allowed else 0)

    def test_rejected_bos_does_not_consume_cycle(self):
        bars = [dict(time=i * 300, open=9, high=12, low=8, close=11) for i in range(12)]
        state = dict(version=2, last_bar_time=3000, trend=1, awaiting_confirm=True,
                     bos_count=0, entry_done_cycle=False, ref_high=10, ref_low=1,
                     last_bear_ob_high=1000, last_bull_ob_low=1,
                     swing_highs=[], swing_lows=[], order_blocks=[])
        for accepted in (False, True):
            with self.subTest(accepted=accepted):
                result, events = advance_live_state(bars, copy.deepcopy(state), DEFAULT_CFG,
                                                   entry_filter=lambda *args: accepted)
                self.assertEqual(result["entry_done_cycle"], accepted)
                self.assertEqual(len(events), int(accepted))

    def test_m5_deeper_ob_age_uses_bars_not_minutes(self):
        bars = [dict(time=i * 300, open=9, high=10, low=8, close=9) for i in range(22)]
        obs = [dict(high=10, low=8, bullish=True, active=True, in_zone=False,
                    created_time=0, from_choch=False, fib50=9),
               dict(high=9, low=7, bullish=True, active=True, in_zone=False,
                    created_time=0, from_choch=False, fib50=9)]
        state = dict(version=2, last_bar_time=6000, trend=1, awaiting_confirm=False,
                     bos_count=0, entry_done_cycle=False, ref_high=1000, ref_low=1,
                     last_bear_ob_high=1000, last_bull_ob_low=1,
                     swing_highs=[], swing_lows=[], order_blocks=obs)
        cfg = dict(DEFAULT_CFG, OB_MAX_BARS_VALID=50, POINT=.01)
        result, events = advance_live_state(bars, state, cfg)
        self.assertEqual(len(events), 1)
        self.assertTrue(result["order_blocks"][0]["active"])
        self.assertFalse(result["order_blocks"][1]["active"])

    def test_rejected_retest_does_not_consume_cycle(self):
        bars = [dict(time=i * 300, open=9, high=10, low=8, close=9) for i in range(22)]
        state = dict(version=2, last_bar_time=6000, trend=1, awaiting_confirm=False,
                     entry_done_cycle=False, ref_high=1000, ref_low=1,
                     last_bear_ob_high=1000, last_bull_ob_low=1,
                     order_blocks=[dict(high=10, low=8, bullish=True, active=True,
                         in_zone=False, created_time=0, from_choch=False, fib50=9)])
        result, events = advance_live_state(bars, state, DEFAULT_CFG, entry_filter=lambda *args: False)
        self.assertFalse(result["entry_done_cycle"])
        self.assertFalse(result["order_blocks"][0]["active"])  # Same as backtest after retest.
        self.assertEqual(events, [])

    def test_streaming_events_match_backtest_with_rejections(self):
        bars = []
        for i in range(1400):
            price = 100 + 8 * math.sin(i / 11) + 3 * math.sin(i / 3)
            previous = bars[-1]["close"] if bars else price
            bars.append(dict(time=1700000100 + i * 300, open=previous,
                             high=max(price, previous) + .4,
                             low=min(price, previous) - .4, close=price))
        cfg = dict(DEFAULT_CFG, MAX_OPEN_POSITIONS=10000, SL_POINTS=1000000,
                   TP_POINTS=1000000, USE_BREAKEVEN=False, USE_TRAILING=False)
        accept = lambda buy, idx, raw: (raw // 300) % 4 == 0
        _, stats = run_backtest(bars, cfg, start_bar=510, spread=0, entry_filter=accept)
        state = None
        actual = []
        for i in range(510, len(bars) - 1):
            state, events = advance_live_state(bars[:i+1], state, cfg, entry_filter=accept)
            actual.extend((e["bar_time"], e["signal"], e["reason"]) for e in events)
        expected = [(bars[e["event_bar"]]["time"], e["signal"], e["reason"])
                    for e in stats["entry_events"]]
        self.assertGreater(len(expected), 0)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
