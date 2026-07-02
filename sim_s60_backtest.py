"""
sim_s60_backtest.py — Backtest S60 Asian Range Sweep Reversal
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ RESEARCH / BACKTEST-ONLY — ไม่แก้ S1-S59, ไม่ wire เข้า live
"""

import argparse
import csv
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy60 import S60_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim

START_EQUITY = 1000.0
DEFAULT_SPREAD = 0.20


def _cfg_get(cfg, key):
    return cfg[key] if (cfg and key in cfg) else S60_DEFAULTS[key]


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


def _parse_time(s):
    from datetime import time
    h, m = map(int, s.split(":"))
    return time(h, m)


def _in_trade_session(dt_bkk, cfg):
    cur = dt_bkk.time()
    for start_str, end_str in _cfg_get(cfg, "TRADE_SESSIONS"):
        if _parse_time(start_str) <= cur < _parse_time(end_str):
            return True
    return False


def _atr_series(bars, period=14):
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


def _precompute_asian_ranges(bars, all_dt, cfg):
    start_t = _parse_time(_cfg_get(cfg, "ASIA_START"))
    end_t = _parse_time(_cfg_get(cfg, "ASIA_END"))
    grouped = {}
    for b, dt in zip(bars, all_dt):
        if start_t <= dt.time() <= end_t:
            d = dt.date()
            hi, lo, n = grouped.get(d, (None, None, 0))
            bh = float(b["high"]); bl = float(b["low"])
            grouped[d] = (bh if hi is None else max(hi, bh),
                          bl if lo is None else min(lo, bl),
                          n + 1)
    return {d: (hi, lo) for d, (hi, lo, n) in grouped.items() if n >= 12}


