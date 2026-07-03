"""
optimize_s86_s2010_overlay.py - Search S86 using S20.10 DM/SP trap overlay above S85.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

The portfolio side intentionally reuses the same champion framework:
    simulate_equity_substream(raw, cfg, START_EQUITY=1000)
per leg, then sums daily PnL across weighted legs.

Look-ahead guard:
- S20.10 trap detection uses completed bars plus the next bar open where the
  strategy explicitly checks current open for Fakeout_SP.
- Limit orders are considered active only from that known-open bar onward.
- Same-bar ambiguous touches are handled conservatively: for unfilled limits,
  a TP-side touch before entry cancels the order; after fill, SL is checked
  before TP on bars that touch both.
"""

import argparse
import csv
import os
import sys
from datetime import datetime

import MetaTrader5 as mt5
import numpy as np

import config
import sim_s30_backtest as s30sim
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD, ROOT_DIR, _load_cache
from optimize_s75_champion_formula import (
    _normalize_allin_raw,
    _normalize_demo_raw,
    _simulate_leg,
)
from optimize_s83_s87_combo import (
    S84_WEIGHTS,
    _cfg_for_extra,
    _combined_daily,
    _summary,
    _vector_pack,
    _window_stats,
)
from optimize_s85_s208_overlay import S208_CFG, _run_s208_raws


S2010_DIR = os.path.join(os.path.dirname(__file__), "strategy", "s20.10")
if S2010_DIR not in sys.path:
    sys.path.insert(0, S2010_DIR)

from strategy20_10 import strategy_20_10  # noqa: E402


S2010_CFG = {
    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.35,
    "COOLDOWN_TRADES": 10,
}

TF_EXTRA_BARS = {
    "M1": 2400,
    "M5": 1000,
    "M15": 620,
    "M30": 460,
    "H1": 360,
}

PATTERN_KEYS = {
    "S20.10.DM_Trap": "DM",
    "S20.10.SP_Trap": "SP",
    "S20.10.Fakeout_SP": "FSP",
}


class _S2010Config:
    S20_10_ENABLED = True
    S20_10_USE_PSYCHOLOGICAL_NUMBERS = True


def _frange(spec):
    start, stop, step = [float(x) for x in spec.split(":")]
    vals = []
    cur = start
    while cur <= stop + 1e-9:
        vals.append(round(cur, 4))
        cur += step
    return vals


def _cfg_for_leg(leg):
    if leg.startswith("S2010_"):
        return S2010_CFG
    if leg.startswith("S208_"):
        return S208_CFG
    return _cfg_for_extra(leg)


def _fetch_tf_bars(tf_name, days):
    extra = TF_EXTRA_BARS.get(tf_name, 500)
    return s30sim.fetch_bars(config.SYMBOL, tf_name, days, extra_bars=extra)


def _pattern_leg(tf_name, pattern):
    key = PATTERN_KEYS.get(pattern, "UNK")
    return f"S2010_{tf_name}_{key}"


