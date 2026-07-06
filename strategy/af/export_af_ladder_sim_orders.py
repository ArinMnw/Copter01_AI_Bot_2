"""
Export AF ladder order-level simulation rows by leg.

This is the AF equivalent of the P13/P16 sim-module trace: each AF overlay
leg is replayed from its S84/S86 generator, then filtered by mode/RD/hour and
exported with component_no/component_name so every order can be traced back to
the leg that created it.

Notes:
- S88 base is still reported by daily component in export_af_ladder_composition.py.
- Overlay legs use ambfix resolution: ambiguous exit bars are resolved by M1
  where possible; unresolved bars are pessimistic for the selected leg.
"""

import argparse
import bisect
import csv
import itertools
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import MetaTrader5 as mt5

import config
import sim_s30_backtest as s30sim
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD
from optimize_s75_champion_formula import _simulate_leg
from optimize_s87_siglevel_fast import _invert_raw
from optimize_s88_allin4s_fast import (
    OVERLAY_CFG,
    _fetch_tf_bars,
    _grid_s84,
    _grid_s86,
    _make_s84,
    _make_s86,
)
from sim_s62_backtest import _atr_series
from sim_s84_backtest import run_single as run_s84
from sim_s86_backtest import run_single as run_s86


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "strategy" / "af" / "excel"
WINDOWS_DEFAULT = [30, 60, 90, 120, 150, 180]
DIRECT_WINDOWS = [90, 120, 150, 180]
TF_SECS = {"M5": 300, "M15": 900, "M30": 1800, "H1": 3600}


def _write_csv(path, rows, fields):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _formula_from_doc(n):
    text = (ROOT / f"create_af{n}.md").read_text(encoding="utf-8")
    matches = re.findall(rf"AF{n}\s*=\s*([^\n`]+)", text)
    if not matches:
        raise ValueError(f"Cannot find AF{n} formula")
    formula = matches[-1].strip()
    leg = formula.split("+", 1)[1].strip() if "+" in formula else formula
    m = re.search(r"x([0-9]+(?:\.[0-9]+)?)$", leg)
    if not m:
        raise ValueError(f"Cannot parse AF{n} weight from {leg}")
    return {
        "component_no": n,
        "formula": formula,
        "component_name": leg[:m.start()].rstrip(),
        "weight": float(m.group(1)),
    }


def _cfg_for_leg(component_name):
    if "S86RUN" in component_name:
        cfg_idx = int(re.search(r"c([0-9]+)", component_name).group(1))
        cfg = _make_s86(list(itertools.product(*_grid_s86("micro")))[cfg_idx])
        return "s86", cfg, run_s86

    if "c" in component_name:
        cfg_idx = int(re.search(r"c([0-9]+)", component_name).group(1))
        cfg = _make_s84(list(itertools.product(*_grid_s84("micro")))[cfg_idx])
        return "s84", cfg, run_s84

    # AF1-AF19 use the old S84 M15 follow config from the AF/S89-S123 line.
    cfg = dict(_make_s84(list(itertools.product(*_grid_s84("micro")))[28]))
    cfg.update({
        "ENTRY_TF": "M15",
        "LOOKBACK": 48,
        "REF_MIN_WICK_ATR": 0.25,
        "REF_WICK_BODY_MULT": 0.8,
        "EAT_TOL_ATR": 0.06,
        "CLOSE_FAIL_ATR": 0.03,
        "REQUIRE_OPPOSITE_CLOSE": True,
        "MIN_BODY_ATR": 0.06,
        "MIN_RANGE_ATR": 0.35,
        "TARGET_MODE": "rr",
        "MODE": "follow",
        "SL_ATR_MULT": 0.20,
        "TP_RR": 0.90,
    })
    return "s84", cfg, run_s84


def _cfg_key(component_name):
    if "S86RUN" in component_name:
        return f"s86c{re.search(r'c([0-9]+)', component_name).group(1)}"
    if "c" in component_name:
        return f"s84c{re.search(r'c([0-9]+)', component_name).group(1)}"
    return "s84old_m15_follow"


def _parse_filters(component_name):
    mode = "inverse" if "_INV_" in component_name else "direct"
    rd_min = rd_max = None
    m = re.search(r"_RD([0-9.]+)_([0-9.]+)_H", component_name)
    if m:
        rd_min = float(m.group(1))
        rd_max = float(m.group(2))
    h = int(re.search(r"_H([0-9]+)", component_name).group(1))
    return mode, rd_min, rd_max, h


