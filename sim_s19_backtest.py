"""
sim_s19_backtest.py — Backtest S19 ICT Advanced (Silver Bullet/Breaker/BPR) จากข้อมูล MT5 จริง
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
เรียก strategy19.detect_s19() ตรง (pure function — logic เดียวกับ runtime)
inject HTF rates ที่ slice ตามเวลาแท่ง → กัน look-ahead bias ของ bias/MSS

กัน look-ahead bias (เหมือน sim_s18):
  - แท่ง "กำลังวิ่ง" (rates[-1]) ใช้ close = open ของแท่งถัดจาก signal
  - entry = LIMIT รอ fill ภายใน S19_LIMIT_CANCEL_BARS แท่ง
  - TP/SL เดินไปข้างหน้าทีละแท่ง; แท่งเดียวกันแตะทั้ง TP+SL → นับ SL (conservative)
  - spread หักจาก P/L ทุกไม้ (default 0.20 USD)

ตัวอย่าง:
  python sim_s19_backtest.py --days 30 --tf M1,M5
  python sim_s19_backtest.py --days 60 --tf M5 --csv
"""

import argparse
import csv
import os
from datetime import datetime, timezone

import MetaTrader5 as mt5

import config
from strategy19 import detect_s19, _S19_HTF_MAP

SYMBOL = config.SYMBOL
SINCE = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
DEFAULT_SPREAD = 0.20

TF_MAP = {
    "M1":  (mt5.TIMEFRAME_M1, 1440),
    "M5":  (mt5.TIMEFRAME_M5, 288),
    "M15": (mt5.TIMEFRAME_M15, 96),
    "M30": (mt5.TIMEFRAME_M30, 48),
    "H1":  (mt5.TIMEFRAME_H1, 24),
}

TF_SECS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600}


