"""
sim_s28_backtest.py — Backtest S28 (Asian Range Liquidity Sweep) จาก MT5 จริง
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ RESEARCH / BACKTEST-ONLY — strategy28.py ไม่ถูก wire เข้า scanner.py/trailing.py/
   main.py ใดๆ ทั้งสิ้น ไฟล์นี้ไม่แก้ S1-S27, ไม่แก้ bot_state.json, ไม่แตะ live trading

กัน look-ahead bias:
  - แท่งกำลังวิ่งใช้เฉพาะ open (close=open ของแท่งถัดไป)
  - Entry เป็น MARKET ที่ open ของแท่งถัดจากแท่ง signal
  - Asian range ใช้เฉพาะแท่งที่ปิดแล้วในช่วง Asian session
  - แท่งเดียวกันแตะทั้ง TP/SL นับ SL (conservative)

ตัวอย่าง:
  python sim_s28_backtest.py --days 30
  python sim_s28_backtest.py --days 60 --risk 3 --rr 1.5 --csv
"""

import argparse
import csv
import os
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5

import config
from strategy28 import S28_DEFAULTS, detect_s28, detect_sweep, calc_atr, _cfg

SYMBOL = config.SYMBOL
DEFAULT_SPREAD = 0.20
START_EQUITY = 1000.0
ASSUMED_LEVERAGE = 500.0
MAX_MARGIN_USAGE_PCT = 30.0
CONTRACT_OZ = 100.0
MIN_LOT = 0.01
LOT_STEP = 0.01

_TF_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
}
_PER_DAY = {"M1": 1440, "M5": 288, "M15": 96, "M30": 48, "H1": 24, "H4": 6}

BKK = timezone(timedelta(hours=7))


def to_bkk(ts):
    """Convert MT5 bar timestamp to Bangkok datetime"""
    return config.mt5_ts_to_bkk(int(ts))


def fetch_bars(symbol, tf_str, days, extra_bars=500):
    tf_val = _TF_MAP[tf_str]
    per_day = _PER_DAY[tf_str]
    count = min(days * per_day + extra_bars, 99000)
    rates = mt5.copy_rates_from_pos(symbol, tf_val, 0, count)
    if rates is None or len(rates) == 0:
        return None
    return rates


def _calc_atr_series(rates, period=14):
    """ATR series — index i ใช้เฉพาะ 0..i"""
    n = len(rates)
    trs = [0.0] * n
    for i in range(n):
        h = float(rates[i]["high"]); l = float(rates[i]["low"])
        if i == 0:
            trs[i] = h - l
        else:
            pc = float(rates[i - 1]["close"])
            trs[i] = max(h - l, abs(h - pc), abs(l - pc))
    out = [0.0] * n
    if n < period:
        run = 0.0
        for i in range(n):
            run += trs[i]
            out[i] = run / (i + 1)
        return out
    atr = sum(trs[:period]) / period
    for i in range(period):
        out[i] = atr
    for i in range(period, n):
        atr = (atr * (period - 1) + trs[i]) / period
        out[i] = atr
    return out


def _build_daily_asian_ranges(bars, cfg):
    """
    Pre-build Asian range (H/L) ของแต่ละวันจากข้อมูล M1/M5
    Returns: dict keyed by date string -> {"high": float, "low": float}
    """
    asian_start_h = int(_cfg(cfg, "ASIAN_START_H"))
    asian_start_m = int(_cfg(cfg, "ASIAN_START_M"))
    asian_end_h = int(_cfg(cfg, "ASIAN_END_H"))
    asian_end_m = int(_cfg(cfg, "ASIAN_END_M"))

    asian_start_min = asian_start_h * 60 + asian_start_m
    asian_end_min = asian_end_h * 60 + asian_end_m

    ranges = {}
    for bar in bars:
        dt = to_bkk(int(bar["time"]))
        if dt is None:
def _ema_series(closes, period):
    """EMA series (no lookahead — each index uses 0..i only)"""
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


