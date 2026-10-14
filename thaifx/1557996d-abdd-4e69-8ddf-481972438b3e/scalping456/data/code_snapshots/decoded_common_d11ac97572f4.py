"""Shared read-only loaders for the decoded-mechanics experiments.

Ticks come from the hash-verified Vantage demo caches (inferred UTC clock);
orders come from the untouched public snapshot.  Prices are integer cents
(gold) or thousandths (FixedVol20) to avoid float equality errors.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from replay_vantage_candle_grid import load_ticks

ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
SOURCE_SHA256 = "b8f5f75de07ba335ba607855167b5c77600954561c7c740621a335fa1b9825f1"
SERVER_OFFSET_MS = 10_800_000   # raw server clock minus this = inferred UTC
SPLIT_MS = round(datetime(2026, 9, 21, tzinfo=UTC).timestamp() * 1000)


def ms(text: str) -> int:
    """Inferred-UTC wall clock text -> epoch milliseconds."""
    return round(datetime.fromisoformat(text).replace(tzinfo=UTC).timestamp() * 1000)


def load_gold_ticks():
    (times, bids, asks), provenance = load_ticks("vantage_gold_shift3", "XAUUSD")
    return (times, np.rint(bids * 100).astype(np.int64), np.rint(asks * 100).astype(np.int64)), provenance


def load_fixed_ticks():
    (times, bids, asks), provenance = load_ticks("vantage_fixed_shift3", "FixedVol20")
    return (times, np.rint(bids * 1000).astype(np.int64), np.rint(asks * 1000).astype(np.int64)), provenance


def load_source(symbol=None):
    """Raw ledger rows with open/close milliseconds on the inferred-UTC clock."""
    path = ROOT / "data/orders_35462.jsonl"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if symbol is not None and row["symbol"] != symbol:
            continue
        scale = 100 if row["symbol"] == "XAUUSD+" else 1000
        row["opms"] = round(datetime.fromisoformat(row["open_time"]).timestamp() * 1000) - SERVER_OFFSET_MS
        row["clms"] = round(datetime.fromisoformat(row["close_time"]).timestamp() * 1000) - SERVER_OFFSET_MS
        row["E"] = round(float(row["open_price"]) * scale)
        row["X"] = round(float(row["close_price"]) * scale)
        rows.append(row)
    rows.sort(key=lambda row: (row["opms"], row["ticket"]))
    return rows
