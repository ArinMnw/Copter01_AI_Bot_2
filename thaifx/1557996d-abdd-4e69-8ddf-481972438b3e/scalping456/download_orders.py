"""Download the public Scalping456 trade history from ThaiFXBook.

The profile uses a Next.js server action for pagination.  This script keeps a
local, reproducible snapshot of every public closed-order field used in the
analysis.  It validates page coverage, row count, UUID uniqueness and ticket
uniqueness before writing the final files.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import local
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PROFILE_ID = "1557996d-abdd-4e69-8ddf-481972438b3e"
PROFILE_URL = f"https://thaifxbook.com/p/{PROFILE_ID}"
SERVER_ACTION = "60769b4f27558ef8b935c92e07670bdf472bf9374d"
EXPECTED_COUNT = 35_462
PAGE_SIZE = 20
EXPECTED_PAGES = (EXPECTED_COUNT + PAGE_SIZE - 1) // PAGE_SIZE
FIELDS = [
    "id",
    "ticket",
    "symbol",
    "trade_type",
    "volume",
    "profit",
    "close_time",
    "open_time",
    "open_price",
    "close_price",
    "pips",
    "sl",
    "tp",
    "comment",
]
_thread_state = local()


def _session() -> requests.Session:
    session = getattr(_thread_state, "session", None)
    if session is None:
        session = requests.Session()
        retry = Retry(
            total=8,
            connect=8,
            read=8,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"POST"}),
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.headers.update(
            {
                "Accept": "text/x-component",
                "Content-Type": "text/plain;charset=UTF-8",
                "Next-Action": SERVER_ACTION,
                "Origin": "https://thaifxbook.com",
                "Referer": PROFILE_URL,
                "User-Agent": "Scalping456-research-snapshot/1.0",
            }
        )
        _thread_state.session = session
    return session


def fetch_page(page: int) -> tuple[int, list[dict[str, Any]]]:
    response = _session().post(PROFILE_URL, data=json.dumps([PROFILE_ID, page]), timeout=45)
    response.raise_for_status()
    payload_line = next((line[2:] for line in response.text.splitlines() if line.startswith("1:")), None)
    if payload_line is None:
        raise ValueError(f"Page {page}: server-action payload line not found")
    payload = json.loads(payload_line)
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"Page {page}: rows is not a list")
    expected = PAGE_SIZE if page < EXPECTED_PAGES else EXPECTED_COUNT % PAGE_SIZE
    if len(rows) != expected:
        raise ValueError(f"Page {page}: expected {expected} rows, got {len(rows)}")
    return page, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "data")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    started = time.time()
    pages: dict[int, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_page, page): page for page in range(1, EXPECTED_PAGES + 1)}
        for done, future in enumerate(as_completed(futures), start=1):
            page, rows = future.result()
            pages[page] = rows
            if done % 100 == 0 or done == EXPECTED_PAGES:
                print(f"downloaded {done}/{EXPECTED_PAGES} pages", flush=True)

    orders = [row for page in range(1, EXPECTED_PAGES + 1) for row in pages[page]]
    if len(orders) != EXPECTED_COUNT:
        raise ValueError(f"Expected {EXPECTED_COUNT} total rows, got {len(orders)}")
    ids = [row["id"] for row in orders]
    tickets = [row["ticket"] for row in orders]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate order UUIDs detected")
    if len(set(tickets)) != len(tickets):
        raise ValueError("Duplicate tickets detected")

    jsonl_path = args.out / "orders_35462.jsonl"
    csv_path = args.out / "orders_35462.csv"
    manifest_path = args.out / "manifest.json"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in orders:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field) for field in FIELDS} for row in orders)

    manifest = {
        "profile_id": PROFILE_ID,
        "profile_url": PROFILE_URL,
        "server_action": SERVER_ACTION,
        "rows": len(orders),
        "pages": EXPECTED_PAGES,
        "page_size": PAGE_SIZE,
        "first_close_time": orders[-1]["close_time"],
        "last_close_time": orders[0]["close_time"],
        "unique_ids": len(set(ids)),
        "unique_tickets": len(set(tickets)),
        "elapsed_seconds": round(time.time() - started, 2),
        "fields": FIELDS,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
