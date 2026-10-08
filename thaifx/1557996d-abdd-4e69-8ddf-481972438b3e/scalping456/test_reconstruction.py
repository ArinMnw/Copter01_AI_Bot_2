"""Behavior tests; these do not establish fidelity to the original EA."""

import unittest
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from audit_ledger import build_audit
from audit_exception_paths import audit_close_by, audit_contracts, audit_portfolio
import numpy as np

from replay_causal import candidates, match_orders
from replay_vector import replay_candidate
from strategy_scalping456 import (
    BasketEntrySignal, BasketExitSignal, EntrySignal, ExitSignal,
    FixedVol20Config, FixedVol20GridStrategy, Scalping456Config,
    Scalping456Strategy, Side, Tick, CloseByPosition, settle_close_by,
)


BASE = datetime(2026, 9, 7, tzinfo=timezone.utc)


def tick(second, bid, ask=None):
    return Tick(BASE + timedelta(seconds=second), bid, bid if ask is None else ask)


class StrategyTests(unittest.TestCase):
    def test_fixedvol_trial_requires_unknown_parameters(self):
        with self.assertRaises(TypeError):
            Scalping456Config.fixedvol20_trial()
        config = Scalping456Config.fixedvol20_trial(
            entry_reversal_points=300, trailing_activation_points=0,
            trailing_distance_points=1000, stop_fill_mode="level")
        self.assertEqual((config.volume, config.initial_stop_price), (.1, 10))
        strategy = Scalping456Strategy(config)
        strategy.on_tick(tick(0, 100))
        self.assertEqual(strategy.on_tick(tick(1, 103)).volume, .1)
        strategy.on_tick(tick(2, 108))
        closed = strategy.on_tick(tick(3, 97))
        self.assertAlmostEqual(closed.price, 98)
        # A partially negative exit is possible in this unverified a<d candidate.
        self.assertAlmostEqual((closed.price - 103) / config.point, -500)

    def test_fixed_and_rolling_are_distinct(self):
        fixed = Scalping456Strategy(Scalping456Config(entry_mode="fixed_close"))
        rolling = Scalping456Strategy(Scalping456Config(entry_mode="rolling_extrema"))
        for strategy in (fixed, rolling):
            self.assertIsNone(strategy.on_tick(tick(0, 100)))
            self.assertIsNone(strategy.on_tick(tick(1, 99.5)))
        self.assertIsNone(fixed.on_tick(tick(2, 100.5)))
        self.assertEqual(rolling.on_tick(tick(2, 100.5)).side, Side.BUY)
        self.assertEqual(fixed.on_tick(tick(3, 101)).side, Side.BUY)

    def test_activation_and_ratchet(self):
        strategy = Scalping456Strategy()
        strategy.on_tick(tick(0, 100))
        entry = strategy.on_tick(tick(1, 101))
        self.assertIsInstance(entry, EntrySignal)
        strategy.on_tick(tick(2, 101.39))
        self.assertAlmostEqual(strategy.position.stop_loss, 100)
        strategy.on_tick(tick(3, 101.40))
        self.assertAlmostEqual(strategy.position.stop_loss, 101.10)
        strategy.on_tick(tick(4, 101.30))
        self.assertAlmostEqual(strategy.position.stop_loss, 101.10)
        exit_signal = strategy.on_tick(tick(5, 101.09))
        self.assertIsInstance(exit_signal, ExitSignal)
        self.assertAlmostEqual(exit_signal.price, 101.10)
        self.assertAlmostEqual(strategy.flat_reference_price, 101.10)

    def test_sell_activation(self):
        strategy = Scalping456Strategy()
        strategy.on_tick(tick(0, 100))
        self.assertEqual(strategy.on_tick(tick(1, 99)).side, Side.SELL)
        strategy.on_tick(tick(2, 98.6))
        self.assertAlmostEqual(strategy.position.stop_loss, 98.9)
        self.assertIsInstance(strategy.on_tick(tick(3, 98.91)), ExitSignal)

    def test_quote_execution_exposes_gap(self):
        strategy = Scalping456Strategy(Scalping456Config(stop_fill_mode="quote"))
        strategy.on_tick(tick(0, 100))
        strategy.on_tick(tick(1, 101))
        closed = strategy.on_tick(tick(2, 99.5))
        self.assertEqual(closed.stop_loss, 100)
        self.assertEqual(closed.price, 99.5)
        self.assertEqual(strategy.flat_reference_price, 99.5)

    def test_step_and_stop_priority(self):
        strategy = Scalping456Strategy(Scalping456Config(trailing_step_points=20))
        strategy.on_tick(tick(0, 100))
        strategy.on_tick(tick(1, 101))
        strategy.on_tick(tick(2, 101.5))
        self.assertAlmostEqual(strategy.position.stop_loss, 101.2)
        strategy.on_tick(tick(3, 101.6))
        self.assertAlmostEqual(strategy.position.stop_loss, 101.2)
        strategy.on_tick(tick(4, 101.7))
        self.assertAlmostEqual(strategy.position.stop_loss, 101.4)
        self.assertIsInstance(strategy.on_tick(tick(5, 101.3)), ExitSignal)

    def test_invalid_and_out_of_order_ticks(self):
        for bid, ask in ((float("nan"), 100), (100, float("inf")), (101, 100)):
            with self.assertRaises(ValueError):
                tick(0, bid, ask)
        with self.assertRaises(ValueError):
            Tick(BASE.replace(tzinfo=None), 100, 100)
        with self.assertRaises(ValueError):
            Scalping456Config(entry_mode="future_order_lookup")
        strategy = Scalping456Strategy()
        strategy.on_tick(tick(2, 100))
        with self.assertRaises(ValueError):
            strategy.on_tick(tick(1, 100))

    def test_basket_progression_and_weighted_target(self):
        strategy = FixedVol20GridStrategy(FixedVol20Config.early_three_dollar())
        strategy.on_tick(tick(0, 100))
        self.assertIsInstance(strategy.on_tick(tick(1, 103)), BasketEntrySignal)
        add = strategy.on_tick(tick(2, 100))
        self.assertEqual(add.volume, .2)
        self.assertAlmostEqual(strategy.weighted_average_entry, 101)
        self.assertAlmostEqual(add.basket_take_profit, 104)
        closed = strategy.on_tick(tick(3, 104))
        self.assertIsInstance(closed, BasketExitSignal)
        self.assertEqual(closed.positions, 2)
        self.assertEqual(strategy.flat_reference_price, 104)

    def test_progressive_volume_cap(self):
        strategy = FixedVol20GridStrategy(FixedVol20Config.early_three_dollar())
        strategy.on_tick(tick(0, 1000))
        strategy.on_tick(tick(1, 1003))
        volumes = [.1]
        for level in range(1, 23):
            signal = strategy.on_tick(tick(level + 1, 1003 - 3 * level))
            volumes.append(signal.volume)
        self.assertEqual(volumes[:8], [.1, .2, .3, .5, .8, 1.3, 2.2, 3.7])
        self.assertEqual(volumes[-1], 174)

    def test_momentum_uses_only_past_window(self):
        strategy = Scalping456Strategy(Scalping456Config(
            entry_mode="lookback_momentum", momentum_window_seconds=5,
            entry_reversal_points=50))
        strategy.on_tick(tick(0, 100))
        self.assertIsNone(strategy.on_tick(tick(4, 101)))
        self.assertEqual(strategy.on_tick(tick(5, 100.6)).side, Side.BUY)

    def test_future_extension_cannot_change_prefix(self):
        prefix = [tick(0, 100), tick(1, 101), tick(2, 101.5), tick(3, 101.1)]
        extended = prefix + [tick(4, 200), tick(5, 1)]
        first = Scalping456Strategy()
        second = Scalping456Strategy()
        expected = [first.on_tick(value) for value in prefix]
        actual = [second.on_tick(value) for value in extended]
        self.assertEqual(expected, actual[:len(prefix)])


