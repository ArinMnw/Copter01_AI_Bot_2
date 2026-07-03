"""
sim_s84_backtest.py - Backtest S84 Old Wick Eat Close-Fail Revisit.

RESEARCH/BACKTEST-ONLY. No live bot wiring.
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
from sim_s64_backtest import _fixed_lot_stats
from strategy84 import S84_DEFAULTS, _detect_closed, _in_session

START_EQUITY = 1000.0
DEFAULT_SPREAD = 0.20


def replay84(bars, spread, cfg):
    min_gap_bars = int(cfg.get("MIN_GAP_BARS", 5))
    min_start = int(cfg["LOOKBACK"]) + 90
    all_dt = cfg.get("_DT_BKK") or [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
    atr14 = cfg.get("_ATR14") or _atr_series(bars, 14)
    trades = []
    last_fire_idx = -100
    n = len(bars)
    for j in range(min_start, n - 1):
        if j - last_fire_idx < min_gap_bars:
            continue
        if not _in_session(all_dt[j + 1], cfg):
            continue
        sig = _detect_closed(bars, j, cfg, atr_value=atr14[j])
        if sig is None:
            continue
        last_fire_idx = j
        direction = sig["signal"]
        entry = float(sig["entry"])
        sl = float(sig["sl"])
        tp = float(sig["tp"])
        fill_idx = j + 1
        outcome, exit_price, exit_idx = "OPEN", None, None
        for m in range(fill_idx, n):
            hi = float(bars[m]["high"])
            lw = float(bars[m]["low"])
            if direction == "BUY":
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
        if outcome == "OPEN":
            continue
        risk_distance = abs(entry - sl)
        diff = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
        trades.append({
            "signal": direction,
            "outcome": outcome,
            "signal_time_ts": int(bars[j]["time"]),
            "fill_time_ts": int(bars[fill_idx]["time"]),
            "exit_time_ts": int(bars[exit_idx]["time"]),
            "entry": round(entry, 2),
            "tp": round(tp, 2),
            "sl": round(sl, 2),
            "exit_price": round(exit_price, 2),
            "risk_distance": round(risk_distance, 4),
            "diff_usd_per_001lot": round(diff, 4),
            "spread": spread,
            "reason": sig["reason"],
        })
    return trades


def run_single(entry_bars, cfg, days, spread):
    return replay84(entry_bars, spread, cfg)


def run_backtest(cfg, days, spread, label, verbose=True):
    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return None
    entry_bars = s30sim.fetch_bars(config.SYMBOL, cfg["ENTRY_TF"], days, extra_bars=560)
    mt5.shutdown()
    if entry_bars is None:
        print("! fetch entry bars fail")
        return None
    raw = run_single(entry_bars, cfg, days, spread)
    twp, eq = s31sim.simulate_equity_substream(raw, cfg, START_EQUITY)
    s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days) if twp else {
        "trades": 0,
        "wr": 0.0,
        "avg_per_day_span": 0.0,
        "max_dd_pct": 0.0,
        "profit_factor": 0.0,
        "final_equity": START_EQUITY,
    }
    fs = _fixed_lot_stats(raw, days, spread)
    if verbose:
        print(
            f"signals={len(raw)} comp $/d={s['avg_per_day_span']:.2f} PF={s['profit_factor']:.2f} "
            f"DD={s['max_dd_pct']:.1f}% | fixed $/d={fs['fixed_per_day']:.2f} "
            f"PF={fs['fixed_pf']:.2f} sharpe={fs['sharpe_like']:.3f} "
            f"maxStreak={fs['max_losing_day_streak']}d"
        )
    row = dict(s)
    row.update(fs)
    append_summary_csv(label, row, cfg)
    return row


def append_summary_csv(label, s, cfg):
    path = os.path.join(os.path.dirname(__file__), "s84_backtest_summary.csv")
    is_new = not os.path.exists(path)
    fields = [
        "timestamp", "label", "entry_tf", "lookback", "ref_min_wick_atr",
        "ref_wick_body_mult", "eat_tol_atr", "close_fail_atr",
        "require_opposite_close", "min_body_atr", "min_range_atr",
        "target_mode", "mode", "sl_atr_mult", "tp_rr", "trades", "wr",
        "avg_per_day_span", "max_dd_pct", "profit_factor", "fixed_per_day",
        "fixed_per_month", "fixed_pf", "fixed_avg", "pct_pos_days",
        "max_losing_day_streak", "sharpe_like",
    ]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        w.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "label": label,
            "entry_tf": cfg["ENTRY_TF"],
            "lookback": cfg["LOOKBACK"],
            "ref_min_wick_atr": cfg["REF_MIN_WICK_ATR"],
            "ref_wick_body_mult": cfg["REF_WICK_BODY_MULT"],
            "eat_tol_atr": cfg["EAT_TOL_ATR"],
            "close_fail_atr": cfg["CLOSE_FAIL_ATR"],
            "require_opposite_close": cfg["REQUIRE_OPPOSITE_CLOSE"],
            "min_body_atr": cfg["MIN_BODY_ATR"],
            "min_range_atr": cfg["MIN_RANGE_ATR"],
            "target_mode": cfg["TARGET_MODE"],
            "mode": cfg["MODE"],
            "sl_atr_mult": cfg["SL_ATR_MULT"],
            "tp_rr": cfg["TP_RR"],
            "trades": s["trades"],
            "wr": s["wr"],
            "avg_per_day_span": s["avg_per_day_span"],
            "max_dd_pct": s["max_dd_pct"],
            "profit_factor": s["profit_factor"],
            "fixed_per_day": s["fixed_per_day"],
            "fixed_per_month": s["fixed_per_month"],
            "fixed_pf": s["fixed_pf"],
            "fixed_avg": s["fixed_avg"],
            "pct_pos_days": s["pct_pos_days"],
            "max_losing_day_streak": s["max_losing_day_streak"],
            "sharpe_like": s["sharpe_like"],
        })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--tf")
    ap.add_argument("--lookback", type=int)
    ap.add_argument("--refwick", type=float)
    ap.add_argument("--wickbody", type=float)
    ap.add_argument("--eattol", type=float)
    ap.add_argument("--fail", type=float)
    ap.add_argument("--opposite", choices=["on", "off"])
    ap.add_argument("--minbody", type=float)
    ap.add_argument("--minrange", type=float)
    ap.add_argument("--target", choices=["mid", "body", "rr"])
    ap.add_argument("--mode", choices=["revisit", "follow"])
    ap.add_argument("--slmult", type=float)
    ap.add_argument("--rr", type=float)
    args = ap.parse_args()
    cfg = dict(S84_DEFAULTS)
    if args.tf:
        cfg["ENTRY_TF"] = args.tf
    if args.lookback is not None:
        cfg["LOOKBACK"] = args.lookback
    if args.refwick is not None:
        cfg["REF_MIN_WICK_ATR"] = args.refwick
    if args.wickbody is not None:
        cfg["REF_WICK_BODY_MULT"] = args.wickbody
    if args.eattol is not None:
        cfg["EAT_TOL_ATR"] = args.eattol
    if args.fail is not None:
        cfg["CLOSE_FAIL_ATR"] = args.fail
    if args.opposite:
        cfg["REQUIRE_OPPOSITE_CLOSE"] = args.opposite == "on"
    if args.minbody is not None:
        cfg["MIN_BODY_ATR"] = args.minbody
    if args.minrange is not None:
        cfg["MIN_RANGE_ATR"] = args.minrange
    if args.target:
        cfg["TARGET_MODE"] = args.target
    if args.mode:
        cfg["MODE"] = args.mode
    if args.slmult is not None:
        cfg["SL_ATR_MULT"] = args.slmult
    if args.rr is not None:
        cfg["TP_RR"] = args.rr
    run_backtest(cfg, args.days, DEFAULT_SPREAD, args.label)


if __name__ == "__main__":
    main()
