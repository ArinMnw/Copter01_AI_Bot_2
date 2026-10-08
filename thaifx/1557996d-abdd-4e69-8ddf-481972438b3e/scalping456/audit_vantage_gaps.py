"""Classify observed tick gaps against raw M1; requery only bars-without-ticks.

No raw-cache overwrite or silent filling. Supplements have independent hashes.
Absence of M1 bars is not itself proof of scheduled market closure.
"""

import json
from datetime import datetime, timezone

import numpy as np

from probe_vantage_feed import ROOT, sha, stamp, write_json
from vantage_readonly import attach


def main():
    target = ROOT / "data/vantage_gap_audit_20261008"
    target.mkdir(exist_ok=False)
    quotes = ROOT / "data/vantage_full_quotes_20261008/report.json"
    initial = ROOT / "data/vantage_initial_20261008/report.json"
    report = json.loads(quotes.read_text(encoding="utf-8"))
    probes = json.loads(initial.read_text(encoding="utf-8"))
    source = [json.loads(line) for line in (ROOT / "data/orders_35462.jsonl").read_text(encoding="utf-8").splitlines()]
    intervals = {symbol: [(stamp(row["open_time"]) - 10800, stamp(row["close_time"]) - 10800)
                          for row in source if row["symbol"] == symbol] for symbol in ("XAUUSD+", "FixedVol20")}
    result = {"quotes_report_sha256": sha(quotes), "initial_probe_sha256": sha(initial),
              "script_sha256": sha(__file__), "gaps": [], "original_caches_unchanged": True}
    with attach() as reader:
        result["account"] = reader.verify()
        for symbol, feed in (("XAUUSD+", "XAUUSD"), ("FixedVol20", "FixedVol20")):
            path = initial.parent / f"{feed}_m1_raw.npz"
            if sha(path) != probes["feeds"][feed]["raw_m1_sha256"]:
                raise RuntimeError("M1 digest mismatch")
            rates = np.load(path)["rates"]
            t = rates["time"] - 10800
            for index, gap in enumerate(g for g in report["data_gaps"] if g["source_symbol"] == symbol):
                start, end = gap["start_ms"] / 1000, gap["end_ms"] / 1000
                bars = int(((t > start + 60) & (t < end - 60)).sum())
                record = {**gap, "m1_bars_strictly_inside": bars,
                          "orders_held_across_gap": sum(opening < end and closing > start for opening, closing in intervals[symbol]),
                          "classification": "bars_without_exported_ticks" if bars else "no_m1_bars_inside_reason_unverified"}
                if bars:
                    query_start = datetime.fromtimestamp(start + 10800, timezone.utc)
                    query_end = datetime.fromtimestamp(end + 10800 + .001, timezone.utc)
                    ticks = reader.ticks(feed, query_start, query_end)
                    supplemental = target / f"{feed}_gap{index}_requery_raw.npz"
                    np.savez_compressed(supplemental, ticks=ticks)
                    normalized = ticks["time_msc"] - 10800000
                    record.update({"supplemental_raw_file": supplemental.name, "supplemental_sha256": sha(supplemental),
                                   "requery_returned_ticks": len(ticks),
                                   "requery_strictly_inside_ticks": int(((normalized > gap["start_ms"]) & (normalized < gap["end_ms"])).sum()),
                                   "query_start": query_start.isoformat(), "query_end": query_end.isoformat()})
                result["gaps"].append(record)
    write_json(target / "report.json", result)
    print(json.dumps({"gaps": len(result["gaps"]), "bars_without_ticks": [g for g in result["gaps"] if g["m1_bars_strictly_inside"]]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