class CloseByTests(unittest.TestCase):
    @staticmethod
    def leg(side, price, volume=10, symbol="XAUUSD+"):
        return CloseByPosition(symbol, side, BASE, Decimal(str(price)), Decimal(str(volume)))

    def settle(self, first, second):
        return settle_close_by(first, second, time=BASE + timedelta(seconds=1),
                               contract_price_multiplier=Decimal(100), point=Decimal(".01"))

    def test_net_profit_not_double_counted_and_assignment_is_not_always_buy(self):
        buy, sell = self.leg(Side.BUY, "4379.83"), self.leg(Side.SELL, "4377.73")
        first, second = self.settle(buy, sell)
        self.assertEqual((first.pips, second.pips), (Decimal(-210), Decimal(-210)))
        self.assertEqual((first.gross_profit, second.gross_profit), (Decimal(-2100), Decimal(0)))
        self.assertEqual((first.price, second.price), (sell.entry_price, buy.entry_price))
        reverse_first, reverse_second = self.settle(sell, buy)
        self.assertEqual(reverse_first.side, Side.SELL)
        self.assertEqual((reverse_first.gross_profit, reverse_second.gross_profit),
                         (first.gross_profit, second.gross_profit))

    def test_unequal_volumes_leave_residual(self):
        first, second = self.settle(self.leg(Side.BUY, 100, 3), self.leg(Side.SELL, 102, 2))
        self.assertEqual((first.volume, second.volume), (Decimal(2), Decimal(2)))
        self.assertEqual((first.remaining_volume, second.remaining_volume), (Decimal(1), Decimal(0)))
        self.assertEqual(first.gross_profit, Decimal(400))

    def test_invalid_pair_and_time_before_entry_are_rejected(self):
        buy = self.leg(Side.BUY, 100)
        for other in (self.leg(Side.BUY, 102), self.leg(Side.SELL, 102, symbol="FixedVol20")):
            with self.assertRaises(ValueError):
                self.settle(buy, other)
        with self.assertRaises(ValueError):
            settle_close_by(buy, self.leg(Side.SELL, 102), time=BASE - timedelta(seconds=1),
                            contract_price_multiplier=Decimal(100), point=Decimal(".01"))
        with self.assertRaises(ValueError):
            self.leg(Side.BUY, "NaN")


