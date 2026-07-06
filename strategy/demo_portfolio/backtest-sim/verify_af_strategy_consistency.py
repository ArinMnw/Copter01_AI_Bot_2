"""
verify_af_strategy_consistency.py

Compare AF22/AF34/AF47 live-style detection against the S84/S86 backtest
runner over the same bars. This catches drift in cfg, hour/RD filters,
inverse mode, ATR handling, and MIN_GAP_BARS cooldown.
It also exports order-level, daily, and monthly P/L reports.

Run:
  python strategy/demo_portfolio/backtest-sim/verify_af_strategy_consistency.py all
  python strategy/demo_portfolio/backtest-sim/verify_af_strategy_consistency.py AF22 --days 90 120 150 180
  python strategy/demo_portfolio/backtest-sim/verify_af_strategy_consistency.py all --symbol BTCUSD
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import MetaTrader5 as mt5

import config
import sim_s30_backtest as s30sim
from sim_s84_backtest import run_single as run_s84
from sim_s86_backtest import run_single as run_s86
from strategy84 import _detect_closed as _detect_s84_closed, _in_session as _in_s84_session
from strategy86 import _detect_closed as _detect_s86_closed, _in_session as _in_s86_session
from strategy_af import AF_STRATEGIES, _atr_series, apply_af_filters


DEFAULT_SPREAD = 0.20
EXTRA_BARS = {"s84": 560, "s86": 700}
RUNNERS = {"s84": run_s84, "s86": run_s86}
CLOSED_DETECTORS = {"s84": _detect_s84_closed, "s86": _detect_s86_closed}
SESSION_CHECKS = {"s84": _in_s84_session, "s86": _in_s86_session}
MIN_START_EXTRA = {"s84": 90, "s86": 120}


def _fetch_bars(symbol, af_def, days):
    family = af_def["family"]
    return s30sim.fetch_bars(
        symbol,
        af_def["cfg"]["ENTRY_TF"],
        days,
        extra_bars=EXTRA_BARS[family],
    )


def _post_filter_backtest(raw, af_def):
    out = []
    for trade in raw:
        filtered, _ = apply_af_filters(trade, af_def, int(trade["fill_time_ts"]))
        if filtered is None:
            continue
        row = {
            "fill_time_ts": int(trade["fill_time_ts"]),
            "signal_time_ts": int(trade["signal_time_ts"]),
            "signal": filtered["signal"],
            "entry": round(float(filtered["entry"]), 2),
            "sl": round(float(filtered["sl"]), 2),
            "tp": round(float(filtered["tp"]), 2),
            "risk_distance": round(float(filtered["risk_distance"]), 4),
        }
        out.append(row)
    return out


def _bkk_str(ts, fmt):
    return config.mt5_ts_to_bkk(int(ts)).strftime(fmt)


def _post_filter_order_rows(symbol, name, days, raw, af_def, spread):
    out = []
    weight = float(af_def.get("weight", 1.0))
    for idx, trade in enumerate(raw, start=1):
        filtered, _ = apply_af_filters(trade, af_def, int(trade["fill_time_ts"]))
        if filtered is None:
            continue
        diff = float(trade["diff_usd_per_001lot"])
        raw_outcome = trade.get("outcome", "")
        effective_outcome = raw_outcome
        if af_def.get("mode") == "inverse":
            diff = -diff
            effective_outcome = "SL" if raw_outcome == "TP" else ("TP" if raw_outcome == "SL" else raw_outcome)
        pnl = diff - float(spread)
        out.append({
            "symbol": symbol,
            "portfolio": name,
            "window_days": days,
            "order_no": len(out) + 1,
            "raw_no": idx,
            "family": af_def["family"],
            "cfg_idx": af_def["cfg_idx"],
            "mode": af_def["mode"],
            "entry_tf": af_def["cfg"]["ENTRY_TF"],
            "fill_hour": filtered["fill_hour"],
            "signal": filtered["signal"],
            "raw_outcome": raw_outcome,
            "effective_outcome": effective_outcome,
            "signal_time": _bkk_str(trade["signal_time_ts"], "%Y-%m-%d %H:%M"),
            "fill_time": _bkk_str(trade["fill_time_ts"], "%Y-%m-%d %H:%M"),
            "exit_time": _bkk_str(trade["exit_time_ts"], "%Y-%m-%d %H:%M"),
            "exit_date": _bkk_str(trade["exit_time_ts"], "%Y-%m-%d"),
            "exit_month": _bkk_str(trade["exit_time_ts"], "%Y-%m"),
            "entry": round(float(filtered["entry"]), 2),
            "sl": round(float(filtered["sl"]), 2),
            "tp": round(float(filtered["tp"]), 2),
            "exit_price": round(float(trade["exit_price"]), 2),
            "risk_distance": round(float(filtered["risk_distance"]), 4),
            "spread": round(float(spread), 4),
            "pnl_per_001lot": round(pnl, 4),
            "weight": round(weight, 6),
            "pnl_weighted_full": round(pnl * weight, 4),
            "reason": trade.get("reason", ""),
        })
    return out


def _aggregate(rows, keys):
    grouped = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        item = grouped.setdefault(key, {
            **{k: row[k] for k in keys},
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "pnl_per_001lot": 0.0,
            "pnl_weighted_full": 0.0,
            "gross_win_per_001lot": 0.0,
            "gross_loss_per_001lot": 0.0,
        })
        pnl = float(row["pnl_per_001lot"])
        item["trades"] += 1
        item["pnl_per_001lot"] += pnl
        item["pnl_weighted_full"] += float(row["pnl_weighted_full"])
        if pnl > 0:
            item["wins"] += 1
            item["gross_win_per_001lot"] += pnl
        else:
            item["losses"] += 1
            item["gross_loss_per_001lot"] += abs(pnl)
    out = []
    for item in grouped.values():
        gross_loss = item.pop("gross_loss_per_001lot")
        gross_win = item.pop("gross_win_per_001lot")
        item["pnl_per_001lot"] = round(item["pnl_per_001lot"], 4)
        item["pnl_weighted_full"] = round(item["pnl_weighted_full"], 4)
        item["profit_factor"] = round(gross_win / gross_loss, 6) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
        out.append(item)
    return sorted(out, key=lambda r: tuple(r[k] for k in keys))


def _live_style_signals(bars, af_def):
    cfg = af_def["cfg"]
    family = af_def["family"]
    detect_closed = CLOSED_DETECTORS[family]
    in_session = SESSION_CHECKS[family]
    min_gap_bars = int(cfg.get("MIN_GAP_BARS", 1))
    min_start = int(cfg["LOOKBACK"]) + MIN_START_EXTRA[family]
    atr14 = _atr_series(bars, 14)
    last_raw_idx = -100
    out = []
    for fill_idx in range(min_start + 1, len(bars)):
        j = fill_idx - 1
        if j - last_raw_idx < min_gap_bars:
            continue
        fill_ts = int(bars[fill_idx]["time"])
        fill_dt = config.mt5_ts_to_bkk(fill_ts)
        if not in_session(fill_dt, cfg):
            continue
        res = detect_closed(bars, j, cfg, atr_value=atr14[j])
        if res is None or res.get("signal") not in ("BUY", "SELL"):
            continue
        last_raw_idx = j
        filtered, _ = apply_af_filters(res, af_def, fill_ts)
        if filtered is None:
            continue
        out.append({
            "fill_time_ts": fill_ts,
            "signal_time_ts": int(bars[j]["time"]),
            "signal": filtered["signal"],
            "entry": round(float(filtered["entry"]), 2),
            "sl": round(float(filtered["sl"]), 2),
            "tp": round(float(filtered["tp"]), 2),
            "risk_distance": round(float(filtered["risk_distance"]), 4),
        })
    return out


def _same_row(a, b, price_tol=0.01):
    if a["fill_time_ts"] != b["fill_time_ts"]:
        return False
    if a["signal_time_ts"] != b["signal_time_ts"]:
        return False
    if a["signal"] != b["signal"]:
        return False
    for key in ("entry", "sl", "tp", "risk_distance"):
        if abs(float(a[key]) - float(b[key])) > price_tol:
            return False
    return True


def verify_one(symbol, name, days, spread):
    af_def = AF_STRATEGIES[name]
    bars = _fetch_bars(symbol, af_def, days)
    if bars is None:
        return {
            "symbol": symbol,
            "portfolio": name,
            "days": days,
            "result": "NO_DATA",
            "backtest": 0,
            "live_style": 0,
            "detail": "fetch_bars failed",
        }
    raw = RUNNERS[af_def["family"]](bars, af_def["cfg"], days, spread)
    backtest = _post_filter_backtest(raw, af_def)
    order_rows = _post_filter_order_rows(symbol, name, days, raw, af_def, spread)
    live_style = _live_style_signals(bars, af_def)

    result = "MATCH"
    detail = ""
    if len(backtest) != len(live_style):
        result = "COUNT_MISMATCH"
        detail = f"backtest={len(backtest)} live_style={len(live_style)}"
    else:
        for idx, (bt, lv) in enumerate(zip(backtest, live_style), start=1):
            if not _same_row(bt, lv):
                result = "ROW_MISMATCH"
                detail = f"row={idx} bt={bt} live={lv}"
                break
    if result == "MATCH":
        detail = f"{len(backtest)} filtered trades match"

    return {
        "symbol": symbol,
        "portfolio": name,
        "days": days,
        "result": result,
        "backtest": len(backtest),
        "live_style": len(live_style),
        "detail": detail,
    }, order_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("portfolio", nargs="?", default="all", choices=["AF22", "AF34", "AF47", "all"])
    ap.add_argument("--days", nargs="+", type=int, default=[90, 120, 150, 180])
    ap.add_argument("--symbol", default=None,
                    help="Symbol to backtest, e.g. XAUUSD or BTCUSD. Defaults to config.SYMBOL/env SYMBOL.")
    ap.add_argument("--spread", type=float, default=None,
                    help="Override spread cost per trade. If omitted, uses current MT5 ask-bid spread.")
    args = ap.parse_args()

    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize failed: {mt5.last_error()}")
        return 1
    symbol = config.resolve_mt5_symbol(mt5, args.symbol or config.SYMBOL, set_runtime=True)
    spread = args.spread
    if spread is None:
        tick = mt5.symbol_info_tick(symbol)
        if tick is not None:
            spread = max(0.0, float(tick.ask) - float(tick.bid))
        else:
            spread = DEFAULT_SPREAD
    print(f"symbol={symbol} spread={spread:g}" + (" (auto MT5 ask-bid)" if args.spread is None else " (override)"))

    names = list(AF_STRATEGIES) if args.portfolio == "all" else [args.portfolio]
    rows = []
    order_rows = []
    for name in names:
        for days in args.days:
            row, orders = verify_one(symbol, name, days, spread)
            rows.append(row)
            order_rows.extend(orders)
            mark = "OK" if row["result"] == "MATCH" else "FAIL"
            print(f"{mark} {symbol} {name} {days}d {row['result']} - {row['detail']}")

    mt5.shutdown()

    out_dir = os.path.join(os.path.dirname(__file__), "..", "excel")
    os.makedirs(out_dir, exist_ok=True)
    out_symbol = "".join(ch if ch.isalnum() else "_" for ch in symbol.lower())
    out_path = os.path.join(out_dir, f"af_strategy_consistency_{out_symbol}.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["symbol", "portfolio", "days", "result", "backtest", "live_style", "detail"])
        w.writeheader()
        w.writerows(rows)
    print(f"-> {out_path}")

    order_path = os.path.join(out_dir, f"af_pnl_orders_{out_symbol}.csv")
    daily_path = os.path.join(out_dir, f"af_pnl_daily_{out_symbol}.csv")
    monthly_path = os.path.join(out_dir, f"af_pnl_monthly_{out_symbol}.csv")
    order_fields = [
        "symbol", "portfolio", "window_days", "order_no", "raw_no", "family", "cfg_idx",
        "mode", "entry_tf", "fill_hour", "signal", "raw_outcome", "effective_outcome", "signal_time", "fill_time",
        "exit_time", "exit_date", "exit_month", "entry", "tp", "sl", "exit_price",
        "risk_distance", "spread", "pnl_per_001lot", "weight", "pnl_weighted_full", "reason",
    ]
    with open(order_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=order_fields)
        w.writeheader()
        w.writerows(order_rows)
    print(f"-> {order_path}")

    for name in names:
        per_af_path = os.path.join(out_dir, f"af_pnl_orders_{out_symbol}_{name.lower()}.csv")
        per_af_rows = [r for r in order_rows if r["portfolio"] == name]
        with open(per_af_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=order_fields)
            w.writeheader()
            w.writerows(per_af_rows)
        print(f"-> {per_af_path}")

    daily_rows = _aggregate(order_rows, ["symbol", "portfolio", "window_days", "exit_date"])
    monthly_rows = _aggregate(order_rows, ["symbol", "portfolio", "window_days", "exit_month"])
    for path, data, keys in (
        (daily_path, daily_rows, ["symbol", "portfolio", "window_days", "exit_date"]),
        (monthly_path, monthly_rows, ["symbol", "portfolio", "window_days", "exit_month"]),
    ):
        fields = keys + ["trades", "wins", "losses", "pnl_per_001lot", "pnl_weighted_full", "profit_factor"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(data)
        print(f"-> {path}")

    return 0 if all(r["result"] == "MATCH" for r in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