def _classify_and_build(raw, bars, m1, tf_secs, for_inverse):
    m1_ts = [int(b["time"]) for b in m1]
    bar_by_ts = {int(b["time"]): i for i, b in enumerate(bars)}
    out = []
    stats = {"ambiguous": 0, "m1_sl": 0, "m1_tp": 0, "unresolved": 0}
    for trade in raw:
        fi = bar_by_ts.get(int(trade["fill_time_ts"]))
        entry = float(trade["entry"])
        sl = float(trade["sl"])
        tp = float(trade["tp"])
        direction = trade["signal"]
        cls = None
        if fi is not None:
            for m in range(fi, len(bars)):
                hi = float(bars[m]["high"])
                lw = float(bars[m]["low"])
                if direction == "BUY":
                    hit_sl = lw <= sl
                    hit_tp = hi >= tp
                else:
                    hit_sl = hi >= sl
                    hit_tp = lw <= tp
                if not (hit_sl or hit_tp):
                    continue
                if hit_sl and hit_tp:
                    stats["ambiguous"] += 1
                    ts0 = int(bars[m]["time"])
                    i0 = bisect.bisect_left(m1_ts, ts0)
                    i1 = bisect.bisect_left(m1_ts, ts0 + tf_secs)
                    cls = "unresolved"
                    for k in range(i0, i1):
                        h1 = float(m1[k]["high"])
                        l1 = float(m1[k]["low"])
                        if direction == "BUY":
                            s_hit = l1 <= sl
                            t_hit = h1 >= tp
                        else:
                            s_hit = h1 >= sl
                            t_hit = l1 <= tp
                        if s_hit and t_hit:
                            cls = "unresolved"
                            break
                        if s_hit:
                            cls = "sl"
                            break
                        if t_hit:
                            cls = "tp"
                            break
                    key = "m1_sl" if cls == "sl" else "m1_tp" if cls == "tp" else "unresolved"
                    stats[key] += 1
                break
        if cls is None:
            out.append(trade)
            continue

        def mk(outcome):
            row = dict(trade)
            row["outcome"] = outcome
            px = tp if outcome == "TP" else sl
            row["exit_price"] = round(px, 2)
            diff = (px - entry) if direction == "BUY" else (entry - px)
            row["diff_usd_per_001lot"] = round(diff, 4)
            row["ambfix"] = cls
            return row

        if cls == "sl":
            out.append(mk("SL"))
        elif cls == "tp":
            out.append(mk("TP"))
        else:
            out.append(mk("TP" if for_inverse else "SL"))
    return out, stats


def _bkk(ts, fmt="%Y-%m-%d %H:%M"):
    return config.mt5_ts_to_bkk(int(ts)).strftime(fmt)


def _window_cutoff_ts(days):
    now_bkk = datetime.now(timezone(timedelta(hours=7)))
    return int(now_bkk.timestamp()) - int(days) * 86400


def _current_mt5_spread(symbol):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return DEFAULT_SPREAD, "fallback"
    return max(0.0, float(tick.ask) - float(tick.bid)), "auto MT5 ask-bid"


