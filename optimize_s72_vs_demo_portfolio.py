"""
optimize_s72_vs_demo_portfolio.py - Compare All-in-4S overlays against P13/P16.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

Goal:
- Use the same fixed-lot trade accounting as demo_portfolio.py live execution
  (0.01 lot per logical leg).
- Build candidates by adding All-in-4S legs (S63/S64/S69) to P13/P16 and
  search whether any blend improves the current demo portfolio champion.
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime

import MetaTrader5 as mt5

import config
import demo_portfolio as dp
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s31_backtest as s31
import sim_s34_backtest as s34
import sim_s36_backtest as s36
import sim_s37_backtest as s37
import sim_s38_backtest as s38
import sim_s39_backtest as s39
import sim_s40_backtest as s40
import sim_s41_backtest as s41
import sim_s42_backtest as s42
import sim_s44_backtest as s44
import sim_s45_backtest as s45
import sim_s46_backtest as s46
import sim_s47_backtest as s47
import sim_s49_backtest as s49
import sim_s51_backtest as s51
import sim_s56_backtest as s56

from sim_s70_allin4s_portfolio import DEFAULT_SPREAD, run_portfolio as run_allin4s


ROOT_DIR = os.path.dirname(__file__)


SIM_MODULES = {
    "A": s31, "B": s34, "C": s36, "D": s37, "E": s38, "F": s39,
    "G": s40, "H": s41, "I": s42, "K": s44, "L": s45, "M": s46,
    "N": s47, "P": s49, "Q": s51, "R": s56,
}


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _cache_path(cache_dir, days, spread):
    safe_spread = str(spread).replace(".", "p")
    return os.path.join(cache_dir, f"s72_raw_{days}d_sp{safe_spread}.json")


def _load_cache(cache_dir, days, spread):
    path = _cache_path(cache_dir, days, spread)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_cache(cache_dir, days, spread, payload):
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, days, spread)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_jsonable(payload), f, ensure_ascii=False)
    os.replace(tmp, path)


def _tag(raw, leg):
    out = []
    for t in raw:
        x = dict(t)
        x["leg"] = leg
        out.append(x)
    return out


def _run_demo_leg_raw(days, spread, verbose=False):
    entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=700)
    htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=250)
    all_keys = sorted(set(dp.P13_KEYS) | set(dp.P16_KEYS))
    out = {}
    for key in all_keys:
        if verbose:
            print(f"  demo leg {key} ...", flush=True)
        label, _, cfg, _, _ = dp._LEG_DEFS[key]
        sim = SIM_MODULES[key]
        rows = sim.run_single(entry_bars, htf_bars, cfg, days, spread)
        out[key] = rows
    return out


def _portfolio_from_leg_raw(portfolio_name, leg_raw):
    raw = []
    for key in dp.PORTFOLIOS[portfolio_name]:
        raw.extend(_tag(leg_raw.get(key, []), f"{portfolio_name}-{key}"))
    return raw


def _weighted_stats(raw, days, spread, weights):
    gross_win = gross_loss = 0.0
    total = 0.0
    active = 0
    units = 0.0
    by_day = {}
    by_leg = {}
    for t in raw:
        leg = t.get("leg", "?")
        w = float(weights.get(leg, 0.0))
        if w <= 0:
            continue
        pnl = (float(t["diff_usd_per_001lot"]) - spread) * w
        total += pnl
        active += 1
        units += w
        if pnl > 0:
            gross_win += pnl
        else:
            gross_loss += abs(pnl)
        d = config.mt5_ts_to_bkk(t["exit_time_ts"]).strftime("%Y-%m-%d")
        by_day[d] = by_day.get(d, 0.0) + pnl
        by_leg[leg] = by_leg.get(leg, 0.0) + pnl
    c = s31sim.consistency_metrics(by_day) or {
        "pct_pos_days": 0.0,
        "max_losing_day_streak": 0,
        "sharpe_like": 0.0,
    }
    return {
        "trades": active,
        "trade_units": round(units, 2),
        "fixed_pnl": round(total, 2),
        "fixed_per_day": round(total / days, 2) if days else 0.0,
        "fixed_per_month": round(total / days * 30, 2) if days else 0.0,
        "fixed_pf": round(gross_win / gross_loss, 3) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0),
        "pct_pos_days": c["pct_pos_days"],
        "max_losing_day_streak": c["max_losing_day_streak"],
        "sharpe_like": c["sharpe_like"],
        "by_leg": by_leg,
    }


def _aggregate_raw(raw, spread):
    agg = {}
    for t in raw:
        leg = t.get("leg", "?")
        pnl = float(t["diff_usd_per_001lot"]) - spread
        d = config.mt5_ts_to_bkk(t["exit_time_ts"]).strftime("%Y-%m-%d")
        row = agg.setdefault(leg, {
            "trades": 0,
            "gross_win": 0.0,
            "gross_loss": 0.0,
            "total": 0.0,
            "by_day": {},
        })
        row["trades"] += 1
        row["total"] += pnl
        if pnl > 0:
            row["gross_win"] += pnl
        else:
            row["gross_loss"] += abs(pnl)
        row["by_day"][d] = row["by_day"].get(d, 0.0) + pnl
    return agg


def _weighted_stats_from_agg(agg, days, weights):
    gross_win = gross_loss = 0.0
    total = 0.0
    active = 0
    units = 0.0
    by_day = {}
    by_leg = {}
    for leg, row in agg.items():
        w = float(weights.get(leg, 0.0))
        if w <= 0:
            continue
        active += int(row["trades"])
        units += float(row["trades"]) * w
        gross_win += float(row["gross_win"]) * w
        gross_loss += float(row["gross_loss"]) * w
        leg_total = float(row["total"]) * w
        total += leg_total
        by_leg[leg] = leg_total
        for d, pnl in row["by_day"].items():
            by_day[d] = by_day.get(d, 0.0) + float(pnl) * w
    c = s31sim.consistency_metrics(by_day) or {
        "pct_pos_days": 0.0,
        "max_losing_day_streak": 0,
        "sharpe_like": 0.0,
    }
    return {
        "trades": active,
        "trade_units": round(units, 2),
        "fixed_pnl": round(total, 2),
        "fixed_per_day": round(total / days, 2) if days else 0.0,
        "fixed_per_month": round(total / days * 30, 2) if days else 0.0,
        "fixed_pf": round(gross_win / gross_loss, 3) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0),
        "pct_pos_days": c["pct_pos_days"],
        "max_losing_day_streak": c["max_losing_day_streak"],
        "sharpe_like": c["sharpe_like"],
        "by_leg": by_leg,
    }


def _score(rows, p16_rows):
    min_pf = min(r["fixed_pf"] for r in rows)
    avg_day = sum(r["fixed_per_day"] for r in rows) / len(rows)
    avg_month = sum(r["fixed_per_month"] for r in rows) / len(rows)
    avg_sharpe = sum(r["sharpe_like"] for r in rows) / len(rows)
    max_streak = max(r["max_losing_day_streak"] for r in rows)
    p16_avg_day = sum(r["fixed_per_day"] for r in p16_rows) / len(p16_rows)
    beats_p16_yield = avg_day > p16_avg_day
    # Champion scoring: first require beating P16 yield, then preserve streak <=4,
    # then rank by PF/Sharpe/yield.
    return (
        1 if beats_p16_yield else 0,
        1 if max_streak <= 4 else 0,
        round(min_pf, 4),
        round(avg_sharpe, 4),
        round(avg_month, 2),
        -max_streak,
    )


def _label(base, weights):
    parts = [base]
    for leg in ("S63", "S69", "S64"):
        w = weights.get(leg, 0.0)
        if w:
            parts.append(f"{leg}x{w:g}")
    return "+".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--spread", type=float, default=DEFAULT_SPREAD)
    ap.add_argument("--out", default="s72_vs_demo_portfolio_search.csv")
    ap.add_argument("--cache-dir", default=os.path.join(ROOT_DIR, "tmp", "s72_cache"))
    args = ap.parse_args()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]

    raw_by_window = {}
    for days in windows:
        cached = _load_cache(args.cache_dir, days, args.spread)
        if cached is not None:
            print(f"load cache days={days} ...", flush=True)
            raw_by_window[days] = cached
        else:
            print(f"replay base portfolios/all-in-4s days={days} ...", flush=True)
            if not config.mt5_initialize(mt5):
                print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
                return
            print(f"connected: {config.SYMBOL} @ {config.MT5_SERVER} login={config.MT5_LOGIN}", flush=True)
            demo_leg_raw = _run_demo_leg_raw(days, args.spread, verbose=True)
            p13 = _portfolio_from_leg_raw("P13", demo_leg_raw)
            p16 = _portfolio_from_leg_raw("P16", demo_leg_raw)
            mt5.shutdown()
            # run_allin4s owns its own MT5 initialize/shutdown lifecycle.
            print("  all-in-4s legs ...", flush=True)
            allin = run_allin4s(days, args.spread, ["S63", "S64", "S69"])
            raw_by_window[days] = {
                "P13": p13,
                "P16": p16,
                "ALLIN": allin,
            }
            _save_cache(args.cache_dir, days, args.spread, raw_by_window[days])

    p13_rows = []
    p16_rows = []
    agg_by_window = {}
    base_weights_by_window = {}
    for days in windows:
        agg_by_window[(days, "P13")] = _aggregate_raw(raw_by_window[days]["P13"] + raw_by_window[days]["ALLIN"], args.spread)
        agg_by_window[(days, "P16")] = _aggregate_raw(raw_by_window[days]["P16"] + raw_by_window[days]["ALLIN"], args.spread)
        p13_weights = {leg: 1.0 for leg in _aggregate_raw(raw_by_window[days]["P13"], args.spread)}
        p16_weights = {leg: 1.0 for leg in _aggregate_raw(raw_by_window[days]["P16"], args.spread)}
        base_weights_by_window[(days, "P13")] = p13_weights
        base_weights_by_window[(days, "P16")] = p16_weights
        p13_rows.append({"days": days, **_weighted_stats_from_agg(agg_by_window[(days, "P13")], days, p13_weights)})
        p16_rows.append({"days": days, **_weighted_stats_from_agg(agg_by_window[(days, "P16")], days, p16_weights)})

    combos = []
    bases = ["P13", "P16"]
    w63_grid = [0.0, 1.0, 2.0, 4.0, 8.0, 12.0, 16.0]
    w69_grid = [0.0, 1.0, 2.0, 4.0, 8.0, 12.0, 16.0, 24.0]
    w64_grid = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]
    for base in bases:
        for w63 in w63_grid:
            for w69 in w69_grid:
                for w64 in w64_grid:
                    if w63 == 0 and w69 == 0 and w64 == 0:
                        continue
                    rows = []
                    for days in windows:
                        weights = dict(base_weights_by_window[(days, base)])
                        weights.update({"S63": w63, "S69": w69, "S64": w64})
                        rows.append({"days": days, **_weighted_stats_from_agg(agg_by_window[(days, base)], days, weights)})
                    overlay = {"S63": w63, "S69": w69, "S64": w64}
                    combos.append((base, overlay, rows, _score(rows, p16_rows)))
    combos.sort(key=lambda x: x[3], reverse=True)

    fields = [
        "timestamp", "rank", "label", "base", "w_s63", "w_s69", "w_s64",
        "score", "min_pf", "avg_day", "avg_month", "avg_sharpe", "max_streak",
        "days", "trades", "trade_units", "fixed_per_day", "fixed_per_month",
        "fixed_pf", "sharpe_like", "max_losing_day_streak", "by_leg",
    ]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        baseline_blocks = [("BASE_P13", "P13", {}, p13_rows), ("BASE_P16", "P16", {}, p16_rows)]
        output_blocks = baseline_blocks + [
            (_label(base, overlay), base, overlay, rows)
            for base, overlay, rows, _ in combos[:60]
        ]
        for rank, (label, base, overlay, rows) in enumerate(output_blocks, 1):
            min_pf = min(r["fixed_pf"] for r in rows)
            avg_day = sum(r["fixed_per_day"] for r in rows) / len(rows)
            avg_month = sum(r["fixed_per_month"] for r in rows) / len(rows)
            avg_sharpe = sum(r["sharpe_like"] for r in rows) / len(rows)
            max_streak = max(r["max_losing_day_streak"] for r in rows)
            for r in rows:
                w.writerow({
                    "timestamp": ts,
                    "rank": rank,
                    "label": label,
                    "base": base,
                    "w_s63": overlay.get("S63", 0.0),
                    "w_s69": overlay.get("S69", 0.0),
                    "w_s64": overlay.get("S64", 0.0),
                    "score": "" if label.startswith("BASE_") else _score(rows, p16_rows),
                    "min_pf": round(min_pf, 3),
                    "avg_day": round(avg_day, 3),
                    "avg_month": round(avg_month, 2),
                    "avg_sharpe": round(avg_sharpe, 3),
                    "max_streak": max_streak,
                    "days": r["days"],
                    "trades": r["trades"],
                    "trade_units": r["trade_units"],
                    "fixed_per_day": r["fixed_per_day"],
                    "fixed_per_month": r["fixed_per_month"],
                    "fixed_pf": r["fixed_pf"],
                    "sharpe_like": r["sharpe_like"],
                    "max_losing_day_streak": r["max_losing_day_streak"],
                    "by_leg": ";".join(f"{k}:{v:.2f}" for k, v in sorted(r["by_leg"].items())),
                })

    print("\nBaselines:")
    for name, rows in (("P13", p13_rows), ("P16", p16_rows)):
        avg_day = sum(r["fixed_per_day"] for r in rows) / len(rows)
        avg_month = sum(r["fixed_per_month"] for r in rows) / len(rows)
        min_pf = min(r["fixed_pf"] for r in rows)
        max_streak = max(r["max_losing_day_streak"] for r in rows)
        print(f"{name}: avg$/d={avg_day:.2f} avg$/mo={avg_month:.2f} minPF={min_pf:.2f} maxStreak={max_streak}")

    print("\nTop 12 S72 candidates:")
    for i, (base, overlay, rows, score) in enumerate(combos[:12], 1):
        avg_day = sum(r["fixed_per_day"] for r in rows) / len(rows)
        avg_month = sum(r["fixed_per_month"] for r in rows) / len(rows)
        min_pf = min(r["fixed_pf"] for r in rows)
        avg_sharpe = sum(r["sharpe_like"] for r in rows) / len(rows)
        max_streak = max(r["max_losing_day_streak"] for r in rows)
        print(
            f"{i:>2}. {_label(base, overlay)} avg$/d={avg_day:.2f} "
            f"avg$/mo={avg_month:.2f} minPF={min_pf:.2f} "
            f"avgSharpe={avg_sharpe:.3f} maxStreak={max_streak} score={score}"
        )
        print("    " + " | ".join(
            f"{r['days']}d $/d={r['fixed_per_day']:.2f} PF={r['fixed_pf']:.2f} "
            f"st={r['max_losing_day_streak']}" for r in rows
        ))
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
