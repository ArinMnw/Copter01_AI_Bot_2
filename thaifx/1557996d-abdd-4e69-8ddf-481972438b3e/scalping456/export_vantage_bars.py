"""Guarded broker OHLC export for actual closed-bar research, no tick fabrication."""

import argparse
import re
from datetime import datetime, timezone

import numpy as np

from probe_vantage_feed import ROOT, sha, write_json
from vantage_readonly import attach


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="vantage_broker_bars_20261008")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid output tag")
    target = ROOT / "data" / args.tag
    target.mkdir(exist_ok=False)
    # Raw epoch encodes source/server clock, based on previous independent probes.
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    end = datetime(2026, 10, 8, 4, 17, 56, tzinfo=timezone.utc)
    report = {"script_sha256": sha(__file__), "guard_sha256": sha(ROOT / "vantage_readonly.py"),
              "query_start_raw_clock": start.isoformat(), "query_end_raw_clock_exclusive": end.isoformat(),
              "raw_timestamps_preserved": True, "inferred_utc_shift_ms": 10800000,
              "source_feed_identity_verified": False, "feeds": {}}
    with attach() as reader:
        report["account"] = reader.verify()
        for feed in ("XAUUSD", "FixedVol20"):
            for minutes in (1, 5, 15, 30, 60):
                rates = reader.rates(feed, minutes, start, end)
                rates = rates[(rates["time"] >= int(start.timestamp())) & (rates["time"] < int(end.timestamp()))]
                path = target / f"{feed}_M{minutes}_raw.npz"
                np.savez_compressed(path, rates=rates)
                normalized = target / f"{feed}_M{minutes}_inferred.npz"
                close_ms = (rates["time"] + minutes * 60 - 10800) * 1000
                np.savez_compressed(normalized, open_ms=(rates["time"] - 10800) * 1000,
                                    close_ms=close_ms, open=rates["open"], high=rates["high"],
                                    low=rates["low"], close=rates["close"], spread=rates["spread"],
                                    tick_volume=rates["tick_volume"])
                report["feeds"][path.stem] = {
                    "symbol": feed, "minutes": minutes, "rows": len(rates),
                    "raw_sha256": sha(path), "inferred_sha256": sha(normalized),
                    "fully_closed_before_replay_end": int((close_ms <= (int(end.timestamp()) - 10800) * 1000).sum()),
                    "availability_rule": "open + duration <= current tick; incomplete final bar never consumed",
                    "specs": reader.specs(feed),
                }
                print(feed, minutes, len(rates), flush=True)
    write_json(target / "report.json", report)


if __name__ == "__main__":
    main()
