# -*- coding: utf-8 -*-
"""One-off runner: backtest the recommended S103-S302 shortlist across day windows,
individually and as a combined portfolio. Writes results incrementally to
portfolio_backtest_results.csv / .md so a reboot/interrupt doesn't lose progress.
"""
from __future__ import annotations

import importlib
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5

import config
from sim_strategy_backtest import backtest as generic_backtest

BKK = timezone(timedelta(hours=7))
RESULTS_CSV = "portfolio_backtest_results.csv"
TRADES_DIR = "portfolio_backtest_trades"
os.makedirs(TRADES_DIR, exist_ok=True)

DAY_WINDOWS = [30, 60, 90, 120, 150, 365]
MONTH_EQUIV = {30: 1, 60: 2, 90: 3, 120: 4, 150: 5, 365: 12}

# strategies compatible with the generic S115+ runner (has be_rr/cancel_bars in payload)
GENERIC_STRATS = [110, 165, 166, 172, 173, 176, 206, 218, 224, 258, 294]
# older strategies with their own payload shape (no be_rr/cancel_bars) -> custom simple replay
CUSTOM_STRATS = [104, 105, 106, 111]

ALL_STRATS = GENERIC_STRATS + CUSTOM_STRATS


def log(msg):
    print(msg, flush=True)
    with open("portfolio_backtest_progress.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def already_done(strategy_id, days):
    if not os.path.exists(RESULTS_CSV):
        return False
    with open(RESULTS_CSV, encoding="utf-8") as f:
        for line in f:
            parts = line.split(",")
            if len(parts) >= 2 and parts[0] == str(strategy_id) and parts[1] == str(days):
                return True
    return False


def append_result(row):
    is_new = not os.path.exists(RESULTS_CSV)
    with open(RESULTS_CSV, "a", encoding="utf-8") as f:
        if is_new:
            f.write("strategy,days,signals,closed,wins,win_rate,net,pnl_per_day,pf,max_dd,error\n")
        f.write(",".join(str(row.get(k, "")) for k in
                          ["strategy", "days", "signals", "closed", "wins", "win_rate",
                           "net", "pnl_per_day", "pf", "max_dd", "error"]) + "\n")


def save_trades(strategy_id, days, trades):
    path = os.path.join(TRADES_DIR, f"s{strategy_id}_{days}d.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trades, f)


def run_generic(strategy_id, days):
    months = MONTH_EQUIV[days]
    summary, trades = generic_backtest(
        strategy_id, months, "M5", 0.20, 0.01,
        datetime.now(BKK), 300, {},
    )
    return summary, trades


# ---- simple custom replay for S104/105/106/111 (payload has no be_rr/cancel_bars) ----
TF_MAP = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
          "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}
CUSTOM_TF = {104: "H1", 105: "M5", 106: "M5", 111: "M15"}


def fetch_bars_days(symbol, tf_name, days, lookback_extra=400):
    from sim_s30_backtest import fetch_bars as chunked_fetch, _PER_DAY
    # sim_strategy_backtest.backtest() calls mt5.shutdown() internally after every run
    # (generic strategies run before this in main()) — must re-init before fetching here
    # or copy_rates_from_pos silently returns None (เจอบั๊กจริง 2026-07-28: 0 bars ทุก custom strategy)
    if not config.mt5_initialize(mt5):
        raise RuntimeError("MT5 re-initialize failed before custom fetch")
    return chunked_fetch(symbol, tf_name, days, extra_bars=lookback_extra)


def run_custom(strategy_id, days):
    tf_name = CUSTOM_TF[strategy_id]
    mod = importlib.import_module(f"strategy{strategy_id}")
    detect_fn = getattr(mod, f"detect_s{strategy_id}")

    bars = fetch_bars_days(config.SYMBOL, tf_name, days, lookback_extra=300)
    if bars is None or len(bars) < 320:
        return {"error": f"insufficient bars ({0 if bars is None else len(bars)})"}, []

    n = len(bars)
    lookback = 300
    spread = 0.20
    lot = 0.01
    trades = []
    last_trade_idx = -100
    cooldown = 3
    now_ts = bars[-1]["time"]
    cutoff_ts = now_ts - days * 86400

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

        fill_idx = None
        if order_type == "market":
            fill_idx = i + 1
        else:
            for j in range(i + 1, min(i + 20, n)):
                h, l = float(bars[j]["high"]), float(bars[j]["low"])
                if (direction == "BUY" and l <= entry + spread) or (direction == "SELL" and h >= entry - spread):
                    fill_idx = j
                    break
        if fill_idx is None or fill_idx >= n:
            continue

        outcome = None
        exit_price = None
        exit_idx = None
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
        pnl = (diff - spread) * lot * 100.0
        trades.append({
            "signal_time": dt_bkk.isoformat(),
            "exit_time": datetime.fromtimestamp(int(bars[exit_idx]["time"]), tz=timezone.utc).astimezone(BKK).isoformat(),
            "direction": direction, "entry": entry, "sl": sl, "tp": tp,
            "outcome": outcome, "profit": round(pnl, 2),
        })
        last_trade_idx = i

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
    summary = {
        "strategy": f"S{strategy_id}", "closed": len(trades), "wins": wins,
        "win_rate": (wins / len(trades) * 100.0) if trades else None,
        "net_profit": net, "pnl_per_day": net / days,
        "profit_factor": (gross_win / gross_loss) if gross_loss else (math.inf if gross_win else None),
        "max_drawdown": max_dd,
    }
    return summary, trades


def main():
    config.SYMBOL = ""  # force resolve below
    import mt5_worker as mw
    mw.initialize(path=r"profiles\demo\demo-iux-2101182459\mt5\terminal64.exe")
    config.resolve_mt5_symbol(mt5, "XAUUSD", set_runtime=True)
    log(f"Resolved symbol: {config.SYMBOL}")

    for sid in ALL_STRATS:
        for days in DAY_WINDOWS:
            if already_done(sid, days):
                log(f"S{sid} {days}d already done, skipping")
                continue
            log(f"Running S{sid} {days}d ...")
            try:
                if sid in GENERIC_STRATS:
                    summary, trades = run_generic(sid, days)
                    row = {
                        "strategy": sid, "days": days,
                        "signals": summary.get("signals"), "closed": summary.get("closed"),
                        "wins": summary.get("wins"), "win_rate": summary.get("win_rate"),
                        "net": summary.get("net_profit"), "pnl_per_day": summary.get("pnl_per_day"),
                        "pf": summary.get("profit_factor"), "max_dd": summary.get("max_drawdown"),
                        "error": "",
                    }
                else:
                    summary, trades = run_custom(sid, days)
                    if "error" in summary:
                        row = {"strategy": sid, "days": days, "error": summary["error"]}
                    else:
                        row = {
                            "strategy": sid, "days": days,
                            "signals": "", "closed": summary.get("closed"),
                            "wins": summary.get("wins"), "win_rate": summary.get("win_rate"),
                            "net": summary.get("net_profit"), "pnl_per_day": summary.get("pnl_per_day"),
                            "pf": summary.get("profit_factor"), "max_dd": summary.get("max_drawdown"),
                            "error": "",
                        }
                append_result(row)
                save_trades(sid, days, trades)
                log(f"  -> {row}")
            except Exception as e:
                append_result({"strategy": sid, "days": days, "error": f"{type(e).__name__}: {e}"})
                log(f"  -> ERROR: {type(e).__name__}: {e}")

    mt5.shutdown()
    log("ALL DONE")


if __name__ == "__main__":
    main()