def replay60(bars, htf_series, spread, cfg):
    conf_type = cfg["CONFIRMATION_TYPE"]
    min_gap_bars = int(_cfg_get(cfg, "MIN_GAP_BARS"))
    win_size = 320

    trades = []
    last_fire_idx = -10
    fired_day_side = set()
    all_dt = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
    atrs = _atr_series(bars, 14)
    asia_ranges = _precompute_asian_ranges(bars, all_dt, cfg)
    n = len(bars)
    start_j = win_size + 5
    for j in range(start_j, n - 1):
        if j - last_fire_idx < min_gap_bars:
            continue
        entry_bar = bars[j + 1]
        dt_bkk = all_dt[j + 1]
        cur_dt = all_dt[j]
        if not _in_trade_session(dt_bkk, cfg):
            continue
        ar = asia_ranges.get(cur_dt.date())
        if ar is None:
            continue
        asia_high, asia_low = ar
        atr = atrs[j]
        if not atr or atr <= 0:
            continue
        range_size = asia_high - asia_low
        if range_size < float(_cfg_get(cfg, "MIN_RANGE_ATR")) * atr:
            continue
        if range_size > float(_cfg_get(cfg, "MAX_RANGE_ATR")) * atr:
            continue

        cur = bars[j]
        co = float(cur["open"]); ch = float(cur["high"]); cl = float(cur["low"]); cc = float(cur["close"])
        sweep_buf = float(_cfg_get(cfg, "SWEEP_ATR_MULT")) * atr
        reject_buf = float(_cfg_get(cfg, "REJECT_ATR_MULT")) * atr
        body_min = float(_cfg_get(cfg, "BODY_ATR_MULT")) * atr

        mode = _cfg_get(cfg, "MODE")
        sig = None
        sweep_extreme = None
        if mode == "breakout":
            if cc >= asia_high + reject_buf and (cc - co) >= body_min:
                sig = "BUY"; sweep_extreme = cl
            elif cc <= asia_low - reject_buf and (co - cc) >= body_min:
                sig = "SELL"; sweep_extreme = ch
        elif ch >= asia_high + sweep_buf and cc <= asia_high - reject_buf and (co - cc) >= body_min:
            sig = "SELL"; sweep_extreme = ch
        elif cl <= asia_low - sweep_buf and cc >= asia_low + reject_buf and (cc - co) >= body_min:
            sig = "BUY"; sweep_extreme = cl
        if sig is None:
            continue

        htf_ctx = s30sim.htf_lookup(htf_series, int(entry_bar["time"])) if conf_type != "none" else None
        if conf_type == "htf_trend":
            if htf_ctx is None:
                continue
            adx_min = float(_cfg_get(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                continue
            if sig == "BUY" and not htf_ctx.get("trend_down", False):
                continue
            if sig == "SELL" and not htf_ctx.get("trend_up", False):
                continue

        day_side = (dt_bkk.strftime("%Y-%m-%d"), sig)
        if _cfg_get(cfg, "ONE_TRADE_PER_DAY_SIDE") and day_side in fired_day_side:
            continue
        fired_day_side.add(day_side)
        last_fire_idx = j

        entry = round(cc, 2)
        sl_buf = float(_cfg_get(cfg, "SL_ATR_MULT")) * atr
        if sig == "BUY":
            sl = round(sweep_extreme - sl_buf, 2)
        else:
            sl = round(sweep_extreme + sl_buf, 2)
        rr = float(_cfg_get(cfg, "TP_RR"))
        max_risk_mult = float(_cfg_get(cfg, "MAX_RISK_ATR_MULT"))
        if sig == "BUY":
            risk = entry - sl
            tp = round(entry + rr * risk, 2)
            if not (0 < risk <= max_risk_mult * atr and tp > entry):
                continue
        else:
            risk = sl - entry
            tp = round(entry - rr * risk, 2)
            if not (0 < risk <= max_risk_mult * atr and tp < entry):
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
    return replay60(entry_bars, htf_series, spread, cfg)


def run_backtest(cfg, days, spread, label, verbose=True):
    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return None
    entry_bars = s30sim.fetch_bars(config.SYMBOL, cfg["ENTRY_TF"], days, extra_bars=420)
    htf_bars = s30sim.fetch_bars(config.SYMBOL, cfg["HTF_TF"], days,
                                  extra_bars=max(int(cfg["HTF_EMA_PERIOD"]), 28) + 60) if cfg["CONFIRMATION_TYPE"] != "none" else None
    if entry_bars is None:
        print("! fetch entry bars fail"); mt5.shutdown(); return None
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
    row = dict(s)
    row.update(fs)
    append_summary_csv(label, row, cfg)
    mt5.shutdown()
    return row


def append_summary_csv(label, s, cfg):
    path = os.path.join(os.path.dirname(__file__), "s60_backtest_summary.csv")
    is_new = not os.path.exists(path)
    fields = ["timestamp", "label", "mode", "asia_start", "asia_end", "trade_sessions", "sweep_atr_mult",
              "reject_atr_mult", "min_range_atr", "max_range_atr", "body_atr_mult", "sl_atr_mult",
              "tp_rr", "confirmation_type", "risk_pct", "trades", "wr", "avg_per_day_span",
              "max_dd_pct", "profit_factor", "fixed_per_day", "fixed_per_month", "fixed_pf",
              "fixed_avg", "pct_pos_days", "max_losing_day_streak", "sharpe_like"]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        w.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "label": label,
            "mode": cfg["MODE"], "asia_start": cfg["ASIA_START"], "asia_end": cfg["ASIA_END"],
            "trade_sessions": cfg["TRADE_SESSIONS"], "sweep_atr_mult": cfg["SWEEP_ATR_MULT"],
            "reject_atr_mult": cfg["REJECT_ATR_MULT"], "min_range_atr": cfg["MIN_RANGE_ATR"],
            "max_range_atr": cfg["MAX_RANGE_ATR"], "body_atr_mult": cfg["BODY_ATR_MULT"],
            "sl_atr_mult": cfg["SL_ATR_MULT"], "tp_rr": cfg["TP_RR"],
            "confirmation_type": cfg["CONFIRMATION_TYPE"], "risk_pct": cfg["RISK_PCT"],
            "trades": s["trades"], "wr": s["wr"], "avg_per_day_span": s["avg_per_day_span"],
            "max_dd_pct": s["max_dd_pct"], "profit_factor": s["profit_factor"],
            "fixed_per_day": s["fixed_per_day"], "fixed_per_month": s["fixed_per_month"],
            "fixed_pf": s["fixed_pf"], "fixed_avg": s["fixed_avg"],
            "pct_pos_days": s["pct_pos_days"], "max_losing_day_streak": s["max_losing_day_streak"],
            "sharpe_like": s["sharpe_like"],
        })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--spread", type=float, default=DEFAULT_SPREAD)
    ap.add_argument("--risk", type=float, default=S60_DEFAULTS["RISK_PCT"])
    ap.add_argument("--sweep", type=float, default=None)
    ap.add_argument("--reject", type=float, default=None)
    ap.add_argument("--minrange", type=float, default=None)
    ap.add_argument("--maxrange", type=float, default=None)
    ap.add_argument("--body", type=float, default=None)
    ap.add_argument("--slmult", type=float, default=None)
    ap.add_argument("--rr", type=float, default=None)
    ap.add_argument("--conftype", default=None)
    ap.add_argument("--mode", choices=["reversal", "breakout"], default=None)
    ap.add_argument("--label", default="baseline")
    args = ap.parse_args()

    cfg = dict(S60_DEFAULTS)
    cfg["RISK_PCT"] = args.risk
    for arg_name, key in [("sweep", "SWEEP_ATR_MULT"), ("reject", "REJECT_ATR_MULT"),
                          ("minrange", "MIN_RANGE_ATR"), ("maxrange", "MAX_RANGE_ATR"),
                          ("body", "BODY_ATR_MULT"), ("slmult", "SL_ATR_MULT"), ("rr", "TP_RR")]:
        val = getattr(args, arg_name)
        if val is not None:
            cfg[key] = val
    if args.conftype is not None:
        cfg["CONFIRMATION_TYPE"] = args.conftype
    if args.mode is not None:
        cfg["MODE"] = args.mode
    print(f"S60 backtest | days={args.days} sweep={cfg['SWEEP_ATR_MULT']} reject={cfg['REJECT_ATR_MULT']} "
          f"range={cfg['MIN_RANGE_ATR']}-{cfg['MAX_RANGE_ATR']} body={cfg['BODY_ATR_MULT']} "
          f"sl={cfg['SL_ATR_MULT']} rr={cfg['TP_RR']} conf={cfg['CONFIRMATION_TYPE']}")
    run_backtest(cfg, args.days, args.spread, args.label)


if __name__ == "__main__":
    main()
