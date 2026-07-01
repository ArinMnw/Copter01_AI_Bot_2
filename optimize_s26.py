"""
optimize_s26.py — Grid search อัตโนมัติสำหรับ S26 (ตามกฎข้อ 2 ของ
docs/new_strategy_research_template.md) ครอบคลุม setup_type ทั้ง 3 ท่า x
entry threshold x SL ratio x EMA-trend confirmation (TP_RR fixed = 1.0 ตามที่ผู้ใช้สั่ง
ไม่ปรับในกริดนี้)

รัน: python optimize_s26.py
"""

import itertools
import time

import MetaTrader5 as mt5

import config
from strategy26 import S26_DEFAULTS
from sim_s26_backtest import (
    fetch_bars, replay, simulate_equity, summarize, fmt_summary, append_summary_csv,
)

DAYS = 30
RISK_PCT = 1.0  # fixed ระหว่างหา edge (กฎข้อ 3 — แยก leverage scaling ออกจาก edge)


def run_one(cfg, label, bars):
    t0 = time.time()
    raw = replay(bars, 0.20, cfg)
    trades_with_pnl, equity_stats = simulate_equity(raw, cfg["RISK_PCT"])
    s = summarize(trades_with_pnl, equity_stats, cfg["RISK_PCT"], DAYS)
    dt = time.time() - t0
    print(f"[{label}] {fmt_summary(s) if s else 'no trades'}  ({dt:.1f}s)")
    if s:
        append_summary_csv(label, s, cfg, cfg["RISK_PCT"])
    return s


def main():
    if not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return
    bars = fetch_bars(config.SYMBOL, DAYS)
    mt5.shutdown()
    if bars is None:
        print("! ดึงข้อมูล M1 ไม่ได้")
        return
    print(f"loaded {len(bars)} M1 bars for grid search (days={DAYS})")

    results = []
    n_combo = 0

    # ── ท่า 1: ema_pullback ──
    for ema_fast, ema_trend, touch_atr, sl_mult in itertools.product(
        [5, 8, 13], [21, 50], [0.10, 0.20, 0.35], [0.3, 0.5, 0.8]
    ):
        n_combo += 1
        cfg = dict(S26_DEFAULTS)
        cfg.update({
            "SETUP_TYPE": "ema_pullback", "RISK_PCT": RISK_PCT,
            "EMA_FAST": ema_fast, "EMA_TREND": ema_trend,
            "PULLBACK_TOUCH_ATR": touch_atr, "SL_ATR_MULT": sl_mult,
        })
        label = f"grid{n_combo:03d}_ema_ef{ema_fast}_et{ema_trend}_touch{touch_atr}_sl{sl_mult}"
        s = run_one(cfg, label, bars)
        if s:
            results.append((label, cfg, s))

    # ── ท่า 2: momentum_pullback ──
    for mombody, pbmax, sl_mult in itertools.product(
        [0.6, 0.8, 1.2], [0.20, 0.35, 0.5], [0.3, 0.5, 0.8]
    ):
        n_combo += 1
        cfg = dict(S26_DEFAULTS)
        cfg.update({
            "SETUP_TYPE": "momentum_pullback", "RISK_PCT": RISK_PCT,
            "MOMENTUM_BODY_ATR": mombody, "PULLBACK_MAX_ATR": pbmax, "SL_ATR_MULT": sl_mult,
        })
        label = f"grid{n_combo:03d}_mom_body{mombody}_pb{pbmax}_sl{sl_mult}"
        s = run_one(cfg, label, bars)
        if s:
            results.append((label, cfg, s))

    # ── ท่า 3: range_scalp ──
    for rangelb, rangeedge, sl_mult in itertools.product(
        [10, 20, 30], [0.10, 0.15, 0.25], [0.3, 0.5, 0.8]
    ):
        n_combo += 1
        cfg = dict(S26_DEFAULTS)
        cfg.update({
            "SETUP_TYPE": "range_scalp", "RISK_PCT": RISK_PCT,
            "RANGE_LOOKBACK": rangelb, "RANGE_EDGE_PCT": rangeedge, "SL_ATR_MULT": sl_mult,
        })
        label = f"grid{n_combo:03d}_range_lb{rangelb}_edge{rangeedge}_sl{sl_mult}"
        s = run_one(cfg, label, bars)
        if s:
            results.append((label, cfg, s))

    print("=" * 120)
    print(f"รวม {n_combo} combinations, {len(results)} มีไม้เทรด")
    results.sort(key=lambda r: r[2]["avg_r_multiple"], reverse=True)
    print("Top 15 by avgR (expectancy ต่อไม้ — ไม่ขึ้นกับ risk%):")
    for label, cfg, s in results[:15]:
        print(f"  {label:55s} avgR={s['avg_r_multiple']:.3f} WR={s['wr']:.1f}% PF={s['profit_factor']:.2f} "
              f"trades={s['trades']} trades/day={s['trades_per_active_day']:.1f} maxDD%={s['max_dd_pct']:.1f}")


if __name__ == "__main__":
    main()
