"""
sim_s17_backtest.py — Backtest S17 Sweep Sniper จากข้อมูล MT5 จริง
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
เรียก strategy17.detect_s17() ตรง (pure function — logic เดียวกับ runtime)

กัน look-ahead bias:
  - แท่ง "กำลังวิ่ง" (rates[-1]) ใช้ close = open ของแท่งถัดจาก signal
    = ราคา ณ วินาทีที่แท่ง signal เพิ่งปิด (runtime เห็นแบบนี้จริง)
  - entry = open ของแท่งถัดไป, TP/SL เดินไปข้างหน้าทีละแท่ง
  - แท่งเดียวกันแตะทั้ง TP และ SL → นับ SL (conservative)

Bid/Ask fill model (03/07/2026 — แก้จาก audit live 3 สัปดาห์แรก WR 69% vs sim 91%):
  rates ของ MT5 เป็นราคา bid → โมเดลเดิม fill BUY limit เมื่อ bid แตะ entry
  ซึ่งมองโลกดีเกิน (จริงต้อง ask = bid+spread ลงถึง entry) ทำ WR เฟ้อ
  - BUY : fill เมื่อ low ≤ entry − spread | TP เมื่อ high ≥ tp | SL เมื่อ low ≤ sl
  - SELL: fill เมื่อ high ≥ entry | TP เมื่อ low ≤ tp − spread | SL เมื่อ high ≥ sl − spread
  - P/L limit mode = ราคาทำจริง ไม่หัก spread ซ้ำ (ต้นทุนอยู่ในเงื่อนไข fill แล้ว)
  - market mode ยังหัก spread จาก P/L แบบเดิม

ตัวอย่าง:
  python sim_s17_backtest.py --days 30 --tf M1,M5,M15,M30
  python sim_s17_backtest.py --days 30 --tf M5 --sweep --csv
  # Compounding แบบ S20.12 runner: risk 2%/ไม้ จาก balance เริ่ม 1000
  python sim_s17_backtest.py --days 60 --tf M1,M30,H1 --compound 2 --start-balance 1000
  python sim_s17_backtest.py --start "01-05-2026 00:00" --end "01-07-2026 00:00" --tf M1 --compound 2
"""

import argparse
import csv
import os
from datetime import datetime, timezone

import MetaTrader5 as mt5

import config
from strategy17 import detect_s17

SYMBOL = config.SYMBOL
SINCE = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
DEFAULT_SPREAD = 0.20

TF_MAP = {
    "M1":  (mt5.TIMEFRAME_M1, 1440),
    "M5":  (mt5.TIMEFRAME_M5, 288),
    "M15": (mt5.TIMEFRAME_M15, 96),
    "M30": (mt5.TIMEFRAME_M30, 48),
    "H1":  (mt5.TIMEFRAME_H1, 24),
    "H4":  (mt5.TIMEFRAME_H4, 6),
    "H12": (mt5.TIMEFRAME_H12, 2),
    "D1":  (mt5.TIMEFRAME_D1, 1),
}

TF_SECS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600,
           "H4": 14400, "H12": 43200, "D1": 86400}