def replay(bars, spread, cfg):
    """
    Replay M1/M5 bars, detect Asian range sweep signals, simulate trades
    """
    atr_period = int(_cfg(cfg, "ATR_PERIOD"))
    max_trades_per_day = int(_cfg(cfg, "MAX_TRADES_PER_DAY"))
    min_gap = int(_cfg(cfg, "MIN_GAP_BARS"))
    use_ema_filter = bool(_cfg(cfg, "EMA_TREND_FILTER"))
    ema_period = int(_cfg(cfg, "EMA_TREND_PERIOD"))
    use_sl_cooldown = bool(_cfg(cfg, "SL_COOLDOWN"))
    sl_cooldown_count = int(_cfg(cfg, "SL_COOLDOWN_COUNT"))
    sl_cooldown_bars = int(_cfg(cfg, "SL_COOLDOWN_BARS"))

    # Pre-build daily Asian ranges
    daily_ranges = _build_daily_asian_ranges(bars, cfg)

    # Pre-compute ATR series
    atr_series = _calc_atr_series(bars, atr_period)

    # Pre-compute EMA series (for trend filter)
    ema_series = None
    if use_ema_filter:
        closes = [float(b["close"]) for b in bars]
        ema_series = _ema_series(closes, ema_period)

    trades = []
    last_fire_idx = -100
    day_trade_counts = {}

    # SL cooldown state
    sl_consec = {"BUY": 0, "SELL": 0}
    sl_cooldown_until = {"BUY": -1, "SELL": -1}

    n = len(bars)
    warmup = max(atr_period + 5, ema_period + 5 if use_ema_filter else 30, 30)

    for j in range(warmup, n - 1):
        if j - last_fire_idx < min_gap:
            continue

        entry_bar = bars[j + 1]
        dt_bkk = to_bkk(int(entry_bar["time"]))
        if dt_bkk is None:
            continue

        day_key = dt_bkk.strftime("%Y-%m-%d")

        # Check max trades per day
        if day_trade_counts.get(day_key, 0) >= max_trades_per_day:
            continue

        # Get Asian range for today
        ar = daily_ranges.get(day_key)
        if ar is None:
            continue
        asian_high = ar["high"]
        asian_low = ar["low"]

        atr = atr_series[j]
        if atr <= 0:
            continue

        # Build window for detection
        win_start = max(0, j - 30)
        window = list(bars[win_start:j + 1])
        # Add live bar (only open known)
        live = {
            "time": int(entry_bar["time"]),
            "open": float(entry_bar["open"]),
            "high": float(entry_bar["open"]),
            "low": float(entry_bar["open"]),
            "close": float(entry_bar["open"]),
        }
        window.append(live)

        # RSI closes for optional filter
        rsi_closes = [float(bars[k]["close"]) for k in range(max(0, j - 30), j + 1)]

        # Volume data for optional filter
        volumes = None
        avg_volume = None
        if bool(_cfg(cfg, "VOLUME_FILTER")):
            vols = []
            for k in range(max(0, j - 30), j + 1):
                v = float(bars[k].get("tick_volume", bars[k].get("real_volume", 0)))
                vols.append(v)
            volumes = vols
            avg_volume = sum(vols) / len(vols) if vols else 0

        # EMA value for trend filter
        ema_val = ema_series[j] if ema_series is not None and j < len(ema_series) else None

        res = detect_s28(
            window, asian_high, asian_low,
            ar.get("range_atr", 0), atr,
            dt_bkk=dt_bkk, cfg=cfg,
            rsi_closes=rsi_closes,
            volumes=volumes, avg_volume=avg_volume,
            ema_value=ema_val
        )

        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue

        last_fire_idx = j
        day_trade_counts[day_key] = day_trade_counts.get(day_key, 0) + 1

        entry = float(res["entry"])
        tp = float(res["tp"])
        sl = float(res["sl"])
        fill_idx = j + 1
        outcome, exit_price, exit_idx = "OPEN", None, None

        for m in range(fill_idx, n):
            hi = float(bars[m]["high"])
            lw = float(bars[m]["low"])
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
            "signal_time_ts": int(bars[j]["time"]),
            "fill_time_ts": int(bars[fill_idx]["time"]),
            "exit_time_ts": int(bars[exit_idx]["time"]),
            "entry": round(entry, 2), "tp": round(tp, 2), "sl": round(sl, 2),
            "exit_price": round(exit_price, 2),
            "risk_distance": round(risk_distance, 4),
            "diff_usd_per_001lot": round(diff, 4),
            "spread": spread,
            "asian_high": round(asian_high, 2),
            "asian_low": round(asian_low, 2),
        })

    return trades


