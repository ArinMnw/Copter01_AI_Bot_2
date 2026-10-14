"""Read-only probe/export for an ADDITIONAL, already running Vantage demo terminal.

Purpose: find out whether another demo account type (e.g. Raw ECN) on the same
broker exposes the source symbol ``XAUUSD+`` and, if so, record its specs and
(optionally) raw tick history for later comparison with the public ledger.

Guards (same spirit as ``vantage_readonly.py``): the terminal must already be
running (never launched here), no login/password/server parameters are ever
passed, no symbol selection, no order requests, demo accounts only, and the
account/terminal are re-verified before and after every query.  Raw evidence is
written to exclusive-create files; nothing existing is touched.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from probe_vantage_feed import ROOT, sha, write_json
from vantage_readonly import running_terminal_pids, same_path

UTC = timezone.utc
SPEC_FIELDS = ("name", "visible", "digits", "point", "spread", "spread_float", "trade_mode",
               "trade_stops_level", "trade_freeze_level", "trade_contract_size", "volume_min", "volume_max",
               "volume_step", "trade_tick_size", "trade_tick_value", "path", "currency_profit")


class ProbeReader:
    def __init__(self, connector, terminal, expected_login, expected_server):
        self._c = connector
        self.terminal = Path(terminal)
        self.expected_login = expected_login
        self.expected_server = expected_server

    def verify(self):
        account, info = self._c.account_info(), self._c.terminal_info()
        if account is None or info is None:
            raise RuntimeError("Account/terminal metadata unavailable; refuse query")
        if account.trade_mode != self._c.ACCOUNT_TRADE_MODE_DEMO:
            raise RuntimeError("Not a demo account; refuse query")
        if self.expected_login is not None and account.login != self.expected_login:
            raise RuntimeError("Unexpected account login; refuse query without relogin")
        if self.expected_server is not None and account.server != self.expected_server:
            raise RuntimeError("Unexpected server; refuse query")
        if not same_path(info.path, self.terminal.parent) or not info.connected:
            raise RuntimeError("Wrong/disconnected terminal; refuse query")
        return {"login": account.login, "server": account.server, "demo": True, "currency": account.currency,
                "leverage": account.leverage, "company": account.company, "terminal_path": info.path,
                "build": info.build, "connected": info.connected}

    def _read(self, method, *args):
        before = self.verify()
        value = getattr(self._c, method)(*args)
        error = self._c.last_error()
        if self.verify() != before:
            raise RuntimeError("Account/terminal changed during query")
        if value is None:
            raise RuntimeError(f"{method} returned no data: {error}")
        return value

    def symbols(self):
        return self._read("symbols_get")

    def specs(self, symbol):
        row = self._read("symbol_info", symbol)
        return {key: getattr(row, key, None) for key in SPEC_FIELDS}

    def ticks(self, symbol, start, end):
        return self._read("copy_ticks_range", symbol, start, end, self._c.COPY_TICKS_ALL)

    def latest_tick(self, symbol):
        return self._read("symbol_info_tick", symbol)


@contextmanager
def attach_other(terminal, *, expected_login=None, expected_server=None, portable=True,
                 connector=None, process_check=running_terminal_pids):
    terminal = Path(terminal)
    if not terminal.is_file() or not process_check(terminal):
        raise RuntimeError("Terminal is not already running; will not launch it")
    if connector is None:
        import MetaTrader5 as connector
    try:
        if not connector.initialize(str(terminal), portable=portable, timeout=10000):
            raise RuntimeError(f"Read connection failed: {connector.last_error()}")
        reader = ProbeReader(connector, terminal, expected_login, expected_server)
        reader.verify()
        yield reader
    finally:
        connector.shutdown()


def probe(reader, symbol, name_filter="XAU"):
    names = sorted(row.name for row in reader.symbols())
    related = [n for n in names if name_filter.lower() in n.lower()]
    result = {"account": reader.verify(), "symbols_total": len(names), "symbols_matching_filter": related,
              "target_symbol": symbol, "target_present": symbol in names, "specs": {}}
    for name in related:
        result["specs"][name] = reader.specs(name)
    if symbol in names:
        before = int(time.time() * 1000)
        tick = reader.latest_tick(symbol)
        after = int(time.time() * 1000)
        result["clock_probe"] = {"local_utc_ms_before": before, "local_utc_ms_after": after,
                                 "tick_time_msc": int(tick.time_msc), "bid": float(tick.bid), "ask": float(tick.ask),
                                 "note": "tick epoch minus local UTC ~ raw server clock shift if the market is open"}
    return result


def export_ticks(reader, symbol, tag, start, end, shift_ms):
    """Daily raw + normalized (raw - shift) tick caches, exclusive create, half-open filtered."""
    raw_dir, norm_dir = ROOT / "data" / f"vantage_raw_ticks_{tag}", ROOT / "data" / f"proxy_ticks_{tag}"
    raw_dir.mkdir(exist_ok=False)
    norm_dir.mkdir(exist_ok=False)
    cursor, days = start, []
    shift = timedelta(milliseconds=shift_ms)
    while cursor < end:
        stop = min(end, cursor.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
        lo, hi = round((cursor + shift).timestamp() * 1000), round((stop + shift).timestamp() * 1000)
        ticks = reader.ticks(symbol, cursor + shift, stop + shift)
        ticks = ticks[(ticks["time_msc"] >= lo) & (ticks["time_msc"] < hi)]
        if len(ticks) and np.any(np.diff(ticks["time_msc"]) < 0):
            raise RuntimeError("Unordered raw ticks; refuse silent sorting")
        valid = np.isfinite(ticks["bid"]) & np.isfinite(ticks["ask"]) & (ticks["bid"] > 0) & (ticks["ask"] >= ticks["bid"])
        name = f"{cursor:%Y-%m-%d}"
        np.savez_compressed(raw_dir / (name + ".npz"), ticks=ticks)
        np.savez_compressed(norm_dir / (name + ".npz"), time_msc=ticks["time_msc"] - shift_ms,
                            bid=ticks["bid"], ask=ticks["ask"])
        meta = {"day": name, "symbol": symbol, "ticks": len(ticks), "invalid_quotes": int((~valid).sum()),
                "raw_sha256": sha(raw_dir / (name + ".npz")), "sha256": sha(norm_dir / (name + ".npz")),
                "query_shift_ms": shift_ms, "canonical_start_inferred": cursor.isoformat(),
                "canonical_end_exclusive_inferred": stop.isoformat(), "source_feed_identity_verified": False}
        write_json(norm_dir / (name + ".json"), meta)
        days.append(meta)
        cursor = stop
    return days


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", required=True, help="path to the already running terminal64.exe")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--symbol", default="XAUUSD+")
    parser.add_argument("--expected-login", type=int, default=None)
    parser.add_argument("--expected-server", default=None)
    parser.add_argument("--no-portable", action="store_true", help="terminal is a normal (non-portable) install")
    parser.add_argument("--export-start", help="inferred UTC inclusive; omit to only probe")
    parser.add_argument("--export-end", help="inferred UTC exclusive")
    parser.add_argument("--query-shift-hours", type=int, default=3)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    folder = ROOT / "data" / f"vantage_probe_{args.tag}"
    folder.mkdir(exist_ok=False)
    with attach_other(args.terminal, expected_login=args.expected_login, expected_server=args.expected_server,
                      portable=not args.no_portable) as reader:
        report = probe(reader, args.symbol)
        report["created_utc"] = datetime.now(UTC).isoformat()
        report["probe_sha256_of_this_script"] = sha(Path(__file__))
        if args.export_start and args.export_end and report["target_present"]:
            start = datetime.fromisoformat(args.export_start).replace(tzinfo=UTC)
            end = datetime.fromisoformat(args.export_end).replace(tzinfo=UTC)
            report["export"] = export_ticks(reader, args.symbol, args.tag, start, end,
                                            args.query_shift_hours * 3_600_000)
    write_json(folder / "probe.json", report)
    print(json.dumps({k: report[k] for k in ("symbols_matching_filter", "target_present")}, ensure_ascii=False))
    if report["target_present"]:
        print(json.dumps(report["specs"].get(args.symbol), default=str))


if __name__ == "__main__":
    main()
