"""
sim_s24_backtest.py — Backtest S24 Asian-Range London-Breakout จากข้อมูล MT5 จริง
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ RESEARCH / BACKTEST-ONLY — strategy24.py ไม่ถูก wire เข้า scanner.py/trailing.py/
   main.py ใดๆ ทั้งสิ้น ไฟล์นี้ไม่แก้ S1-S23, ไม่แก้ bot_state.json, ไม่แตะ live trading

เรียก strategy24.detect_s24() ตรง (pure function — logic เดียวกับที่จะใช้ถ้า wire จริง)

กัน look-ahead bias (เหมือน sim_s21/22/23_backtest.py):
  - แท่ง "กำลังวิ่ง" (rates[-1]) ใช้ open ของแท่งถัดจากแท่งสัญญาณ
  - entry เป็น MARKET (fill ทันทีที่ open ของแท่งถัดไป)
  - แท่งเดียวกันแตะทั้ง TP และ SL → นับ SL (conservative)
  - spread หักจาก P/L ทุกไม้ (default 0.20 USD ต่อ "lot unit" 0.01)
  - 1 ไม้/วัน/ทิศทาง (เหมือน strategy_24 wrapper) — กันยิงรัวใน entry window เดียวกัน

Position sizing (risk-based, ทุนเริ่มต้น $1000, compounding ตาม equity ปัจจุบัน):
  เหมือน sim_s21/22/23 — lot = risk_usd / risk_distance, margin guard กัน
  margin usage เกิน MAX_MARGIN_USAGE_PCT ของ equity ที่ leverage ASSUMED_LEVERAGE

ตัวอย่าง:
  python sim_s24_backtest.py --days 60 --tf M5,M15
  python sim_s24_backtest.py --days 60 --tf M5 --risk 1.5 --rr 1.5 --csv
"""

import argparse
import csv
import os
from datetime import datetime, timezone

import MetaTrader5 as mt5

import config
from strategy24 import S24_DEFAULTS, detect_s24