def _replay_s2010_tf(bars, tf_name, spread):
    out = {f"S2010_{tf_name}_{key}": [] for key in PATTERN_KEYS.values()}
    out[f"S2010_{tf_name}_ALL"] = []
    if bars is None or len(bars) < 40:
        return out

    last_fire_idx = -100
    for j in range(20, len(bars)):
        if j - last_fire_idx < 3:
            continue

        # strategy_20_10 uses rates[-2] as the completed signal bar and only
        # rates[-1]["open"] for the Fakeout_SP current-open check.
        rates_slice = bars[max(0, j - 20):j + 1]
        res = strategy_20_10(rates_slice, tf_name=tf_name, config=_S2010Config)
        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue

        entry = float(res["entry"])
        sl = float(res["sl"])
        tp = float(res["tp"])
        pattern = str(res.get("pattern", "S20.10"))
        if sig == "BUY":
            if not (sl < entry < tp):
                continue
            risk_distance = entry - sl
        else:
            if not (tp < entry < sl):
                continue
            risk_distance = sl - entry
        if risk_distance <= 0:
            continue

        filled = False
        fill_idx = None
        outcome = "OPEN"
        exit_price = None
        exit_idx = None
        for m in range(j, len(bars)):
            hi = float(bars[m]["high"])
            lw = float(bars[m]["low"])

            if not filled:
                if sig == "BUY":
                    if hi >= tp:
                        break
                    if lw <= entry:
                        filled = True
                        fill_idx = m
                else:
                    if lw <= tp:
                        break
                    if hi >= entry:
                        filled = True
                        fill_idx = m

            if filled:
                if sig == "BUY":
                    if lw <= sl:
                        outcome, exit_price = "SL", sl
                    elif hi >= tp:
                        outcome, exit_price = "TP", tp
                else:
                    if hi >= sl:
                        outcome, exit_price = "SL", sl
                    elif lw <= tp:
                        outcome, exit_price = "TP", tp
                if outcome != "OPEN":
                    exit_idx = m
                    break

        if outcome == "OPEN" or fill_idx is None or exit_idx is None:
            continue

        last_fire_idx = j
        diff = (exit_price - entry) if sig == "BUY" else (entry - exit_price)
        trade = {
            "leg": _pattern_leg(tf_name, pattern),
            "tf": tf_name,
            "signal": sig,
            "outcome": outcome,
            "signal_time_ts": int(bars[j - 1]["time"]),
            "order_active_time_ts": int(bars[j]["time"]),
            "fill_time_ts": int(bars[fill_idx]["time"]),
            "exit_time_ts": int(bars[exit_idx]["time"]),
            "entry": round(entry, 2),
            "tp": round(tp, 2),
            "sl": round(sl, 2),
            "exit_price": round(exit_price, 2),
            "risk_distance": round(risk_distance, 4),
            "diff_usd_per_001lot": round(diff, 4),
            "spread": spread,
            "pattern": pattern,
            "reason": "S20.10 closed-bar/current-open detect; conservative limit replay",
        }
        out[trade["leg"]].append(trade)
        all_trade = dict(trade)
        all_trade["leg"] = f"S2010_{tf_name}_ALL"
        out[all_trade["leg"]].append(all_trade)
    return out


def _run_s2010_raws(days, spread, tfs):
    out = {}
    for tf_name in tfs:
        bars = _fetch_tf_bars(tf_name, days)
        out.update(_replay_s2010_tf(bars, tf_name, spread))
    return out


def _build_packs(windows, cache_dir, tfs):
    packs = {}
    for days in windows:
        payload = _load_cache(cache_dir, days, DEFAULT_SPREAD)
        if payload is None:
            raise SystemExit(f"missing S72 cache for {days}d")
        demo_raw = _normalize_demo_raw(payload)
        allin_raw = _normalize_allin_raw(payload)
        from optimize_s83_s87_combo import _run_s87_raws

        s87_raw = _run_s87_raws(days, DEFAULT_SPREAD)
        s208_raw = _run_s208_raws(days, DEFAULT_SPREAD, ["M1"])
        s2010_raw = _run_s2010_raws(days, DEFAULT_SPREAD, tfs)
        pre = {}
        for leg, raw in {**demo_raw, **allin_raw, **s87_raw, **s208_raw, **s2010_raw}.items():
            pre[leg] = _simulate_leg(raw, _cfg_for_leg(leg))
        packs[days] = _vector_pack(pre)
    return packs


def _floor_flags(summary, floors):
    return ";".join(
        f"{floor:g}:{'PASS' if summary['worst_day'] >= floor else 'FAIL'}"
        for floor in floors
    )


