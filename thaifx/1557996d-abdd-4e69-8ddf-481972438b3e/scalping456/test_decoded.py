"""Tests for the decoded engines: causality, semantics, determinism, matcher honesty.

These tests prove the code does what the plan says; they are not evidence that
the engines clone the source EA (see DECODED_MECHANICS_RESULTS.md for scores).
"""

import json
import re
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import numpy as np

from decoded_schedule import FIXED_REGIMES, GOLD_REGIMES
from strategy_scalping456_decoded import (FixedParams, FixedRegime, GoldParams, GoldRegime, basket_take_profit,
                                          next_lot_tenths, simulate_fixed, simulate_gold)
from strict_source_matcher import enrich_prediction, match_exact

ROOT = Path(__file__).resolve().parent
MODULE = ROOT / "strategy_scalping456_decoded.py"


def gold_ticks(path_mid, step_ms=100, spread=21):
    """Demo-feed XAUUSD ticks (cents).  Source quotes = bid+6 / ask-5."""
    times = np.arange(len(path_mid), dtype=np.int64) * step_ms + 1_000_000
    bids = np.array(path_mid, dtype=np.int64)
    return times, bids, bids + spread


def fixed_ticks(path_bid, spread=600):
    times = np.arange(len(path_bid), dtype=np.int64) * 1000 + 9 + 1_000_000
    bids = np.array(path_bid, dtype=np.int64)
    return times, bids, bids + spread


GOLD = (GoldRegime(0, True, 100, "10"),)
FIXED = (FixedRegime(0, True, 3000, 3000, 3000, 1),)


class StaticGuards(unittest.TestCase):
    def test_model_never_touches_ledger_or_tickets(self):
        text = MODULE.read_text(encoding="utf-8")
        for forbidden in ("orders_35462", "jsonl", "ticket", "open(", "read_text", "csv", "decoded_common", "load_source"):
            self.assertNotIn(forbidden, text, forbidden)

    def test_schedule_is_sorted_and_carries_no_trade_fields(self):
        for schedule in (GOLD_REGIMES, FIXED_REGIMES):
            starts = [r.start_ms for r in schedule]
            self.assertEqual(starts, sorted(starts))
            self.assertEqual(len(set(starts)), len(starts))
            for regime in schedule:
                self.assertFalse(hasattr(regime, "ticket") or hasattr(regime, "price"))

    def test_text_files_are_utf8_lf(self):
        for name in ("strategy_scalping456_decoded.py", "decoded_schedule.py", "decoded_common.py", "replay_decoded.py",
                     "EXPERIMENT_DECODED_PLAN.md"):
            raw = (ROOT / name).read_bytes()
            raw.decode("utf-8")
            self.assertNotIn(b"\r\n", raw, name)


class LotAndTakeProfit(unittest.TestCase):
    def test_lot_progressions_from_both_bases(self):
        seq, lot = [1], 1
        for _ in range(15):
            lot = next_lot_tenths(lot)
            seq.append(lot)
        self.assertEqual([x / 10 for x in seq[:11]], [0.1, 0.2, 0.3, 0.5, 0.8, 1.3, 2.2, 3.7, 6.2, 10.4, 17.5])
        self.assertEqual(seq[-1], 1740)
        seq, lot = [10], 10
        for _ in range(4):
            lot = next_lot_tenths(lot)
            seq.append(lot)
        self.assertEqual([x / 10 for x in seq], [1.0, 1.7, 2.9, 4.9, 8.2])

    def test_take_profit_rounds_weighted_entry_half_up(self):
        legs = [[8318057, 1, 0], [8321561, 2, 0]]
        self.assertEqual(basket_take_profit(legs, -1, 3000), 8320393 - 3000)   # (1*8318057+2*8321561)/3 = 8320393 exactly
        legs = [[1000, 1, 0], [1001, 1, 0]]                                    # 1000.5 -> 1001 (half up)
        self.assertEqual(basket_take_profit(legs, 1, 10), 1001 + 10)