SYMBOL = config.SYMBOL
SINCE = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
DEFAULT_SPREAD = 0.20          # USD ต่อไม้ ต่อ 0.01 lot (IUX XAU โดยประมาณ)
START_EQUITY = 1000.0
ASSUMED_LEVERAGE = 500.0       # สมมติแบบระมัดระวัง (บัญชีจริงอาจได้ leverage สูงกว่านี้)
MAX_MARGIN_USAGE_PCT = 30.0    # ใช้ margin ต่อไม้ไม่เกิน % นี้ของ equity ปัจจุบัน
CONTRACT_OZ = 100.0            # 1.00 lot XAUUSD = 100 oz
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
    """replay 1 TF → คืน list ของ trade dict (ยังไม่คิด lot/equity — ทำใน main เพื่อ
    compounding ข้าม TF ตามลำดับเวลาจริง). 1 ไม้/วัน/ทิศทาง ตาม wrapper logic"""
    trades = []
    fired_today = {}
    n = len(bars)
    start_j = 250
    for j in range(start_j, n - 1):
        sig_bar = bars[j + 1]
        live = {
            "time":  int(sig_bar["time"]),
            "open":  float(sig_bar["open"]),
            "high":  float(sig_bar["open"]),
            "low":   float(sig_bar["open"]),
            "close": float(sig_bar["open"]),
        }
        lo = max(0, j + 1 - 260)
        window = list(bars[lo:j + 1]) + [live]

        dt_bkk = config.mt5_ts_to_bkk(int(sig_bar["time"]))
        res = detect_s24(window, tf=tf_name, dt_bkk=dt_bkk, cfg=cfg, dt_bkk_fn=config.mt5_ts_to_bkk)
        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue

        day_key = res.get("signal_day", "")
        if fired_today.get(day_key):
            continue
        fired_today[day_key] = True

        entry, tp, sl = float(res["entry"]), float(res["tp"]), float(res["sl"])
        fill_idx = j + 1  # market fill ทันทีที่ open ของแท่งถัดจากแท่งสัญญาณ

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
            continue  # ไม้ค้างท้ายข้อมูล — ไม่นับ

        risk_distance = abs(entry - sl)
        diff = (exit_price - entry) if sig == "BUY" else (entry - exit_price)
        trades.append({
            "tf": tf_name, "signal": sig, "outcome": outcome,
            "signal_time_ts": int(sig_bar["time"]),
            "fill_time_ts": int(bars[fill_idx]["time"]),
            "exit_time_ts": int(bars[exit_idx]["time"]),
            "entry": round(entry, 2), "tp": round(tp, 2), "sl": round(sl, 2),
            "exit_price": round(exit_price, 2),
            "risk_distance": round(risk_distance, 4),
            "diff_usd_per_001lot": round(diff, 4),   # ก่อนหัก spread
            "spread": spread,
            "rsi": res.get("rsi_at_signal", 0),
            "atr": res.get("atr_at_signal", 0),
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
        f"final_equity=${s['final_equity']:.2f} | maxLossStreak={s['max_consec_loss']}"
    )


def append_summary_csv(label, s, cfg, risk_pct):
    path = os.path.join(os.path.dirname(__file__), "s24_backtest_summary.csv")
    is_new = not os.path.exists(path)
    fields = [
        "timestamp", "label", "trades", "wr", "total_pnl",
        "avg_per_day_span", "avg_per_day_active", "n_days_with_trades", "span_days",
        "days_hit_1000", "max_dd_usd", "max_dd_pct", "lot_min", "lot_max",
        "risk_pct", "final_equity", "max_consec_loss",
        "max_asian_range_atr_mult", "tp_rr", "sl_atr_mult",
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
                "max_consec_loss",
            )},
            "max_asian_range_atr_mult": cfg["MAX_ASIAN_RANGE_ATR_MULT"],
            "tp_rr": cfg["TP_RR"],
            "sl_atr_mult": cfg["SL_ATR_MULT"],
        }
        w.writerow(row)
    print(f"  -> appended to {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--tf", default="M5,M15")
    ap.add_argument("--spread", type=float, default=DEFAULT_SPREAD)
    ap.add_argument("--risk", type=float, default=S24_DEFAULTS["RISK_PCT"], help="risk %% per trade")
    ap.add_argument("--rr", type=float, default=None, help="override TP_RR")
    ap.add_argument("--slmult", type=float, default=None, help="override SL_ATR_MULT")
    ap.add_argument("--maxrange", type=float, default=None, help="override MAX_ASIAN_RANGE_ATR_MULT")
    ap.add_argument("--label", default="baseline", help="label สำหรับ s24_backtest_summary.csv")
    ap.add_argument("--csv", action="store_true", help="เซฟ trade-level CSV ด้วย")
    args = ap.parse_args()

    cfg = dict(S24_DEFAULTS)
    cfg["RISK_PCT"] = args.risk
    if args.rr is not None:
        cfg["TP_RR"] = args.rr
    if args.slmult is not None:
        cfg["SL_ATR_MULT"] = args.slmult
    if args.maxrange is not None:
        cfg["MAX_ASIAN_RANGE_ATR_MULT"] = args.maxrange

    if not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return
    symbol = config.SYMBOL
    print(f"S24 backtest | Symbol={symbol} | days={args.days} | spread=${args.spread:.2f} | "
          f"risk={cfg['RISK_PCT']}%/trade | start_equity=${START_EQUITY:.0f}")
    print(f"cfg: max_asian_range_atr_mult={cfg['MAX_ASIAN_RANGE_ATR_MULT']} "
          f"RR={cfg['TP_RR']} SLmult={cfg['SL_ATR_MULT']} entry_window={cfg['ENTRY_WINDOW_START']}-{cfg['ENTRY_WINDOW_END']}")

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
        out_dir = os.path.join("excel_reports", "backtest_compare", "s24")
        os.makedirs(out_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        path = os.path.join(out_dir, f"sim_s24_{args.label}_{stamp}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(trades_with_pnl[0].keys()))
            w.writeheader()
            w.writerows(trades_with_pnl)
        print(f"CSV: {path}")


if __name__ == "__main__":
    main()
