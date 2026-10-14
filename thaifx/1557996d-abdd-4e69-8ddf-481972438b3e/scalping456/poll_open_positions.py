"""Read-only watcher for the PUBLIC profile page's current open positions (observation only).

The page embeds the open positions (ticket, side, volume, open price/time, current price, sl, tp, comment,
profit) and a data-sync timestamp ``updated_at``.  This script GETs the public profile page (robots.txt allows
``/p/...``), and appends a record only when the sync timestamp or any position field changes, plus a
heartbeat.  It polls slowly while the page is stale and faster once ``updated_at`` advances.  Nothing is
logged in, no form is submitted, no credentials are used, and the frozen order snapshot is never touched.
Output is exclusive-create JSONL; the manifest with hashes is written when the run ends normally.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from download_orders import PROFILE_URL
from extract_public_metadata import hydration_records, objects

ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
POSITION_FIELDS = ("ticket", "symbol", "trade_type", "volume", "open_price", "current_price", "sl", "tp", "comment",
                   "open_time", "profit", "pips", "swap")
HEARTBEAT_SECONDS = 600


def parse_page(html):
    """Return (updated_at or None, positions sorted by ticket) from the hydrated page."""
    updated, positions = None, {}
    for _, value in hydration_records(html):
        for obj in objects(value):
            if "updated_at" in obj and isinstance(obj["updated_at"], str):
                updated = obj["updated_at"]
            if "current_price" in obj and "open_time" in obj and "ticket" in obj:
                positions[obj["ticket"]] = {key: obj[key] for key in POSITION_FIELDS if key in obj}
    return updated, [positions[key] for key in sorted(positions)]


def signature(updated, positions):
    return json.dumps([updated, positions], sort_keys=True, separators=(",", ":"))


def next_interval(updated, last_change_monotonic, now_monotonic, idle, live, live_window=180):
    """Slow polling while the page has not synced recently, fast polling once it moves."""
    if updated is None or last_change_monotonic is None:
        return idle
    return live if now_monotonic - last_change_monotonic <= live_window else idle


def fetch(session):
    response = session.get(PROFILE_URL, timeout=45)
    response.raise_for_status()
    return response.text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--idle-interval", type=int, default=180, help="seconds while the page is stale")
    parser.add_argument("--live-interval", type=int, default=15, help="seconds after a recent sync")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    if args.idle_interval < 60 or args.live_interval < 10:
        parser.error("Refusing to poll a third-party page faster than 10 s (live) / 60 s (idle)")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    session = requests.Session()
    session.headers.update({"User-Agent": "Scalping456-research-forward/1.0", "Accept": "text/html"})
    path = folder / "open_positions_0000.jsonl"
    started = time.monotonic()
    last_signature, last_written, last_change = None, 0.0, None
    stats = {"polls": 0, "records": 0, "errors": 0, "sync_changes": 0}
    sync_seen = []
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        while time.monotonic() - started < args.hours * 3600:
            poll_start = datetime.now(UTC).isoformat()
            try:
                updated, positions = parse_page(fetch(session))
            except Exception as error:  # network/parse problems are recorded, never hidden
                stats["errors"] += 1
                stream.write(json.dumps({"poll_start_utc": poll_start, "error": repr(error)[:300]}) + "\n")
                stream.flush()
                time.sleep(args.idle_interval)
                continue
            poll_end = datetime.now(UTC).isoformat()
            stats["polls"] += 1
            sig = signature(updated, positions)
            now = time.monotonic()
            changed = sig != last_signature
            if changed:
                last_change = now
            if updated is not None and (not sync_seen or sync_seen[-1] != updated):
                if sync_seen:
                    stats["sync_changes"] += 1
                sync_seen.append(updated)
            if changed or now - last_written >= HEARTBEAT_SECONDS:
                stream.write(json.dumps({"poll_start_utc": poll_start, "poll_end_utc": poll_end, "updated_at": updated,
                                         "changed": changed, "n_open": len(positions), "positions": positions},
                                        ensure_ascii=False, separators=(",", ":")) + "\n")
                stream.flush()
                stats["records"] += 1
                last_written = now
            last_signature = sig
            time.sleep(next_interval(updated, last_change, time.monotonic(), args.idle_interval, args.live_interval))
    manifest = {"created_utc": datetime.now(UTC).isoformat(), "profile_url": PROFILE_URL, "stats": stats,
                "distinct_updated_at_values_seen": len(sync_seen), "first_updated_at": sync_seen[0] if sync_seen else None,
                "last_updated_at": sync_seen[-1] if sync_seen else None,
                "sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()},
                "note": "observation only; positions/sl/current_price are as published by the page, sync cadence = updated_at changes"}
    with (folder / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