class SourceAccountingTests(unittest.TestCase):
    """All-row reconciliation only; not an autonomous order-generation test."""

    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parent / "data" / "orders_35462.jsonl"
        with source.open(encoding="utf-8") as stream:
            cls.rows = [json.loads(line, parse_float=Decimal) for line in stream if line.strip()]

    def test_all_35462_gross_results_and_pips_reconcile(self):
        self.assertEqual(len(self.rows), 35462)
        self.assertEqual(len({r["ticket"] for r in self.rows}), 35462)
        close_by, allocations = audit_close_by(self.rows)
        self.assertEqual(close_by["source_close_by_rows"], 12)
        self.assertEqual(len(close_by["verified_pairs"]), 6)
        self.assertEqual(close_by["unresolved_groups"], [])
        for result in audit_contracts(self.rows, allocations)["by_symbol"].values():
            self.assertEqual(result["orders"], result["pips_reconcile_within_0_000001"])
            self.assertEqual(result["orders"],
                             result["gross_profit_after_close_by_allocation_reconcile_within_half_cent"])

    def test_overlap_audit_is_not_core_only_or_same_second_guessing(self):
        def row(ticket, opened, closed, side, comment):
            return dict(ticket=ticket, symbol="XAUUSD+", trade_type=side,
                        open_time=(BASE + timedelta(seconds=opened)).isoformat(),
                        close_time=(BASE + timedelta(seconds=closed)).isoformat(),
                        open_price=100, close_price=99, volume=1, pips=-100, comment=comment)
        rows = [row(1, 0, 10, "buy", ""), row(2, 1, 2, "sell", "[sl 99]"),
                row(3, 10, 12, "buy", "[sl 99]"), row(4, 10, 11, "sell", "")]
        report = audit_portfolio(rows)
        self.assertEqual(report["strict_overlap_order_pairs"], 2)
        self.assertEqual(report["maximum_concurrent_positive_duration_positions"], 2)
        self.assertEqual(report["rows_opened_while_earlier_order_still_active"], 1)
        self.assertEqual(report["rows_at_prior_close_same_second_ambiguous"], 2)
        self.assertTrue(any(pair["same_reported_open_second"] for pair in report["pairs"]))


