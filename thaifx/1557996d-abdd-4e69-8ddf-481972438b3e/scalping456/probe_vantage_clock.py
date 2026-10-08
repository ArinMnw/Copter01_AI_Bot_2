"""Independent live epoch anchor and prespecified tick hour-offset diagnostics."""

import json
from datetime import datetime, timezone

import numpy as np

from probe_vantage_feed import ROOT, group, score_tick, sha, stamp, write_json
from vantage_readonly import attach


def main():
    target = ROOT / "data/vantage_tick_clock_20261008"
    target.mkdir(exist_ok=True)
    if any(target.iterdir()):
        raise RuntimeError("Previous clock evidence exists; refuse overwrite")
    source = ROOT / "data/orders_35462.jsonl"
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    report = {"source_sha256": sha(source), "script_sha256": sha(__file__),
              "live_anchors": [], "tick_offset_witnesses": [], "not_strategy_verification": True}
    with attach() as reader:
        report["account"] = reader.verify()
        for feed, source_symbol in (("XAUUSD", "XAUUSD+"), ("FixedVol20", "FixedVol20")):
            before = datetime.now(timezone.utc)
            tick = reader.latest_tick(feed)
            after = datetime.now(timezone.utc)
            report["live_anchors"].append({
                "feed": feed, "utc_before": before.isoformat(), "utc_after": after.isoformat(),
                "latest_tick_raw_time_msc": tick.time_msc,
                "raw_epoch_minus_utc_before_seconds": tick.time_msc / 1000 - before.timestamp(),
                "stale_quote_possible": True,
            })
            subset = sorted((row for row in rows if row["symbol"] == source_symbol), key=lambda r: r["open_time"])
            indices = np.linspace(0, len(subset) - 1, 8).astype(int)
            digits = reader.specs(feed)["digits"]
            for index in indices:
                row = subset[index]
                for offset in (-3, -2, -1, 0, 1, 2, 3):
                    second = stamp(row["open_time"]) + offset * 3600
                    start = datetime.fromtimestamp(second - 2, timezone.utc)
                    end = datetime.fromtimestamp(second + 3, timezone.utc)
                    ticks = reader.ticks(feed, start, end)
                    path = target / f"{feed}_{row['ticket']}_{offset:+d}.npz"
                    np.savez_compressed(path, ticks=ticks)
                    witness = score_tick(row, "open", ticks, offset, digits)
                    witness.update({"raw_file": path.name, "sha256": sha(path)})
                    report["tick_offset_witnesses"].append(witness)
    write_json(target / "report.json", report)
    print(json.dumps({"live_anchors": report["live_anchors"]}, indent=2), flush=True)
    for source_symbol in ("XAUUSD+", "FixedVol20"):
        for offset in (-3, -2, -1, 0, 1, 2, 3):
            subset = [x for x in report["tick_offset_witnesses"] if x["source_symbol"] == source_symbol and x["raw_to_query_hours"] == offset]
            errors = [x["min_abs_error_same_second"] for x in subset if x["min_abs_error_same_second"] is not None]
            print(json.dumps({"symbol": source_symbol, "offset": offset, "covered": len(errors),
                              "median_abs_same_second_error": float(np.median(errors)) if errors else None}), flush=True)


if __name__ == "__main__":
    main()
