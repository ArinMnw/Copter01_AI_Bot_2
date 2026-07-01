"""
sim_s25_backtest.py — Backtest S25 Liquidity Sweep Reversal จากข้อมูล MT5 จริง
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ RESEARCH / BACKTEST-ONLY — strategy25.py ไม่ถูก wire เข้า scanner.py/trailing.py/
   main.py ใดๆ ทั้งสิ้น ไฟล์นี้ไม่แก้ S1-S24, ไม่แก้ bot_state.json, ไม่แตะ live trading

เรียก strategy25.detect_s25() ตรง (pure function — logic เดียวกับที่จะใช้ถ้า wire จริง)

กัน look-ahead bias (เหมือน sim_s21-24_backtest.py):
  - แท่ง "กำลังวิ่ง" (rates[-1]) ใช้ close = open ของแท่งถัดจากแท่ง sweep
  - entry เป็น MARKET ที่ open ของแท่งถัดจากแท่ง sweep (แท่ง sweep ต้องปิดก่อนถึงรู้สัญญาณ)
  - แท่งเดียวกันแตะทั้ง TP และ SL → นับ SL (conservative)
  - spread หักจาก P/L ทุกไม้ (default 0.20 USD ต่อ "lot unit" 0.01)

Position sizing: เหมือน sim_s21-24 — risk-based, compounding equity ตามลำดับเวลา fill จริง

ตัวอย่าง:
  python sim_s25_backtest.py --days 60 --tf M5,M15
  python sim_s25_backtest.py --days 60 --tf M5 --risk 1.0 --rr 1.5 --csv
"""

import argparse
import csv
import os
from datetime import datetime, timezone

import MetaTrader5 as mt5

import config
from strategy25 import S25_DEFAULTS, detect_s25

SYMBOL = config.SYMBOL
SINCE = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
DEFAULT_SPREAD = 0.20
START_EQUITY = 1000.0
ASSUMED_LEVERAGE = 500.0
MAX_MARGIN_USAGE_PCT = 30.0
CONTRACT_OZ = 100.0
MIN_LOT = 0.01
LOT_STEP = 0.01

TF_MAP = {
    "M1":  (mt5.TIMEFRAME_M1, 1440),
    "M5":  (mt5.TIMEFRAME_M5, 288),
    "M15": (mt5.TIMEFRAME_M15, 96),
    "M30": (mt5.TIMEFRAME_M30, 48),
    "H1":  (mt5.TIMEFRAME_H1, 24),
    "H4":  (mt5.TIMEFRAME_H4, 6),
}


def fetch_bars(symbol, tf_name, days):
    tf_val, per_day = TF_MAP[tf_name]
    count = min(days * per_day + 300, 90000)
    rates = mt5.copy_rates_from_pos(symbol, tf_val, 0, count)
    if rates is None or len(rates) == 0:
        return None
    return rates


def replay_tf(bars, tf_name, spread, cfg):
    lookback = int(cfg["SWING_LOOKBACK"])
    ema_period = int(cfg["EMA_TREND"])
    slope_bars = int(cfg["EMA_SLOPE_BARS"])
    win_size = lookback + ema_period + slope_bars + 30

    trades = []
    sweep_fired = {}
    n = len(bars)
    start_j = lookback + ema_period + slope_bars + 5
    for j in range(start_j, n - 1):
        entry_bar = bars[j + 1]
        live = {
            "time":  int(entry_bar["time"]),
            "open":  float(entry_bar["open"]),
            "high":  float(entry_bar["open"]),
            "low":   float(entry_bar["open"]),
            "close": float(entry_bar["open"]),
        }
        lo = max(0, j + 1 - win_size)
        window = list(bars[lo:j + 1]) + [live]

        dt_bkk = config.mt5_ts_to_bkk(int(entry_bar["time"]))
        res = detect_s25(window, tf=tf_name, dt_bkk=dt_bkk, cfg=cfg)
        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue

        bar_time = int(res.get("sweep_bar_time", 0))
        lv_key = (sig, round(float(res.get("swing_level", 0.0)), 1))
        last_t = sweep_fired.get(lv_key, 0)
        if last_t and (bar_time - last_t) < 20 * _tf_secs(tf_name):
            continue
        sweep_fired[lv_key] = bar_time

        entry, tp, sl = float(res["entry"]), float(res["tp"]), float(res["sl"])
        fill_idx = j + 1  # market fill ทันทีที่ open ของแท่งถัดจากแท่ง sweep
        risk_dist0 = abs(entry - sl)
        be_after_r = float(cfg.get("BREAKEVEN_AFTER_R", 0.0))

        outcome, exit_price, exit_idx = "OPEN", None, None
        cur_sl = sl
        for m in range(fill_idx, n):
            hi, lw = float(bars[m]["high"]), float(bars[m]["low"])
            if sig == "BUY":
                if lw <= cur_sl:
                    outcome, exit_price = ("BE" if cur_sl != sl else "SL"), cur_sl
                elif hi >= tp:
                    outcome, exit_price = "TP", tp
                elif be_after_r > 0 and cur_sl != entry and hi >= entry + be_after_r * risk_dist0:
                    cur_sl = entry  # ขยับ SL มา breakeven หลังราคาวิ่งไปทาง favor >= be_after_r R
            else:
                if hi >= cur_sl:
                    outcome, exit_price = ("BE" if cur_sl != sl else "SL"), cur_sl
                elif lw <= tp:
                    outcome, exit_price = "TP", tp
                elif be_after_r > 0 and cur_sl != entry and lw <= entry - be_after_r * risk_dist0:
                    cur_sl = entry
            if outcome != "OPEN":
                exit_idx = m
                break
        if outcome == "OPEN":
            continue

        risk_distance = abs(entry - sl)
        diff = (exit_price - entry) if sig == "BUY" else (entry - exit_price)
        trades.append({
            "tf": tf_name, "signal": sig, "outcome": outcome,
            "sweep_time_ts": int(entry_bar["time"]),
            "fill_time_ts": int(bars[fill_idx]["time"]),
            "exit_time_ts": int(bars[exit_idx]["time"]),
            "entry": round(entry, 2), "tp": round(tp, 2), "sl": round(sl, 2),
            "exit_price": round(exit_price, 2),
            "risk_distance": round(risk_distance, 4),
            "diff_usd_per_001lot": round(diff, 4),
            "spread": spread,
            "rsi": res.get("rsi_at_signal", 0),
            "atr": res.get("atr_at_signal", 0),
        })
    return trades