class LedgerTests(unittest.TestCase):
    @staticmethod
    def order(ticket, opened, closed, comment, entry, exit_price):
        return {"id": str(ticket), "ticket": str(ticket), "symbol": "XAUUSD+",
                "trade_type": "buy", "volume": "1", "profit": "1", "pips": "1",
                "actual_open_utc": (BASE + timedelta(seconds=opened)).isoformat(),
                "actual_close_utc": (BASE + timedelta(seconds=closed)).isoformat(),
                "open_price": str(entry), "close_price": str(exit_price), "comment": comment}

    def test_other_exit_is_not_skipped(self):
        rows = [self.order(1, 0, 1, "[sl 101]", 100, 101),
                self.order(2, 2, 3, "", 102, 98),
                self.order(3, 4, 5, "[sl 100]", 99, 100)]
        last = build_audit(rows)[-1]
        self.assertEqual(last["previous_opened_ticket"], "2")
        self.assertEqual(last["previous_core_only_ticket"], "1")
        self.assertTrue(last["previous_opened_direction_match"])
        self.assertFalse(last["previous_core_only_direction_match"])

    def test_latest_completed_is_not_future_close(self):
        rows = [self.order(1, 0, 20, "[sl 101]", 100, 101),
                self.order(2, 1, 2, "", 100, 98),
                self.order(3, 3, 4, "[sl 100]", 99, 100)]
        last = build_audit(rows)[-1]
        self.assertEqual(last["previous_completed_ticket"], "2")
        self.assertEqual(last["active_same_symbol_before_open"], 1)

    def test_matcher_does_not_hide_missing_or_extra_orders(self):
        source = [self.order(1, 0, 1, "[sl 101]", 100, 101),
                  self.order(2, 20, 21, "[sl 101]", 100, 101)]
        epoch = round(BASE.timestamp() * 1000)
        prediction = [dict(open_ms=epoch, close_ms=epoch + 1000, side="sell",
                           volume=1, open_price=100, close_price=101),
                      dict(open_ms=epoch + 100000, close_ms=epoch + 101000, side="buy",
                           volume=1, open_price=100, close_price=101)]
        rows, score = match_orders(source, prediction)
        self.assertEqual(score["missing_source_orders"], 1)
        self.assertEqual(score["extra_predictions"], 1)
        self.assertFalse(rows[0]["direction_match"])
        self.assertEqual(score["joint_source_fields_at_reported_precision"], 0)


class ReplayParityTests(unittest.TestCase):
    def test_vector_matches_reference_for_all_candidates(self):
        rng = np.random.default_rng(456)
        epoch = round(BASE.timestamp() * 1000)
        times = epoch + np.arange(12000, dtype=np.int64) * 400
        bids = np.round(1000 + np.cumsum(rng.normal(0, .3, len(times))), 2)
        asks = bids + rng.choice([.1, .2, .3], len(times))
        for name, config in candidates().items():
            with self.subTest(model=name):
                strategy = Scalping456Strategy(config)
                expected = []
                opened = None
                for instant, bid, ask in zip(times, bids, asks):
                    value = Tick(datetime.fromtimestamp(int(instant) / 1000, timezone.utc), float(bid), float(ask))
                    signal = strategy.on_tick(value)
                    if isinstance(signal, EntrySignal):
                        opened = signal
                    elif isinstance(signal, ExitSignal):
                        expected.append(dict(open_ms=round(opened.time.timestamp() * 1000),
                                             close_ms=round(signal.time.timestamp() * 1000),
                                             side=opened.side.value, volume=opened.volume,
                                             open_price=opened.price, close_price=signal.price))
                        opened = None
                if opened is not None:
                    expected.append(dict(open_ms=round(opened.time.timestamp() * 1000), close_ms=None,
                                         side=opened.side.value, volume=opened.volume,
                                         open_price=opened.price, close_price=None))
                actual = replay_candidate(times, bids, asks, config, chunk_size=37)
                self.assertEqual(len(expected), len(actual))
                for reference, accelerated in zip(expected, actual):
                    for key in ("open_ms", "close_ms", "side", "volume"):
                        self.assertEqual(reference[key], accelerated[key])
                    self.assertAlmostEqual(reference["open_price"], accelerated["open_price"], places=9)
                    if reference["close_price"] is None:
                        self.assertIsNone(accelerated["close_price"])
                    else:
                        self.assertAlmostEqual(reference["close_price"], accelerated["close_price"], places=9)


if __name__ == "__main__":
    unittest.main()