def _simulate_component(component, windows, m1, bars_cache, replay_cache, spread):
    family, cfg, runner = _cfg_for_leg(component["component_name"])
    mode, rd_min, rd_max, hour = _parse_filters(component["component_name"])
    tf = cfg["ENTRY_TF"]
    cfg_key = _cfg_key(component["component_name"])
    out = []
    stats_rows = []

    for days in windows:
        cache_key = (cfg_key, mode, days, round(float(spread), 6))
        if cache_key not in replay_cache:
            bars = bars_cache[(tf, days)]
            run_cfg = dict(cfg)
            run_cfg["_ATR14"] = _atr_series(bars, 14)
            run_cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
            raw = runner(bars, run_cfg, days, spread)
            replay_cache[cache_key] = _classify_and_build(raw, bars, m1, TF_SECS[tf], mode == "inverse")
        fixed, amb_stats = replay_cache[cache_key]

        window_trades = []
        for trade in fixed:
            rd = float(trade.get("risk_distance", 0.0))
            if rd_min is not None and rd < rd_min:
                continue
            if rd_max is not None and rd > rd_max:
                continue
            if config.mt5_ts_to_bkk(int(trade["fill_time_ts"])).hour != hour:
                continue
            window_trades.append(trade)
        if mode == "inverse":
            window_trades = _invert_raw(window_trades)

        twp, eq, by_day = _simulate_leg(window_trades, OVERLAY_CFG)
        stats_rows.append({
            "target_af": "",
            "window_days": days,
            "component_no": component["component_no"],
            "component_name": component["component_name"],
            "family": family,
            "entry_tf": tf,
            "mode": mode,
            "rd_min": "" if rd_min is None else rd_min,
            "rd_max": "" if rd_max is None else rd_max,
            "fill_hour": hour,
            "weight": component["weight"],
            "orders": len(window_trades),
            "pnl_per_001lot": round(sum(by_day.values()), 6),
            "pnl_weighted_full": round(sum(by_day.values()) * component["weight"], 6),
            "lot_max": eq.get("lot_max", ""),
            "max_dd_pct": eq.get("max_dd_pct", ""),
            "skipped_by_cb": eq.get("skipped_by_circuit_breaker", ""),
            "ambiguous": amb_stats["ambiguous"],
            "m1_sl": amb_stats["m1_sl"],
            "m1_tp": amb_stats["m1_tp"],
            "unresolved": amb_stats["unresolved"],
        })
        for order_no, trade in enumerate(window_trades, start=1):
            pnl = float(trade["diff_usd_per_001lot"]) - spread
            out.append({
                "target_af": "",
                "window_days": days,
                "component_no": component["component_no"],
                "component_name": component["component_name"],
                "order_no": order_no,
                "family": family,
                "entry_tf": tf,
                "mode": mode,
                "rd_min": "" if rd_min is None else rd_min,
                "rd_max": "" if rd_max is None else rd_max,
                "fill_hour": hour,
                "weight": component["weight"],
                "signal": trade.get("signal", ""),
                "outcome": trade.get("outcome", ""),
                "signal_time": _bkk(trade["signal_time_ts"]),
                "fill_time": _bkk(trade["fill_time_ts"]),
                "exit_time": _bkk(trade["exit_time_ts"]),
                "exit_date": _bkk(trade["exit_time_ts"], "%Y-%m-%d"),
                "entry": trade.get("entry", ""),
                "tp": trade.get("tp", ""),
                "sl": trade.get("sl", ""),
                "exit_price": trade.get("exit_price", ""),
                "risk_distance": trade.get("risk_distance", ""),
                "spread": spread,
                "pnl_per_001lot": round(pnl, 6),
                "pnl_weighted_full": round(pnl * component["weight"], 6),
                "reason": trade.get("reason", ""),
            })
    return out, stats_rows