def s17_runtime_feature_coverage() -> list[dict]:
    return [
        {
            "name": "S17 Sweep Sniper detect",
            "config_on": bool(config.active_strategies.get(17, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay calls pure strategy17.detect_s17() with historical BKK signal time",
        },
        {
            "name": "Session / PD / RSI gates",
            "config_on": True,
            "runtime": "apply",
            "replay": "apply",
            "note": "Detector reads S17_* config values restored from bot_state/config",
        },
        {
            "name": "Limit lifecycle",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay models cancel_bars fill, fixed SL/TP, time stop, and conservative same-bar SL-before-TP",
        },
        {
            "name": "Standalone recheck bypass",
            "config_on": True,
            "runtime": "skip_s17",
            "replay": "skip_s17",
            "note": "Runtime skips PD/trend/RSI fill recheck, entry candle, trail SL, Opposite Order, and limit guard for S17",
        },
        {
            "name": "SL Guard",
            "config_on": getattr(config, "SL_GUARD_ENABLED", False) or getattr(config, "SL_GUARD_GROUP_ENABLED", False),
            "runtime": "apply",
            "replay": "partial",
            "note": "S17 keeps SL Guard; central replay applies SL Guard Group close-on-activate overlay as a baseline",
        },
    ]


def s17_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s17_runtime_feature_coverage()
        if item["config_on"] and item["replay"] == "gap"
    ]


def fetch_bars(symbol, tf_name, days):
    tf_val, per_day = TF_MAP[tf_name]
    count = min(days * per_day + 300, 90000)  # cap: MT5 คืน None ถ้าขอเกิน ~90k
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
    if outcome == "TP":
        close_price = float(row.get("tp"))
    elif outcome == "TS" and row.get("exit_price") is not None:
        close_price = float(row.get("exit_price"))
    else:
        close_price = float(row.get("sl"))
    return {
        "sid": 17,
        "tf": tf_name,
        "signal": row.get("signal", ""),
        "side": row.get("signal", ""),
        "pattern": "S17 Sweep Sniper",
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
        "rsi": row.get("rsi", 0),
    }


def backtest_tf(tf_name: str, tf_val: int | tuple) -> list[dict]:
    days = _days_from_since()
    bars = fetch_bars(SYMBOL, tf_name, days)
    if bars is None:
        return []
    rows = replay_tf(bars, tf_name, DEFAULT_SPREAD)
    since_bkk = config.mt5_ts_to_bkk(int(SINCE.timestamp())) if SINCE else None
    trades = [_central_trade(row, tf_name) for row in rows]
    if since_bkk:
        since_cmp = since_bkk.replace(tzinfo=timezone.utc)
        trades = [t for t in trades if t["entry_time"] >= since_cmp]
    return trades


def replay_tf(bars, tf_name, spread):
    """replay 1 TF → คืน list ของ trade dict"""
    lookback = int(getattr(config, "S17_LOOKBACK", 60))
    cooldown_bars = int(getattr(config, "S17_LEVEL_COOLDOWN_BARS", 20))
    tf_secs = TF_SECS.get(tf_name, 60)
    win_size = lookback + 50  # ขนาด slice ใกล้เคียง TF_LOOKBACK runtime + ที่ให้ ATR converge

    trades = []
    level_fired = {}
    n = len(bars)
    for j in range(lookback + 2, n - 1):
        entry_bar = bars[j + 1]
        # แท่งกำลังวิ่ง: รู้แค่ open (= ราคาตอนแท่ง signal เพิ่งปิด)
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
        res = detect_s17(window, tf=tf_name, dt_bkk=dt_bkk)
        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue

        # dedup level cooldown (logic เดียวกับ strategy_17 wrapper)
        bar_time = int(res.get("sweep_bar_time", 0))
        lv_key = (sig, round(float(res.get("sweep_level", 0.0)), 1))
        last_t = level_fired.get(lv_key, 0)
        if last_t and (bar_time - last_t) < cooldown_bars * tf_secs:
            continue
        level_fired[lv_key] = bar_time

        entry, tp, sl = float(res["entry"]), float(res["tp"]), float(res["sl"])
        time_stop = int(getattr(config, "S17_TIME_STOP_BARS", 0))
        is_limit = res.get("order_mode") == "limit"

        # LIMIT mode: รอ fill ภายใน S17_LIMIT_CANCEL_BARS แท่ง — ไม่ fill = ไม่มีไม้
        # bid/ask: BUY fill ต้องให้ ask ลงถึง entry → bid ≤ entry − spread
        start = j + 1
        if is_limit:
            cancel_bars = int(getattr(config, "S17_LIMIT_CANCEL_BARS", 5))
            fill_idx = None
            for m in range(j + 1, min(j + 1 + cancel_bars, n)):
                hi, lw = float(bars[m]["high"]), float(bars[m]["low"])
                if sig == "BUY":
                    if lw <= entry - spread:
                        fill_idx = m
                        break
                    if hi >= tp:
                        break  # ราคาวิ่งถึง TP โดยไม่ retrace → cancel
                else:
                    if hi >= entry:
                        fill_idx = m
                        break
                    if lw <= tp - spread:
                        break
            if fill_idx is None:
                continue
            start = fill_idx

        outcome, exit_price, exit_time = "OPEN", None, None
        for m in range(start, n):
            hi, lw = float(bars[m]["high"]), float(bars[m]["low"])
            if sig == "BUY":
                if lw <= sl:            # conservative: เช็ค SL ก่อน (bid)
                    outcome, exit_price = "SL", sl
                elif hi >= tp:
                    outcome, exit_price = "TP", tp
            else:
                if hi >= sl - spread:   # SELL ปิดที่ ask → SL โดนเร็วขึ้น
                    outcome, exit_price = "SL", sl
                elif lw <= tp - spread:  # SELL TP ต้องให้ ask ลงถึง tp
                    outcome, exit_price = "TP", tp
            if outcome == "OPEN" and time_stop > 0 and (m - start + 1) >= time_stop:
                outcome, exit_price = "TS", float(bars[m]["close"])
            if outcome != "OPEN":
                exit_time = int(bars[m]["time"])
                break

        if outcome == "OPEN":
            continue  # ไม้ค้างท้ายข้อมูล — ไม่นับ

        diff = (exit_price - entry) if sig == "BUY" else (entry - exit_price)
        # limit mode: ต้นทุน spread อยู่ในเงื่อนไข fill/exit แล้ว — หักซ้ำเฉพาะ TS (ปิด market)
        # market mode: หัก spread เต็มแบบเดิม
        if is_limit:
            pnl = diff - (spread if outcome == "TS" and sig == "SELL" else 0.0)
        else:
            pnl = diff - spread  # $ ต่อ 0.01 lot (XAU 0.01 lot = 1 oz)
        trades.append({
            "tf": tf_name, "signal": sig, "outcome": outcome,
            "entry_time": config.mt5_ts_to_bkk(int(bars[start]["time"])).strftime("%Y-%m-%d %H:%M"),
            "exit_time": config.mt5_ts_to_bkk(exit_time).strftime("%Y-%m-%d %H:%M"),
            "entry_ts": int(bars[start]["time"]),
            "entry": round(entry, 2), "tp": round(tp, 2), "sl": round(sl, 2),
            "exit_price": round(exit_price, 2),
            "risk_dist": round(abs(entry - sl), 2),
            "pnl_usd_001lot": round(pnl, 2),
            "rsi": res.get("rsi_at_signal", 0),
        })
    return trades


def simulate_compound(trades, risk_pct, start_balance, max_lot=50.0):
    """จำลอง compounding แบบ S20.12: lot = balance × risk% / (ระยะ SL × 100)
    เรียงไม้ตามเวลา fill, ปรับ balance ต่อไม้ (sequential approximation)
    คืน dict summary (final_balance, return_pct, max_dd_pct, min/max lot)
    """
    if not trades:
        return None
    balance = float(start_balance)
    peak = balance
    max_dd = 0.0
    lots = []
    for t in sorted(trades, key=lambda x: x.get("entry_ts", 0)):
        risk_dist = float(t.get("risk_dist", 0) or 0)
        if risk_dist <= 0:
            continue
        risk_usd = balance * (risk_pct / 100.0)
        lot = risk_usd / (risk_dist * 100.0)   # XAU: 1 lot = 100 oz
        lot = max(0.01, min(round(lot, 2), float(max_lot)))
        lots.append(lot)
        # pnl_usd_001lot = P/L ต่อ 1 oz (0.01 lot) → คูณสเกลเป็น lot จริง
        balance += float(t["pnl_usd_001lot"]) * (lot / 0.01)
        peak = max(peak, balance)
        if peak > 0:
            max_dd = max(max_dd, (peak - balance) / peak * 100.0)
        if balance <= 0:
            balance = 0.0
            break
    return {
        "final_balance": round(balance, 2),
        "return_pct": round((balance - start_balance) / start_balance * 100.0, 1),
        "max_dd_pct": round(max_dd, 1),
        "lot_min": min(lots) if lots else 0,
        "lot_max": max(lots) if lots else 0,
        "n": len(lots),
    }


def summarize(trades):
    closed = [t for t in trades if t["outcome"] in ("TP", "SL", "TS")]
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
    ap.add_argument("--tf", default="M1,M5,M15,M30")
    ap.add_argument("--spread", type=float, default=0.20, help="spread USD ต่อไม้ (หักจาก P/L)")
    ap.add_argument("--sweep", action="store_true", help="param sweep: TP mult × SL buf × RSI gate")
    ap.add_argument("--sweep2", action="store_true", help="param sweep: trend filter × time stop × risk cap")
    ap.add_argument("--sweep3", action="store_true", help="param sweep: session × lookback × wick")
    ap.add_argument("--sweep4", action="store_true", help="param sweep: entry mode × TP × SLbuf × RSI")
    ap.add_argument("--mode", default=None, help="override S17_ENTRY_MODE")
    ap.add_argument("--tp", type=float, default=None, help="override S17_TP_ATR_MULT")
    ap.add_argument("--slb", type=float, default=None, help="override S17_SL_ATR_BUFFER")
    ap.add_argument("--rsib", type=float, default=None, help="override S17_RSI_BUY_MAX")
    ap.add_argument("--rsis", type=float, default=None, help="override S17_RSI_SELL_MIN")
    ap.add_argument("--wick", type=float, default=None, help="override S17_WICK_MIN_PCT")
    ap.add_argument("--symbol", default="", help="override symbol (default: config.SYMBOL)")
    ap.add_argument("--compound", type=float, default=0.0,
                    help="Risk %% ต่อไม้แบบ compounding (0 = ปิด) — แบบเดียวกับ backtest_S20_12_runner_mt5.py")
    ap.add_argument("--start-balance", type=float, default=1000.0, help="balance เริ่มต้นสำหรับ compounding (default 1000)")
    ap.add_argument("--start", default=None, help="เวลาเริ่ม dd-MM-yyyy HH:mm (BKK) — override --days")
    ap.add_argument("--end", default=None, help="เวลาจบ dd-MM-yyyy HH:mm (BKK) — ไม่ระบุ = ปัจจุบัน")
    ap.add_argument("--max-lot", type=float, default=None, help="เพดาน lot compounding (default: config.S17_MAX_LOT)")
    ap.add_argument("--csv", action="store_true", help="เซฟ trades ลง excel_reports/backtest_compare/s17/")
    args = ap.parse_args()

    if args.mode is not None:
        config.S17_ENTRY_MODE = args.mode
    if args.tp is not None:
        config.S17_TP_ATR_MULT = args.tp
    if args.slb is not None:
        config.S17_SL_ATR_BUFFER = args.slb
    if args.rsib is not None:
        config.S17_RSI_BUY_MAX = args.rsib
    if args.rsis is not None:
        config.S17_RSI_SELL_MIN = args.rsis
    if args.wick is not None:
        config.S17_WICK_MIN_PCT = args.wick

    def parse_bkk(text):
        for fmt in ("%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        raise SystemExit(f"รูปแบบเวลาไม่ถูกต้อง: {text} (ใช้ dd-MM-yyyy HH:mm)")

    start_dt = parse_bkk(args.start) if args.start else None
    end_dt = parse_bkk(args.end) if args.end else None
    fetch_days = args.days
    if start_dt:
        fetch_days = max(args.days, (datetime.now() - start_dt).days + 2)

    def in_range(t):
        dt = datetime.strptime(t["entry_time"], "%Y-%m-%d %H:%M")
        if start_dt and dt < start_dt:
            return False
        if end_dt and dt > end_dt:
            return False
        return True

    if not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return
    symbol = args.symbol or config.SYMBOL
    rng = f"{args.start} -> {args.end or 'now'}" if start_dt else f"days={args.days}"
    print(f"Symbol: {symbol} | {rng} | spread=${args.spread:.2f}/trade | lot=0.01")

    # --tf all = ทุก TF ที่ sim รองรับ (เหมือน backtest_S20_12_runner_mt5.py)
    if args.tf.strip().lower() == "all":
        tf_list = list(TF_MAP.keys())
        allowed = getattr(config, "S17_ALLOWED_TFS", [])
        if allowed:
            print(f"หมายเหตุ: live ใช้เฉพาะ TF {','.join(allowed)} (S17_ALLOWED_TFS) — sim รันทุก TF เพื่อเปรียบเทียบ")
    else:
        tf_list = [t.strip() for t in args.tf.split(",") if t.strip() in TF_MAP]
    if not tf_list:
        print(f"ไม่รู้จัก TF: {args.tf} — ใช้ได้: all หรือ {','.join(TF_MAP.keys())}")
        mt5.shutdown()
        return
    bars_by_tf = {}
    for tf_name in tf_list:
        bars = fetch_bars(symbol, tf_name, fetch_days)
        if bars is None:
            print(f"! {tf_name}: ดึงข้อมูลไม่ได้ - ข้าม")
            continue
        t0 = config.mt5_ts_to_bkk(int(bars[0]["time"])).strftime("%Y-%m-%d %H:%M")
        t1 = config.mt5_ts_to_bkk(int(bars[-1]["time"])).strftime("%Y-%m-%d %H:%M")
        print(f"  {tf_name}: {len(bars)} bars ({t0} -> {t1} BKK)")
        bars_by_tf[tf_name] = bars
    mt5.shutdown()

    if args.sweep:
        combos = [
            (tp, slb, rb, rs)
            for tp in (0.4, 0.5, 0.8, 1.0)
            for slb in (0.3, 0.5, 1.0)
            for rb, rs in ((32, 68), (35, 65))
        ]
        print("\n== PARAM SWEEP (session+PD+wick ตาม config) ==")
        for tp_mult, sl_buf, rsi_b, rsi_s in combos:
            config.S17_TP_ATR_MULT = tp_mult
            config.S17_SL_ATR_BUFFER = sl_buf
            config.S17_RSI_BUY_MAX = rsi_b
            config.S17_RSI_SELL_MIN = rsi_s
            all_trades = []
            for tf_name, bars in bars_by_tf.items():
                all_trades += replay_tf(bars, tf_name, args.spread)
            label = f"TP={tp_mult} SLbuf={sl_buf} RSI {rsi_b}/{rsi_s}"
            print(fmt_row(label, summarize(all_trades)))
        return

    if args.sweep2:
        print("\n== PARAM SWEEP 2 (trend filter x time stop x risk cap; TP/SLbuf/RSI ตาม config) ==")
        for trend in (False, True):
            for cap in (1.5, 2.5, 4.0):
                for ts in (0, 10, 20):
                    config.S17_TREND_FILTER = trend
                    config.S17_MAX_RISK_ATR_MULT = cap
                    config.S17_TIME_STOP_BARS = ts
                    all_trades = []
                    for tf_name, bars in bars_by_tf.items():
                        all_trades += replay_tf(bars, tf_name, args.spread)
                    label = f"trend={'Y' if trend else 'N'} cap={cap} TS={ts}"
                    print(fmt_row(label, summarize(all_trades)))
        return

    if args.sweep3:
        sessions = {
            "KZ":   (True, [("14:00", "18:00"), ("19:00", "23:00")]),
            "ASIA": (True, [("06:00", "13:00")]),
            "ALL":  (False, []),
        }
        print("\n== PARAM SWEEP 3 (session x lookback x wick; TP/SLbuf/RSI ตาม config) ==")
        for sname, (s_on, s_ranges) in sessions.items():
            for lb in (30, 60, 120):
                for wick in (0.3, 0.5):
                    config.S17_SESSION_FILTER = s_on
                    if s_ranges:
                        config.S17_SESSIONS = s_ranges
                    config.S17_LOOKBACK = lb
                    config.S17_WICK_MIN_PCT = wick
                    all_trades = []
                    for tf_name, bars in bars_by_tf.items():
                        all_trades += replay_tf(bars, tf_name, args.spread)
                    label = f"sess={sname} LB={lb} wick={wick}"
                    print(fmt_row(label, summarize(all_trades)))
        return

    if args.sweep4:
        config.S17_WICK_MIN_PCT = 0.3
        config.S17_LOOKBACK = 60
        print("\n== PARAM SWEEP 4 (entry mode x TP x SLbuf x RSI; KZ LB=60 wick=0.3) ==")
        for mode in ("limit_50", "limit_618"):
            for tp in (0.4, 0.5, 0.8):
                for slb in (0.3, 0.5):
                    for rb, rs in ((32, 68), (35, 65)):
                        config.S17_ENTRY_MODE = mode
                        config.S17_TP_ATR_MULT = tp
                        config.S17_SL_ATR_BUFFER = slb
                        config.S17_RSI_BUY_MAX = rb
                        config.S17_RSI_SELL_MIN = rs
                        all_trades = []
                        for tf_name, bars in bars_by_tf.items():
                            all_trades += replay_tf(bars, tf_name, args.spread)
                        label = f"{mode} TP={tp} SLb={slb} RSI {rb}/{rs}"
                        print(fmt_row(label, summarize(all_trades)))
        return

    all_trades = []
    print("\n== BASELINE (config ปัจจุบัน) ==")
    for tf_name, bars in bars_by_tf.items():
        trades = [t for t in replay_tf(bars, tf_name, args.spread) if in_range(t)]
        all_trades += trades
        print(fmt_row(tf_name, summarize(trades)))
    print("-" * 100)
    print(fmt_row("TOTAL", summarize(all_trades)))

    if args.compound > 0 and all_trades:
        max_lot = args.max_lot if args.max_lot else float(getattr(config, "S17_MAX_LOT", 50.0))
        c = simulate_compound(all_trades, args.compound, args.start_balance, max_lot=max_lot)
        if c:
            print(f"\n== COMPOUNDING (risk {args.compound}%/ไม้, เริ่ม ${args.start_balance:,.0f}, max lot {max_lot}) ==")
            print(f"Balance สุดท้าย : ${c['final_balance']:,.2f}  ({c['return_pct']:+.1f}%)")
            print(f"Max Drawdown    : {c['max_dd_pct']:.1f}%")
            print(f"Lot ที่ใช้       : {c['lot_min']:.2f} - {c['lot_max']:.2f} ({c['n']} ไม้)")
            fixed_pnl = sum(t["pnl_usd_001lot"] for t in all_trades)
            print(f"เทียบ fixed 0.01: {fixed_pnl:+.2f} USD")

    if args.csv and all_trades:
        out_dir = os.path.join("excel_reports", "backtest_compare", "s17")
        os.makedirs(out_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        path = os.path.join(out_dir, f"sim_s17_{stamp}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(all_trades[0].keys()))
            w.writeheader()
            w.writerows(all_trades)
        print(f"CSV: {path}")


if __name__ == "__main__":
    main()