class GoldSemantics(unittest.TestCase):
    def run_path(self, path, **kwargs):
        times, bids, asks = gold_ticks(path)
        return simulate_gold(times, bids, asks, GOLD, GoldParams(**kwargs))

    def test_buy_stop_fills_at_its_level_and_stops_out_at_level(self):
        # flat then up 1.5 then down 3
        path = [400000] * 12 + list(range(400000, 400220, 20)) + list(range(400200, 399600, -20))
        trades = self.run_path(path)
        self.assertTrue(trades)
        first = trades[0]
        self.assertEqual(first["side"], "buy")
        ref_ask = 400000 + 21 - 5      # tick before placement, source ask
        self.assertEqual(round(first["open_price"] * 100), ref_ask + 100)
        self.assertEqual(first["close_behavior"], "sl")
        self.assertEqual(first["volume"], "10")

    def test_trailing_needs_strictly_more_than_activation(self):
        # price rises exactly 20 above entry (not strictly more): stop must stay at the initial -100 level
        times, bids, asks = gold_ticks([400000] * 12 + [400100 + 6 + 20 + 5 - 6] * 10)
        trades = simulate_gold(times, bids, asks, GOLD, GoldParams())
        for trade in trades:
            if trade["close_ms"] is not None:
                self.assertLess(trade["close_price"], trade["open_price"] + 0.2)

    def test_pair_after_a_close_waits_for_the_reaction_delay(self):
        path = ([400000] * 12 + list(range(400000, 400220, 20)) + list(range(400200, 399600, -60)) + [399600] * 5
                + list(range(399600, 399900, 30)))
        times, bids, asks = gold_ticks(path)
        quick = simulate_gold(times, bids, asks, GOLD, GoldParams(react_ms=110))
        slow = simulate_gold(times, bids, asks, GOLD, GoldParams(react_ms=60_000))
        self.assertGreater(len(quick), len(slow))
        self.assertTrue(all(t['open_ms'] < 1_000_000 + 60_000 for t in slow))
        # with a 60 s delay no pair can be placed after the first close inside this 8 s path
        self.assertEqual(sum(t['side'] == 'buy' for t in slow), 1)

    def test_tick_offset_places_the_pair_that_many_ticks_after_the_observed_close(self):
        path = list(range(400000, 400000 + 20 * 60, 20))             # steady rise, one 0.20 step per tick
        times, bids, asks = gold_ticks(path)
        levels = {}
        for offset in (0, 1, 3):
            regime = (GoldRegime(0, True, 100, "10", place_offset=offset),)
            trades = simulate_gold(times, bids, asks, regime, GoldParams(), begin=0, initial_close_ms=int(times[0]),
                                   stop_after_trades=1)
            first = [t for t in trades if t["side"] == "buy"][0]
            levels[offset] = round(first["open_price"] * 100)
        self.assertEqual(levels[1] - levels[0], 20)
        self.assertEqual(levels[3] - levels[0], 60)

    def test_stops_level_model_rejects_a_trailing_request_when_price_falls_before_it_arrives(self):
        # fill, one spike tick, then a steady fall: the 0.20-behind request is stale when it arrives
        rise = list(range(400000, 400120, 20)) + [400180]         # fills, then one spike tick
        fall = list(range(400160, 399600, -20))
        times, bids, asks = gold_ticks([400000] * 12 + rise + fall)
        new = simulate_gold(times, bids, asks, GOLD, GoldParams(trail_model="stops_level", trail_latency_ms=300, trail_block_ms=300))
        old = simulate_gold(times, bids, asks, GOLD, GoldParams(trail_model="busy_effect"))
        first_new = [t for t in new if t["close_ms"] is not None][0]
        first_old = [t for t in old if t["close_ms"] is not None][0]
        self.assertEqual(round(first_new["close_price"] * 100), round(first_new["open_price"] * 100) - 100)
        self.assertGreater(first_old["close_price"], first_new["close_price"])

    def test_stops_level_model_accepts_requests_while_price_keeps_rising(self):
        times, bids, asks = gold_ticks([400000] * 12 + list(range(400000, 400600, 20)) + list(range(400600, 399000, -20)))
        trades = simulate_gold(times, bids, asks, GOLD, GoldParams())
        first = [t for t in trades if t["close_ms"] is not None][0]
        self.assertGreater(first["close_price"], first["open_price"])

    def test_future_ticks_do_not_change_earlier_decisions(self):
        rng = np.random.default_rng(3)
        walk = 400000 + np.cumsum(rng.integers(-15, 16, size=3000))
        times, bids, asks = gold_ticks(walk)
        cut = 1500
        full = simulate_gold(times, bids, asks, GOLD, GoldParams())
        alt_bids = bids.copy()
        alt_bids[cut:] += rng.integers(-5000, 5000, size=len(bids) - cut)
        altered = simulate_gold(times, alt_bids, alt_bids + 21, GOLD, GoldParams())
        horizon = int(times[cut])
        keep = lambda rows: [r for r in rows if r["close_ms"] is not None and r["close_ms"] < horizon]
        self.assertEqual(keep(full), keep(altered))
        self.assertEqual([r for r in full if r["open_ms"] < horizon], [r for r in altered if r["open_ms"] < horizon])

    def test_deterministic(self):
        rng = np.random.default_rng(4)
        times, bids, asks = gold_ticks(400000 + np.cumsum(rng.integers(-12, 13, size=2000)))
        self.assertEqual(simulate_gold(times, bids, asks, GOLD), simulate_gold(times, bids, asks, GOLD))

    def test_inactive_regime_places_nothing(self):
        times, bids, asks = gold_ticks(list(range(400000, 401500, 10)))
        self.assertEqual(simulate_gold(times, bids, asks, (GoldRegime(0, False),)), [])


