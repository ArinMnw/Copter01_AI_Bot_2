"""Read-only MT5 tick export for offline research. Never sends trade requests.

Run using the installed MetaTrader5 Python binding; bundled analysis Python
does not include that broker connector. Cache times are normalized by the
explicit empirical feed shift. This is a proxy feed, not the source EA feed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5
import numpy as np


ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--symbol", default="XAUUSD.iux")
    parser.add_argument("--tag", default="iux_shift1")
    parser.add_argument("--feed-time-shift-hours", type=float, default=1)
    parser.add_argument("--start", required=True, help="Canonical UTC date, inclusive")
    parser.add_argument("--end", required=True, help="Canonical UTC date, exclusive")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.tag):
        parser.error("Tag may contain only letters, digits, underscores and hyphens")
    day = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
    if end <= day:
        parser.error("End must be later than start")
    shift = timedelta(hours=args.feed_time_shift_hours)
    shift_ms = round(shift.total_seconds() * 1000)
    target = ROOT / "data" / f"proxy_ticks_{args.tag}"
    target.mkdir(parents=True, exist_ok=True)
    if not mt5.initialize(args.terminal, portable=True):
        raise RuntimeError(f"MT5 read connection failed: {mt5.last_error()}")
    try:
        if not mt5.symbol_select(args.symbol, True):
            raise RuntimeError(f"Symbol unavailable: {mt5.last_error()}")
        while day < end:
            file = target / f"{day:%Y-%m-%d}.npz"
            meta_file = file.with_suffix(".json")
            if file.exists() and meta_file.exists():
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                if meta["symbol"] != args.symbol or meta["feed_time_shift_hours"] != args.feed_time_shift_hours:
                    raise RuntimeError(f"Cache provenance differs: {file.name}")
                digest = hashlib.sha256(file.read_bytes()).hexdigest()
                if digest != meta["sha256"]:
                    raise RuntimeError(f"Cache digest differs: {file.name}")
                print(f"verified existing {day.date()} ticks={meta['ticks']}", flush=True)
                day += timedelta(days=1)
                continue
            ticks = mt5.copy_ticks_range(args.symbol, day + shift, day + timedelta(days=1) + shift, mt5.COPY_TICKS_ALL)
            if ticks is None:
                raise RuntimeError(f"Tick query failed for {day.date()}: {mt5.last_error()}")
            times = ticks["time_msc"].astype(np.int64) - shift_ms
            bid = ticks["bid"].astype(np.float64)
            ask = ticks["ask"].astype(np.float64)
            # MT5 ranges can include the end boundary. Make cached days disjoint.
            keep = (times >= int(day.timestamp() * 1000)) & (times < int((day + timedelta(days=1)).timestamp() * 1000))
            times, bid, ask = times[keep], bid[keep], ask[keep]
            if len(times) and np.any(times[1:] < times[:-1]):
                raise RuntimeError(f"Out-of-order MT5 history: {day.date()}")
            np.savez_compressed(file, time_msc=times, bid=bid, ask=ask)
            valid = np.isfinite(bid) & np.isfinite(ask) & (bid > 0) & (ask >= bid)
            meta = {
                "symbol": args.symbol, "proxy_not_source": True,
                "canonical_utc_day": str(day.date()),
                "feed_time_shift_hours": args.feed_time_shift_hours,
                "ticks": len(times), "invalid_bid_ask_ticks": int((~valid).sum()),
                "first_time_msc": int(times[0]) if len(times) else None,
                "last_time_msc": int(times[-1]) if len(times) else None,
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            }
            meta_file.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")
            print(f"exported {day.date()} ticks={len(times)} invalid={meta['invalid_bid_ask_ticks']}", flush=True)
            day += timedelta(days=1)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
