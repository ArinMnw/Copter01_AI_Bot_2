"""Guarded market-data reader: attach only to the already running demo terminal.

No account credentials, symbol selection, trade requests or production imports.
The connector's shutdown disconnects Python, not the running MT5 application.
"""

from __future__ import annotations

import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path


TERMINAL = Path(__file__).resolve().parents[3] / "profiles/demo/demo-vantage-26253671/mt5/terminal64.exe"
EXPECTED_LOGIN = 26253671
EXPECTED_SERVER = "VantageMarkets-Demo"


def same_path(first, second):
    return os.path.normcase(os.path.abspath(str(first))) == os.path.normcase(os.path.abspath(str(second)))


def running_terminal_pids(terminal=TERMINAL):
    """Inventory only PID/Path; never inspect CommandLine or credentials."""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Get-Process -Name terminal64 -ErrorAction SilentlyContinue | "
         "Select-Object Id,Path | ConvertTo-Json -Compress"],
        capture_output=True, text=True, encoding="utf-8", check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    rows = json.loads(result.stdout.strip() or "[]")
    if isinstance(rows, dict):
        rows = [rows]
    return [int(row["Id"]) for row in rows if row.get("Path") and same_path(row["Path"], terminal)]


class MarketReader:
    def __init__(self, connector, terminal, pids):
        self._connector = connector
        self.terminal = terminal
        self.pids = pids

    def verify(self):
        account = self._connector.account_info()
        info = self._connector.terminal_info()
        if account is None or info is None:
            raise RuntimeError("Account/terminal metadata unavailable; refuse query")
        if (account.login != EXPECTED_LOGIN or account.server != EXPECTED_SERVER
                or account.trade_mode != self._connector.ACCOUNT_TRADE_MODE_DEMO):
            raise RuntimeError("Unexpected account/server/type; refuse query without relogin")
        if not same_path(info.path, self.terminal.parent) or not info.connected:
            raise RuntimeError("Wrong/disconnected terminal; refuse query")
        return {
            "expected_account_matches": True, "server": account.server,
            "demo": True, "currency": account.currency, "leverage": account.leverage,
            "company": account.company, "terminal_path": info.path,
            "data_path": info.data_path, "build": info.build, "connected": info.connected,
            "existing_process_ids": self.pids,
        }

    def _read(self, method, *args):
        self.verify()
        value = getattr(self._connector, method)(*args)
        error = self._connector.last_error()
        self.verify()
        if value is None:
            raise RuntimeError(f"{method} returned no data: {error}")
        return value

    def specs(self, symbol):
        row = self._read("symbol_info", symbol)
        fields = ("name", "visible", "digits", "point", "trade_contract_size",
                  "volume_min", "volume_max", "volume_step", "trade_tick_size",
                  "trade_tick_value", "trade_calc_mode", "path", "currency_profit")
        return {key: getattr(row, key) for key in fields}

    def symbols(self):
        return [row.name for row in self._read("symbols_get")]

    def rates_m1(self, symbol, start, end):
        return self._read("copy_rates_range", symbol, self._connector.TIMEFRAME_M1, start, end)

    def rates(self, symbol, minutes, start, end):
        names = {1: "TIMEFRAME_M1", 5: "TIMEFRAME_M5", 15: "TIMEFRAME_M15",
                 30: "TIMEFRAME_M30", 60: "TIMEFRAME_H1"}
        if minutes not in names:
            raise ValueError("Unsupported research timeframe")
        return self._read("copy_rates_range", symbol, getattr(self._connector, names[minutes]), start, end)

    def ticks(self, symbol, start, end):
        return self._read("copy_ticks_range", symbol, start, end, self._connector.COPY_TICKS_ALL)

    def latest_tick(self, symbol):
        return self._read("symbol_info_tick", symbol)


@contextmanager
def attach(*, connector=None, process_check=running_terminal_pids, terminal=TERMINAL):
    pids = process_check(terminal)
    if not pids or not terminal.is_file():
        raise RuntimeError("Expected terminal is not already running; will not launch it")
    if connector is None:
        import MetaTrader5 as connector
    # No login/password/server parameters: use existing, human-selected account.
    try:
        if not connector.initialize(str(terminal), portable=True, timeout=10000):
            raise RuntimeError(f"Read connection failed: {connector.last_error()}")
        reader = MarketReader(connector, terminal, pids)
        reader.verify()
        yield reader
    finally:
        connector.shutdown()