class FixedSemantics(unittest.TestCase):
    def test_first_leg_uses_tick_after_close_and_grid_adds_on_first_adverse_tick(self):
        # flat start, rise 3.5 (BUY STOP at ask+3.0 fills), then fall 3.1 -> second leg, then recover to TP
        path = [8000000] * 4 + [8000000 + 500 * k for k in range(1, 8)] + [8003500 - 600 * k for k in range(1, 7)] + [8003500] * 3
        times, bids, asks = fixed_ticks(path)
        trades = simulate_fixed(times, bids, asks, FIXED)
        self.assertGreaterEqual(len(trades), 1)
        self.assertEqual(trades[0]["side"], "buy")
        self.assertEqual(round(trades[0]["open_price"] * 1000), 8000000 + 600 + 3000)   # placed with tick 0 ask, level fill

    def test_lot_cap_and_progression_inside_basket(self):
        path = [8000000] + [8000000 + 3100 * k for k in range(1, 3)] + [8006200 - 3100 * k for k in range(1, 30)]
        times, bids, asks = fixed_ticks(path)
        trades = simulate_fixed(times, bids, asks, FIXED)
        lots = [t["volume"] for t in trades]
        self.assertTrue(all(lot <= 174.0 for lot in lots))

    def test_tp_closes_whole_basket_at_the_level(self):
        path = [8000000] * 3 + [8004000] + [8004000 + 1000 * k for k in range(1, 6)]
        times, bids, asks = fixed_ticks(path)
        trades = simulate_fixed(times, bids, asks, FIXED)
        closed = [t for t in trades if t["close_ms"] is not None]
        self.assertTrue(closed)
        self.assertEqual(closed[0]["close_behavior"], "tp")
        self.assertEqual(round(closed[0]["close_price"] * 1000), round(closed[0]["open_price"] * 1000) + 3000)

    def test_future_ticks_do_not_change_earlier_decisions(self):
        rng = np.random.default_rng(5)
        walk = 8000000 + np.cumsum(rng.integers(-900, 901, size=4000))
        times, bids, asks = fixed_ticks(walk)
        full = simulate_fixed(times, bids, asks, FIXED)
        cut = 2000
        alt = bids.copy()
        alt[cut:] += rng.integers(-40000, 40000, size=len(alt) - cut)
        altered = simulate_fixed(times, alt, alt + 600, FIXED)
        horizon = int(times[cut])
        keep = lambda rows: [r for r in rows if r["close_ms"] is not None and r["close_ms"] < horizon]
        self.assertEqual(keep(full), keep(altered))


