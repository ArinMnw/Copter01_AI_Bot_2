"""
optimize_s75_champion_formula.py - Search candidates with the same sizing formula
used by backtest_demo_portfolio.py for P13/P16.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

This is intentionally different from the fixed-lot S72/S74 scripts. It uses:
    sim_s31_backtest.simulate_equity_substream(raw, cfg, START_EQUITY)
per leg, then sums daily PnL across legs, matching the P13/P16 baseline CSV.
"""

import argparse
import csv
import os
from datetime import datetime

import demo_portfolio as dp
import sim_s31_backtest as s31sim

from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD, ROOT_DIR, _load_cache
from sim_s70_allin4s_portfolio import S63_A, S64_A, S69_HC


START_EQUITY = s31sim.START_EQUITY
DEMO_KEYS = list("ABCDEFGHIKLMNPQR")
P13_KEYS = list("BCDFGHIKMNPQR")
P16_KEYS = list("ABCDEFGHIKLMNPQR")
ALLIN_KEYS = ["S63", "S69", "S64"]


def _normalize_demo_raw(payload):
    out = {k: [] for k in DEMO_KEYS}
    for t in payload["P16"]:
        leg = str(t.get("leg", ""))
        if leg.startswith("P16-"):
            key = leg.split("-", 1)[1]
            if key in out:
                x = dict(t)
                x["leg"] = key
                out[key].append(x)
    return out


def _normalize_allin_raw(payload):
    out = {k: [] for k in ALLIN_KEYS}
    for t in payload["ALLIN"]:
        key = str(t.get("leg", ""))
        if key in out:
            out[key].append(dict(t))
    return out


def _cfg_for_leg(key):
    if key in DEMO_KEYS:
        return dp._LEG_DEFS[key][2]
    if key == "S63":
        return S63_A
    if key == "S64":
        return S64_A
    if key == "S69":
        return S69_HC
    raise KeyError(key)


def _simulate_leg(raw, cfg):
    twp, eq = s31sim.simulate_equity_substream(raw, cfg, START_EQUITY)
    by_day = s31sim.daily_series_from_trades(twp)
    return twp, eq, by_day


def _pf_from_daily(by_day):
    gross_win = sum(v for v in by_day.values() if v > 0)
    gross_loss = sum(abs(v) for v in by_day.values() if v <= 0)
    if gross_loss <= 0:
        return 99.0 if gross_win > 0 else 0.0
    return gross_win / gross_loss


def _combine(precomputed, weights):
    combined = {}
    by_leg_total = {}
    eq_stats = {}
    trade_units = 0.0
    for leg, weight in weights.items():
        if weight <= 0 or leg not in precomputed:
            continue
        twp, eq, by_day = precomputed[leg]
        trade_units += len(twp) * weight
        by_leg_total[leg] = sum(by_day.values()) * weight
        eq_stats[leg] = eq
        for d, pnl in by_day.items():
            combined[d] = combined.get(d, 0.0) + pnl * weight
    return combined, by_leg_total, eq_stats, trade_units


def _stats(precomputed, weights, days):
    combined, by_leg_total, eq_stats, trade_units = _combine(precomputed, weights)
    c = s31sim.consistency_metrics(combined) or {
        "pct_pos_days": 0.0,
        "max_losing_day_streak": 0,
        "sharpe_like": 0.0,
    }
    total = sum(combined.values())
    vals = list(combined.values())
    max_leg_dd = max((float(eq.get("max_dd_pct", 0.0)) for eq in eq_stats.values()), default=0.0)
    max_lot = max((float(eq.get("lot_max", 0.0)) for eq in eq_stats.values()), default=0.0)
    skipped = sum(int(eq.get("skipped_by_circuit_breaker", 0)) for eq in eq_stats.values())
    return {
        "days": days,
        "trading_days": len(combined),
        "day": total / days if days else 0.0,
        "month": total / days * 30 if days else 0.0,
        "daily_pf": _pf_from_daily(combined),
        "sharpe": c["sharpe_like"],
        "pos_day_pct": c["pct_pos_days"],
        "max_streak": c["max_losing_day_streak"],
        "worst_day": min(vals) if vals else 0.0,
        "best_day": max(vals) if vals else 0.0,
        "max_leg_dd_pct": max_leg_dd,
        "max_lot": max_lot,
        "skipped_by_cb": skipped,
        "trade_units": trade_units,
        "by_leg": by_leg_total,
    }


