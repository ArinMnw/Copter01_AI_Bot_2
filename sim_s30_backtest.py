"""
sim_s30_backtest.py — Backtest S30 (frequency-optimized engulfing family + multi-TF)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ RESEARCH / BACKTEST-ONLY — strategy30.py ไม่ถูก wire เข้า scanner/trailing/main ใดๆ
   ไม่แก้ S1-S29, ไม่แก้ bot_state.json, ไม่แตะ live trading

กัน look-ahead bias 2 ชั้น เหมือน sim_s29 (entry-TF + ข้าม timeframe ด้วย bisect บนเวลาปิดแท่ง HTF)
ต่างจาก S29: MIN_GAP_BARS อ่านจาก cfg (S29 hardcode=2), ENTRY_TF M5/M1, เขียน s30_backtest_summary.csv

ตัวอย่าง:
  python sim_s30_backtest.py --days 90 --pattern family --entrytf M5 --label baseline --csv
"""

import argparse
import bisect
import csv
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy30 import S30_DEFAULTS, detect_s30

SYMBOL = config.SYMBOL
DEFAULT_SPREAD = 0.20
START_EQUITY = 1000.0
ASSUMED_LEVERAGE = 500.0
MAX_MARGIN_USAGE_PCT = 30.0
CONTRACT_OZ = 100.0
MIN_LOT = 0.01
LOT_STEP = 0.01

_TF_MAP = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
           "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}
_PER_DAY = {"M1": 1440, "M5": 288, "M15": 96, "M30": 48, "H1": 24, "H4": 6}
_TF_SECS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}


def fetch_bars(symbol, tf_str, days, extra_bars=400):
    per_day = _PER_DAY[tf_str]
    count = min(days * per_day + extra_bars, 95000)
    rates = mt5.copy_rates_from_pos(symbol, _TF_MAP[tf_str], 0, count)
    if rates is None or len(rates) == 0:
        return None
    return rates


def _ema_full(closes, period):
    n = len(closes)
    if n == 0:
        return []
    k = 2.0 / (period + 1.0)
    ema = closes[0]
    out = [ema]
    for i in range(1, n):
        ema = closes[i] * k + ema * (1.0 - k)
        out.append(ema)
    return out


def _adx_series(rates, period=14):
    n = len(rates)
    out = [0.0] * n
    if n < period * 2 + 1:
        return out
    highs = [float(r["high"]) for r in rates]
    lows = [float(r["low"]) for r in rates]
    closes = [float(r["close"]) for r in rates]
    plus_dm = [0.0] * n; minus_dm = [0.0] * n; tr = [0.0] * n
    for i in range(1, n):
        up = highs[i] - highs[i - 1]; down = lows[i - 1] - lows[i]
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))

    def _ws(vals):
        sm = [0.0] * n
        sm[period] = sum(vals[1:period + 1])
        for i in range(period + 1, n):
            sm[i] = sm[i - 1] - sm[i - 1] / period + vals[i]
        return sm

    tr_sm = _ws(tr); pdm_sm = _ws(plus_dm); mdm_sm = _ws(minus_dm)
    dx = [0.0] * n
    for i in range(period, n):
        if tr_sm[i] <= 0:
            continue
        pdi = 100.0 * pdm_sm[i] / tr_sm[i]; mdi = 100.0 * mdm_sm[i] / tr_sm[i]
        denom = pdi + mdi
        dx[i] = 100.0 * abs(pdi - mdi) / denom if denom > 0 else 0.0
    start = period * 2
    if start >= n:
        return out
    adx = sum(dx[period:start]) / period
    out[start] = adx
    for i in range(start + 1, n):
        adx = (adx * (period - 1) + dx[i]) / period
        out[i] = adx
    return out


def _cfg_get(cfg, key):
    return cfg[key] if (cfg and key in cfg) else S30_DEFAULTS[key]


def build_htf_series(htf_bars, cfg):
    closes = [float(r["close"]) for r in htf_bars]
    ema = _ema_full(closes, int(_cfg_get(cfg, "HTF_EMA_PERIOD")))
    adx = _adx_series(htf_bars, int(_cfg_get(cfg, "ADX_PERIOD")))
    close_times = [int(r["time"]) + _TF_SECS[_cfg_get(cfg, "HTF_TF")] for r in htf_bars]
    return {"close_times": close_times, "closes": closes, "ema": ema, "adx": adx,
            "slope_bars": int(_cfg_get(cfg, "HTF_SLOPE_BARS"))}