class FixedExtensions(unittest.TestCase):
    TRAIL = (FixedRegime(0, True, 5000, mode="trailing", base_lot_tenths=1),)

    def test_trailing_mode_places_5_0_stop_then_trails_2_8_behind_the_best_bid(self):
        # tick0 sets the reference (ask 8000600), BUY STOP at ask+5.000; price climbs, then falls through the trailed stop
        path = [8000000] + [8000000 + 1500 * k for k in range(1, 8)] + [8010500 - 1500 * k for k in range(1, 8)]
        times, bids, asks = fixed_ticks(path)
        trades = simulate_fixed(times, bids, asks, self.TRAIL)
        closed = [t for t in trades if t["close_ms"] is not None]
        self.assertTrue(closed)
        first = closed[0]
        self.assertEqual(first["close_behavior"], "sl")
        self.assertEqual(round(first["open_price"] * 1000), 8000600 + 5000)
        peak_bid = max(path)
        self.assertEqual(round(first["close_price"] * 1000), peak_bid - 2800)

    def test_trailing_mode_keeps_initial_stop_until_activation_gain(self):
        # after the fill the bid only drifts: the stop stays at entry - 10.000
        path = [8000000] + [8000000 + 1700 * k for k in range(1, 5)] + [8006800 - 900 * k for k in range(1, 30)]
        times, bids, asks = fixed_ticks(path)
        trades = simulate_fixed(times, bids, asks, self.TRAIL)
        closed = [t for t in trades if t["close_ms"] is not None]
        self.assertTrue(closed)
        self.assertEqual(round(closed[0]["close_price"] * 1000), round(closed[0]["open_price"] * 1000) - 10000)

    def test_sessions_block_new_pairs_outside_the_window_and_cancel_pending(self):
        inside = ((0, 1),)          # 00:00-00:01 UTC only; the synthetic clock starts at ~00:16:40
        regime = (FixedRegime(0, True, 3000, 3000, 3000, 1, sessions=inside),)
        times, bids, asks = fixed_ticks([8000000 + 1500 * k for k in range(40)])
        self.assertEqual(simulate_fixed(times, bids, asks, regime), [])

    def test_flatten_at_start_drops_the_old_basket_and_replaces_the_pair(self):
        regimes = (FixedRegime(0, True, 3000, 3000, 3000, 1),
                   FixedRegime(1_000_000 + 12_000, True, 3000, 3000, 3000, 1, flatten_at_start=True))
        path = [8000000] * 3 + [8004000] + [8003000] * 10 + [8010000] * 5
        times, bids, asks = fixed_ticks(path)
        trades = simulate_fixed(times, bids, asks, regimes)
        self.assertFalse(any(t["close_ms"] is None for t in trades if t["open_ms"] < 1_000_000 + 12_000))

    def test_trailing_mode_future_ticks_do_not_change_earlier_decisions(self):
        rng = np.random.default_rng(8)
        walk = 8000000 + np.cumsum(rng.integers(-1500, 1501, size=3000))
        times, bids, asks = fixed_ticks(walk)
        regimes = (FixedRegime(0, True, 3000, mode="trailing", base_lot_tenths=1),)
        full = simulate_fixed(times, bids, asks, regimes)
        cut = 1500
        alt = bids.copy()
        alt[cut:] += rng.integers(-60000, 60000, size=len(alt) - cut)
        altered = simulate_fixed(times, alt, alt + 600, regimes)
        horizon = int(times[cut])
        keep = lambda rows: [r for r in rows if r["close_ms"] is not None and r["close_ms"] < horizon]
        self.assertEqual(keep(full), keep(altered))


class MatcherHonesty(unittest.TestCase):
    def source_row(self, close_price="4110.00"):
        return {"ticket": 1, "symbol": "XAUUSD+", "trade_type": "buy", "volume": Decimal("10"),
                "open_time": "2026-10-08T01:00:00+00:00", "close_time": "2026-10-08T01:00:05+00:00",
                "open_price": Decimal("4109.00"), "close_price": Decimal(close_price), "pips": Decimal("100"),
                "profit": Decimal("1000.00"), "comment": "[sl 4110.00]"}

    def prediction(self, close_price):
        base = 1791421200000 - 10800000
        row = {"open_ms": base, "close_ms": base + 5000, "side": "buy", "volume": "10", "open_price": 4109.0,
               "close_price": close_price}
        return enrich_prediction(row, "XAUUSD+", "sl")

    def test_exact_prediction_matches_and_one_cent_error_is_missing_plus_extra(self):
        _, extra, score = match_exact([self.source_row()], [self.prediction(4110.0)])
        self.assertEqual((score["exact_all_observable_fields"], score["missing"], score["extra"]), (1, 0, 0))
        _, extra, score = match_exact([self.source_row()], [self.prediction(4109.99)])
        self.assertEqual((score["exact_all_observable_fields"], score["missing"], score["extra"]), (0, 1, 1))


class ReportInvariants(unittest.TestCase):
    def test_saved_replay_reports_account_for_every_source_row(self):
        for report_path in sorted((ROOT / "data").glob("decoded_replay_*/report.json")):
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["source_orders"], 35462)
            self.assertEqual(report["exact_all_observable_fields"] + report["missing"], 35462)
            self.assertFalse(report["full_source_clone_complete"])
            self.assertEqual(report["timing_tolerance_seconds"], 0)
            self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", report["source_sha256"]))
            rows = (report_path.parent / "all_source_results.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 35462)
            self.assertEqual(len({json.loads(r)["ticket"] for r in rows}), 35462)


if __name__ == "__main__":
    unittest.main()