def _write_worst_day_audit(path, packs, windows, weights_by_label, focus_legs):
    fields = ["label", "days", "date", "total"] + focus_legs + ["other_total"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for label, weights in weights_by_label.items():
            for days in windows:
                pack = packs[days]
                vals, parts = _combined_daily(pack, weights)
                if len(vals) == 0:
                    continue
                idx = int(vals.argmin())
                zeros = np.zeros(len(vals))
                leg_vals = {leg: float(parts.get(leg, zeros)[idx]) for leg in focus_legs}
                row = {
                    "label": label,
                    "days": days,
                    "date": pack["days"][idx],
                    "total": round(float(vals[idx]), 4),
                    "other_total": round(float(vals[idx] - sum(leg_vals.values())), 4),
                }
                row.update({leg: round(v, 4) for leg, v in leg_vals.items()})
                w.writerow(row)


def _write_daily_audit(path, packs, windows, label, weights, focus_legs):
    fields = ["label", "days", "date", "total"] + focus_legs + ["other_total"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for days in windows:
            pack = packs[days]
            vals, parts = _combined_daily(pack, weights)
            zeros = np.zeros(len(vals))
            for idx, date in enumerate(pack["days"]):
                leg_vals = {leg: float(parts.get(leg, zeros)[idx]) for leg in focus_legs}
                row = {
                    "label": label,
                    "days": days,
                    "date": date,
                    "total": round(float(vals[idx]), 4),
                    "other_total": round(float(vals[idx] - sum(leg_vals.values())), 4),
                }
                row.update({leg: round(v, 4) for leg, v in leg_vals.items()})
                w.writerow(row)


def _row(ts, rank, label, leg, weight, score, beats, floor_flags, summary, r):
    return {
        "timestamp": ts,
        "rank": rank,
        "label": label,
        "add_leg": leg,
        "add_weight": weight,
        "beats_s85": beats,
        "floor_flags": floor_flags,
        "score": score,
        "avg_day": round(summary["avg_day"], 2),
        "min_day": round(summary["min_day"], 2),
        "min_pf": round(summary["min_pf"], 3),
        "max_streak": summary["max_streak"],
        "worst_day": round(summary["worst_day"], 2),
        "max_lot": round(summary["max_lot"], 2),
        "max_leg_dd_pct": round(summary["max_leg_dd_pct"], 2),
        "skipped_by_cb": summary["skipped_by_cb"],
        "days": r["days"],
        "day": round(r["day"], 2),
        "daily_pf": round(r["daily_pf"], 3),
        "window_streak": r["max_streak"],
        "window_worst_day": round(r["worst_day"], 2),
        "best_day": round(r["best_day"], 2),
        "trade_units": round(r["trade_units"], 2),
        "by_leg": ";".join(f"{k}:{v:.2f}" for k, v in sorted(r["by_leg"].items())),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--cache-dir", default=os.path.join(ROOT_DIR, "tmp", "s72_cache"))
    ap.add_argument("--tfs", default="M1,M5,M15,M30,H1")
    ap.add_argument("--legs", default="ALL,DM,SP,FSP")
    ap.add_argument("--w", default="0:20:0.25")
    ap.add_argument("--base-s2010-m30-fsp", type=float, default=0.0,
                    help="include S2010_M30_FSP in the baseline before searching other S20.10 legs")
    ap.add_argument("--floor", type=float, default=-1000.0)
    ap.add_argument("--floors", default="-700,-900,-973.16,-999.91,-1000")
    ap.add_argument("--max-streak", type=int, default=3)
    ap.add_argument("--out", default="s86_s2010_overlay_search.csv")
    ap.add_argument("--audit-out", default="s86_s2010_overlay_worst_day.csv")
    ap.add_argument("--daily-out", default="")
    ap.add_argument("--top", type=int, default=300)
    args = ap.parse_args()

    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    tfs = [x.strip() for x in args.tfs.split(",") if x.strip()]
    fetch_tfs = list(tfs)
    if args.base_s2010_m30_fsp > 0 and "M30" not in fetch_tfs:
        fetch_tfs.append("M30")
    leg_suffixes = [x.strip() for x in args.legs.split(",") if x.strip()]
    legs = [f"S2010_{tf}_{suffix}" for tf in tfs for suffix in leg_suffixes]
    w_grid = _frange(args.w)
    floors = [float(x.strip()) for x in args.floors.split(",") if x.strip()]

    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
    try:
        packs = _build_packs(windows, args.cache_dir, fetch_tfs)
    finally:
        mt5.shutdown()

    base_weights = dict(S84_WEIGHTS)
    base_weights["S208_M1"] = 39.33
    base_label = "S85_BASELINE"
    if args.base_s2010_m30_fsp > 0:
        base_weights["S2010_M30_FSP"] = args.base_s2010_m30_fsp
        base_label = f"S86_BASELINE_S2010_M30_FSPx{args.base_s2010_m30_fsp:g}"
    base_rows = [_window_stats(packs[d], base_weights, d) for d in windows]
    base_summary = _summary(base_rows)

    candidates = []
    for leg in legs:
        for weight in w_grid:
            weights = dict(base_weights)
            weights[leg] = weight
            rows = [_window_stats(packs[d], weights, d) for d in windows]
            summary = _summary(rows)
            beats = (
                summary["avg_day"] > base_summary["avg_day"]
                and summary["min_day"] > base_summary["min_day"]
                and summary["max_streak"] <= args.max_streak
                and summary["worst_day"] >= args.floor
            )
            valid = summary["max_streak"] <= args.max_streak and summary["worst_day"] >= args.floor
            score = (
                1 if beats else 0,
                1 if valid else 0,
                round(summary["avg_day"], 6),
                round(summary["min_day"], 6),
                round(summary["worst_day"], 4),
                round(summary["min_pf"], 6),
                -summary["max_streak"],
            )
            label = f"{base_label}+{leg}x{weight:g}"
            candidates.append((score, leg, weight, label, rows, summary, beats, weights))
    candidates.sort(key=lambda x: x[0], reverse=True)

    fields = [
        "timestamp", "rank", "label", "add_leg", "add_weight", "beats_s85",
        "floor_flags", "score", "avg_day", "min_day", "min_pf", "max_streak",
        "worst_day", "max_lot", "max_leg_dd_pct", "skipped_by_cb", "days",
        "day", "daily_pf", "window_streak", "window_worst_day", "best_day",
        "trade_units", "by_leg",
    ]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in base_rows:
            w.writerow(_row(ts, 0, base_label, "", "", "", "", _floor_flags(base_summary, floors), base_summary, r))
        for rank, (score, leg, weight, label, rows, summary, beats, _weights) in enumerate(candidates[:args.top], 1):
            flags = _floor_flags(summary, floors)
            for r in rows:
                w.writerow(_row(ts, rank, label, leg, weight, score, beats, flags, summary, r))

    audit_weights = {base_label: dict(base_weights)}
    for _score, _leg, _weight, label, _rows, _cand_summary, _beats, weights in candidates[:20]:
        audit_weights[label] = weights
    focus_legs = ["S208_M1"] + legs
    _write_worst_day_audit(args.audit_out, packs, windows, audit_weights, focus_legs)
    if args.daily_out and candidates:
        _score, _leg, _weight, label, _rows, _cand_summary, _beats, weights = candidates[0]
        _write_daily_audit(args.daily_out, packs, windows, label, weights, focus_legs)

    print(
        f"{base_label} avg$/d={base_summary['avg_day']:.2f} min$/d={base_summary['min_day']:.2f} "
        f"PF={base_summary['min_pf']:.2f} st={base_summary['max_streak']} worst={base_summary['worst_day']:.2f}"
    )
    print("S20.10 raw counts:")
    for days in windows:
        counts = ", ".join(f"{leg}={packs[days]['counts'].get(leg, 0)}" for leg in legs)
        print(f"  {days}d {counts}")
    print("Top S86 S20.10 candidates:")
    for i, (score, leg, weight, label, rows, summary, beats, _weights) in enumerate(candidates[:20], 1):
        print(
            f"{i:>2}. {label} avg$/d={summary['avg_day']:.2f} min$/d={summary['min_day']:.2f} "
            f"minPF={summary['min_pf']:.2f} st={summary['max_streak']} "
            f"worst={summary['worst_day']:.2f} beats={beats} floors={_floor_flags(summary, floors)}"
        )
        print("  " + " | ".join(
            f"{r['days']}d {r['day']:.2f}/d PF={r['daily_pf']:.2f} "
            f"st={r['max_streak']} worst={r['worst_day']:.2f}" for r in rows
        ))
    print(f"\n-> {os.path.abspath(args.out)}")
    print(f"-> {os.path.abspath(args.audit_out)}")
    if args.daily_out:
        print(f"-> {os.path.abspath(args.daily_out)}")


if __name__ == "__main__":
    main()
