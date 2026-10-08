"""Guarded, resumable raw + separate normalized bid/ask history export.

Alignment is explicit, not inferred from broker branding or inherited IUX shift.
The normalized clock is an inference, never a rewrite of raw evidence.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from probe_vantage_feed import ROOT, sha, write_json
from vantage_readonly import attach


UTC = timezone.utc


def utc_datetime(value):
    result = datetime.fromisoformat(value)
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)


def normalize_ticks(ticks, shift_ms):
    return {
        "time_msc": ticks["time_msc"] - shift_ms,
        "bid": ticks["bid"], "ask": ticks["ask"],
    }


def validate_cache(meta, raw, normalized, symbol, shift_ms, start, end):
    if (meta["symbol"] != symbol or meta["query_shift_ms"] != shift_ms
            or meta["canonical_start_inferred"] != start.isoformat()
            or meta["canonical_end_exclusive_inferred"] != end.isoformat()
            or sha(raw) != meta["raw_sha256"] or sha(normalized) != meta["sha256"]):
        raise RuntimeError("Cache/provenance mismatch: refuse overwrite " + str(raw))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", choices=["XAUUSD", "XAUUSD.crp", "FixedVol20"], required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--start", required=True, help="Inferred canonical UTC inclusive")
    parser.add_argument("--end", required=True, help="Inferred canonical UTC exclusive")
    parser.add_argument("--query-shift-hours", type=int, required=True,
                        help="Vantage raw query epoch minus inferred canonical epoch, measured independently")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    start, end = utc_datetime(args.start), utc_datetime(args.end)
    if end <= start:
        parser.error("Empty range")
    shift = timedelta(hours=args.query_shift_hours)
    shift_ms = int(shift.total_seconds() * 1000)
    raw_dir = ROOT / "data" / f"vantage_raw_ticks_{args.tag}"
    normalized_dir = ROOT / "data" / f"proxy_ticks_{args.tag}"
    raw_dir.mkdir(exist_ok=True)
    normalized_dir.mkdir(exist_ok=True)
    summary_path = raw_dir / "manifest.json"
    if summary_path.exists():
        old = json.loads(summary_path.read_text(encoding="utf-8"))
        if (old["symbol"] != args.symbol or old["query_shift_ms"] != shift_ms
                or old["start_inferred"] != start.isoformat() or old["end_inferred"] != end.isoformat()):
            raise RuntimeError("Manifest differs; use another tag, do not overwrite")
    with attach() as reader:
        account = reader.verify()
        specs = reader.specs(args.symbol)
        if not summary_path.exists():
            write_json(summary_path, {
                "created_utc": datetime.now(UTC).isoformat(), "symbol": args.symbol,
                "account": account, "specs": specs, "query_shift_ms": shift_ms,
                "start_inferred": start.isoformat(), "end_inferred": end.isoformat(),
                "raw_order_snapshot_sha256": sha(ROOT / "data/orders_35462.jsonl"),
                "exporter_sha256": sha(Path(__file__)), "guard_sha256": sha(ROOT / "vantage_readonly.py"),
                "source_feed_identity_verified": False,
                "clock": "raw numeric epoch matches source raw clock; inferred UTC = raw - explicit shift",
                "normalization_is_inference_not_verified_original_feed": True,
            })
        cursor = start
        while cursor < end:
            boundary = cursor.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            stop = min(end, boundary)
            name = f"{cursor:%Y-%m-%d}"
            raw_path = raw_dir / (name + ".npz")
            normalized_path = normalized_dir / (name + ".npz")
            meta_path = normalized_path.with_suffix(".json")
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                validate_cache(meta, raw_path, normalized_path, args.symbol, shift_ms, cursor, stop)
                print(json.dumps({"day": name, "cached": True, "ticks": meta["ticks"]}), flush=True)
                cursor = stop
                continue
            if raw_path.exists() or normalized_path.exists():
                raise RuntimeError("Partial export retained; verify separately/use another tag: " + name)
            query_start, query_end = cursor + shift, stop + shift
            ticks = reader.ticks(args.symbol, query_start, query_end)
            lo, hi = round(query_start.timestamp() * 1000), round(query_end.timestamp() * 1000)
            # API end can be inclusive. Half-open filtering prevents boundary duplication.
            ticks = ticks[(ticks["time_msc"] >= lo) & (ticks["time_msc"] < hi)]
            valid = (np.isfinite(ticks["bid"]) & np.isfinite(ticks["ask"])
                     & (ticks["bid"] > 0) & (ticks["ask"] >= ticks["bid"]))
            invalid = int((~valid).sum())
            if len(ticks) and np.any(np.diff(ticks["time_msc"]) < 0):
                raise RuntimeError("Unordered raw ticks; refuse silent sorting")
            np.savez_compressed(raw_path, ticks=ticks)
            np.savez_compressed(normalized_path, **normalize_ticks(ticks, shift_ms))
            gaps = np.diff(ticks["time_msc"]) if len(ticks) > 1 else np.array([], dtype=np.int64)
            meta = {
                "day": name, "symbol": args.symbol, "ticks": len(ticks), "invalid_quotes": invalid,
                "raw_file": str(raw_path), "raw_sha256": sha(raw_path), "sha256": sha(normalized_path),
                "query_shift_ms": shift_ms, "feed_time_shift_hours": args.query_shift_hours,
                "canonical_start_inferred": cursor.isoformat(), "canonical_end_exclusive_inferred": stop.isoformat(),
                "query_start": query_start.isoformat(), "query_end_exclusive": query_end.isoformat(),
                "first_raw_time_msc": int(ticks["time_msc"][0]) if len(ticks) else None,
                "last_raw_time_msc": int(ticks["time_msc"][-1]) if len(ticks) else None,
                "maximum_intertick_gap_ms": int(gaps.max()) if len(gaps) else None,
                "gaps_over_60s": int((gaps > 60000).sum()),
                "spread_min": float((ticks["ask"] - ticks["bid"]).min()) if len(ticks) else None,
                "spread_median": float(np.median(ticks["ask"] - ticks["bid"])) if len(ticks) else None,
                "spread_max": float((ticks["ask"] - ticks["bid"]).max()) if len(ticks) else None,
                "source_feed_identity_verified": False,
            }
            write_json(meta_path, meta)
            print(json.dumps({"day": name, "symbol": args.symbol, "ticks": len(ticks),
                              "invalid": invalid, "maximum_gap_ms": meta["maximum_intertick_gap_ms"]}), flush=True)
            cursor = stop


if __name__ == "__main__":
    main()
