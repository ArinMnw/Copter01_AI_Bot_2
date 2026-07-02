"""
sim_s61_backtest.py — Backtest S61 CYQONX Three-Line Mean Reversion
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ RESEARCH / BACKTEST-ONLY — ไม่แก้ S1-S60, ไม่ wire เข้า live
"""

import argparse
import csv
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy61 import S61_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim

START_EQUITY = 1000.0
DEFAULT_SPREAD = 0.20


def _fixed_lot_stats(raw, days, spread):
    vals = []
    wins = losses = 0
    gross_win = gross_loss = 0.0
    by_day = {}
    for t in raw:
        pnl = float(t["diff_usd_per_001lot"]) - spread
        vals.append(pnl)
        if pnl > 0:
            wins += 1; gross_win += pnl
        else:
            losses += 1; gross_loss += abs(pnl)
        d = config.mt5_ts_to_bkk(t["exit_time_ts"]).strftime("%Y-%m-%d")
        by_day[d] = by_day.get(d, 0.0) + pnl
    c = s31sim.consistency_metrics(by_day) or {"pct_pos_days": 0.0, "max_losing_day_streak": 0, "sharpe_like": 0.0}
    total = sum(vals)
    return {
        "trades": len(vals), "wr": round(100.0 * wins / len(vals), 1) if vals else 0.0,
        "fixed_pnl": round(total, 2), "fixed_per_day": round(total / days, 2) if days else 0.0,
        "fixed_per_month": round(total / days * 30, 2) if days else 0.0,
        "fixed_pf": round(gross_win / gross_loss, 3) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0),
        "fixed_avg": round(total / len(vals), 3) if vals else 0.0,
        "pct_pos_days": c["pct_pos_days"], "max_losing_day_streak": c["max_losing_day_streak"],
        "sharpe_like": c["sharpe_like"],
    }


def _ema_series(values, period):
    out = []
    if not values:
        return out
    k = 2.0 / (period + 1.0)
    val = values[0]
    for x in values:
        val = val + k * (x - val)
        out.append(val)
    return out


def _sma_series(values, period):
    out = []
    s = 0.0
    q = []
    for x in values:
        q.append(x); s += x
        if len(q) > period:
            s -= q.pop(0)
        out.append(s / len(q))
    return out


def _rolling_std(values, period):
    out = []
    q = []
    for x in values:
        q.append(x)
        if len(q) > period:
            q.pop(0)
        m = sum(q) / len(q)
        out.append((sum((v - m) ** 2 for v in q) / len(q)) ** 0.5)
    return out


def _atr_series(bars, period):
    trs = []
    out = []
    atr = None
    for i, b in enumerate(bars):
        h = float(b["high"]); l = float(b["low"])
        if i == 0:
            tr = h - l
        else:
            pc = float(bars[i - 1]["close"])
            tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
        if i + 1 < period:
            out.append(sum(trs) / len(trs))
        elif i + 1 == period:
            atr = sum(trs[-period:]) / period
            out.append(atr)
        else:
            atr = (atr * (period - 1) + tr) / period
            out.append(atr)
    return out


def _parse_time(s):
    from datetime import time
    h, m = map(int, s.split(":"))
    return time(h, m)


def _in_session(dt_bkk, cfg):
    if not cfg.get("SESSION_FILTER", True):
        return True
    cur = dt_bkk.time()
    for start_str, end_str in cfg["SESSIONS"]:
        if _parse_time(start_str) <= cur < _parse_time(end_str):
            return True
    return False