def _tf_secs(tf_name):
    return {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}.get(tf_name, 60)


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
    n_days_with_trades = len(by_day)
    span_days = max(days, 1)
    avg_per_day_all_span = total_pnl / span_days
    avg_per_day_active = (total_pnl / n_days_with_trades) if n_days_with_trades else 0.0
    days_hit_1000 = sum(1 for v in by_day.values() if v >= 1000.0)
    max_consec_loss = consec = 0
    for t in trades_with_pnl:
        consec = consec + 1 if t["pnl_usd"] <= 0 else 0
        max_consec_loss = max(max_consec_loss, consec)

    # expectancy ต่อไม้ใน R-multiple (ไม่ขึ้นกับ risk% / lot — ตามกฎข้อ 3)
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
        f"n={s['trades']:>4} WR={s['wr']:>5.1f}% | total P/L=${s['total_pnl']:>9.2f} | "
        f"avg/day(span {s['span_days']}d)=${s['avg_per_day_span']:>8.2f} | "
        f"avg/day(active {s['n_days_with_trades']}d)=${s['avg_per_day_active']:>8.2f} | "
        f"days>=$1000: {s['days_hit_1000']}/{s['n_days_with_trades']} | "
        f"maxDD=${s['max_dd_usd']:>8.2f} ({s['max_dd_pct']:.1f}%) | "
        f"lot={s['lot_min']}-{s['lot_max']} | risk={s['risk_pct']}% | "
        f"avgR={s['avg_r_multiple']:.3f} | PF={s['profit_factor']:.2f} | "
        f"final_equity=${s['final_equity']:.2f} | maxLossStreak={s['max_consec_loss']}"
    )


