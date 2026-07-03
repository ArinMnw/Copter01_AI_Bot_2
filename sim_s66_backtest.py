"""
sim_s66_backtest.py - Backtest S66 All-in-4S FVG Ladder Follow Trend.

RESEARCH/BACKTEST-ONLY. No live bot wiring.
"""

import argparse
import csv
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy66 import S66_DEFAULTS, _detect_closed, _in_session
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
from sim_s62_backtest import _atr_series
from sim_s64_backtest import _fixed_lot_stats

START_EQUITY = 1000.0
DEFAULT_SPREAD = 0.20


def replay66(bars, spread, cfg):
    min_gap_bars = int(cfg.get("MIN_GAP_BARS", 5))
    min_start = int(cfg["LOOKBACK"]) + 100
    all_dt = cfg.get("_DT_BKK") or [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
    atr14 = cfg.get("_ATR14") or _atr_series(bars, 14)
    trades = []
    last_fire_idx = -100
    used_zones = set()
    n = len(bars)
    for j in range(min_start, n - 1):
        if j - last_fire_idx < min_gap_bars:
            continue
        if not _in_session(all_dt[j + 1], cfg):
            continue
        sig = _detect_closed(bars, j, cfg, atr_value=atr14[j])
        if sig is None:
            continue
        key = (sig.get("zone_idx"), sig["signal"], cfg["ZONE_SELECT"], round(float(sig["entry"]), 1))
        if key in used_zones:
            continue
        used_zones.add(key)
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
            "signal": direction, "outcome": outcome,
            "signal_time_ts": int(bars[j]["time"]), "fill_time_ts": int(bars[fill_idx]["time"]),
            "exit_time_ts": int(bars[exit_idx]["time"]), "entry": round(entry, 2),
            "tp": round(tp, 2), "sl": round(sl, 2), "exit_price": round(exit_price, 2),
            "risk_distance": round(risk_distance, 4), "diff_usd_per_001lot": round(diff, 4),
            "spread": spread, "reason": sig["reason"],
        })
    return trades


def run_single(entry_bars, cfg, days, spread):
    return replay66(entry_bars, spread, cfg)


def run_backtest(cfg, days, spread, label, verbose=True):
    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return None
    entry_bars = s30sim.fetch_bars(config.SYMBOL, cfg["ENTRY_TF"], days, extra_bars=620)
    mt5.shutdown()
    if entry_bars is None:
        print("! fetch entry bars fail")
        return None
    raw = run_single(entry_bars, cfg, days, spread)
    twp, eq = s31sim.simulate_equity_substream(raw, cfg, START_EQUITY)
    s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days) if twp else {
        "trades": 0, "wr": 0.0, "avg_per_day_span": 0.0,
        "max_dd_pct": 0.0, "profit_factor": 0.0, "final_equity": START_EQUITY,
    }
    fs = _fixed_lot_stats(raw, days, spread)
    if verbose:
        print(
            f"signals={len(raw)} comp $/d={s['avg_per_day_span']:.2f} PF={s['profit_factor']:.2f} "
            f"DD={s['max_dd_pct']:.1f}% | fixed $/d={fs['fixed_per_day']:.2f} "
            f"PF={fs['fixed_pf']:.2f} sharpe={fs['sharpe_like']:.3f} "
            f"maxStreak={fs['max_losing_day_streak']}d"
        )
    row = dict(s); row.update(fs)
    append_summary_csv(label, row, cfg)
    return row


