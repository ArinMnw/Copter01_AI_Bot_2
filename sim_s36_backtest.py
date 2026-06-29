"""
sim_s36_backtest.py — Backtest S36 (FVG retracement, ICT/SMC)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ RESEARCH / BACKTEST-ONLY — ไม่แก้ S1-S35, ไม่ wire เข้า live
"""

import argparse
import csv
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy36 import S36_DEFAULTS, detect_s36
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim

START_EQUITY = 1000.0


def _cfg_get(cfg, key):
    return cfg[key] if (cfg and key in cfg) else S36_DEFAULTS[key]


def replay36(bars, htf_series, spread, cfg):
    conf_type = cfg["CONFIRMATION_TYPE"]
    min_gap_bars = int(_cfg_get(cfg, "MIN_GAP_BARS"))
    max_gap_age = int(_cfg_get(cfg, "MAX_GAP_AGE_BARS"))
    win_size = max_gap_age + 30

    trades = []
    last_fire_idx = -10
    n = len(bars)
    start_j = win_size + 5
    for j in range(start_j, n - 1):
        if j - last_fire_idx < min_gap_bars:
            continue
        entry_bar = bars[j + 1]
        live = {"time": int(entry_bar["time"]), "open": float(entry_bar["open"]),
                "high": float(entry_bar["open"]), "low": float(entry_bar["open"]),
                "close": float(entry_bar["open"])}
        lo = max(0, j + 1 - win_size)
        window = list(bars[lo:j + 1]) + [live]
        dt_bkk = config.mt5_ts_to_bkk(int(entry_bar["time"]))
        htf_ctx = s30sim.htf_lookup(htf_series, int(entry_bar["time"])) if conf_type != "none" else None

        res = detect_s36(window, tf=cfg["ENTRY_TF"], dt_bkk=dt_bkk, cfg=cfg, htf_ctx=htf_ctx)
        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue
        last_fire_idx = j

        entry, tp, sl = float(res["entry"]), float(res["tp"]), float(res["sl"])
        fill_idx = j + 1
        outcome, exit_price, exit_idx = "OPEN", None, None
        for m in range(fill_idx, n):
            hi, lw = float(bars[m]["high"]), float(bars[m]["low"])
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
        if outcome == "OPEN":
            continue
        risk_distance = abs(entry - sl)
        diff = (exit_price - entry) if sig == "BUY" else (entry - exit_price)
        trades.append({
            "signal": sig, "outcome": outcome, "signal_time_ts": int(entry_bar["time"]),
            "fill_time_ts": int(bars[fill_idx]["time"]), "exit_time_ts": int(bars[exit_idx]["time"]),
            "entry": round(entry, 2), "tp": round(tp, 2), "sl": round(sl, 2),
            "exit_price": round(exit_price, 2), "risk_distance": round(risk_distance, 4),
            "diff_usd_per_001lot": round(diff, 4), "spread": spread,
        })
    return trades


def run_single(entry_bars, htf_bars, cfg, days, spread):
    htf_series = s30sim.build_htf_series(htf_bars, cfg) if cfg["CONFIRMATION_TYPE"] != "none" else None
    return replay36(entry_bars, htf_series, spread, cfg)