def simulate_equity(all_trades, risk_pct):
    ordered = sorted(all_trades, key=lambda t: t["fill_time_ts"])
    equity = START_EQUITY
    peak = equity
    max_dd_usd = 0.0
    max_dd_pct = 0.0
    out = []
    lots_used = []
    for t in ordered:
        risk_usd = equity * risk_pct / 100.0
        risk_distance = t["risk_distance"]
        if risk_distance <= 0:
            continue
        lot_oz = risk_usd / risk_distance
        lot = round(lot_oz * 0.01 / LOT_STEP) * LOT_STEP
        lot = max(MIN_LOT, lot)

        approx_price = t["entry"]
        max_margin_usd = equity * MAX_MARGIN_USAGE_PCT / 100.0
        max_lot_by_margin = (max_margin_usd * ASSUMED_LEVERAGE) / (CONTRACT_OZ * approx_price)
        max_lot_by_margin = max(MIN_LOT, round(max_lot_by_margin / LOT_STEP) * LOT_STEP)
        if lot > max_lot_by_margin:
            lot = max_lot_by_margin

        lot_001_units = lot / 0.01
        pnl = (t["diff_usd_per_001lot"] - t["spread"]) * lot_001_units
        equity += pnl
        peak = max(peak, equity)
        dd_usd = peak - equity
        dd_pct = (dd_usd / peak * 100.0) if peak > 0 else 0.0
        max_dd_usd = max(max_dd_usd, dd_usd)
        max_dd_pct = max(max_dd_pct, dd_pct)
        lots_used.append(lot)

        row = dict(t)
        row["lot"] = lot
        row["risk_usd"] = round(risk_usd, 2)
        row["pnl_usd"] = round(pnl, 2)
        row["equity_after"] = round(equity, 2)
        out.append(row)

    return out, {
        "final_equity": round(equity, 2),
        "max_dd_usd": round(max_dd_usd, 2),
        "max_dd_pct": round(max_dd_pct, 2),
        "lot_min": round(min(lots_used), 2) if lots_used else 0.0,
        "lot_max": round(max(lots_used), 2) if lots_used else 0.0,
    }


def daily_pnl(trades_with_pnl):
    by_day = {}
    for t in trades_with_pnl:
        day = to_bkk(t["exit_time_ts"]).strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, 0.0) + t["pnl_usd"]
    return by_day


def summarize(trades_with_pnl, equity_stats, risk_pct, days):
    if not trades_with_pnl:
        return None
    wins = [t for t in trades_with_pnl if t["pnl_usd"] > 0]
    losses = [t for t in trades_with_pnl if t["pnl_usd"] <= 0]
    total_pnl = sum(t["pnl_usd"] for t in trades_with_pnl)
    by_day = daily_pnl(trades_with_pnl)
    n_days_with_trades = len(by_day)
    span_days = max(days, 1)
    avg_per_day_all_span = total_pnl / span_days
    avg_per_day_active = (total_pnl / n_days_with_trades) if n_days_with_trades else 0.0
    trades_per_active_day = (len(trades_with_pnl) / n_days_with_trades) if n_days_with_trades else 0.0
    days_hit_1000 = sum(1 for v in by_day.values() if v >= 1000.0)
    max_consec_loss = consec = 0
    for t in trades_with_pnl:
        consec = consec + 1 if t["pnl_usd"] <= 0 else 0
        max_consec_loss = max(max_consec_loss, consec)

    r_multiples = [t["pnl_usd"] / t["risk_usd"] for t in trades_with_pnl if t.get("risk_usd")]
    avg_r = round(sum(r_multiples) / len(r_multiples), 3) if r_multiples else 0.0

    pf_gain = sum(t["pnl_usd"] for t in wins) if wins else 0.0
    pf_loss = abs(sum(t["pnl_usd"] for t in losses)) if losses else 0.0
    profit_factor = round(pf_gain / pf_loss, 2) if pf_loss > 0 else (round(pf_gain, 2) if pf_gain > 0 else 0.0)

    return {
        "trades": len(trades_with_pnl),
        "wins": len(wins),
        "losses": len(losses),
        "wr": round(100.0 * len(wins) / len(trades_with_pnl), 1),
        "total_pnl": round(total_pnl, 2),
        "avg_per_day_span": round(avg_per_day_all_span, 2),
        "avg_per_day_active": round(avg_per_day_active, 2),
        "trades_per_active_day": round(trades_per_active_day, 1),
        "n_days_with_trades": n_days_with_trades,
        "span_days": span_days,
        "days_hit_1000": days_hit_1000,
        "max_consec_loss": max_consec_loss,
        "risk_pct": risk_pct,
        "avg_r_multiple": avg_r,
        "profit_factor": profit_factor,
        **equity_stats,
    }