def replay61(bars, htf_series, spread, cfg):
    conf_type = cfg["CONFIRMATION_TYPE"]
    min_gap_bars = int(cfg.get("MIN_GAP_BARS", 1))
    mean_period = int(cfg["MEAN_PERIOD"])
    dev_period = int(cfg["DEV_PERIOD"])
    phase_lb = int(cfg["PHASE_LOOKBACK"])
    win_size = max(mean_period, dev_period) + 80
    closes = [float(b["close"]) for b in bars]
    means = _sma_series(closes, mean_period) if cfg["MEAN_TYPE"] == "sma" else _ema_series(closes, mean_period)
    devs = _rolling_std(closes, dev_period) if cfg["DEV_TYPE"] == "std" else _atr_series(bars, dev_period)
    atr14 = _atr_series(bars, 14)
    all_dt = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
    trades = []
    last_fire_idx = -10
    n = len(bars)
    for j in range(win_size + 5, n - 1):
        if j - last_fire_idx < min_gap_bars:
            continue
        entry_bar = bars[j + 1]
        dt_bkk = all_dt[j + 1]
        if not _in_session(dt_bkk, cfg):
            continue
        mean_now = means[j]
        dev = devs[j]
        atr = atr14[j]
        if not dev or dev <= 0 or not atr or atr <= 0:
            continue
        z = (closes[j] - mean_now) / dev
        recent = [closes[k] - means[k] for k in range(j - phase_lb + 1, j + 1)]
        sig = None
        if z <= -float(cfg["ENTRY_Z"]) and recent[-1] > recent[-2] and min(recent) == recent[-2]:
            sig = "BUY"
        elif z >= float(cfg["ENTRY_Z"]) and recent[-1] < recent[-2] and max(recent) == recent[-2]:
            sig = "SELL"
        if sig is None:
            continue
        mean_prev_idx = max(0, j - phase_lb)
        slope_atr = (mean_now - means[mean_prev_idx]) / atr
        max_slope = float(cfg["MAX_MEAN_SLOPE_ATR"])
        if cfg["SLOPE_FILTER"] == "mean_flat" and abs(slope_atr) > max_slope:
            continue
        if cfg["SLOPE_FILTER"] == "counter_slope":
            if sig == "BUY" and slope_atr < -max_slope:
                continue
            if sig == "SELL" and slope_atr > max_slope:
                continue
        htf_ctx = s30sim.htf_lookup(htf_series, int(entry_bar["time"])) if conf_type != "none" else None
        if conf_type == "htf_trend":
            if htf_ctx is None:
                continue
            if sig == "BUY" and not htf_ctx.get("trend_down", False):
                continue
            if sig == "SELL" and not htf_ctx.get("trend_up", False):
                continue
        last_fire_idx = j

        cur = bars[j]
        entry = round(closes[j], 2)
        sl_buf = float(cfg["SL_ATR_MULT"]) * atr
        if sig == "BUY":
            sl = round(min(float(cur["low"]), entry) - sl_buf, 2)
            tp = round(mean_now, 2) if cfg["TP_MODE"] == "mean" else round(entry + float(cfg["TP_RR"]) * (entry - sl), 2)
            risk = entry - sl
            if not (0 < risk <= float(cfg["MAX_RISK_ATR_MULT"]) * atr and tp > entry):
                continue
        else:
            sl = round(max(float(cur["high"]), entry) + sl_buf, 2)
            tp = round(mean_now, 2) if cfg["TP_MODE"] == "mean" else round(entry - float(cfg["TP_RR"]) * (sl - entry), 2)
            risk = sl - entry
            if not (0 < risk <= float(cfg["MAX_RISK_ATR_MULT"]) * atr and tp < entry):
                continue
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
    return replay61(entry_bars, htf_series, spread, cfg)


def run_backtest(cfg, days, spread, label, verbose=True):
    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return None
    entry_bars = s30sim.fetch_bars(config.SYMBOL, cfg["ENTRY_TF"], days, extra_bars=300)
    htf_bars = s30sim.fetch_bars(config.SYMBOL, cfg["HTF_TF"], days,
                                  extra_bars=max(int(cfg["HTF_EMA_PERIOD"]), 28) + 60) if cfg["CONFIRMATION_TYPE"] != "none" else None
    mt5.shutdown()
    if entry_bars is None:
        print("! fetch entry bars fail")
        return None
    raw = run_single(entry_bars, htf_bars, cfg, days, spread)
    twp, eq = s31sim.simulate_equity_substream(raw, cfg, START_EQUITY)
    s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days) if twp else {
        "trades": 0, "wr": 0.0, "avg_per_day_span": 0.0, "max_dd_pct": 0.0,
        "profit_factor": 0.0, "final_equity": START_EQUITY,
    }
    fs = _fixed_lot_stats(raw, days, spread)
    if verbose:
        print(f"signals={len(raw)} comp $/d={s['avg_per_day_span']:.2f} PF={s['profit_factor']:.2f} "
              f"DD={s['max_dd_pct']:.1f}% | fixed $/d={fs['fixed_per_day']:.2f} "
              f"PF={fs['fixed_pf']:.2f} sharpe={fs['sharpe_like']:.3f} "
              f"maxStreak={fs['max_losing_day_streak']}d")
    row = dict(s); row.update(fs)
    append_summary_csv(label, row, cfg)
    return row


