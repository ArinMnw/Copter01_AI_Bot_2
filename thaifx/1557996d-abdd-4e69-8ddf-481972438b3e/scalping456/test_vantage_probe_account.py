"""Offline safety tests for the additional-terminal probe: no live MT5 calls."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np

import vantage_probe_account as vpa


class FakeConnector:
    ACCOUNT_TRADE_MODE_DEMO = 0
    COPY_TICKS_ALL = 3

    def __init__(self, terminal, names=("XAUUSD", "XAUUSD+")):
        self.terminal = terminal
        self.names = names
        self.login_value = 111
        self.server = "VantageMarkets-Demo"
        self.mode = 0
        self.connected = True
        self.calls = []

    def initialize(self, path, **kwargs):
        self.calls.append(("initialize", path, kwargs))
        return True

    def shutdown(self):
        self.calls.append(("shutdown",))

    def account_info(self):
        return SimpleNamespace(login=self.login_value, server=self.server, trade_mode=self.mode,
                               currency="USD", leverage=500, company="test")

    def terminal_info(self):
        return SimpleNamespace(path=str(self.terminal.parent), connected=self.connected, build=1)

    def last_error(self):
        return (1, "Success")

    def symbols_get(self):
        return [SimpleNamespace(name=n) for n in self.names]

    def symbol_info(self, name):
        return SimpleNamespace(name=name, visible=True, digits=2, point=0.01, spread=10, spread_float=True,
                               trade_mode=4, trade_stops_level=20, trade_freeze_level=0, trade_contract_size=100,
                               volume_min=0.01, volume_max=100, volume_step=0.01, trade_tick_size=0.01,
                               trade_tick_value=1.0, path="Metals\\" + name, currency_profit="USD")

    def symbol_info_tick(self, name):
        return SimpleNamespace(time_msc=1_700_000_000_000, bid=2000.0, ask=2000.2)

    def copy_ticks_range(self, *args):
        self.calls.append(("copy_ticks_range", args))
        dtype = [("time_msc", "i8"), ("bid", "f8"), ("ask", "f8")]
        return np.array([(1_700_000_000_000, 1.0, 1.1)], dtype=dtype)

    def __getattr__(self, name):
        if name in ("login", "order_send", "order_check", "symbol_select", "positions_get", "orders_get"):
            raise AssertionError("Forbidden call: " + name)
        raise AttributeError(name)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.terminal = Path(self.dir.name) / "terminal64.exe"
        self.terminal.write_text("x")

    def tearDown(self):
        self.dir.cleanup()

    def test_refuses_to_launch(self):
        connector = FakeConnector(self.terminal)
        with self.assertRaises(RuntimeError):
            with vpa.attach_other(self.terminal, connector=connector, process_check=lambda _: []):
                pass
        self.assertEqual(connector.calls, [])

    def test_probe_reports_target_and_never_selects_symbol(self):
        connector = FakeConnector(self.terminal)
        with vpa.attach_other(self.terminal, expected_login=111, connector=connector,
                              process_check=lambda _: [1]) as reader:
            report = vpa.probe(reader, "XAUUSD+")
        self.assertTrue(report["target_present"])
        self.assertEqual(report["specs"]["XAUUSD+"]["trade_stops_level"], 20)
        self.assertEqual(connector.calls[0][2], {"portable": True, "timeout": 10000})
        self.assertEqual(connector.calls[-1], ("shutdown",))

    def test_absent_symbol_is_reported_not_forced(self):
        connector = FakeConnector(self.terminal, names=("XAUUSD",))
        with vpa.attach_other(self.terminal, connector=connector, process_check=lambda _: [1]) as reader:
            report = vpa.probe(reader, "XAUUSD+")
        self.assertFalse(report["target_present"])
        self.assertNotIn("clock_probe", report)

    def test_mismatch_rejected_and_disconnects(self):
        for field, value in (("login_value", 5), ("server", "Other"), ("mode", 2), ("connected", False)):
            connector = FakeConnector(self.terminal)
            setattr(connector, field, value)
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                with vpa.attach_other(self.terminal, expected_login=111, expected_server="VantageMarkets-Demo",
                                      connector=connector, process_check=lambda _: [1]):
                    pass
            self.assertEqual(connector.calls[-1], ("shutdown",))

    def test_account_change_during_query_rejected(self):
        connector = FakeConnector(self.terminal)
        original = connector.symbols_get

        def switching():
            connector.login_value = 999
            return original()
        connector.symbols_get = switching
        with self.assertRaises(RuntimeError):
            with vpa.attach_other(self.terminal, connector=connector, process_check=lambda _: [1]) as reader:
                reader.symbols()

    def test_export_applies_shift_and_half_open_filter(self):
        connector = FakeConnector(self.terminal)
        shift_ms = 3 * 3_600_000
        start = datetime(2023, 11, 14, 22, 0, tzinfo=timezone.utc)
        raw_epoch = 1_700_000_000_000          # 2023-11-14T22:13:20Z in raw numbers
        connector.copy_ticks_range = lambda *a: np.array(
            [(raw_epoch + shift_ms - 1, 1.0, 1.1), (raw_epoch + shift_ms, 2.0, 2.1)],
            dtype=[("time_msc", "i8"), ("bid", "f8"), ("ask", "f8")])
        import tempfile as _t
        original_root = vpa.ROOT
        with _t.TemporaryDirectory() as tmp:
            vpa.ROOT = Path(tmp)
            (Path(tmp) / "data").mkdir()
            try:
                with vpa.attach_other(self.terminal, connector=connector, process_check=lambda _: [1]) as reader:
                    days = vpa.export_ticks(reader, "XAUUSD+", "t", start, datetime(2023, 11, 14, 23, 0, tzinfo=timezone.utc), shift_ms)
            finally:
                vpa.ROOT = original_root
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0]["invalid_quotes"], 0)


if __name__ == "__main__":
    unittest.main()