def htf_lookup(series, entry_time):
    ct = series["close_times"]
    idx = bisect.bisect_right(ct, entry_time) - 1
    if idx < 0:
        return None
    sb = series["slope_bars"]
    ema_now = series["ema"][idx]
    ema_prev = series["ema"][max(0, idx - sb)]
    return {"trend_up": ema_now > ema_prev, "trend_down": ema_now < ema_prev,
            "adx": series["adx"][idx], "price": series["closes"][idx], "idx": idx}


def replay(bars, htf_series, spread, cfg):
    ema_fast = int(cfg["EMA_FAST"])
    win_size = ema_fast + 40
    conf_type = cfg["CONFIRMATION_TYPE"]
    min_gap_bars = int(_cfg_get(cfg, "MIN_GAP_BARS"))

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
        htf_ctx = htf_lookup(htf_series, int(entry_bar["time"])) if conf_type != "none" else None

        res = detect_s30(window, tf=cfg["ENTRY_TF"], dt_bkk=dt_bkk, cfg=cfg, htf_ctx=htf_ctx)
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
            "signal": sig, "outcome": outcome,
            "signal_time_ts": int(entry_bar["time"]),
            "fill_time_ts": int(bars[fill_idx]["time"]),
            "exit_time_ts": int(bars[exit_idx]["time"]),
            "entry": round(entry, 2), "tp": round(tp, 2), "sl": round(sl, 2),
            "exit_price": round(exit_price, 2),
            "risk_distance": round(risk_distance, 4),
            "diff_usd_per_001lot": round(diff, 4), "spread": spread,
        })
    return trades


def simulate_equity_v2(all_trades, cfg):
    dd_control = cfg.get("DD_CONTROL", "none")
    base_risk_pct = float(cfg["RISK_PCT"])
    trigger = int(_cfg_get(cfg, "CONSEC_LOSS_TRIGGER"))
    reduced_risk_pct = float(_cfg_get(cfg, "REDUCED_RISK_PCT"))
    cooldown_trades = int(_cfg_get(cfg, "COOLDOWN_TRADES"))

    ordered = sorted(all_trades, key=lambda t: t["fill_time_ts"])
    equity = START_EQUITY; peak = equity
    max_dd_usd = 0.0; max_dd_pct = 0.0
    out = []; lots_used = []
    consec_loss = 0; cooldown_remaining = 0; skipped_by_cb = 0

    for t in ordered:
        if dd_control == "circuit_breaker" and cooldown_remaining > 0:
            cooldown_remaining -= 1; skipped_by_cb += 1
            continue
        risk_pct = base_risk_pct
        if dd_control == "dynamic_risk" and consec_loss >= trigger:
            risk_pct = reduced_risk_pct
        risk_usd = equity * risk_pct / 100.0
        risk_distance = t["risk_distance"]
        if risk_distance <= 0:
            continue
        lot = max(MIN_LOT, round((risk_usd / risk_distance) * 0.01 / LOT_STEP) * LOT_STEP)
        approx_price = t["entry"]
        max_margin_usd = equity * MAX_MARGIN_USAGE_PCT / 100.0
        max_lot_by_margin = max(MIN_LOT, round(((max_margin_usd * ASSUMED_LEVERAGE) /
                                                (CONTRACT_OZ * approx_price)) / LOT_STEP) * LOT_STEP)
        if lot > max_lot_by_margin:
            lot = max_lot_by_margin
        lot_001_units = lot / 0.01
        pnl = (t["diff_usd_per_001lot"] - t["spread"]) * lot_001_units
        equity += pnl; peak = max(peak, equity)
        dd_usd = peak - equity
        dd_pct = (dd_usd / peak * 100.0) if peak > 0 else 0.0
        max_dd_usd = max(max_dd_usd, dd_usd); max_dd_pct = max(max_dd_pct, dd_pct)
        lots_used.append(lot)
        if pnl <= 0:
            consec_loss += 1
            if dd_control == "circuit_breaker" and consec_loss >= trigger:
                cooldown_remaining = cooldown_trades; consec_loss = 0
        else:
            consec_loss = 0
        row = dict(t)
        row["lot"] = lot; row["risk_pct_used"] = round(risk_pct, 3)
        row["risk_usd"] = round(risk_usd, 2); row["pnl_usd"] = round(pnl, 2)
        row["equity_after"] = round(equity, 2)
        out.append(row)

    return out, {"final_equity": round(equity, 2), "max_dd_usd": round(max_dd_usd, 2),
                 "max_dd_pct": round(max_dd_pct, 2),
                 "lot_min": round(min(lots_used), 2) if lots_used else 0.0,
                 "lot_max": round(max(lots_used), 2) if lots_used else 0.0,
                 "skipped_by_circuit_breaker": skipped_by_cb}


