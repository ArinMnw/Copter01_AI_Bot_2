"""
sim_s87_filter_s86.py - Test S87 HTF closed-bar filter on S86 raw trades.

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
from sim_s86_backtest import DEFAULT_SPREAD, START_EQUITY, run_single as run_s86
from strategy86 import S86_DEFAULTS
from strategy87 import build_closed_series, filter_trades


S86_M15_STRICT = dict(S86_DEFAULTS)
S86_M15_STRICT.update({
    "ENTRY_TF": "M15",
    "LOOKBACK": 96,
    "IMPULSE_MIN_ATR": 2.6,
    "ZONE_TOL_ATR": 0.08,
    "CONFIRM_BODY_ATR": 0.14,
    "CONFIRM_BODY_RATIO": 0.35,
    "REQUIRE_TREND": True,
    "TREND_LOOKBACK": 16,
    "TREND_MIN_ATR": 1.0,
    "SL_MODE": "zone",
    "SL_ATR_MULT": 0.20,
    "TP_MODE": "rr",
    "TP_RR": 1.5,
})

S87_MODES = [
    "D1_LAST",
    "H12_LAST",
    "D1_AND_H12",
    "H12_TURN",
    "D1_H12_TURN",
    "D1_OR_H12_TURN",
    "D1_THEN_H12_REVERSAL",
]

_TF_MAP = {
    "H12": mt5.TIMEFRAME_H12,
    "D1": mt5.TIMEFRAME_D1,
}

_PER_DAY = {
    "H12": 2,
    "D1": 1,
}


def fetch_htf_bars(symbol, tf_name, days, extra_bars=40):
    count = min(days * _PER_DAY[tf_name] + extra_bars, 95000)
    rates = mt5.copy_rates_from_pos(symbol, _TF_MAP[tf_name], 0, count)
    if rates is None or len(rates) == 0:
        return None
    return rates


def _row_from_raw(label, days, raw, cfg, spread, mode="", relation=""):
    twp, eq = s31sim.simulate_equity_substream(raw, cfg, START_EQUITY)
    s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days) if twp else {
        "trades": 0,
        "wr": 0.0,
        "avg_per_day_span": 0.0,
        "max_dd_pct": 0.0,
        "profit_factor": 0.0,
        "final_equity": START_EQUITY,
        "max_consec_loss": 0,
    }
    fs = _fixed_lot_stats(raw, days, spread)
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "label": label,
        "days": days,
        "mode": mode,
        "relation": relation,
        "raw_trades": len(raw),
        "comp_trades": s.get("trades", 0),
        "avg_per_day_span": round(s.get("avg_per_day_span", 0.0), 2),
        "profit_factor": round(s.get("profit_factor", 0.0), 3),
        "max_consec_loss": s.get("max_consec_loss", 0),
        "max_dd_pct": round(s.get("max_dd_pct", 0.0), 2),
        "final_equity": round(s.get("final_equity", START_EQUITY), 2),
        "lot_max": round(eq.get("lot_max", 0.0), 2),
        "skipped_by_cb": eq.get("skipped_by_circuit_breaker", 0),
        "fixed_per_day": fs["fixed_per_day"],
        "fixed_pf": fs["fixed_pf"],
        "fixed_streak": fs["max_losing_day_streak"],
        "pct_pos_days": fs["pct_pos_days"],
        "sharpe_like": fs["sharpe_like"],
    }


def _summary(rows):
    return {
        "avg_day": sum(r["avg_per_day_span"] for r in rows) / len(rows),
        "min_day": min(r["avg_per_day_span"] for r in rows),
        "min_pf": min(r["profit_factor"] for r in rows),
        "max_streak": max(r["fixed_streak"] for r in rows),
        "max_comp_loss": max(r["max_consec_loss"] for r in rows),
        "max_lot": max(r["lot_max"] for r in rows),
        "max_dd_pct": max(r["max_dd_pct"] for r in rows),
        "skipped_by_cb": max(r["skipped_by_cb"] for r in rows),
        "min_trades": min(r["raw_trades"] for r in rows),
    }


def _print_summary(label, rows):
    s = _summary(rows)
    print(
        f"{label:<34} avg$/d={s['avg_day']:.2f} min$/d={s['min_day']:.2f} "
        f"minPF={s['min_pf']:.2f} fixedStreak={s['max_streak']} "
        f"compLoss={s['max_comp_loss']} maxLot={s['max_lot']:.2f} "
        f"DD={s['max_dd_pct']:.2f}% trades>={s['min_trades']}"
    )


def run_window(days, spread):
    cfg = dict(S86_M15_STRICT)
    entry_bars = s30sim.fetch_bars(config.SYMBOL, cfg["ENTRY_TF"], days, extra_bars=760)
    d1_bars = fetch_htf_bars(config.SYMBOL, "D1", days, extra_bars=60)
    h12_bars = fetch_htf_bars(config.SYMBOL, "H12", days, extra_bars=120)
    if entry_bars is None or d1_bars is None or h12_bars is None:
        raise RuntimeError(f"failed to fetch bars for {days}d")
    cfg["_ATR14"] = _atr_series(entry_bars, 14)
    cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in entry_bars]
    raw = run_s86(entry_bars, cfg, days, spread)
    d1_series = build_closed_series(d1_bars, "D1")
    h12_series = build_closed_series(h12_bars, "H12")

    rows = [_row_from_raw("S86_RAW", days, raw, cfg, spread)]
    for mode in S87_MODES:
        for relation in ("follow", "inverse"):
            filtered = filter_trades(raw, d1_series, h12_series, mode, relation=relation)
            label = f"S87_{mode}_{relation}"
            rows.append(_row_from_raw(label, days, filtered, cfg, spread, mode, relation))
    return rows


def write_csv(path, rows):
    fields = [
        "timestamp", "label", "days", "mode", "relation", "raw_trades",
        "comp_trades", "avg_per_day_span", "profit_factor", "max_consec_loss",
        "max_dd_pct", "final_equity", "lot_max", "skipped_by_cb",
        "fixed_per_day", "fixed_pf", "fixed_streak", "pct_pos_days",
        "sharpe_like",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--spread", type=float, default=DEFAULT_SPREAD)
    ap.add_argument("--out", default="s87_filter_s86_summary.csv")
    args = ap.parse_args()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]

    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
    try:
        all_rows = []
        for days in windows:
            rows = run_window(days, args.spread)
            all_rows.extend(rows)
    finally:
        mt5.shutdown()

    write_csv(args.out, all_rows)
    grouped = {}
    for row in all_rows:
        grouped.setdefault(row["label"], []).append(row)
    print("S87 filter over S86 M15 strict:")
    for label, rows in sorted(grouped.items()):
        if len(rows) == len(windows):
            _print_summary(label, rows)
    print(f"\n-> {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