def s19_runtime_feature_coverage() -> list[dict]:
    return [
        {
            "name": "S19 ICT Advanced detect",
            "config_on": bool(config.active_strategies.get(19, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay calls pure strategy19.detect_s19() with sliced HTF rates",
        },
        {
            "name": "Silver Bullet / P3 / NDOG",
            "config_on": True,
            "runtime": "apply",
            "replay": "apply",
            "note": "Detector receives historical BKK signal time and uses S19 config gates",
        },
        {
            "name": "Limit lifecycle",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay models cancel_bars fill, fixed SL/TP, and conservative same-bar SL-before-TP",
        },
        {
            "name": "Standalone recheck bypass",
            "config_on": True,
            "runtime": "skip_s19",
            "replay": "skip_s19",
            "note": "Runtime skips PD/trend/RSI fill recheck, entry candle, trail SL, and limit guard for S19",
        },
        {
            "name": "SL Guard",
            "config_on": getattr(config, "SL_GUARD_ENABLED", False) or getattr(config, "SL_GUARD_GROUP_ENABLED", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "S19 keeps SL Guard, but central replay does not overlay guard context yet",
        },
    ]


def s19_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s19_runtime_feature_coverage()
        if item["config_on"] and item["replay"] == "gap"
    ]


def fetch_bars(symbol, tf_name, days, extra=300):
    tf_val, per_day = TF_MAP[tf_name]
    count = days * per_day + extra
    rates = mt5.copy_rates_from_pos(symbol, tf_val, 0, count)
    if rates is None or len(rates) == 0:
        return None
    return rates


def _days_from_since(default: int = 30) -> int:
    try:
        now = datetime.now(timezone.utc)
        since = SINCE if SINCE.tzinfo is not None else SINCE.replace(tzinfo=timezone.utc)
        return max(default, int((now - since).days) + 3)
    except Exception:
        return default


def _parse_bkk_text(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def _central_trade(row: dict, tf_name: str) -> dict:
    outcome = str(row.get("outcome", "OPEN") or "OPEN")
    close_price = float(row.get("tp") if outcome == "TP" else row.get("sl"))
    return {
        "sid": 19,
        "tf": tf_name,
        "signal": row.get("signal", ""),
        "side": row.get("signal", ""),
        "pattern": f"S19 ICT SB {row.get('zone_type', '')}".strip(),
        "entry_time": _parse_bkk_text(str(row["entry_time"])),
        "close_time": _parse_bkk_text(str(row["exit_time"])),
        "close_type": outcome,
        "entry": round(float(row["entry"]), 2),
        "tp": round(float(row["tp"]), 2),
        "sl": round(float(row["sl"]), 2),
        "close_price": round(close_price, 2),
        "pnl": round(float(row.get("pnl_usd_001lot", 0.0) or 0.0), 2),
        "profit": round(float(row.get("pnl_usd_001lot", 0.0) or 0.0), 2),
        "reason": outcome,
        "zone_type": row.get("zone_type", ""),
        "tp_source": row.get("tp_source", ""),
        "htf_bias": row.get("htf_bias", ""),
        "rsi": row.get("rsi", 0),
    }


def backtest_tf(tf_name: str, tf_val: int | tuple) -> list[dict]:
    days = _days_from_since()
    bars = fetch_bars(SYMBOL, tf_name, days)
    if bars is None:
        return []
    htf_map = getattr(config, "S19_HTF_MAP", _S19_HTF_MAP)
    htf_tf = htf_map.get(tf_name, "M15")
    htf_bars = fetch_bars(SYMBOL, htf_tf, days, extra=400) if htf_tf in TF_MAP else None
    rows = replay_tf(bars, htf_bars, tf_name, DEFAULT_SPREAD)
    since_bkk = config.mt5_ts_to_bkk(int(SINCE.timestamp())) if SINCE else None
    trades = [_central_trade(row, tf_name) for row in rows]
    if since_bkk:
        since_cmp = since_bkk.replace(tzinfo=timezone.utc)
        trades = [t for t in trades if t["entry_time"] >= since_cmp]
    return trades


def replay_tf(bars, htf_bars, tf_name, spread):
    """replay 1 TF → คืน list ของ trade dict"""
    lookback = int(getattr(config, "S19_LOOKBACK", 60))
    cooldown_bars = int(getattr(config, "S19_LEVEL_COOLDOWN_BARS", 20))
    cancel_bars = int(getattr(config, "S19_LIMIT_CANCEL_BARS", 8))
    tf_secs = TF_SECS.get(tf_name, 60)
    win_size = lookback + 50

    trades = []
    level_fired = {}
    n = len(bars)
    for j in range(lookback + 2, n - 1):
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

        sig_time = int(entry_bar["time"])
        # slice HTF bars ที่ปิดก่อน/เท่ากับเวลาแท่ง signal (กัน look-ahead)
        htf_slice = None
        if htf_bars is not None:
            htf_slice = [r for r in htf_bars if int(r["time"]) <= sig_time]
            htf_slice = htf_slice[-300:] if htf_slice else None

        dt_bkk = config.mt5_ts_to_bkk(sig_time)
        res = detect_s19(window, tf=tf_name, dt_bkk=dt_bkk, htf_rates=htf_slice)
        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue

        # dedup level cooldown (logic เดียวกับ strategy_19 wrapper)
        bar_time = int(res.get("sweep_bar_time", 0))
        lv_key = (sig, round(float(res.get("sweep_level", 0.0)), 1))
        last_t = level_fired.get(lv_key, 0)
        if last_t and (bar_time - last_t) < cooldown_bars * tf_secs:
            continue
        level_fired[lv_key] = bar_time

        entry, tp, sl = float(res["entry"]), float(res["tp"]), float(res["sl"])

        # LIMIT: รอ fill ภายใน cancel_bars แท่ง
        start = None
        for m in range(j + 1, min(j + 1 + cancel_bars, n)):
            hi, lw = float(bars[m]["high"]), float(bars[m]["low"])
            if sig == "BUY":
                if lw <= entry:
                    start = m
                    break
                if hi >= tp:
                    break  # วิ่งถึง TP โดยไม่ retrace → cancel
            else:
                if hi >= entry:
                    start = m
                    break
                if lw <= tp:
                    break
        if start is None:
            continue

        outcome, exit_price, exit_time = "OPEN", None, None
        for m in range(start, n):
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
                exit_time = int(bars[m]["time"])
                break

        if outcome == "OPEN":
            continue

        diff = (exit_price - entry) if sig == "BUY" else (entry - exit_price)
        pnl = diff - spread
        trades.append({
            "tf": tf_name, "signal": sig, "outcome": outcome,
            "entry_time": config.mt5_ts_to_bkk(sig_time).strftime("%Y-%m-%d %H:%M"),
            "exit_time": config.mt5_ts_to_bkk(exit_time).strftime("%Y-%m-%d %H:%M"),
            "entry": round(entry, 2), "tp": round(tp, 2), "sl": round(sl, 2),
            "pnl_usd_001lot": round(pnl, 2),
            "zone_type": res.get("zone_type", ""),
            "tp_source": res.get("tp_source", ""),
            "htf_bias": res.get("htf_bias", ""),
            "rsi": res.get("rsi_at_signal", 0),
        })
    return trades


def summarize(trades):
    closed = [t for t in trades if t["outcome"] in ("TP", "SL")]
    if not closed:
        return None
    wins = [t for t in closed if t["pnl_usd_001lot"] > 0]
    losses = [t for t in closed if t["pnl_usd_001lot"] <= 0]
    pnl = sum(t["pnl_usd_001lot"] for t in closed)
    max_consec_sl = consec = 0
    for t in closed:
        consec = consec + 1 if t["pnl_usd_001lot"] <= 0 else 0
        max_consec_sl = max(max_consec_sl, consec)
    return {
        "trades": len(closed),
        "tp": len(wins),
        "sl": len(losses),
        "wr": round(100.0 * len(wins) / len(closed), 1),
        "pnl": round(pnl, 2),
        "avg_win": round(sum(t["pnl_usd_001lot"] for t in wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum(t["pnl_usd_001lot"] for t in losses) / len(losses), 2) if losses else 0.0,
        "max_consec_sl": max_consec_sl,
    }


def fmt_row(label, s):
    if s is None:
        return f"{label:<28} | no trades"
    return (
        f"{label:<28} | n={s['trades']:>4} | WR={s['wr']:>5.1f}% | "
        f"P/L=${s['pnl']:>8.2f} | avgW=${s['avg_win']:>5.2f} | "
        f"avgL=${s['avg_loss']:>7.2f} | maxSLstreak={s['max_consec_sl']}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--tf", default="M1,M5")
    ap.add_argument("--spread", type=float, default=0.20, help="spread USD ต่อไม้ (หักจาก P/L)")
    ap.add_argument("--csv", action="store_true", help="เซฟ trades ลง excel_reports/backtest_compare/s19/")
    args = ap.parse_args()

    if not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return
    symbol = config.SYMBOL
    print(f"Symbol: {symbol} | days={args.days} | spread=${args.spread:.2f}/trade | lot=0.01")

    htf_map = getattr(config, "S19_HTF_MAP", _S19_HTF_MAP)
    tf_list = [t.strip() for t in args.tf.split(",") if t.strip() in TF_MAP]

    bars_by_tf = {}
    htf_by_tf = {}
    htf_cache = {}
    for tf_name in tf_list:
        bars = fetch_bars(symbol, tf_name, args.days)
        if bars is None:
            print(f"! {tf_name}: ดึงข้อมูลไม่ได้ - ข้าม")
            continue
        bars_by_tf[tf_name] = bars
        htf_tf = htf_map.get(tf_name, "M15")
        if htf_tf in TF_MAP:
            if htf_tf not in htf_cache:
                htf_cache[htf_tf] = fetch_bars(symbol, htf_tf, args.days, extra=400)
            htf_by_tf[tf_name] = htf_cache[htf_tf]
        else:
            htf_by_tf[tf_name] = None
            print(f"  (หมายเหตุ {tf_name}: HTF {htf_tf} ไม่อยู่ใน TF_MAP — bias จะเป็น UNKNOWN)")
        t0 = config.mt5_ts_to_bkk(int(bars[0]["time"])).strftime("%Y-%m-%d %H:%M")
        t1 = config.mt5_ts_to_bkk(int(bars[-1]["time"])).strftime("%Y-%m-%d %H:%M")
        print(f"  {tf_name}: {len(bars)} bars ({t0} -> {t1} BKK) | bias TF={htf_tf}")
    mt5.shutdown()

    all_trades = []
    print("\n== BASELINE (config ปัจจุบัน) ==")
    for tf_name, bars in bars_by_tf.items():
        trades = replay_tf(bars, htf_by_tf.get(tf_name), tf_name, args.spread)
        all_trades += trades
        print(fmt_row(tf_name, summarize(trades)))
    print("-" * 100)
    print(fmt_row("TOTAL", summarize(all_trades)))

    if args.csv and all_trades:
        out_dir = os.path.join("excel_reports", "backtest_compare", "s19")
        os.makedirs(out_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        path = os.path.join(out_dir, f"sim_s19_{stamp}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(all_trades[0].keys()))
            w.writeheader()
            w.writerows(all_trades)
        print(f"CSV: {path}")


if __name__ == "__main__":
    main()
