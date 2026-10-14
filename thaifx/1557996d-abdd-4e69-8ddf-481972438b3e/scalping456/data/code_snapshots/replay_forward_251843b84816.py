"""Forward holdout: frozen decoded engines vs orders published AFTER the frozen snapshot.

Predictions are produced from ticks and the unchanged regime schedule only and
are hashed into ``pre_score_manifest.json`` BEFORE any forward order is parsed.
Scoring then uses the same strict matcher (timing tolerance 0 at source
precision).  Nothing here is tuned on the forward rows.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np

from decoded_common import ROOT, SERVER_OFFSET_MS, SOURCE_SHA256, load_fixed_ticks, load_gold_ticks, ms
from decoded_schedule import FIXED_REGIMES, GOLD_REGIMES
from probe_vantage_feed import sha, write_json
from replay_decoded import to_prediction
from strategy_scalping456_decoded import FixedParams, GoldParams, simulate_fixed, simulate_gold
from strict_source_matcher import match_exact

UTC = timezone.utc
CODE = ("strategy_scalping456_decoded.py", "decoded_schedule.py", "decoded_common.py", "replay_decoded.py",
        "replay_forward.py", "fetch_forward_orders.py", "strict_source_matcher.py", "EXPERIMENT_DECODED_PLAN.md")
FORWARD_START = datetime(2026, 10, 8, 1, 17, 56, tzinfo=UTC)
FROZEN_LAST_CLOSE_MS = ms("2026-10-08T01:17:55")     # snapshot's last close (04:17:55 raw server clock - 3 h)


def load_forward_cache(tag, symbol, scale, start, end):
    """Hash/clock-verified forward tick cache (inferred UTC), half-open [start, end)."""
    cache = ROOT / "data" / ("proxy_ticks_" + tag)
    t, b, a, provenance = [], [], [], []
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    lo, hi = round(start.timestamp() * 1000), round(end.timestamp() * 1000)
    while day < end:
        path = cache / f"{day:%Y-%m-%d}.npz"
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        if sha(path) != meta["sha256"] or meta["symbol"] != symbol or meta["query_shift_ms"] != SERVER_OFFSET_MS:
            raise RuntimeError("Wrong cache/hash/clock: " + str(path))
        if meta["invalid_quotes"]:
            raise RuntimeError("Invalid quotes: refuse silently discarding")
        with np.load(path) as archive:
            if len(archive["time_msc"]) != meta["ticks"]:
                raise RuntimeError("Tick count mismatch")
            keep = (archive["time_msc"] >= lo) & (archive["time_msc"] < hi)
            t.append(archive["time_msc"][keep])
            b.append(np.rint(archive["bid"][keep] * scale).astype(np.int64))
            a.append(np.rint(archive["ask"][keep] * scale).astype(np.int64))
        provenance.append(meta)
        day += timedelta(days=1)
    return tuple(np.concatenate(parts) for parts in (t, b, a)), provenance


def join(old, new, label):
    (ot, ob, oa), (nt, nb, na) = old, new
    if len(ot) == 0 or len(nt) == 0 or nt[0] < ot[-1]:
        raise RuntimeError(f"{label}: caches overlap or are empty")
    return np.concatenate([ot, nt]), np.concatenate([ob, nb]), np.concatenate([oa, na])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--gold-tag", default="vantage_gold_fwd1")
    parser.add_argument("--fixed-tag", default="vantage_fixed_fwd1")
    parser.add_argument("--forward-tag", default="forward_watch_20261009")
    parser.add_argument("--horizon", default="2026-10-09T02:00:00", help="inferred UTC, exclusive")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid tag")
    horizon = datetime.fromisoformat(args.horizon).replace(tzinfo=UTC)
    horizon_ms = round(horizon.timestamp() * 1000)
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    hashes = {name: sha(ROOT / name) for name in CODE}
    gold_params = GoldParams()
    report = {"created_utc": datetime.now(UTC).isoformat(), "code_plan_sha256": hashes,
              "horizon_exclusive_inferred_utc": horizon.isoformat(), "frozen_last_close_inferred_ms": FROZEN_LAST_CLOSE_MS,
              "gold_params": gold_params.__dict__, "fixed_params": {k: str(v) for k, v in FixedParams().__dict__.items()},
              "regimes": "decoded_schedule.py unchanged (last regimes: gold E4, Fixed F2) — inputs assumed unchanged",
              "method": "continuous_from_first_warmup_tick_no_resets_forward_extension", "artifact_sha256": {}}
    write_json(folder / "run_manifest.json", report)
    old_gold, gold_prov = load_gold_ticks()
    old_fixed, fixed_prov = load_fixed_ticks()
    new_gold, gold_fwd_prov = load_forward_cache(args.gold_tag, "XAUUSD", 100, FORWARD_START, horizon)
    new_fixed, fixed_fwd_prov = load_forward_cache(args.fixed_tag, "FixedVol20", 1000, FORWARD_START, horizon)
    gt, gb, ga = join(old_gold, new_gold, "gold")
    ft, fb, fa = join(old_fixed, new_fixed, "fixed")
    report["tick_counts"] = {"gold_old": len(old_gold[0]), "gold_forward": len(new_gold[0]),
                             "fixed_old": len(old_fixed[0]), "fixed_forward": len(new_fixed[0])}
    report["forward_cache_sha256"] = {m["day"] + "|" + m["symbol"]: m["sha256"] for m in gold_fwd_prov + fixed_fwd_prov}
    gold = simulate_gold(gt, gb, ga, GOLD_REGIMES, gold_params)
    fixed = simulate_fixed(ft, fb, fa, FIXED_REGIMES, FixedParams())
    predictions = [to_prediction(t, "XAUUSD+") for t in gold] + [to_prediction(t, "FixedVol20") for t in fixed]
    scored = [p for p in predictions if p["close_ms"] is not None and FROZEN_LAST_CLOSE_MS < p["close_ms"] < horizon_ms]
    open_at_horizon = [p for p in predictions if p["close_ms"] is None or p["close_ms"] >= horizon_ms]
    path = folder / "predictions_forward.jsonl"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for index, row in enumerate(scored):
            stream.write(json.dumps({"prediction_index": index, **row}, default=str) + "\n")
    report["artifact_sha256"][path.name] = sha(path)
    report["forward_predictions"] = Counter(p["symbol"] for p in scored)
    report["open_or_unclosed_at_horizon"] = Counter(p["symbol"] for p in open_at_horizon if p["open_ms"] < horizon_ms)
    write_json(folder / "pre_score_manifest.json", {
        "written_before_forward_orders_parsed": True, "predictions_sha256": report["artifact_sha256"][path.name],
        "n_predictions": len(scored), "code_plan_sha256": hashes})
    # ---- forward ledger is read only now ----
    if hashes != {name: sha(ROOT / name) for name in CODE}:
        raise RuntimeError("Code/plan changed during replay")
    snapshot = ROOT / "data/orders_35462.jsonl"
    if sha(snapshot) != SOURCE_SHA256:
        raise RuntimeError("Source snapshot changed")
    frozen = {json.loads(line)["ticket"] for line in snapshot.read_text(encoding="utf-8").splitlines()}
    rows = {}
    for file in sorted((ROOT / "data" / args.forward_tag).glob("new_orders_*.jsonl")):
        for line in file.read_text(encoding="utf-8").splitlines():
            row = json.loads(line, parse_float=Decimal)
            if row["ticket"] not in frozen:
                rows.setdefault(row["ticket"], row)
    from probe_vantage_feed import stamp
    source = []
    for row in rows.values():
        close = round((stamp(row["close_time"]) - 10800) * 1000)
        if close < horizon_ms:
            source.append(row)
    source.sort(key=lambda row: (row["open_time"], row["ticket"]))
    report["forward_source_rows"] = Counter(row["symbol"] for row in source)
    report["forward_files_sha256"] = {f.name: sha(f) for f in sorted((ROOT / "data" / args.forward_tag).glob("new_orders_*.jsonl"))}
    matches, extra, score = match_exact(source, scored)
    report.update(score)
    path = folder / "forward_results.jsonl"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row, match in zip(source, matches):
            stream.write(json.dumps({"open_time": row["open_time"], **match}) + "\n")
    report["artifact_sha256"][path.name] = sha(path)
    path = folder / "extras.jsonl"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for index in extra:
            stream.write(json.dumps({"comparison_prediction_index": index, **scored[index]}, default=str) + "\n")
    report["artifact_sha256"][path.name] = sha(path)
    by_symbol = Counter()
    exact_by_symbol = Counter()
    for row, match in zip(source, matches):
        by_symbol[row["symbol"]] += 1
        exact_by_symbol[row["symbol"]] += match["exact_all_observable_fields"]
    report["by_symbol"] = {s: {"source_rows": by_symbol[s], "exact": exact_by_symbol[s]} for s in sorted(by_symbol)}
    report["extras_by_symbol"] = dict(Counter(scored[i]["symbol"] for i in extra))
    write_json(folder / "report.json", {k: (dict(v) if isinstance(v, Counter) else v) for k, v in report.items()})
    print(json.dumps(score))
    print(json.dumps(report["by_symbol"]), json.dumps(report["extras_by_symbol"]))


if __name__ == "__main__":
    main()