def daily_pnl(trades_with_pnl):
    by_day = {}
    for t in trades_with_pnl:
        day = config.mt5_ts_to_bkk(t["exit_time_ts"]).strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, 0.0) + t["pnl_usd"]
    return by_day


def summarize(trades_with_pnl, equity_stats, risk_pct, days):
    if not trades_with_pnl:
        return None
    wins = [t for t in trades_with_pnl if t["pnl_usd"] > 0]
    losses = [t for t in trades_with_pnl if t["pnl_usd"] <= 0]
    total_pnl = sum(t["pnl_usd"] for t in trades_with_pnl)
    by_day = daily_pnl(trades_with_pnl)
    n_days = len(by_day); span_days = max(days, 1)
    avg_span = total_pnl / span_days
    avg_active = (total_pnl / n_days) if n_days else 0.0
    tpd = (len(trades_with_pnl) / n_days) if n_days else 0.0
    days_hit = sum(1 for v in by_day.values() if v >= 1000.0)
    mcl = consec = 0
    for t in trades_with_pnl:
        consec = consec + 1 if t["pnl_usd"] <= 0 else 0
        mcl = max(mcl, consec)
    rmult = [t["pnl_usd"] / t["risk_usd"] for t in trades_with_pnl if t.get("risk_usd")]
    avg_r = round(sum(rmult) / len(rmult), 3) if rmult else 0.0
    pf_gain = sum(t["pnl_usd"] for t in wins) if wins else 0.0
    pf_loss = abs(sum(t["pnl_usd"] for t in losses)) if losses else 0.0
    pf = round(pf_gain / pf_loss, 2) if pf_loss > 0 else (round(pf_gain, 2) if pf_gain > 0 else 0.0)
    return {"trades": len(trades_with_pnl), "wins": len(wins), "losses": len(losses),
            "wr": round(100.0 * len(wins) / len(trades_with_pnl), 1),
            "total_pnl": round(total_pnl, 2), "avg_per_day_span": round(avg_span, 2),
            "avg_per_day_active": round(avg_active, 2), "trades_per_active_day": round(tpd, 1),
            "n_days_with_trades": n_days, "span_days": span_days, "days_hit_1000": days_hit,
            "max_consec_loss": mcl, "risk_pct": risk_pct, "avg_r_multiple": avg_r,
            "profit_factor": pf, **equity_stats}


def fmt_summary(s):
    if s is None:
        return "no trades"
    return (f"n={s['trades']:>5} WR={s['wr']:>5.1f}% | total P/L=${s['total_pnl']:>9.2f} | "
            f"avg/day(span {s['span_days']}d)=${s['avg_per_day_span']:>8.2f} | "
            f"~/month=${s['avg_per_day_span']*30:>8.2f} | "
            f"trades/day(active)={s['trades_per_active_day']:>6.1f} | "
            f"maxDD=${s['max_dd_usd']:>8.2f} ({s['max_dd_pct']:.1f}%) | "
            f"risk={s['risk_pct']}% | avgR={s['avg_r_multiple']:.3f} | PF={s['profit_factor']:.2f} | "
            f"final=${s['final_equity']:.2f} | maxLossStreak={s['max_consec_loss']} | "
            f"cbSkipped={s.get('skipped_by_circuit_breaker', 0)}")