def append_summary_csv(label, s, cfg):
    path = os.path.join(os.path.dirname(__file__), "s66_backtest_summary.csv")
    is_new = not os.path.exists(path)
    fields = ["timestamp", "label", "entry_tf", "lookback", "fvg_min_atr",
              "min_fvg_count", "zone_select", "touch_tol_atr", "min_body_atr",
              "body_ratio", "latest_fail", "sl_atr_mult", "tp_rr", "trades",
              "wr", "avg_per_day_span", "max_dd_pct", "profit_factor",
              "fixed_per_day", "fixed_per_month", "fixed_pf", "fixed_avg",
              "pct_pos_days", "max_losing_day_streak", "sharpe_like"]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        w.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "label": label,
            "entry_tf": cfg["ENTRY_TF"], "lookback": cfg["LOOKBACK"],
            "fvg_min_atr": cfg["FVG_MIN_ATR"], "min_fvg_count": cfg["MIN_FVG_COUNT"],
            "zone_select": cfg["ZONE_SELECT"], "touch_tol_atr": cfg["TOUCH_TOL_ATR"],
            "min_body_atr": cfg["MIN_BODY_ATR"], "body_ratio": cfg["MIN_BODY_RATIO"],
            "latest_fail": cfg["REQUIRE_LATEST_FAIL"], "sl_atr_mult": cfg["SL_ATR_MULT"],
            "tp_rr": cfg["TP_RR"], "trades": s["trades"], "wr": s["wr"],
            "avg_per_day_span": s["avg_per_day_span"], "max_dd_pct": s["max_dd_pct"],
            "profit_factor": s["profit_factor"], "fixed_per_day": s["fixed_per_day"],
            "fixed_per_month": s["fixed_per_month"], "fixed_pf": s["fixed_pf"],
            "fixed_avg": s["fixed_avg"], "pct_pos_days": s["pct_pos_days"],
            "max_losing_day_streak": s["max_losing_day_streak"], "sharpe_like": s["sharpe_like"],
        })


def print_examples(raw, limit=8):
    print("\nSample trades:")
    for t in raw[:limit]:
        dt = config.mt5_ts_to_bkk(t["signal_time_ts"]).strftime("%Y-%m-%d %H:%M")
        print(f"{dt} {t['signal']} {t['outcome']} entry={t['entry']:.2f} sl={t['sl']:.2f} "
              f"tp={t['tp']:.2f} diff={t['diff_usd_per_001lot']:.2f} {t['reason']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--tf")
    ap.add_argument("--lookback", type=int)
    ap.add_argument("--fvgmin", type=float)
    ap.add_argument("--count", type=int)
    ap.add_argument("--zone", choices=["base", "middle", "latest"])
    ap.add_argument("--touch", type=float)
    ap.add_argument("--minbody", type=float)
    ap.add_argument("--bodyratio", type=float)
    ap.add_argument("--latestfail", choices=["on", "off"])
    ap.add_argument("--slmult", type=float)
    ap.add_argument("--rr", type=float)
    ap.add_argument("--examples", action="store_true")
    args = ap.parse_args()
    cfg = dict(S66_DEFAULTS)
    if args.tf: cfg["ENTRY_TF"] = args.tf
    if args.lookback is not None: cfg["LOOKBACK"] = args.lookback
    if args.fvgmin is not None: cfg["FVG_MIN_ATR"] = args.fvgmin
    if args.count is not None: cfg["MIN_FVG_COUNT"] = args.count
    if args.zone: cfg["ZONE_SELECT"] = args.zone
    if args.touch is not None: cfg["TOUCH_TOL_ATR"] = args.touch
    if args.minbody is not None: cfg["MIN_BODY_ATR"] = args.minbody
    if args.bodyratio is not None: cfg["MIN_BODY_RATIO"] = args.bodyratio
    if args.latestfail: cfg["REQUIRE_LATEST_FAIL"] = args.latestfail == "on"
    if args.slmult is not None: cfg["SL_ATR_MULT"] = args.slmult
    if args.rr is not None: cfg["TP_RR"] = args.rr
    row = run_backtest(cfg, args.days, DEFAULT_SPREAD, args.label)
    if args.examples and row is not None:
        if not config.mt5_initialize(mt5):
            print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
            return
        bars = s30sim.fetch_bars(config.SYMBOL, cfg["ENTRY_TF"], args.days, extra_bars=620)
        mt5.shutdown()
        print_examples(run_single(bars, cfg, args.days, DEFAULT_SPREAD))


if __name__ == "__main__":
    main()
