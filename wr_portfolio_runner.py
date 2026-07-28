# -*- coding: utf-8 -*-
"""Backtest high-win-rate candidates (S99, S100, S101, S102, S105) individually
and combined, across 30/60/90/120/150/365 day windows."""
from __future__ import annotations
import csv
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5
import config

BKK = timezone(timedelta(hours=7))
DAY_WINDOWS = [30, 60, 90, 120, 150, 365]
TRADES_DIR = "wr_portfolio_trades"
os.makedirs(TRADES_DIR, exist_ok=True)

SCRIPT_STRATS = {
    99: "sim_s99_backtest.py",
    100: "sim_s100_backtest.py",
    101: "strategy/demo_portfolio/backtest-sim/sim_s101_backtest.py",
    102: "strategy/demo_portfolio/backtest-sim/sim_s102_backtest.py",
    103: "sim_s103_backtest.py",
    110: "sim_s110_backtest.py",
    113: "sim_s113_backtest.py",
}
CUSTOM_STRATS = {105: "M5"}


def log(msg):
    print(msg, flush=True)
    with open("wr_portfolio_progress.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def run_script_strat(sid, days):
    script = SCRIPT_STRATS[sid]
    prefix = os.path.join(TRADES_DIR, f"s{sid}_{days}d")
    cmd = [sys.executable, script, "--days", str(days), "--out-prefix", prefix]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    trades_csv = f"{prefix}_trades.csv"
    trades = []
    if os.path.exists(trades_csv):
        with open(trades_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    ft = row.get("fill_time") or row.get("time")
                    et = row["exit_time"]
                    trades.append({
                        "exit_time": datetime.strptime(et, "%Y-%m-%d %H:%M").replace(tzinfo=BKK).isoformat(),
                        "fill_time": datetime.strptime(ft, "%Y-%m-%d %H:%M").replace(tzinfo=BKK).isoformat(),
                        "profit": float(row["profit"]),
                        "outcome": row.get("outcome", ""),
                    })
                except Exception:
                    continue
    return trades, r.stdout, r.stderr


def fetch_bars_days(symbol, tf_name, days, lookback_extra=300):
    from sim_s30_backtest import fetch_bars as chunked_fetch
    if not config.mt5_initialize(mt5):
        raise RuntimeError("MT5 re-init failed")
    return chunked_fetch(symbol, tf_name, days, extra_bars=lookback_extra)


def run_custom_strat(sid, days, tf_name):
    import importlib
    mod = importlib.import_module(f"strategy{sid}")
    detect_fn = getattr(mod, f"detect_s{sid}")
    bars = fetch_bars_days(config.SYMBOL, tf_name, days)
    if bars is None or len(bars) < 320:
        return []
    n = len(bars)
    lookback = 300
    spread = 0.20
    trades = []
    last_trade_idx = -100
    cooldown = 3
    cutoff_ts = bars[-1]["time"] - days * 86400
    for i in range(lookback, n - 1):
        if int(bars[i]["time"]) < cutoff_ts:
            continue
        if i - last_trade_idx < cooldown:
            continue
        rates_slice = bars[max(0, i - lookback + 1): i + 1]
        dt_bkk = datetime.fromtimestamp(int(rates_slice[-1]["time"]), tz=timezone.utc).astimezone(BKK)
        try:
            res = detect_fn(rates_slice, tf=tf_name, dt_bkk=dt_bkk, cfg=None)
        except Exception:
            continue
        if not res or res.get("signal") not in ("BUY", "SELL"):
            continue
        direction = res["signal"]
        entry = float(res.get("entry", 0.0) or 0.0)
        sl = float(res.get("sl", 0.0) or 0.0)
        tp = float(res.get("tp", 0.0) or 0.0)
        if entry <= 0 or sl <= 0 or tp <= 0:
            continue
        order_type = res.get("order_type", "market")
        fill_idx = i + 1 if order_type == "market" else None
        if fill_idx is None:
            for j in range(i + 1, min(i + 20, n)):
                h, l = float(bars[j]["high"]), float(bars[j]["low"])
                if (direction == "BUY" and l <= entry + spread) or (direction == "SELL" and h >= entry - spread):
                    fill_idx = j
                    break
        if fill_idx is None or fill_idx >= n:
            continue
        outcome = exit_price = exit_idx = None
        for j in range(fill_idx, n):
            h, l = float(bars[j]["high"]), float(bars[j]["low"])
            if direction == "BUY":
                if l <= sl:
                    outcome, exit_price, exit_idx = "SL", sl, j
                    break
                if h >= tp:
                    outcome, exit_price, exit_idx = "TP", tp, j
                    break
            else:
                if h >= sl:
                    outcome, exit_price, exit_idx = "SL", sl, j
                    break
                if l <= tp:
                    outcome, exit_price, exit_idx = "TP", tp, j
                    break
        if outcome is None:
            continue
        diff = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
        pnl = round((diff - spread) * 0.01 * 100.0, 2)
        trades.append({
            "exit_time": datetime.fromtimestamp(int(bars[exit_idx]["time"]), tz=timezone.utc).astimezone(BKK).isoformat(),
            "fill_time": dt_bkk.isoformat(),
            "profit": pnl, "outcome": outcome,
        })
        last_trade_idx = i
    return trades


def stats(trades):
    profits = [t["profit"] for t in trades]
    wins = sum(p > 0 for p in profits)
    gross_win = sum(p for p in profits if p > 0)
    gross_loss = -sum(p for p in profits if p < 0)
    net = sum(profits)
    equity = peak = max_dd = 0.0
    for p in profits:
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    pf = (gross_win / gross_loss) if gross_loss else (math.inf if gross_win else None)
    return {"closed": len(trades), "wins": wins,
            "win_rate": (wins / len(trades) * 100.0) if trades else None,
            "net": net, "pf": pf, "max_dd": max_dd}


def main():
    import mt5_worker as mw
    mw.initialize(path=r"profiles\demo\demo-iux-2101182459\mt5\terminal64.exe")
    config.resolve_mt5_symbol(mt5, "XAUUSD", set_runtime=True)
    log(f"Symbol resolved: {config.SYMBOL}")

    all_data = {}
    for sid in list(SCRIPT_STRATS) + list(CUSTOM_STRATS):
        all_data[sid] = {}
        for days in DAY_WINDOWS:
            cache_path = os.path.join(TRADES_DIR, f"s{sid}_{days}d.json")
            if os.path.exists(cache_path):
                with open(cache_path, encoding="utf-8") as f:
                    trades = json.load(f)
                all_data[sid][days] = trades
                log(f"S{sid} {days}d already done, skipping -> {stats(trades)}")
                continue
            log(f"Running S{sid} {days}d ...")
            if sid in SCRIPT_STRATS:
                trades, out, err = run_script_strat(sid, days)
            else:
                mt5.shutdown()
                trades = run_custom_strat(sid, days, CUSTOM_STRATS[sid])
            all_data[sid][days] = trades
            s = stats(trades)
            log(f"  -> S{sid} {days}d: {s}")
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(trades, f)

    log("\n=== COMBINED (S99+S100+S101+S102+S105) ===")
    orig5 = (99, 100, 101, 102, 105)
    for days in DAY_WINDOWS:
        combined = []
        for sid in orig5:
            combined.extend(all_data[sid][days])
        s = stats(combined)
        log(f"  combined_orig5 {days}d: {s}")

    log("\n=== NEW CANDIDATES ALONE (S103+S110+S113) ===")
    new3 = (103, 110, 113)
    for days in DAY_WINDOWS:
        combined = []
        for sid in new3:
            combined.extend(all_data[sid][days])
        s = stats(combined)
        log(f"  combined_new3 {days}d: {s}")

    mt5.shutdown()
    log("ALL DONE")


if __name__ == "__main__":
    main()