def fmt_summary(s):
    if s is None:
        return "no trades"
    return (
        f"n={s['trades']:>5} WR={s['wr']:>5.1f}% | total P/L=${s['total_pnl']:>9.2f} | "
        f"avg/day(span {s['span_days']}d)=${s['avg_per_day_span']:>8.2f} | "
        f"trades/day(active)={s['trades_per_active_day']:>6.1f} | "
        f"days>=$1000: {s['days_hit_1000']}/{s['n_days_with_trades']} | "
        f"maxDD=${s['max_dd_usd']:>8.2f} ({s['max_dd_pct']:.1f}%) | "
        f"lot={s['lot_min']}-{s['lot_max']} | risk={s['risk_pct']}% | "
        f"avgR={s['avg_r_multiple']:.3f} | PF={s['profit_factor']:.2f} | "
        f"final_equity=${s['final_equity']:.2f} | maxLossStreak={s['max_consec_loss']}"
    )


def append_summary_csv(label, s, cfg, risk_pct):
    path = os.path.join(os.path.dirname(__file__), "s28_backtest_summary.csv")
    is_new = not os.path.exists(path)
    fields = [
        "timestamp", "label", "entry_tf", "trades", "wr",
        "total_pnl", "avg_per_day_span", "avg_per_day_active", "trades_per_active_day",
        "n_days_with_trades", "span_days", "days_hit_1000", "max_dd_usd", "max_dd_pct",
        "lot_min", "lot_max", "risk_pct", "final_equity", "max_consec_loss",
        "avg_r_multiple", "profit_factor",
        "sweep_min_atr", "sweep_max_atr", "body_rev_pct", "sl_atr_mult", "tp_rr",
        "min_range_atr", "max_range_atr", "max_trades_per_day",
        "rsi_filter", "momentum_filter", "volume_filter", "atr_regime_filter",
    ]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        row = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "label": label,
            "entry_tf": cfg.get("ENTRY_TF", "M5"),
            **{k: s[k] for k in (
                "trades", "wr", "total_pnl", "avg_per_day_span", "avg_per_day_active",
                "trades_per_active_day", "n_days_with_trades", "span_days", "days_hit_1000",
                "max_dd_usd", "max_dd_pct", "lot_min", "lot_max", "risk_pct", "final_equity",
                "max_consec_loss", "avg_r_multiple", "profit_factor",
            )},
            "sweep_min_atr": cfg.get("SWEEP_MIN_ATR", S28_DEFAULTS["SWEEP_MIN_ATR"]),
            "sweep_max_atr": cfg.get("SWEEP_MAX_ATR", S28_DEFAULTS["SWEEP_MAX_ATR"]),
            "body_rev_pct": cfg.get("BODY_REVERSAL_PCT", S28_DEFAULTS["BODY_REVERSAL_PCT"]),
            "sl_atr_mult": cfg.get("SL_ATR_MULT", S28_DEFAULTS["SL_ATR_MULT"]),
            "tp_rr": cfg.get("TP_RR", S28_DEFAULTS["TP_RR"]),
            "min_range_atr": cfg.get("MIN_RANGE_ATR", S28_DEFAULTS["MIN_RANGE_ATR"]),
            "max_range_atr": cfg.get("MAX_RANGE_ATR", S28_DEFAULTS["MAX_RANGE_ATR"]),
            "max_trades_per_day": cfg.get("MAX_TRADES_PER_DAY", S28_DEFAULTS["MAX_TRADES_PER_DAY"]),
            "rsi_filter": cfg.get("RSI_FILTER", False),
            "momentum_filter": cfg.get("MOMENTUM_FILTER", False),
            "volume_filter": cfg.get("VOLUME_FILTER", False),
            "atr_regime_filter": cfg.get("ATR_REGIME_FILTER", False),
        }
        w.writerow(row)
    print(f"  -> appended to {path}")