def append_summary_csv(label, s, cfg):
    path = os.path.join(os.path.dirname(__file__), "s30_backtest_summary.csv")
    is_new = not os.path.exists(path)
    fields = ["timestamp", "label", "entry_tf", "entry_pattern", "confirmation_type", "htf_tf",
              "dd_control", "min_gap_bars", "trades", "wr", "total_pnl", "avg_per_day_span",
              "avg_per_month", "avg_per_day_active", "trades_per_active_day", "n_days_with_trades",
              "span_days", "days_hit_1000", "max_dd_usd", "max_dd_pct", "lot_min", "lot_max",
              "risk_pct", "final_equity", "max_consec_loss", "avg_r_multiple", "profit_factor",
              "skipped_by_circuit_breaker", "ema_fast", "engulf_min_ratio", "strong_close_pct",
              "strong_body_atr", "sl_atr_mult", "tp_rr", "htf_ema_period", "consec_loss_trigger",
              "cooldown_trades", "sessions"]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        row = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "label": label,
               "entry_tf": cfg["ENTRY_TF"], "entry_pattern": cfg["ENTRY_PATTERN"],
               "confirmation_type": cfg["CONFIRMATION_TYPE"], "htf_tf": cfg["HTF_TF"],
               "dd_control": cfg["DD_CONTROL"], "min_gap_bars": cfg["MIN_GAP_BARS"],
               **{k: s[k] for k in ("trades", "wr", "total_pnl", "avg_per_day_span",
                  "avg_per_day_active", "trades_per_active_day", "n_days_with_trades", "span_days",
                  "days_hit_1000", "max_dd_usd", "max_dd_pct", "lot_min", "lot_max", "risk_pct",
                  "final_equity", "max_consec_loss", "avg_r_multiple", "profit_factor")},
               "avg_per_month": round(s["avg_per_day_span"] * 30, 2),
               "skipped_by_circuit_breaker": s.get("skipped_by_circuit_breaker", 0),
               "ema_fast": cfg["EMA_FAST"], "engulf_min_ratio": cfg["ENGULF_MIN_RATIO"],
               "strong_close_pct": cfg["STRONG_CLOSE_PCT"], "strong_body_atr": cfg["STRONG_BODY_ATR"],
               "sl_atr_mult": cfg["SL_ATR_MULT"], "tp_rr": cfg["TP_RR"],
               "htf_ema_period": cfg["HTF_EMA_PERIOD"], "consec_loss_trigger": cfg["CONSEC_LOSS_TRIGGER"],
               "cooldown_trades": cfg["COOLDOWN_TRADES"], "sessions": str(cfg["SESSIONS"])}
        w.writerow(row)
    print(f"  -> appended to {path}")


