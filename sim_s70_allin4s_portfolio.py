"""
sim_s70_allin4s_portfolio.py - All-in-4S mini-portfolio backtest.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

Combines current All-in-4S legs:
- S63 Normal: SP breakout engine
- S64: KRH fibo expansion candidate
- S69: S63 high-confidence base-FVG overlay
"""

import argparse
import csv
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
from sim_s62_backtest import _atr_series
from strategy63 import S63_DEFAULTS
from strategy64 import S64_DEFAULTS
from strategy69 import S69_DEFAULTS
import sim_s63_backtest as s63sim
import sim_s64_backtest as s64sim
import sim_s69_backtest as s69sim

START_EQUITY = 1000.0
DEFAULT_SPREAD = 0.20


S63_A = dict(S63_DEFAULTS)
S63_A.update({
    "ENTRY_TF": "M5",
    "SP_LOOKBACK": 8,
    "SP_MAX_ATR": 1.4,
    "MODE": "breakout",
    "FVG_REQUIRED": False,
    "MIN_BODY_ATR": 0.35,
    "MIN_BODY_RATIO": 0.40,
    "SL_ATR_MULT": 0.35,
    "TP_RR": 1.20,
})

S64_A = dict(S64_DEFAULTS)
S64_A.update({
    "ENTRY_TF": "M15",
    "SEED_LOOKBACK": 36,
    "LEVEL": 3.097,
    "TARGET_LEVEL": 5.165,
    "MODE": "break",
    "SEED_MIN_BODY_ATR": 0.25,
    "MIN_BODY_ATR": 0.12,
    "SL_LEVEL": 1.617,
    "SL_ATR_MULT": 0.25,
    "TP_MODE": "krh",
    "TP_RR": 1.20,
})

S69_HC = dict(S69_DEFAULTS)


def _fetch_bars(tfs, days):
    out = {}
    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return out
    for tf in tfs:
        out[tf] = s30sim.fetch_bars(config.SYMBOL, tf, days, extra_bars=700)
    mt5.shutdown()
    return out


def _with_cache(cfg, bars):
    out = dict(cfg)
    out["_ATR14"] = _atr_series(bars, 14)
    out["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
    return out


def _tag(raw, leg):
    tagged = []
    for t in raw:
        x = dict(t)
        x["leg"] = leg
        tagged.append(x)
    return tagged


def _dedupe_same_leg(raw):
    seen = set()
    out = []
    for t in sorted(raw, key=lambda x: (x["signal_time_ts"], x.get("leg", ""), x["signal"])):
        key = (t.get("leg"), t["signal_time_ts"], t["signal"])
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def _fixed_lot_stats(raw, days, spread):
    wins = losses = 0
    gross_win = gross_loss = 0.0
    total = 0.0
    by_day = {}
    by_leg = {}
    for t in raw:
        pnl = float(t["diff_usd_per_001lot"]) - spread
        total += pnl
        if pnl > 0:
            wins += 1
            gross_win += pnl
        else:
            losses += 1
            gross_loss += abs(pnl)
        d = config.mt5_ts_to_bkk(t["exit_time_ts"]).strftime("%Y-%m-%d")
        by_day[d] = by_day.get(d, 0.0) + pnl
        leg = t.get("leg", "?")
        by_leg[leg] = by_leg.get(leg, 0.0) + pnl
    c = s31sim.consistency_metrics(by_day) or {"pct_pos_days": 0.0, "max_losing_day_streak": 0, "sharpe_like": 0.0}
    return {
        "trades": len(raw),
        "wr": round(100.0 * wins / len(raw), 1) if raw else 0.0,
        "fixed_pnl": round(total, 2),
        "fixed_per_day": round(total / days, 2) if days else 0.0,
        "fixed_per_month": round(total / days * 30, 2) if days else 0.0,
        "fixed_pf": round(gross_win / gross_loss, 3) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0),
        "fixed_avg": round(total / len(raw), 3) if raw else 0.0,
        "pct_pos_days": c["pct_pos_days"],
        "max_losing_day_streak": c["max_losing_day_streak"],
        "sharpe_like": c["sharpe_like"],
        "by_leg": by_leg,
    }


def run_portfolio(days, spread, legs):
    need_tfs = set()
    if "S63" in legs or "S69" in legs:
        need_tfs.add("M5")
    if "S64" in legs:
        need_tfs.add("M15")
    bars_by_tf = _fetch_bars(sorted(need_tfs), days)
    raw = []
    if "S63" in legs and bars_by_tf.get("M5") is not None:
        cfg = _with_cache(S63_A, bars_by_tf["M5"])
        raw += _tag(s63sim.run_single(bars_by_tf["M5"], cfg, days, spread), "S63")
    if "S64" in legs and bars_by_tf.get("M15") is not None:
        cfg = _with_cache(S64_A, bars_by_tf["M15"])
        raw += _tag(s64sim.run_single(bars_by_tf["M15"], cfg, days, spread), "S64")
    if "S69" in legs and bars_by_tf.get("M5") is not None:
        cfg = _with_cache(S69_HC, bars_by_tf["M5"])
        raw += _tag(s69sim.run_single(bars_by_tf["M5"], cfg, days, spread), "S69")
    return _dedupe_same_leg(raw)


def append_summary(label, days, legs, stats):
    path = "s70_allin4s_portfolio_summary.csv"
    is_new = not os.path.exists(path)
    fields = ["timestamp", "label", "days", "legs", "trades", "wr", "fixed_pnl",
              "fixed_per_day", "fixed_per_month", "fixed_pf", "fixed_avg",
              "pct_pos_days", "max_losing_day_streak", "sharpe_like", "by_leg"]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        row = {k: stats.get(k) for k in fields if k not in ("timestamp", "label", "days", "legs", "by_leg")}
        row.update({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "label": label,
            "days": days,
            "legs": "+".join(legs),
            "by_leg": ";".join(f"{k}:{v:.2f}" for k, v in sorted(stats["by_leg"].items())),
        })
        w.writerow(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--legs", default="S63,S64,S69")
    ap.add_argument("--label", default="s70")
    args = ap.parse_args()
    legs = [x.strip().upper() for x in args.legs.split(",") if x.strip()]
    raw = run_portfolio(args.days, DEFAULT_SPREAD, legs)
    stats = _fixed_lot_stats(raw, args.days, DEFAULT_SPREAD)
    append_summary(args.label, args.days, legs, stats)
    by_leg = " ".join(f"{k}={v:.2f}" for k, v in sorted(stats["by_leg"].items()))
    print(
        f"legs={'+'.join(legs)} trades={stats['trades']} fixed $/d={stats['fixed_per_day']:.2f} "
        f"$/mo={stats['fixed_per_month']:.2f} PF={stats['fixed_pf']:.2f} "
        f"sharpe={stats['sharpe_like']:.3f} streak={stats['max_losing_day_streak']}d | {by_leg}"
    )


if __name__ == "__main__":
    main()
