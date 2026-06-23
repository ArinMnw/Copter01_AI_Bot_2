"""
backtest_S20_6_runner_mt5.py — Backtest S20.6 FVG Standalone
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
จำลองการรัน S20.6 FVG Entry:
- สแกนหา 3-bar FVG โครงสร้าง
- รอราคากลับมารีเทสต์ใน FVG (รับแรง)
- รอยืนยันจากแท่งเทียน (Engulfing / ครึ่ง Engulfing)
- ตัดบาร์ที่มีเนื้อไส้กินหัว (Head cutting wick)
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5

import config
import hhll_swing
import htf_fvg
from strategy20_6 import strategy_20_6

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

def fetch_bars(symbol, tf_name, days):
    tf_val, per_day = TF_MAP[tf_name]
    count = days * per_day + 300
    rates = mt5.copy_rates_from_pos(symbol, tf_val, 0, count)
    if rates is None or len(rates) == 0:
        return None
    return rates

def replay_tf(bars, tf_name, spread):
    trades = []
    n = len(bars)
    last_signal_bar = {}  # dedup: กัน signal ซ้ำ bar ติดกัน
    
    # วนลูปสมมติว่าปัจจุบันคือแท่ง j
    # rates_slice เอาถึงแค่ j
    for j in range(30, n - 1):
        entry_bar = bars[j]
        # rates สำหรับให้ strategy_20_6 มองเห็น ต้องดึงมาให้พอสำหรับคำนวณ ATR (16+) และ FVG (30+)
        rates_slice = bars[max(0, j - 50):j + 1]
        
        # แปลง bar time เป็น BKK สำหรับ session filter
        bar_dt_bkk = config.mt5_ts_to_bkk(int(entry_bar["time"]))
        res = strategy_20_6(rates_slice, tf=tf_name, dt_bkk=bar_dt_bkk)
        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue

        # ── Dedup: กัน signal ซ้ำ bar ติดกัน
        dedup_key = (sig, res.get("pattern", ""))
        if dedup_key in last_signal_bar and j - last_signal_bar[dedup_key] < 3:
            continue
        last_signal_bar[dedup_key] = j

        # S20.6 executes immediately via Market Order (in live trailing.py usually bypassed, 
        # but the document specifies it enters Market after engulfing confirmation)
        entry = float(res["entry"])
        tp = float(res["tp"])
        sl = float(res["sl"])
        
        outcome, exit_price, exit_time = "OPEN", None, None
        
        for m in range(j + 1, n):
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
            "sub_pattern": res.get("pattern", "S20.6"),
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
    ap.add_argument("--days", type=int, default=30) # 4 weeks roughly
    ap.add_argument("--tf", default="M1,M5,M15,M30,H1,H4,H12,D1")
    ap.add_argument("--spread", type=float, default=0.20)
    args = ap.parse_args()

    if not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return
        
    print(f"Symbol: {SYMBOL} | days={args.days} | spread=${args.spread:.2f}/trade | lot=0.01")

    # ── Prevent Look-ahead Bias in Backtest ──
    config.S20_TREND_FILTER = False
    print("  ⚠️ S20_TREND_FILTER ถูกตั้งเป็น False สำหรับการทำ Backtest (ป้องกัน Look-ahead Bias)")

    tf_list = [t.strip() for t in args.tf.split(",") if t.strip() in TF_MAP]
    bars_by_tf = {}
    for tf_name in tf_list:
        bars = fetch_bars(SYMBOL, tf_name, args.days)
        if bars is None:
            print(f"! {tf_name}: ดึงข้อมูลไม่ได้ - ข้าม")
            continue
        t0 = config.mt5_ts_to_bkk(int(bars[0]["time"])).strftime("%Y-%m-%d %H:%M")
        t1 = config.mt5_ts_to_bkk(int(bars[-1]["time"])).strftime("%Y-%m-%d %H:%M")
        print(f"  {tf_name}: {len(bars)} bars ({t0} -> {t1} BKK)")
        bars_by_tf[tf_name] = bars
    mt5.shutdown()

    all_trades = []
    print("\n== BASELINE (S20.6 FVG Entry Standalone) ==")
    for tf_name, bars in bars_by_tf.items():
        trades = replay_tf(bars, tf_name, args.spread)
        all_trades += trades
        print(fmt_row(tf_name, summarize(trades)))
    print("-" * 100)
    print(fmt_row("TOTAL (All Variants)", summarize(all_trades)))
    
    # Export to CSV
    csv_file = "s20_6_backtest_summary.csv"
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["TF", "Sub-Pattern", "Trades", "WinRate(%)", "P/L($)", "AvgWin($)", "AvgLoss($)", "MaxSLStreak"])
        
        for tf_name in tf_list:
            sp_tf_trades = [t for t in all_trades if t.get("tf") == tf_name]
            s = summarize(sp_tf_trades)
            if s:
                writer.writerow([tf_name, "S20.6", s['trades'], s['wr'], s['pnl'], s['avg_win'], s['avg_loss'], s['max_consec_sl']])
    print(f"\n✅ Exported detailed breakdown to {csv_file}")
    
    # Print 10 recent cases
    print("\n== RECENT 10 TRADES (Detailed Analysis) ==")
    for t in all_trades[-10:]:
        print(f"[{t['tf']}] {t['signal']} at {t['entry_time']} => {t['outcome']} at {t['exit_time']} | P/L: ${t['pnl_usd_001lot']}")

if __name__ == "__main__":
    main()