def run_backtest(cfg, days, spread, label, save_csv=False, verbose=True, mt5_already_init=False):
    if not mt5_already_init and not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return None
    symbol = config.SYMBOL
    entry_bars = fetch_bars(symbol, cfg["ENTRY_TF"], days, extra_bars=max(300, int(cfg["EMA_FAST"]) + 60))
    if entry_bars is None:
        if verbose:
            print("! ดึงข้อมูล entry TF ไม่ได้")
        return None
    htf_series = None
    if cfg["CONFIRMATION_TYPE"] != "none":
        htf_extra = max(int(cfg["HTF_EMA_PERIOD"]), int(cfg["ADX_PERIOD"]) * 2 + 5) + 60
        htf_bars = fetch_bars(symbol, cfg["HTF_TF"], days, extra_bars=htf_extra)
        if htf_bars is None:
            if verbose:
                print("! ดึงข้อมูล HTF ไม่ได้")
            return None
        htf_series = build_htf_series(htf_bars, cfg)
    if verbose:
        t0 = config.mt5_ts_to_bkk(int(entry_bars[0]["time"])).strftime("%Y-%m-%d %H:%M")
        t1 = config.mt5_ts_to_bkk(int(entry_bars[-1]["time"])).strftime("%Y-%m-%d %H:%M")
        print(f"  {cfg['ENTRY_TF']}: {len(entry_bars)} bars ({t0} -> {t1} BKK) | "
              f"pattern={cfg['ENTRY_PATTERN']} htf={cfg['HTF_TF']} dd={cfg['DD_CONTROL']} "
              f"min_gap={cfg['MIN_GAP_BARS']}")
    raw = replay(entry_bars, htf_series, spread, cfg)
    if verbose:
        print(f"    signals(after fill+SL/TP resolved): {len(raw)}")
    trades_with_pnl, equity_stats = simulate_equity_v2(raw, cfg)
    s = summarize(trades_with_pnl, equity_stats, cfg["RISK_PCT"], days)
    if verbose:
        print("-" * 130)
        print(fmt_summary(s) if s else "no trades")
    if s:
        append_summary_csv(label, s, cfg)
    if save_csv and trades_with_pnl:
        out_dir = os.path.join("excel_reports", "backtest_compare", "s30")
        os.makedirs(out_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        path = os.path.join(out_dir, f"sim_s30_{label}_{stamp}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(trades_with_pnl[0].keys()))
            w.writeheader(); w.writerows(trades_with_pnl)
        if verbose:
            print(f"CSV: {path}")
    if not mt5_already_init:
        mt5.shutdown()
    return s, trades_with_pnl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--spread", type=float, default=DEFAULT_SPREAD)
    ap.add_argument("--risk", type=float, default=None)
    ap.add_argument("--entrytf", default=None, choices=["M1", "M5"])
    ap.add_argument("--pattern", default=None, choices=["engulfing", "strong_close", "family"])
    ap.add_argument("--dd", default=None, choices=["none", "dynamic_risk", "circuit_breaker"])
    ap.add_argument("--engulfratio", type=float, default=None)
    ap.add_argument("--strongclose", type=float, default=None)
    ap.add_argument("--strongbody", type=float, default=None)
    ap.add_argument("--mingap", type=int, default=None)
    ap.add_argument("--slmult", type=float, default=None)
    ap.add_argument("--rr", type=float, default=None)
    ap.add_argument("--consecloss", type=int, default=None)
    ap.add_argument("--cooldown", type=int, default=None)
    ap.add_argument("--session", default=None, help="เช่น 14:00-23:00 หรือ 'all'")
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--csv", action="store_true")
    args = ap.parse_args()

    cfg = dict(S30_DEFAULTS)
    if args.risk is not None:
        cfg["RISK_PCT"] = args.risk
    if args.entrytf is not None:
        cfg["ENTRY_TF"] = args.entrytf
    if args.pattern is not None:
        cfg["ENTRY_PATTERN"] = args.pattern
    if args.dd is not None:
        cfg["DD_CONTROL"] = args.dd
    if args.engulfratio is not None:
        cfg["ENGULF_MIN_RATIO"] = args.engulfratio
    if args.strongclose is not None:
        cfg["STRONG_CLOSE_PCT"] = args.strongclose
    if args.strongbody is not None:
        cfg["STRONG_BODY_ATR"] = args.strongbody
    if args.mingap is not None:
        cfg["MIN_GAP_BARS"] = args.mingap
    if args.slmult is not None:
        cfg["SL_ATR_MULT"] = args.slmult
    if args.rr is not None:
        cfg["TP_RR"] = args.rr
    if args.consecloss is not None:
        cfg["CONSEC_LOSS_TRIGGER"] = args.consecloss
    if args.cooldown is not None:
        cfg["COOLDOWN_TRADES"] = args.cooldown
    if args.session is not None:
        if args.session.lower() == "all":
            cfg["SESSION_FILTER"] = False
        else:
            a, b = args.session.split("-")
            cfg["SESSIONS"] = [(a, b)]

    print(f"S30 backtest | Symbol={config.SYMBOL} | days={args.days} | spread=${args.spread:.2f} | "
          f"risk={cfg['RISK_PCT']}% | entry_tf={cfg['ENTRY_TF']} pattern={cfg['ENTRY_PATTERN']} "
          f"htf={cfg['HTF_TF']} dd={cfg['DD_CONTROL']} | start_equity=${START_EQUITY:.0f}")
    run_backtest(cfg, args.days, args.spread, args.label, save_csv=args.csv, verbose=True)


if __name__ == "__main__":
    main()
