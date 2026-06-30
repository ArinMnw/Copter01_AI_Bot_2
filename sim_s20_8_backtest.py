"""
sim_s20_backtest.py — Backtest S20 All in 4s (Reversal & Retracement)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
จำลองการรัน S20 โดยตรง:
- entry = 50% ของเนื้อแท่งยืนยัน (รอเป็น limit order)
- ถ้าราคาไม่ลงมาเกี่ยวภายใน S20_CANCEL_BARS -> cancel
- TP = Fibo 161.8%
- SL = ปลายไส้สุดของชุด reversal + buffer
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone, timedelta

BKK = timezone(timedelta(hours=7))

sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5

import config
import hhll_swing
import htf_fvg
from strategy20_8 import strategy_20_8

# Force enable strategy for backtest
config.S20_8_ENABLED = True
config.active_strategies[20.8] = True

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

def fetch_bars(symbol, tf_name, days, start_dt=None, end_dt=None):
    tf_val, per_day = TF_MAP[tf_name]
    if start_dt is not None:
        if end_dt is None:
            end_dt = datetime.now(BKK)
        rates = mt5.copy_rates_range(symbol, tf_val, start_dt, end_dt)
    else:
        count = days * per_day + 300
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

def replay_tf(bars, tf_name, spread):
    trades = []
    n = len(bars)
    last_signal_bar = {}  # dedup: กัน signal ซ้ำ bar ติดกัน
    
    # วนลูปสมมติว่าปัจจุบันคือแท่ง j
    # rates_slice เอาถึงแค่ j
    for j in range(5, n - 1):
        entry_bar = bars[j]
        # rates สำหรับให้ strategy_20_8 มองเห็น ต้องดึงมาให้พอสำหรับคำนวณ ATR และ Liquidity Sweep (60+)
        rates_slice = bars[max(0, j - 100):j + 1]
        
        # แปลง bar time เป็น BKK สำหรับ session filter
        bar_dt_bkk = config.mt5_ts_to_bkk(int(entry_bar["time"]))
        res = strategy_20_8(rates_slice, tf=tf_name)
        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue

        # ── Dedup: กัน signal ซ้ำ bar ติดกัน (เหมือน last_traded_per_tf ใน live) ──
        dedup_key = (sig, res.get("pattern", ""))
        if dedup_key in last_signal_bar and j - last_signal_bar[dedup_key] < 3:
            continue
        last_signal_bar[dedup_key] = j

        entry = float(res["entry"])
        tp = float(res["tp"])
        sl = float(res["sl"])
        
        cancel_bars = int(getattr(config, "S20_CANCEL_BARS", 5))
        
        # Simulate fill
        order_mode = res.get("order_mode", "limit")
        
        start = j + 1
        fill_idx = None
        
        if order_mode == "market":
            fill_idx = j # Filled instantly at the close of the current bar (which is entry)
        else:
            for m in range(j + 1, min(j + 1 + cancel_bars, n)):
                hi = float(bars[m]["high"])
                lw = float(bars[m]["low"])
                
                if sig == "BUY":
                    if lw <= entry:
                        fill_idx = m
                        break
                    # ถ้าราคาพุ่งไปชน TP ก่อนเกี่ยวไม้ จริงๆ แล้วเราไม่ได้ไม้ 
                    if hi >= tp:
                        break
                else:
                    if hi >= entry:
                        fill_idx = m
                        break
                    if lw <= tp:
                        break
        
        if fill_idx is None:
            # ไม่ได้ไม้ (Limit ไม่ถึง / ทะลุ TP ก่อน)
            continue  # Order is cancelled
            
        start = fill_idx
        outcome, exit_price, exit_time = "OPEN", None, None
        
        for m in range(start, n):
            hi = float(bars[m]["high"])
            lw = float(bars[m]["low"])
            
            if sig == "BUY":
                # เช็ค SL ก่อน
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
        pnl = diff - spread  # $ ต่อ 0.01 lot
        
        trades.append({
            "tf": tf_name, 
            "signal": sig,
            "sub_pattern": res.get("pattern", "S20.8"),
            "outcome": outcome,
            "entry_time": config.mt5_ts_to_bkk(int(entry_bar["time"])).strftime("%Y-%m-%d %H:%M"),
            "exit_time": config.mt5_ts_to_bkk(exit_time).strftime("%Y-%m-%d %H:%M"),
            "entry": round(entry, 2), 
            "tp": round(tp, 2), 
            "sl": round(sl, 2),
            "exit_price": round(exit_price, 2),
            "pnl_usd_001lot": round(pnl, 2),
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
    ap.add_argument("--tf", default="M1,M5,M15,M30,H1,H4,H12,D1")
    ap.add_argument("--spread", type=float, default=0.20)
    ap.add_argument("--fibo", type=float, default=None)
    ap.add_argument("--start", type=str, default=None, help="Start time dd-MM-yyyy HH:mm")
    ap.add_argument("--end", type=str, default=None, help="End time dd-MM-yyyy HH:mm")
    args = ap.parse_args()

    if args.fibo is not None:
        config.S20_FIBO_TP_LEVEL = args.fibo

    if not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return
        
    # --- [NEW] Pre-fetch HTF FVGs for Backtest ---
    print("  fetching D1/H4 FVG Liquidity Zones for backtest...")
    htf_fvg.clear_cache()
    htf_fvg.fetch_active_fvgs("D1", SYMBOL, lookback=1000)
    htf_fvg.fetch_active_fvgs("H4", SYMBOL, lookback=5000)
    print("  Done fetching HTF FVGs.")
    # ---------------------------------------------
        
    print(f"Symbol: {SYMBOL} | days={args.days} | spread=${args.spread:.2f}/trade | lot=0.01")

    # ── Prevent Look-ahead Bias in Backtest ──
    # S20_TREND_FILTER and S20.3 (HTF Fibo) rely on live H1 data.
    # In backtest, we disable Trend Filter to prevent applying today's trend to historical trades.
    config.S20_TREND_FILTER = False
    print("  ⚠️ S20_TREND_FILTER ถูกตั้งเป็น False สำหรับการทำ Backtest (ป้องกัน Look-ahead Bias)")
    print("  ⚠️ ท่า S20.3 (HTF Fibo) จะไม่ทำงานใน Backtest นี้ เนื่องจากไม่สามารถดึงข้อมูลสวิง H1 ย้อนหลังแบบ Dynamic ได้")

    tf_list = [t.strip() for t in args.tf.split(",") if t.strip() in TF_MAP]
    bars_by_tf = {}
    
    start_dt = None
    end_dt = None
    if args.start:
        start_dt = datetime.strptime(args.start, "%d-%m-%Y %H:%M").replace(tzinfo=BKK)
    if args.end:
        end_dt = datetime.strptime(args.end, "%d-%m-%Y %H:%M").replace(tzinfo=BKK)
        
    for tf_name in tf_list:
        bars = fetch_bars(SYMBOL, tf_name, args.days, start_dt, end_dt)
        if bars is None:
            print(f"! {tf_name}: ดึงข้อมูลไม่ได้ - ข้าม")
            continue
        t0 = config.mt5_ts_to_bkk(int(bars[0]["time"])).strftime("%Y-%m-%d %H:%M")
        t1 = config.mt5_ts_to_bkk(int(bars[-1]["time"])).strftime("%Y-%m-%d %H:%M")
        print(f"  {tf_name}: {len(bars)} bars ({t0} -> {t1} BKK)")
        bars_by_tf[tf_name] = bars
    mt5.shutdown()

    all_trades = []
    print("\n== BASELINE (S20 All in 4s) ==")
    for tf_name, bars in bars_by_tf.items():
        trades = replay_tf(bars, tf_name, args.spread)
        all_trades += trades
        print(fmt_row(tf_name, summarize(trades)))
    print("-" * 100)
    print(fmt_row("TOTAL (All Variants)", summarize(all_trades)))
    
    print("\n== BREAKDOWN BY SUB-PATTERN ==")
    sub_patterns = set(t.get("sub_pattern", "S20") for t in all_trades)
    for sp in sorted(list(sub_patterns)):
        sp_trades = [t for t in all_trades if t.get("sub_pattern") == sp]
        print(fmt_row(f"Sub-pattern {sp}", summarize(sp_trades)))

    # Export to CSV
    csv_file = "s20_backtest_summary.csv"
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["TF", "Sub-Pattern", "Trades", "WinRate(%)", "P/L($)", "AvgWin($)", "AvgLoss($)", "MaxSLStreak"])
        
        for tf_name in tf_list:
            for sp in sorted(list(sub_patterns)):
                sp_tf_trades = [t for t in all_trades if t.get("tf") == tf_name and t.get("sub_pattern") == sp]
                s = summarize(sp_tf_trades)
                if s:
                    writer.writerow([tf_name, sp, s['trades'], s['wr'], s['pnl'], s['avg_win'], s['avg_loss'], s['max_consec_sl']])
    # Export detailed trades
    trades_csv = "s20_8_trades.csv"
    with open(trades_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["tf", "signal", "sub_pattern", "outcome", "entry_time", "exit_time", "entry", "tp", "sl", "exit_price", "pnl_usd_001lot"])
        writer.writeheader()
        writer.writerows(all_trades)
    print(f"✅ Exported detailed trades to {trades_csv}")

if __name__ == "__main__":
    main()
