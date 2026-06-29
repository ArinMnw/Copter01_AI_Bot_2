"""
optimize_s30.py — Grid search S30 (frequency-optimized engulfing family บน M5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ RESEARCH / BACKTEST-ONLY. fetch M5 + M15 ครั้งเดียว แล้ว loop config ใน-process (เร็ว)
เป้า S30: เพิ่มความถี่ไม้/วันสูงสุด โดยรักษา avgR >= ~0.15 และ maxDD <= 25%
M1 พิสูจน์แล้วว่าพัง (noise) — กริดนี้ lock entry_tf=M5

  python optimize_s30.py --days 90 --group A
"""

import argparse
import itertools

import MetaTrader5 as mt5

import config
from strategy30 import S30_DEFAULTS
import sim_s30_backtest as sim


def make_cfg(**over):
    cfg = dict(S30_DEFAULTS)
    cfg.update(over)
    return cfg


def run_one(entry_bars, htf_bars_cache, cfg, days, spread, label):
    htf_series = None
    if cfg["CONFIRMATION_TYPE"] != "none":
        htf_series = sim.build_htf_series(htf_bars_cache, cfg)
    raw = sim.replay(entry_bars, htf_series, spread, cfg)
    twp, eq = sim.simulate_equity_v2(raw, cfg)
    s = sim.summarize(twp, eq, cfg["RISK_PCT"], days)
    if s:
        sim.append_summary_csv(label, s, cfg)
    return s


def grid_group_A():
    """Pattern x quality x mingap x SL/RR sweep (M5, risk0.5%, circuit_breaker locked)"""
    combos = []
    # engulfing variants
    for ratio, mingap, sl, rr in itertools.product([1.0, 1.3, 1.6], [1, 2], [0.5, 0.8], [0.8, 1.0]):
        combos.append(make_cfg(ENTRY_PATTERN="engulfing", ENGULF_MIN_RATIO=ratio,
                               MIN_GAP_BARS=mingap, SL_ATR_MULT=sl, TP_RR=rr))
    # strong_close variants
    for sc, sb, mingap, sl, rr in itertools.product([0.62, 0.70, 0.78], [0.4, 0.6], [1, 2], [0.5], [0.8, 1.0]):
        combos.append(make_cfg(ENTRY_PATTERN="strong_close", STRONG_CLOSE_PCT=sc,
                               STRONG_BODY_ATR=sb, MIN_GAP_BARS=mingap, SL_ATR_MULT=sl, TP_RR=rr))
    # family variants
    for ratio, sc, sb, mingap, rr in itertools.product([1.3], [0.62, 0.70], [0.5], [1, 2], [0.8, 1.0]):
        combos.append(make_cfg(ENTRY_PATTERN="family", ENGULF_MIN_RATIO=ratio, STRONG_CLOSE_PCT=sc,
                               STRONG_BODY_ATR=sb, MIN_GAP_BARS=mingap, SL_ATR_MULT=0.5, TP_RR=rr))
    return combos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--spread", type=float, default=0.20)
    ap.add_argument("--group", default="A")
    args = ap.parse_args()

    if not mt5.initialize():
        print("MT5 init fail", mt5.last_error())
        return

    combos = {"A": grid_group_A}[args.group]()
    print(f"S30 grid group {args.group}: {len(combos)} combos | days={args.days} | entry_tf=M5")

    # fetch ครั้งเดียว (ทุก combo ใช้ M5 + M15 เหมือนกัน)
    entry_bars = sim.fetch_bars(config.SYMBOL, "M5", args.days, extra_bars=400)
    htf_bars = sim.fetch_bars(config.SYMBOL, "M15", args.days, extra_bars=200)
    if entry_bars is None or htf_bars is None:
        print("! fetch bars ไม่ได้")
        mt5.shutdown()
        return

    results = []
    for i, cfg in enumerate(combos):
        label = (f"g{args.group}{i:03d}_{cfg['ENTRY_PATTERN']}_r{cfg['ENGULF_MIN_RATIO']}"
                 f"_sc{cfg['STRONG_CLOSE_PCT']}_gap{cfg['MIN_GAP_BARS']}_sl{cfg['SL_ATR_MULT']}_rr{cfg['TP_RR']}")
        s = run_one(entry_bars, htf_bars, cfg, args.days, args.spread, label)
        if s:
            results.append((label, cfg, s))
            print(f"  [{i+1:>2}/{len(combos)}] {label:<58} "
                  f"n={s['trades']:>4} WR={s['wr']:>4.1f}% tpd={s['trades_per_active_day']:>5.1f} "
                  f"avgR={s['avg_r_multiple']:>6.3f} PF={s['profit_factor']:>4.2f} "
                  f"DD={s['max_dd_pct']:>4.1f}% $/d={s['avg_per_day_span']:>6.2f} $/mo={s['avg_per_day_span']*30:>7.2f}")

    mt5.shutdown()

    # จัดอันดับ: เน้น $/วัน (span) ที่ DD <= 25% และ avgR > 0
    print("\n" + "=" * 130)
    safe = [r for r in results if r[2]["max_dd_pct"] <= 25.0 and r[2]["avg_r_multiple"] > 0]
    safe.sort(key=lambda r: r[2]["avg_per_day_span"], reverse=True)
    print(f"TOP 12 (DD<=25%, avgR>0) by $/day จาก {len(safe)} ตัวที่ผ่านเกณฑ์:")
    for label, cfg, s in safe[:12]:
        print(f"  {label:<58} n={s['trades']:>4} WR={s['wr']:>4.1f}% tpd={s['trades_per_active_day']:>5.1f} "
              f"avgR={s['avg_r_multiple']:>6.3f} PF={s['profit_factor']:>4.2f} DD={s['max_dd_pct']:>4.1f}% "
              f"$/d={s['avg_per_day_span']:>6.2f} $/mo={s['avg_per_day_span']*30:>7.2f}")


if __name__ == "__main__":
    main()
