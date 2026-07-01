"""
optimize_s25.py — Grid search อัตโนมัติสำหรับ S25 Liquidity Sweep Reversal
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ดึงข้อมูล MT5 ครั้งเดียวต่อ TF แล้ว loop พารามิเตอร์ทั้งหมดผ่าน replay_tf/simulate_equity
ของ sim_s25_backtest.py ตรง (เร็วกว่าเรียก subprocess ทีละ combination)

ครอบคลุม: lookback, pierce_atr, wick_pct, rsi_ob/os, sl_atr_mult, tp_rr, trend_filter
ตามกฎข้อ 2 ของ docs/new_strategy_research_template.md (>= 50 combination ก่อนสรุปอะไร)

ใช้:
  python optimize_s25.py --days 60 --tf M5,M15
"""

import argparse
import itertools

import MetaTrader5 as mt5

import config
from sim_s25_backtest import (
    TF_MAP, append_summary_csv, fetch_bars, fmt_summary, replay_tf,
    simulate_equity, summarize,
)
from strategy25 import S25_DEFAULTS


def run_grid(days, tf_list, spread):
    if not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return []
    symbol = config.SYMBOL
    bars_by_tf = {}
    for tf_name in tf_list:
        bars = fetch_bars(symbol, tf_name, days)
        if bars is None:
            print(f"! {tf_name}: ดึงข้อมูลไม่ได้ - ข้าม")
            continue
        bars_by_tf[tf_name] = bars
        t0 = config.mt5_ts_to_bkk(int(bars[0]["time"])).strftime("%Y-%m-%d %H:%M")
        t1 = config.mt5_ts_to_bkk(int(bars[-1]["time"])).strftime("%Y-%m-%d %H:%M")
        print(f"  {tf_name}: {len(bars)} bars ({t0} -> {t1} BKK)")
    mt5.shutdown()

    # ── grid ครอบคลุม entry filter/threshold, SL/TP ratio, session, confirmation ──
    # (รอบที่ 1: คุม combination count ให้รันจบในเวลาที่เหมาะสม >= 50 combination ตามกฎข้อ 2
    #  rsi_ob/slmult fixed ที่ default รอบนี้ — ทดสอบแยกในรอบถัดไปเพื่อความลึกเพิ่ม)
    grid = list(itertools.product(
        [15, 20, 30],               # SWING_LOOKBACK
        [0.05, 0.10, 0.20],         # SWEEP_MIN_PIERCE_ATR
        [0.35, 0.45, 0.55],         # REJECTION_WICK_PCT
        [62.0],                     # RSI_OVERBOUGHT (fixed รอบนี้)
        [0.6],                      # SL_ATR_MULT (fixed รอบนี้)
        [1.0, 1.5, 2.0, 2.5],       # TP_RR
        ["none", "against"],       # TREND_FILTER (filter ประเภท B ตาม Exhaustion Checklist)
    ))
    # RSI_OVERSOLD = 100 - RSI_OVERBOUGHT (สมมาตร) เพื่อคุม combination count ให้บริหารได้
    print(f"Grid size: {len(grid)} combinations")

    results = []
    for idx, (lookback, pierce, wick, rsi_ob, slmult, rr, trend) in enumerate(grid):
        cfg = dict(S25_DEFAULTS)
        cfg["SWING_LOOKBACK"] = lookback
        cfg["SWEEP_MIN_PIERCE_ATR"] = pierce
        cfg["REJECTION_WICK_PCT"] = wick
        cfg["RSI_OVERBOUGHT"] = rsi_ob
        cfg["RSI_OVERSOLD"] = 100.0 - rsi_ob
        cfg["SL_ATR_MULT"] = slmult
        cfg["TP_RR"] = rr
        cfg["TREND_FILTER"] = trend
        cfg["RISK_PCT"] = 1.0  # risk คงที่ตอน grid search edge — แยก leverage scaling ทีหลัง (กฎข้อ 3)

        all_raw = []
        for tf_name, bars in bars_by_tf.items():
            all_raw += replay_tf(bars, tf_name, spread, cfg)
        trades_with_pnl, eq_stats = simulate_equity(all_raw, cfg["RISK_PCT"])
        s = summarize(trades_with_pnl, eq_stats, cfg["RISK_PCT"], days)

        label = f"grid{idx:03d}_lb{lookback}_p{pierce}_w{wick}_ob{rsi_ob}_sl{slmult}_rr{rr}_{trend}"
        if s is None:
            print(f"[{idx+1}/{len(grid)}] {label}: no trades")
            continue
        print(f"[{idx+1}/{len(grid)}] {label}: {fmt_summary(s)}")
        append_summary_csv(label, s, cfg, cfg["RISK_PCT"])
        results.append((label, s, dict(cfg)))

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--tf", default="M5,M15")
    ap.add_argument("--spread", type=float, default=0.20)
    args = ap.parse_args()

    tf_list = [t.strip() for t in args.tf.split(",") if t.strip() in TF_MAP]
    results = run_grid(args.days, tf_list, args.spread)

    if not results:
        print("ไม่มีผลลัพธ์เลย (no trades ทุก combination)")
        return

    # จัดอันดับตาม avg_per_day_span (ดอลลาร์ดิบ) และ avg_r_multiple (edge จริง) แยกกัน
    by_dollar = sorted(results, key=lambda x: x[1]["avg_per_day_span"], reverse=True)[:10]
    by_r = sorted(results, key=lambda x: x[1]["avg_r_multiple"], reverse=True)[:10]

    print("\n" + "=" * 110)
    print("TOP 10 by avg_per_day_span (ดอลลาร์ดิบ — อาจปนเปื้อน leverage):")
    for label, s, cfg in by_dollar:
        print(f"  {label}: avg/day=${s['avg_per_day_span']:.2f} maxDD={s['max_dd_pct']:.1f}% "
              f"avgR={s['avg_r_multiple']:.3f} WR={s['wr']:.1f}% PF={s['profit_factor']:.2f} n={s['trades']}")

    print("\nTOP 10 by avg_r_multiple (edge จริงต่อไม้ — ไม่ขึ้นกับ risk%):")
    for label, s, cfg in by_r:
        print(f"  {label}: avgR={s['avg_r_multiple']:.3f} WR={s['wr']:.1f}% PF={s['profit_factor']:.2f} "
              f"avg/day=${s['avg_per_day_span']:.2f} maxDD={s['max_dd_pct']:.1f}% n={s['trades']}")


if __name__ == "__main__":
    main()
