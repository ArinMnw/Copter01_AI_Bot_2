"""Decode observed public hydration JSON without executing JavaScript.

Keep current-open observations separate from the closed-order snapshot.
Only selected trading statistics/market fields are exported, never credentials.
"""

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone

from probe_vantage_feed import ROOT, sha, write_json


def hydration_records(html):
    decoder = json.JSONDecoder()
    pieces = []
    for match in re.finditer(r"self\.__next_f\.push\(", html):
        value, _ = decoder.raw_decode(html, match.end())
        if isinstance(value, list) and len(value) > 1 and value[0] == 1 and isinstance(value[1], str):
            pieces.append(value[1])
    records = []
    for line in "".join(pieces).splitlines():
        if ":" not in line:
            continue
        record_id, value = line.split(":", 1)
        try:
            records.append((record_id, json.loads(value)))
        except json.JSONDecodeError:
            pass  # React import/text records are not JSON data; never execute them.
    return records


def objects(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from objects(item)
    elif isinstance(value, list):
        for item in value:
            yield from objects(item)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-tag", required=True)
    parser.add_argument("--output-name", default="metadata_extract.json")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.snapshot_tag):
        parser.error("Invalid tag")
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.json", args.output_name):
        parser.error("Invalid output name")
    folder = ROOT / "data" / args.snapshot_tag
    manifest = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        if sha(folder / item["file"]) != item["sha256"]:
            raise RuntimeError("Public archive digest differs")
    html = (folder / "profile.html").read_text(encoding="utf-8")
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "profile_sha256": sha(folder / "profile.html"),
              "script_sha256": sha(__file__), "snapshot_manifest_sha256": sha(folder / "report.json"),
              "public_url": manifest["public_url"], "stats": [], "equity_snapshot_series": [],
              "current_open_observations_not_source_orders": [], "closed_table_observed_keys": [],
              "all_original_closed_order_fields": manifest["original_field_population"],
              "current_open_comment_not_proof_of_past_EA_identity": True,
              "sparse_equity_not_full_balance_or_parameter_history": True,
              "source_snapshot_modified": False}
    stat_fields = ("total_trades", "ea_trade_count", "manual_trade_count", "verify_trade_count", "currency",
                   "deposits", "withdrawals", "total_commission", "abs_gain", "highest_balance",
                   "highest_balance_date", "total_lots", "total_pips", "long_trades", "short_trades")
    opening_fields = ("id", "ticket", "symbol", "trade_type", "volume", "pips", "profit", "open_price",
                      "current_price", "sl", "tp", "swap", "comment", "open_time")
    counter = Counter()
    for record_id, value in hydration_records(html):
        for obj in objects(value):
            counter.update(obj.keys())
            if isinstance(obj.get("stats"), dict) and "ea_trade_count" in obj["stats"]:
                stats = {key: obj["stats"][key] for key in stat_fields if key in obj["stats"]}
                report["stats"].append({"hydration_record_id": record_id, "fields": stats,
                                         "currentBalance": obj.get("currentBalance")})
            if isinstance(obj.get("snapshots"), list):
                report["equity_snapshot_series"].append({"hydration_record_id": record_id,
                    "currentBalance": obj.get("currentBalance"), "totalProfitOverride": obj.get("totalProfitOverride"),
                    "rows": [{"equity": row.get("equity"), "recorded_at": row.get("recorded_at")} for row in obj["snapshots"]]})
            if "current_price" in obj and "open_time" in obj and "ticket" in obj:
                report["current_open_observations_not_source_orders"].append({"hydration_record_id": record_id,
                    **{key: obj[key] for key in opening_fields if key in obj}})
            if "totalCount" in obj and isinstance(obj.get("rows"), list):
                report["closed_table_observed_keys"].append({"hydration_record_id": record_id,
                    "totalCount": obj["totalCount"], "row_keys": sorted({key for row in obj["rows"] for key in row})})
    report["selected_public_data_field_occurrences"] = {key: counter[key] for key in
        ("magic", "magic_number", "position_id", "deal_id", "commission", "swap", "ea_trade_count", "manual_trade_count")}
    write_json(folder / args.output_name, report)
    print(json.dumps({key: value for key, value in report.items() if key != "equity_snapshot_series"}, indent=2), flush=True)
    print("Equity snapshot row counts", [len(series["rows"]) for series in report["equity_snapshot_series"]], flush=True)


if __name__ == "__main__":
    main()