def append_summary_csv(label, s, cfg, risk_pct):
    path = os.path.join(os.path.dirname(__file__), "s25_backtest_summary.csv")
    is_new = not os.path.exists(path)
    fields = [
        "timestamp", "label", "trades", "wr", "total_pnl",
        "avg_per_day_span", "avg_per_day_active", "n_days_with_trades", "span_days",
        "days_hit_1000", "max_dd_usd", "max_dd_pct", "lot_min", "lot_max",
        "risk_pct", "final_equity", "max_consec_loss", "avg_r_multiple", "profit_factor",
        "swing_lookback", "sweep_min_pierce_atr", "rejection_wick_pct",
        "rsi_overbought", "rsi_oversold", "sl_atr_mult", "tp_rr", "trend_filter",
    ]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        row = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "label": label,
            **{k: s[k] for k in (
                "trades", "wr", "total_pnl", "avg_per_day_span", "avg_per_day_active",
                "n_days_with_trades", "span_days", "days_hit_1000", "max_dd_usd",
                "max_dd_pct", "lot_min", "lot_max", "risk_pct", "final_equity",
                "max_consec_loss", "avg_r_multiple", "profit_factor",
            )},
            "swing_lookback": cfg["SWING_LOOKBACK"],
            "sweep_min_pierce_atr": cfg["SWEEP_MIN_PIERCE_ATR"],
            "rejection_wick_pct": cfg["REJECTION_WICK_PCT"],
            "rsi_overbought": cfg["RSI_OVERBOUGHT"],
            "rsi_oversold": cfg["RSI_OVERSOLD"],
            "sl_atr_mult": cfg["SL_ATR_MULT"],
            "tp_rr": cfg["TP_RR"],
            "trend_filter": cfg["TREND_FILTER"],
        }
        w.writerow(row)
    print(f"  -> appended to {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--tf", default="M5,M15")
    ap.add_argument("--spread", type=float, default=DEFAULT_SPREAD)
    ap.add_argument("--risk", type=float, default=S25_DEFAULTS["RISK_PCT"], help="risk %% per trade")
    ap.add_argument("--rr", type=float, default=None, help="override TP_RR")
    ap.add_argument("--slmult", type=float, default=None, help="override SL_ATR_MULT")
    ap.add_argument("--pierce", type=float, default=None, help="override SWEEP_MIN_PIERCE_ATR")
    ap.add_argument("--wick", type=float, default=None, help="override REJECTION_WICK_PCT")
    ap.add_argument("--lookback", type=int, default=None, help="override SWING_LOOKBACK")
    ap.add_argument("--rsiob", type=float, default=None, help="override RSI_OVERBOUGHT")
    ap.add_argument("--rsios", type=float, default=None, help="override RSI_OVERSOLD")
    ap.add_argument("--trend", default=None, choices=["none", "with", "against"], help="override TREND_FILTER")
    ap.add_argument("--nosession", action="store_true", help="ปิด session filter")
    ap.add_argument("--label", default="baseline", help="label สำหรับ s25_backtest_summary.csv")
    ap.add_argument("--csv", action="store_true", help="เซฟ trade-level CSV ด้วย")
    args = ap.parse_args()

    cfg = dict(S25_DEFAULTS)
    cfg["RISK_PCT"] = args.risk
    if args.rr is not None:
        cfg["TP_RR"] = args.rr
    if args.slmult is not None:
        cfg["SL_ATR_MULT"] = args.slmult
    if args.pierce is not None:
        cfg["SWEEP_MIN_PIERCE_ATR"] = args.pierce
    if args.wick is not None:
        cfg["REJECTION_WICK_PCT"] = args.wick
    if args.lookback is not None:
        cfg["SWING_LOOKBACK"] = args.lookback
    if args.rsiob is not None:
        cfg["RSI_OVERBOUGHT"] = args.rsiob
    if args.rsios is not None:
        cfg["RSI_OVERSOLD"] = args.rsios
    if args.trend is not None:
        cfg["TREND_FILTER"] = args.trend
    if args.nosession:
        cfg["SESSION_FILTER"] = False

    if not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return
    symbol = config.SYMBOL
    print(f"S25 backtest | Symbol={symbol} | days={args.days} | spread=${args.spread:.2f} | "
          f"risk={cfg['RISK_PCT']}%/trade | start_equity=${START_EQUITY:.0f}")
    print(f"cfg: lookback={cfg['SWING_LOOKBACK']} pierce={cfg['SWEEP_MIN_PIERCE_ATR']} "
          f"wick%={cfg['REJECTION_WICK_PCT']} RSI_ob={cfg['RSI_OVERBOUGHT']} RSI_os={cfg['RSI_OVERSOLD']} "
          f"RR={cfg['TP_RR']} SLmult={cfg['SL_ATR_MULT']} trend={cfg['TREND_FILTER']} "
          f"session_filter={cfg['SESSION_FILTER']}")

    tf_list = [t.strip() for t in args.tf.split(",") if t.strip() in TF_MAP]
    all_raw = []
    for tf_name in tf_list:
        bars = fetch_bars(symbol, tf_name, args.days)
        if bars is None:
            print(f"! {tf_name}: ดึงข้อมูลไม่ได้ - ข้าม")
            continue
        t0 = config.mt5_ts_to_bkk(int(bars[0]["time"])).strftime("%Y-%m-%d %H:%M")
        t1 = config.mt5_ts_to_bkk(int(bars[-1]["time"])).strftime("%Y-%m-%d %H:%M")
        print(f"  {tf_name}: {len(bars)} bars ({t0} -> {t1} BKK)")
        raw = replay_tf(bars, tf_name, args.spread, cfg)
        print(f"    signals(after fill+SL/TP resolved): {len(raw)}")
        all_raw += raw
    mt5.shutdown()

    trades_with_pnl, equity_stats = simulate_equity(all_raw, cfg["RISK_PCT"])
    s = summarize(trades_with_pnl, equity_stats, cfg["RISK_PCT"], args.days)
    print("-" * 110)
    print(fmt_summary(s) if s else "no trades")

    if s:
        append_summary_csv(args.label, s, cfg, cfg["RISK_PCT"])

    if args.csv and trades_with_pnl:
        out_dir = os.path.join("excel_reports", "backtest_compare", "s25")
        os.makedirs(out_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        path = os.path.join(out_dir, f"sim_s25_{args.label}_{stamp}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(trades_with_pnl[0].keys()))
            w.writeheader()
            w.writerows(trades_with_pnl)
        print(f"CSV: {path}")


if __name__ == "__main__":
    main()