def export(targets, windows, spread=None):
    max_af = max(targets)
    components = [_formula_from_doc(n) for n in range(1, max_af + 1)]

    needed_tfs = sorted({_cfg_for_leg(c["component_name"])[1]["ENTRY_TF"] for c in components})
    max_days = max(max(DIRECT_WINDOWS), max(windows))
    if not config.mt5_initialize(mt5):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        if spread is None:
            spread, spread_source = _current_mt5_spread(config.SYMBOL)
        else:
            spread_source = "override"
        print(f"symbol={config.SYMBOL} spread={spread:g} ({spread_source})", flush=True)
        bars_cache = {(tf, days): _fetch_tf_bars(tf, days) for tf in needed_tfs for days in windows}
        m1 = s30sim.fetch_bars(config.SYMBOL, "M1", max(185, max_days + 5), extra_bars=2000)
    finally:
        mt5.shutdown()

    all_orders = []
    all_summary = []
    replay_cache = {}
    for component in components:
        print(f"component AF{component['component_no']}: {component['component_name']}", flush=True)
        rows, stats_rows = _simulate_component(component, windows, m1, bars_cache, replay_cache, spread)
        for target in targets:
            if component["component_no"] > target:
                continue
            tag = f"AF{target}"
            for row in rows:
                item = dict(row)
                item["target_af"] = tag
                all_orders.append(item)
            for row in stats_rows:
                item = dict(row)
                item["target_af"] = tag
                all_summary.append(item)

    all_orders.sort(key=lambda r: (int(r["target_af"][2:]), int(r["window_days"]), int(r["component_no"]), r["fill_time"]))
    all_summary.sort(key=lambda r: (int(r["target_af"][2:]), int(r["window_days"]), int(r["component_no"])))

    daily = defaultdict(float)
    monthly = defaultdict(float)
    for row in all_orders:
        key = (
            row["target_af"], row["window_days"], row["exit_date"], row["component_no"],
            row["component_name"], row["weight"],
        )
        daily[key] += float(row["pnl_weighted_full"])
        month_key = (
            row["target_af"], row["window_days"], row["exit_date"][:7], row["component_no"],
            row["component_name"], row["weight"],
        )
        monthly[month_key] += float(row["pnl_weighted_full"])

    daily_rows = [
        {
            "target_af": k[0], "window_days": k[1], "date": k[2], "component_no": k[3],
            "component_name": k[4], "weight": k[5], "pnl_weighted_full": round(v, 6),
        }
        for k, v in daily.items()
    ]
    monthly_rows = [
        {
            "target_af": k[0], "window_days": k[1], "month": k[2], "component_no": k[3],
            "component_name": k[4], "weight": k[5], "pnl_weighted_full": round(v, 6),
        }
        for k, v in monthly.items()
    ]
    daily_rows.sort(key=lambda r: (int(r["target_af"][2:]), int(r["window_days"]), r["date"], int(r["component_no"])))
    monthly_rows.sort(key=lambda r: (int(r["target_af"][2:]), int(r["window_days"]), r["month"], int(r["component_no"])))

    order_fields = [
        "target_af", "window_days", "component_no", "component_name", "order_no",
        "family", "entry_tf", "mode", "rd_min", "rd_max", "fill_hour", "weight",
        "signal", "outcome", "signal_time", "fill_time", "exit_time", "exit_date",
        "entry", "tp", "sl", "exit_price", "risk_distance", "spread",
        "pnl_per_001lot", "pnl_weighted_full", "reason",
    ]
    summary_fields = [
        "target_af", "window_days", "component_no", "component_name", "family",
        "entry_tf", "mode", "rd_min", "rd_max", "fill_hour", "weight", "orders",
        "pnl_per_001lot", "pnl_weighted_full", "lot_max", "max_dd_pct",
        "skipped_by_cb", "ambiguous", "m1_sl", "m1_tp", "unresolved",
    ]
    daily_fields = ["target_af", "window_days", "date", "component_no", "component_name", "weight", "pnl_weighted_full"]
    monthly_fields = ["target_af", "window_days", "month", "component_no", "component_name", "weight", "pnl_weighted_full"]

    _write_csv(OUT_DIR / "af_ladder_sim_orders.csv", all_orders, order_fields)
    _write_csv(OUT_DIR / "af_ladder_sim_leg_summary.csv", all_summary, summary_fields)
    _write_csv(OUT_DIR / "af_ladder_sim_daily.csv", daily_rows, daily_fields)
    _write_csv(OUT_DIR / "af_ladder_sim_monthly.csv", monthly_rows, monthly_fields)
    for target in targets:
        tag = f"AF{target}"
        _write_csv(OUT_DIR / f"af_ladder_sim_orders_af{target}.csv", [r for r in all_orders if r["target_af"] == tag], order_fields)
        _write_csv(OUT_DIR / f"af_ladder_sim_leg_summary_af{target}.csv", [r for r in all_summary if r["target_af"] == tag], summary_fields)
    return len(all_orders), len(all_summary), len(daily_rows), len(monthly_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", nargs="+", type=int, default=[22, 34, 47])
    ap.add_argument("--days", nargs="+", type=int, default=WINDOWS_DEFAULT)
    ap.add_argument("--spread", type=float, default=None,
                    help="Override spread cost per trade. If omitted, uses current MT5 ask-bid spread.")
    args = ap.parse_args()
    counts = export(args.targets, args.days, spread=args.spread)
    print(f"orders={counts[0]} leg_summary_rows={counts[1]} daily_rows={counts[2]} monthly_rows={counts[3]}")
    print(f"-> {OUT_DIR / 'af_ladder_sim_orders.csv'}")
    print(f"-> {OUT_DIR / 'af_ladder_sim_leg_summary.csv'}")
    print(f"-> {OUT_DIR / 'af_ladder_sim_daily.csv'}")
    print(f"-> {OUT_DIR / 'af_ladder_sim_monthly.csv'}")
    for target in args.targets:
        print(f"-> {OUT_DIR / f'af_ladder_sim_orders_af{target}.csv'}")
        print(f"-> {OUT_DIR / f'af_ladder_sim_leg_summary_af{target}.csv'}")


if __name__ == "__main__":
    main()