def run_backtest(cfg, days, spread, label, verbose=True):
    if not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return None
    symbol = config.SYMBOL
    max_gap_age = int(cfg["MAX_GAP_AGE_BARS"])
    entry_bars = s30sim.fetch_bars(symbol, cfg["ENTRY_TF"], days, extra_bars=max_gap_age + 80)
    htf_bars = s30sim.fetch_bars(symbol, cfg["HTF_TF"], days,
                                  extra_bars=max(int(cfg["HTF_EMA_PERIOD"]), 28) + 60) if cfg["CONFIRMATION_TYPE"] != "none" else None
    if entry_bars is None:
        print("! fetch entry bars fail"); mt5.shutdown(); return None
    raw = run_single(entry_bars, htf_bars, cfg, days, spread)
    if verbose:
        print(f"  signals(after fill+SL/TP resolved): {len(raw)}")
    twp, eq = s31sim.simulate_equity_substream(raw, cfg, START_EQUITY)
    if not twp:
        if verbose:
            print("no trades")
        mt5.shutdown()
        return None
    s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days)
    by_day = s31sim.daily_series_from_trades(twp)
    c = s31sim.consistency_metrics(by_day)
    if verbose:
        print(f"n={s['trades']:>4} WR={s['wr']:>5.1f}% $/d={s['avg_per_day_span']:>7.2f} "
              f"$/mo={s['avg_per_day_span']*30:>8.1f} DD={s['max_dd_pct']:>5.1f}% PF={s['profit_factor']:>4.2f} "
              f"posDay={c['pct_pos_days']:>5.1f}% maxStreak={c['max_losing_day_streak']:>2}d "
              f"sharpe={c['sharpe_like']:>6.3f}")
    s.update(c)
    append_summary_csv(label, s, cfg)
    mt5.shutdown()
    return s


def append_summary_csv(label, s, cfg):
    path = os.path.join(os.path.dirname(__file__), "s36_backtest_summary.csv")
    is_new = not os.path.exists(path)
    fields = ["timestamp", "label", "entry_tf", "min_gap_atr", "max_gap_age_bars",
              "retrace_entry_pct", "sl_atr_mult", "tp_rr", "risk_pct", "trades", "wr",
              "avg_per_day_span", "avg_per_month", "max_dd_pct", "profit_factor", "pct_pos_days",
              "max_losing_day_streak", "sharpe_like", "final_equity"]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        w.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "label": label,
            "entry_tf": cfg["ENTRY_TF"], "min_gap_atr": cfg["MIN_GAP_ATR"],
            "max_gap_age_bars": cfg["MAX_GAP_AGE_BARS"], "retrace_entry_pct": cfg["RETRACE_ENTRY_PCT"],
            "sl_atr_mult": cfg["SL_ATR_MULT"], "tp_rr": cfg["TP_RR"], "risk_pct": cfg["RISK_PCT"],
            "trades": s["trades"], "wr": s["wr"], "avg_per_day_span": s["avg_per_day_span"],
            "avg_per_month": round(s["avg_per_day_span"] * 30, 2), "max_dd_pct": s["max_dd_pct"],
            "profit_factor": s["profit_factor"], "pct_pos_days": s["pct_pos_days"],
            "max_losing_day_streak": s["max_losing_day_streak"], "sharpe_like": s["sharpe_like"],
            "final_equity": s["final_equity"],
        })
    print(f"  -> appended to {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--spread", type=float, default=0.20)
    ap.add_argument("--risk", type=float, default=S36_DEFAULTS["RISK_PCT"])
    ap.add_argument("--mingapatr", type=float, default=None)
    ap.add_argument("--maxgapage", type=int, default=None)
    ap.add_argument("--retracepct", type=float, default=None)
    ap.add_argument("--slmult", type=float, default=None)
    ap.add_argument("--rr", type=float, default=None)
    ap.add_argument("--label", default="baseline")
    args = ap.parse_args()

    cfg = dict(S36_DEFAULTS)
    cfg["RISK_PCT"] = args.risk
    if args.mingapatr is not None:
        cfg["MIN_GAP_ATR"] = args.mingapatr
    if args.maxgapage is not None:
        cfg["MAX_GAP_AGE_BARS"] = args.maxgapage
    if args.retracepct is not None:
        cfg["RETRACE_ENTRY_PCT"] = args.retracepct
    if args.slmult is not None:
        cfg["SL_ATR_MULT"] = args.slmult
    if args.rr is not None:
        cfg["TP_RR"] = args.rr

    print(f"S36 backtest | days={args.days} | risk={cfg['RISK_PCT']}% | mingap={cfg['MIN_GAP_ATR']} "
          f"maxage={cfg['MAX_GAP_AGE_BARS']} retrace={cfg['RETRACE_ENTRY_PCT']} sl={cfg['SL_ATR_MULT']} "
          f"rr={cfg['TP_RR']}")
    run_backtest(cfg, args.days, args.spread, args.label)


if __name__ == "__main__":
    main()
