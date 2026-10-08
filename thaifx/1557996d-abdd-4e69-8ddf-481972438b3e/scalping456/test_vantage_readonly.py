"""Offline safety/alignment tests: no live MT5 calls."""

import unittest
from types import SimpleNamespace

import numpy as np

from vantage_readonly import EXPECTED_LOGIN, EXPECTED_SERVER, TERMINAL, attach
from probe_vantage_feed import score_offsets, score_tick
from export_vantage_ticks import normalize_ticks
from audit_vantage_quotes import compare_event, event_witness


class FakeConnector:
    ACCOUNT_TRADE_MODE_DEMO = 0
    TIMEFRAME_M1 = 1
    COPY_TICKS_ALL = 3

    def __init__(self):
        self.calls = []
        self.login_value = EXPECTED_LOGIN
        self.server = EXPECTED_SERVER
        self.mode = 0
        self.connected = True

    def initialize(self, path, **kwargs):
        self.calls.append(("initialize", path, kwargs))
        return True

    def shutdown(self):
        self.calls.append(("shutdown",))

    def account_info(self):
        return SimpleNamespace(login=self.login_value, server=self.server, trade_mode=self.mode,
                               currency="USD", leverage=500, company="test")

    def terminal_info(self):
        return SimpleNamespace(path=str(TERMINAL.parent), data_path=str(TERMINAL.parent),
                               connected=self.connected, build=6230)

    def last_error(self):
        return (1, "Success")

    def copy_ticks_range(self, *args):
        self.calls.append(("copy_ticks_range", args))
        return []

    def __getattr__(self, name):
        if name in ("login", "order_send", "order_check", "symbol_select"):
            raise AssertionError("Forbidden call: " + name)
        raise AttributeError(name)


class ReadonlyTests(unittest.TestCase):
    def test_no_launch_when_process_missing(self):
        connector = FakeConnector()
        with self.assertRaises(RuntimeError):
            with attach(connector=connector, process_check=lambda _: []):
                pass
        self.assertEqual(connector.calls, [])

    def test_init_has_no_credentials_and_cleanup(self):
        connector = FakeConnector()
        with attach(connector=connector, process_check=lambda _: [123]) as reader:
            self.assertTrue(reader.verify()["demo"])
            reader.ticks("FixedVol20", None, None)
        self.assertEqual(connector.calls[0][2], {"portable": True, "timeout": 10000})
        self.assertEqual(connector.calls[-1], ("shutdown",))

    def test_mismatches_reject_and_disconnect(self):
        for field, value in (("login_value", 123), ("server", "Other"), ("mode", 2), ("connected", False)):
            connector = FakeConnector()
            setattr(connector, field, value)
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                with attach(connector=connector, process_check=lambda _: [123]):
                    pass
            self.assertEqual(connector.calls[-1], ("shutdown",))

    def test_account_change_during_query_rejected(self):
        connector = FakeConnector()
        with attach(connector=connector, process_check=lambda _: [123]) as reader:
            def query(*args):
                connector.login_value = 123
                return []
            connector.copy_ticks_range = query
            with self.assertRaises(RuntimeError):
                reader.ticks("XAUUSD", None, None)

    def test_offset_clock_not_iux_shift(self):
        row = {"symbol": "XAUUSD+", "open_time": "2026-10-08T01:04:15+00:00",
               "open_price": 4113.03, "close_time": "2026-10-08T01:04:20+00:00",
               "close_price": 4112.93, "trade_type": "sell", "comment": "[sl 4112.93]"}
        rates = np.array([(1791410640, 4112.8, 4113.1, 10)],
                         dtype=[("time", "i8"), ("low", "f8"), ("high", "f8"), ("spread", "i4")])
        scores = score_offsets([row], rates, .01)
        best = max(scores, key=lambda x: x["spread_adjusted_containment_count"])
        self.assertEqual(best["raw_to_query_hours"], -3)
        self.assertEqual(best["covered_witnesses"], 2)

    def test_bid_ask_seconds_source_precision(self):
        row = {"ticket": 1, "symbol": "XAUUSD+", "open_time": "2026-10-08T01:04:15+00:00",
               "open_price": 4113.03, "trade_type": "buy", "comment": "[sl 0]"}
        ticks = np.array([(1791410655010, 4112.82, 4113.031),
                          (1791410656010, 4112.82, 4113.03)],
                         dtype=[("time_msc", "i8"), ("bid", "f8"), ("ask", "f8")])
        scored = score_tick(row, "open", ticks, -3, 3)
        self.assertEqual(scored["quote_side"], "ask")
        self.assertEqual(scored["exact_price_ticks_same_second"], 1)
        self.assertEqual(scored["source_digits"], 2)

    def test_normalization_separate_raw_unchanged(self):
        ticks = np.array([(1791421651000, 4109.94, 4110.21)],
                         dtype=[("time_msc", "i8"), ("bid", "f8"), ("ask", "f8")])
        original = ticks.copy()
        normalized = normalize_ticks(ticks, 10800000)
        np.testing.assert_array_equal(ticks, original)
        self.assertEqual(normalized["time_msc"][0], 1791410851000)

    def test_full_audit_window_not_promoted_to_exact_second(self):
        event = {"source_symbol": "XAUUSD+", "source_price": 100., "quote_side": "bid",
                 "inferred_canonical_ms": 1000, "market_quote_witness_applicable": True}
        result = compare_event(event, np.array([1200, 2000]), np.array([100.01, 100.]), np.array([100.2, 100.2]))
        self.assertEqual(result["same_second"]["exact_price_ticks"], 0)
        self.assertEqual(result["window_minus2_plus3_seconds"]["exact_price_ticks"], 1)

    def test_close_by_retained_but_not_market_witness(self):
        row = {"ticket": 1, "symbol": "XAUUSD+", "trade_type": "sell", "close_price": 100.,
               "close_time": "2026-10-08T01:04:15+00:00", "comment": "#2 by #3"}
        event = event_witness(row, "close")
        self.assertFalse(event["market_quote_witness_applicable"])
        self.assertEqual(event["ticket"], 1)
        self.assertEqual(event["quote_side"], "ask")


if __name__ == "__main__":
    unittest.main()