def _candidate_weights(name):
    weights = {k: 0.0 for k in DEMO_KEYS + ALLIN_KEYS}
    if name == "P13":
        for k in P13_KEYS:
            weights[k] = 1.0
    elif name == "P16":
        for k in P16_KEYS:
            weights[k] = 1.0
    elif name == "S74_FIXED":
        for k in list("BCEGHIMNPR"):
            weights[k] = 1.0
        weights.update({"S63": 4.0, "S69": 32.0, "S64": 8.0})
    elif name == "P16_PLUS_ALLIN_1X":
        for k in P16_KEYS:
            weights[k] = 1.0
        weights.update({"S63": 1.0, "S69": 1.0, "S64": 1.0})
    elif name == "P16_PLUS_S74_ALLIN":
        for k in P16_KEYS:
            weights[k] = 1.0
        weights.update({"S63": 4.0, "S69": 32.0, "S64": 8.0})
    else:
        raise KeyError(name)
    return weights


def _score(rows, p16_rows):
    min_day = min(r["day"] for r in rows)
    avg_day = sum(r["day"] for r in rows) / len(rows)
    min_pf = min(r["daily_pf"] for r in rows)
    max_streak = max(r["max_streak"] for r in rows)
    worst_day = min(r["worst_day"] for r in rows)
    p16_avg = sum(r["day"] for r in p16_rows) / len(p16_rows)
    p16_min = min(r["day"] for r in p16_rows)
    return (
        1 if avg_day > p16_avg else 0,
        1 if min_day > p16_min else 0,
        1 if max_streak <= max(r["max_streak"] for r in p16_rows) else 0,
        round(avg_day, 4),
        round(min_pf, 4),
        round(worst_day, 2),
    )


def _search_p16_allin(pre_by_window, windows, p16_rows, worst_floor=-1000.0):
    combos = []
    for w63 in [0.0, 1.0, 2.0, 4.0, 8.0]:
        for w69 in [0.0, 1.0, 2.0, 4.0, 8.0, 16.0, 24.0, 32.0]:
            for w64 in [0.0, 1.0, 2.0, 4.0, 8.0]:
                if w63 == 0 and w69 == 0 and w64 == 0:
                    continue
                weights = _candidate_weights("P16")
                weights.update({"S63": w63, "S69": w69, "S64": w64})
                rows = [_stats(pre_by_window[d], weights, d) for d in windows]
                avg_day = sum(r["day"] for r in rows) / len(rows)
                min_day = min(r["day"] for r in rows)
                min_pf = min(r["daily_pf"] for r in rows)
                max_streak = max(r["max_streak"] for r in rows)
                worst_day = min(r["worst_day"] for r in rows)
                p16_avg = sum(r["day"] for r in p16_rows) / len(p16_rows)
                p16_min = min(r["day"] for r in p16_rows)
                ok = avg_day > p16_avg and min_day > p16_min and max_streak <= 4 and worst_day >= worst_floor
                score = (
                    1 if ok else 0,
                    round(avg_day, 4),
                    round(min_day, 4),
                    round(min_pf, 4),
                    round(worst_day, 2),
                    -max_streak,
                )
                combos.append((weights, rows, {
                    "avg_day": avg_day,
                    "min_day": min_day,
                    "min_pf": min_pf,
                    "max_streak": max_streak,
                    "worst_day": worst_day,
                    "ok": ok,
                }, score))
    combos.sort(key=lambda x: x[3], reverse=True)
    return combos


