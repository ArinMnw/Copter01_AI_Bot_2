"""One-to-one entry-only diagnostics; never a full-goal success metric."""

import argparse
import json
import re
from collections import Counter, defaultdict, deque
from decimal import Decimal

from probe_vantage_feed import ROOT, group, sha, stamp, write_json
from strict_source_matcher import decimal


def entry_key(row):
    return (row["symbol"], row["side"], row["open_second"], decimal(row["volume"]),
            decimal(row["open_price"], ".01" if row["symbol"] == "XAUUSD+" else ".001"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-tag", required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", value) for value in (args.tag, args.replay_tag)):
        parser.error("Invalid tag")
    folder = ROOT / "data" / args.replay_tag
    full = folder / "report.json"
    report = json.loads(full.read_text(encoding="utf-8"))
    source_path = ROOT / "data/orders_35462.jsonl"
    source = [json.loads(line, parse_float=Decimal) for line in source_path.read_text(encoding="utf-8").splitlines()]
    target = ROOT / "data" / args.tag
    target.mkdir(exist_ok=False)
    start_ms = round((min(stamp(row["open_time"]) for row in source) - 10800) * 1000)
    end_ms = round((max(stamp(row["close_time"]) for row in source) - 10800 + 1) * 1000)
    result = {"full_replay_report_sha256": sha(full), "source_sha256": sha(source_path), "script_sha256": sha(__file__),
              "diagnostic_only_not_goal_success": True, "full_source_clone_complete": False, "models": []}
    for model in report["models"]:
        name = model["name"]
        components = model["config"].get("components", [name])
        predicted = []
        for component in components:
            predicted.extend(json.loads(line) for line in (folder / f"{component}_predictions.jsonl").read_text(encoding="utf-8").splitlines())
        predicted = [row for row in predicted if row["open_ms"] < end_ms and (row["close_ms"] is None or row["close_ms"] >= start_ms)]
        assert len(predicted) == model["predicted_orders"]
        buckets = defaultdict(deque)
        for index, row in enumerate(predicted):
            buckets[entry_key(row)].append(index)
        counts = Counter()
        matched = 0
        with (target / f"{name}_all_source_entries.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for row in source:
                source_entry = {"symbol": row["symbol"], "side": row["trade_type"], "volume": row["volume"],
                                "open_second": round(stamp(row["open_time"])) - 10800, "open_price": row["open_price"]}
                queue = buckets[entry_key(source_entry)]
                index = queue.popleft() if queue else None
                if index is not None:
                    matched += 1
                    counts[group(row)] += 1
                stream.write(json.dumps({"ticket": row["ticket"], "symbol": row["symbol"],
                                         "entry_only_exact_prediction_index": index,
                                         "not_full_order_match": True}) + "\n")
        result["models"].append({"name": name, "source_orders": len(source), "predicted_orders": len(predicted),
                                 "entry_only_exact": matched, "entry_only_missing": len(source) - matched,
                                 "entry_only_extra": len(predicted) - matched, "by_cohort": dict(counts),
                                 "full_order_exact": model["exact_all_observable_fields"]})
    write_json(target / "report.json", result)
    print(json.dumps(sorted(result["models"], key=lambda x: x["entry_only_exact"], reverse=True)[:8], indent=2), flush=True)


if __name__ == "__main__":
    main()