def append_summary_csv(label, s, cfg):
    path = os.path.join(os.path.dirname(__file__), "s61_backtest_summary.csv")
    is_new = not os.path.exists(path)
    fields = ["timestamp", "label", "mean_type", "mean_period", "dev_type", "dev_period",
              "band_mult", "entry_z", "phase_lookback", "slope_filter", "sl_atr_mult",
              "tp_mode", "tp_rr", "confirmation_type", "trades", "wr", "avg_per_day_span",
              "max_dd_pct", "profit_factor", "fixed_per_day", "fixed_per_month", "fixed_pf",
              "fixed_avg", "pct_pos_days", "max_losing_day_streak", "sharpe_like"]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        w.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "label": label,
            "mean_type": cfg["MEAN_TYPE"], "mean_period": cfg["MEAN_PERIOD"],
            "dev_type": cfg["DEV_TYPE"], "dev_period": cfg["DEV_PERIOD"],
            "band_mult": cfg["BAND_MULT"], "entry_z": cfg["ENTRY_Z"],
            "phase_lookback": cfg["PHASE_LOOKBACK"], "slope_filter": cfg["SLOPE_FILTER"],
            "sl_atr_mult": cfg["SL_ATR_MULT"], "tp_mode": cfg["TP_MODE"], "tp_rr": cfg["TP_RR"],
            "confirmation_type": cfg["CONFIRMATION_TYPE"], "trades": s["trades"], "wr": s["wr"],
            "avg_per_day_span": s["avg_per_day_span"], "max_dd_pct": s["max_dd_pct"],
            "profit_factor": s["profit_factor"], "fixed_per_day": s["fixed_per_day"],
            "fixed_per_month": s["fixed_per_month"], "fixed_pf": s["fixed_pf"],
            "fixed_avg": s["fixed_avg"], "pct_pos_days": s["pct_pos_days"],
            "max_losing_day_streak": s["max_losing_day_streak"], "sharpe_like": s["sharpe_like"],
        })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--meanperiod", type=int)
    ap.add_argument("--devtype")
    ap.add_argument("--devperiod", type=int)
    ap.add_argument("--entryz", type=float)
    ap.add_argument("--phase", type=int)
    ap.add_argument("--slopefilter")
    ap.add_argument("--slmult", type=float)
    ap.add_argument("--tpmode")
    ap.add_argument("--rr", type=float)
    args = ap.parse_args()
    cfg = dict(S61_DEFAULTS)
    if args.meanperiod is not None:
        cfg["MEAN_PERIOD"] = args.meanperiod
    if args.devtype is not None:
        cfg["DEV_TYPE"] = args.devtype
    if args.devperiod is not None:
        cfg["DEV_PERIOD"] = args.devperiod
    if args.entryz is not None:
        cfg["ENTRY_Z"] = args.entryz
    if args.phase is not None:
        cfg["PHASE_LOOKBACK"] = args.phase
    if args.slopefilter is not None:
        cfg["SLOPE_FILTER"] = args.slopefilter
    if args.slmult is not None:
        cfg["SL_ATR_MULT"] = args.slmult
    if args.tpmode is not None:
        cfg["TP_MODE"] = args.tpmode
    if args.rr is not None:
        cfg["TP_RR"] = args.rr
    print(f"S61 backtest | days={args.days} mean={cfg['MEAN_PERIOD']} dev={cfg['DEV_TYPE']}:{cfg['DEV_PERIOD']} "
          f"z={cfg['ENTRY_Z']} phase={cfg['PHASE_LOOKBACK']} slope={cfg['SLOPE_FILTER']} "
          f"sl={cfg['SL_ATR_MULT']} tp={cfg['TP_MODE']} rr={cfg['TP_RR']}")
    run_backtest(cfg, args.days, DEFAULT_SPREAD, args.label)


if __name__ == "__main__":
    main()