def _weights_label(weights):
    parts = ["P16"]
    for leg in ALLIN_KEYS:
        val = weights.get(leg, 0.0)
        if val:
            parts.append(f"{leg}x{val:g}")
    return "+".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--cache-dir", default=os.path.join(ROOT_DIR, "tmp", "s72_cache"))
    ap.add_argument("--out", default="s75_champion_formula_summary.csv")
    args = ap.parse_args()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]

    rows_by_label = {}
    pre_by_window = {}
    for days in windows:
        payload = _load_cache(args.cache_dir, days, DEFAULT_SPREAD)
        if payload is None:
            raise SystemExit(f"missing S72 cache for {days}d")
        demo_raw = _normalize_demo_raw(payload)
        allin_raw = _normalize_allin_raw(payload)
        pre = {}
        for leg, raw in {**demo_raw, **allin_raw}.items():
            pre[leg] = _simulate_leg(raw, _cfg_for_leg(leg))
        pre_by_window[days] = pre

    labels = ["P13", "P16", "P16_PLUS_ALLIN_1X", "S74_FIXED", "P16_PLUS_S74_ALLIN"]
    for label in labels:
        rows = []
        for days in windows:
            rows.append(_stats(pre_by_window[days], _candidate_weights(label), days))
        rows_by_label[label] = rows

    p16_rows = rows_by_label["P16"]
    searched = _search_p16_allin(pre_by_window, windows, p16_rows)
    fields = [
        "timestamp", "label", "score", "days", "trading_days", "day", "month",
        "daily_pf", "sharpe", "pos_day_pct", "max_streak", "worst_day",
        "best_day", "max_leg_dd_pct", "max_lot", "skipped_by_cb", "trade_units",
        "by_leg",
    ]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for label in labels:
            score = _score(rows_by_label[label], p16_rows)
            for r in rows_by_label[label]:
                w.writerow({
                    "timestamp": ts,
                    "label": label,
                    "score": score,
                    "days": r["days"],
                    "trading_days": r["trading_days"],
                    "day": round(r["day"], 2),
                    "month": round(r["month"], 2),
                    "daily_pf": round(r["daily_pf"], 3),
                    "sharpe": r["sharpe"],
                    "pos_day_pct": r["pos_day_pct"],
                    "max_streak": r["max_streak"],
                    "worst_day": round(r["worst_day"], 2),
                    "best_day": round(r["best_day"], 2),
                    "max_leg_dd_pct": round(r["max_leg_dd_pct"], 2),
                    "max_lot": round(r["max_lot"], 2),
                    "skipped_by_cb": r["skipped_by_cb"],
                    "trade_units": round(r["trade_units"], 2),
                    "by_leg": ";".join(f"{k}:{v:.2f}" for k, v in sorted(r["by_leg"].items())),
                })
        for rank, (weights, rows, summary, score) in enumerate(searched[:40], 1):
            label = f"S75_GRID_{rank:02d}_{_weights_label(weights)}"
            for r in rows:
                w.writerow({
                    "timestamp": ts,
                    "label": label,
                    "score": score,
                    "days": r["days"],
                    "trading_days": r["trading_days"],
                    "day": round(r["day"], 2),
                    "month": round(r["month"], 2),
                    "daily_pf": round(r["daily_pf"], 3),
                    "sharpe": r["sharpe"],
                    "pos_day_pct": r["pos_day_pct"],
                    "max_streak": r["max_streak"],
                    "worst_day": round(r["worst_day"], 2),
                    "best_day": round(r["best_day"], 2),
                    "max_leg_dd_pct": round(r["max_leg_dd_pct"], 2),
                    "max_lot": round(r["max_lot"], 2),
                    "skipped_by_cb": r["skipped_by_cb"],
                    "trade_units": round(r["trade_units"], 2),
                    "by_leg": ";".join(f"{k}:{v:.2f}" for k, v in sorted(r["by_leg"].items())),
                })

    print("Candidate summary using P13/P16 sizing formula:")
    for label in labels:
        rows = rows_by_label[label]
        avg_day = sum(r["day"] for r in rows) / len(rows)
        min_day = min(r["day"] for r in rows)
        min_pf = min(r["daily_pf"] for r in rows)
        max_st = max(r["max_streak"] for r in rows)
        worst = min(r["worst_day"] for r in rows)
        max_dd = max(r["max_leg_dd_pct"] for r in rows)
        max_lot = max(r["max_lot"] for r in rows)
        print(
            f"{label}: avg$/d={avg_day:.2f} min$/d={min_day:.2f} "
            f"minPF={min_pf:.2f} maxStreak={max_st} worstDay={worst:.2f} "
            f"maxLegDD={max_dd:.1f}% maxLot={max_lot:.2f} score={_score(rows, p16_rows)}"
        )
        print("  " + " | ".join(
            f"{r['days']}d {r['day']:.2f}/d PF={r['daily_pf']:.2f} st={r['max_streak']}"
            for r in rows
        ))
    print("\nTop P16 + All-in-4S grid candidates with worst-day guard:")
    for i, (weights, rows, summary, score) in enumerate(searched[:10], 1):
        print(
            f"{i:>2}. {_weights_label(weights)} avg$/d={summary['avg_day']:.2f} "
            f"min$/d={summary['min_day']:.2f} minPF={summary['min_pf']:.2f} "
            f"maxStreak={summary['max_streak']} worstDay={summary['worst_day']:.2f} "
            f"ok={summary['ok']} score={score}"
        )
        print("  " + " | ".join(
            f"{r['days']}d {r['day']:.2f}/d PF={r['daily_pf']:.2f} st={r['max_streak']}"
            for r in rows
        ))
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
