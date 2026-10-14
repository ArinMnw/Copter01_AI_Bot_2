"""Fetch closed orders published AFTER the frozen 35,462-row snapshot (forward data).

Read-only public POST used by the profile's own pagination (same call as
download_orders.py).  The frozen snapshot files are never modified: new rows go
to a fresh folder with their first-seen UTC time.  Pages are fetched newest
first until a ticket from the frozen snapshot appears, one request at a time
with a pause between requests.  ``--watch`` repeats every ``--interval``
seconds and appends only unseen tickets (exclusive per-run files).
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

from download_orders import PROFILE_ID, PROFILE_URL, SERVER_ACTION

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "data/orders_35462.jsonl"
SNAPSHOT_SHA256 = "b8f5f75de07ba335ba607855167b5c77600954561c7c740621a335fa1b9825f1"
PAUSE_SECONDS = 1.0
MAX_PAGES = 200


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_tickets():
    if sha256(SNAPSHOT) != SNAPSHOT_SHA256:
        raise RuntimeError("Frozen snapshot changed; refuse to continue")
    return {json.loads(line)["ticket"] for line in SNAPSHOT.read_text(encoding="utf-8").splitlines()}


def fetch_page(session, page):
    response = session.post(PROFILE_URL, data=json.dumps([PROFILE_ID, page]), timeout=45)
    response.raise_for_status()
    line = next((x[2:] for x in response.text.splitlines() if x.startswith("1:")), None)
    if line is None:
        raise ValueError(f"page {page}: payload not found")
    rows = json.loads(line).get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"page {page}: rows missing")
    return rows


def new_session():
    session = requests.Session()
    session.headers.update({
        "Accept": "text/x-component", "Content-Type": "text/plain;charset=UTF-8", "Next-Action": SERVER_ACTION,
        "Origin": "https://thaifxbook.com", "Referer": PROFILE_URL, "User-Agent": "Scalping456-research-forward/1.0"})
    return session


def collect_new(session, known):
    """Newest-first pages until the frozen snapshot (or a known forward ticket) is reached."""
    fresh, seen_boundary = [], False
    for page in range(1, MAX_PAGES + 1):
        rows = fetch_page(session, page)
        for row in rows:
            if row["ticket"] in known:
                seen_boundary = True
            else:
                fresh.append(row)
        if seen_boundary or not rows:
            break
        time.sleep(PAUSE_SECONDS)
    if not seen_boundary:
        raise RuntimeError("Reached MAX_PAGES without touching known tickets; gap possible")
    return fresh


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=120)
    parser.add_argument("--hours", type=float, default=0.0, help="stop watching after this many hours (0 = single pass)")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    known = set(frozen_tickets())
    session = new_session()
    started = time.time()
    run, total, log = 0, 0, []
    while True:
        observed = datetime.now(timezone.utc).isoformat()
        fresh = collect_new(session, known)
        new_rows = [dict(row, first_seen_utc=observed) for row in fresh]
        if new_rows:
            path = folder / f"new_orders_{run:04d}.jsonl"
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                for row in new_rows:
                    stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            known.update(row["ticket"] for row in new_rows)
            total += len(new_rows)
            run += 1
        log.append({"observed_utc": observed, "new_rows": len(new_rows), "total_forward_rows": total})
        print(observed, "new", len(new_rows), "total", total, flush=True)
        if not args.watch or (args.hours and time.time() - started > args.hours * 3600):
            break
        time.sleep(args.interval)
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "profile_id": PROFILE_ID,
                "frozen_snapshot_sha256": SNAPSHOT_SHA256, "pause_seconds": PAUSE_SECONDS, "rows": total, "polls": log,
                "files": {p.name: sha256(p) for p in sorted(folder.glob("new_orders_*.jsonl"))},
                "note": "read-only public POST; frozen snapshot untouched; first_seen_utc is the poll time, not the order time"}
    with (folder / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