def run_backtest(cfg, days, spread, label, entry_tf="M5", save_csv=False, verbose=True,
                 mt5_already_init=False):
    if not mt5_already_init and not mt5.initialize():
        print(f"MT5 initialize failed: {mt5.last_error()}")
        return None

    symbol = config.SYMBOL
    cfg["ENTRY_TF"] = entry_tf

    bars = fetch_bars(symbol, entry_tf, days, extra_bars=max(500, 1500))
    if bars is None:
        if verbose:
            print("! Cannot fetch bars")
        return None

    if verbose:
        t0 = to_bkk(int(bars[0]["time"])).strftime("%Y-%m-%d %H:%M")
        t1 = to_bkk(int(bars[-1]["time"])).strftime("%Y-%m-%d %H:%M")
        print(f"  {entry_tf}: {len(bars)} bars ({t0} -> {t1} BKK)")

    raw = replay(bars, spread, cfg)
    if verbose:
        print(f"    signals(resolved): {len(raw)}")

    trades_with_pnl, equity_stats = simulate_equity(raw, cfg["RISK_PCT"])
    s = summarize(trades_with_pnl, equity_stats, cfg["RISK_PCT"], days)
    if verbose:
        print("-" * 120)
        print(fmt_summary(s) if s else "no trades")

    if s:
        append_summary_csv(label, s, cfg, cfg["RISK_PCT"])

    if save_csv and trades_with_pnl:
        out_dir = os.path.join("excel_reports", "backtest_compare", "s28")
        os.makedirs(out_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        path = os.path.join(out_dir, f"sim_s28_{label}_{stamp}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(trades_with_pnl[0].keys()))
            w.writeheader()
            w.writerows(trades_with_pnl)
        if verbose:
            print(f"CSV: {path}")

    if not mt5_already_init:
        mt5.shutdown()

    return s, trades_with_pnl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--spread", type=float, default=DEFAULT_SPREAD)
    ap.add_argument("--risk", type=float, default=S28_DEFAULTS["RISK_PCT"])
    ap.add_argument("--tf", default="M5", choices=["M1", "M5", "M15"])
    ap.add_argument("--rr", type=float, default=None)
    ap.add_argument("--slmult", type=float, default=None)
    ap.add_argument("--sweepmin", type=float, default=None)
    ap.add_argument("--sweepmax", type=float, default=None)
    ap.add_argument("--bodyrev", type=float, default=None)
    ap.add_argument("--maxday", type=int, default=None)
    ap.add_argument("--rsi", action="store_true")
    ap.add_argument("--momentum", action="store_true")
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--csv", action="store_true")
    args = ap.parse_args()

    cfg = dict(S28_DEFAULTS)
    cfg["RISK_PCT"] = args.risk
    if args.rr is not None:
        cfg["TP_RR"] = args.rr
    if args.slmult is not None:
        cfg["SL_ATR_MULT"] = args.slmult
    if args.sweepmin is not None:
        cfg["SWEEP_MIN_ATR"] = args.sweepmin
    if args.sweepmax is not None:
        cfg["SWEEP_MAX_ATR"] = args.sweepmax
    if args.bodyrev is not None:
        cfg["BODY_REVERSAL_PCT"] = args.bodyrev
    if args.maxday is not None:
        cfg["MAX_TRADES_PER_DAY"] = args.maxday
    if args.rsi:
        cfg["RSI_FILTER"] = True
    if args.momentum:
        cfg["MOMENTUM_FILTER"] = True

    print(f"S28 backtest | Symbol={config.SYMBOL} | days={args.days} | spread=${args.spread:.2f} | "
          f"risk={cfg['RISK_PCT']}%/trade | tf={args.tf} | start_equity=${START_EQUITY:.0f}")
    print(f"cfg: sweep_min={cfg['SWEEP_MIN_ATR']} sweep_max={cfg['SWEEP_MAX_ATR']} "
          f"body_rev={cfg['BODY_REVERSAL_PCT']} sl_mult={cfg['SL_ATR_MULT']} rr={cfg['TP_RR']} "
          f"max_trades/day={cfg['MAX_TRADES_PER_DAY']} rsi={cfg['RSI_FILTER']} mom={cfg['MOMENTUM_FILTER']}")

    run_backtest(cfg, args.days, args.spread, args.label, entry_tf=args.tf, save_csv=args.csv)


if __name__ == "__main__":
    main()
