"""
optimize_s29.py — Grid search สำหรับ S29 (entry-pattern lever + DD-control lever) ตามกฎข้อ 2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESEARCH / BACKTEST-ONLY — ดึง bars จาก MT5 ครั้งเดียวต่อ timeframe แล้วรันกริดทั้งหมดในหน่วย
ความจำ (ไม่ดึงซ้ำทุก combination) เพื่อความเร็ว htf_trend confirmation (M15/EMA50) lock ตาม S27
ไม่ grid ซ้ำ — เหลือ 2 lever ใหม่ที่ grid: ENTRY_PATTERN (+threshold เฉพาะ pattern) และ DD_CONTROL

โครงสร้าง (ทำเป็นลำดับ adaptive เหมือน S27 groups A-D):
  Group A: entry pattern sweep (pattern x threshold x TP_RR) — DD_CONTROL=none, risk=1.0% คงที่
           เพื่อหา pattern/threshold ที่ดีที่สุดก่อน (33 combos)
  Group B: DD control sweep บน pattern ที่ดีที่สุดจาก A (risk%/dynamic_risk/circuit_breaker)
           (12 combos)
  Group D: cross-check pattern+DD ที่ดีที่สุดข้าม SL_ATR_MULT x TP_RR เพิ่มเติม (10 combos)
รวม >= 50 combination ที่มีความหมายตามกฎข้อ 2
"""

import time as _time

import MetaTrader5 as mt5

import config
from strategy29 import S29_DEFAULTS
import sim_s29_backtest as sim

DAYS = 30
SPREAD = 0.20


def main():
    if not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return

    symbol = config.SYMBOL
    print(f"=== S29 grid search | symbol={symbol} | days={DAYS} ===")

    entry_bars = sim.fetch_bars(symbol, "M5", DAYS, extra_bars=500)
    print(f"  fetched entry M5: {len(entry_bars) if entry_bars is not None else 0} bars")
    htf_bars = sim.fetch_bars(symbol, "M15", DAYS, extra_bars=200)
    print(f"  fetched htf M15: {len(htf_bars) if htf_bars is not None else 0} bars")

    mt5.shutdown()

    base_cfg = dict(S29_DEFAULTS)
    htf_series = sim.build_htf_series(htf_bars, base_cfg)  # htf_trend/M15/EMA50 lock — ไม่เปลี่ยนระหว่างกริด

    results = []

    def run_one(cfg, label):
        t0 = _time.time()
        raw = sim.replay(entry_bars, htf_series, SPREAD, cfg)
        trades_with_pnl, equity_stats = sim.simulate_equity_v2(raw, cfg)
        s = sim.summarize(trades_with_pnl, equity_stats, cfg["RISK_PCT"], DAYS)
        dt = _time.time() - t0
        if s:
            sim.append_summary_csv(label, s, cfg, cfg["RISK_PCT"])
            print(f"[{label}] {sim.fmt_summary(s)}  ({dt:.1f}s)")
        else:
            print(f"[{label}] no trades  ({dt:.1f}s)")
        results.append((label, cfg.copy(), s))
        return s

    combo_idx = 0

    # ── Group A: entry pattern sweep (DD_CONTROL=none, risk=1.0%, SL=0.8 คงที่) ──
    group_a_results = []

    for touch in (0.10, 0.15, 0.20):
        for rr in (0.8, 1.0, 1.5):
            combo_idx += 1
            cfg = dict(S29_DEFAULTS)
            cfg["ENTRY_PATTERN"] = "ema_bounce"
            cfg["PULLBACK_TOUCH_ATR"] = touch
            cfg["TP_RR"] = rr
            cfg["DD_CONTROL"] = "none"
            lbl = f"grid{combo_idx:03d}_emabounce_touch{touch}_rr{rr}"
            s = run_one(cfg, lbl)
            group_a_results.append((lbl, "ema_bounce", cfg.copy(), s))

    for ratio in (1.0, 1.3, 1.6):
        for rr in (0.8, 1.0, 1.5):
            combo_idx += 1
            cfg = dict(S29_DEFAULTS)
            cfg["ENTRY_PATTERN"] = "engulfing"
            cfg["ENGULF_MIN_RATIO"] = ratio
            cfg["TP_RR"] = rr
            cfg["DD_CONTROL"] = "none"
            lbl = f"grid{combo_idx:03d}_engulf_ratio{ratio}_rr{rr}"
            s = run_one(cfg, lbl)
            group_a_results.append((lbl, "engulfing", cfg.copy(), s))

    for wratio in (2.0, 2.5, 3.0):
        for rr in (0.8, 1.0, 1.5):
            combo_idx += 1
            cfg = dict(S29_DEFAULTS)
            cfg["ENTRY_PATTERN"] = "pinbar"
            cfg["PINBAR_WICK_RATIO"] = wratio
            cfg["TP_RR"] = rr
            cfg["DD_CONTROL"] = "none"
            lbl = f"grid{combo_idx:03d}_pinbar_wick{wratio}_rr{rr}"
            s = run_one(cfg, lbl)
            group_a_results.append((lbl, "pinbar", cfg.copy(), s))

    for nbars in (2, 3):
        for rr in (0.8, 1.0, 1.5):
            combo_idx += 1
            cfg = dict(S29_DEFAULTS)
            cfg["ENTRY_PATTERN"] = "confluence"
            cfg["CONFLUENCE_BARS"] = nbars
            cfg["TP_RR"] = rr
            cfg["DD_CONTROL"] = "none"
            lbl = f"grid{combo_idx:03d}_confluence_n{nbars}_rr{rr}"
            s = run_one(cfg, lbl)
            group_a_results.append((lbl, "confluence", cfg.copy(), s))

    print(f"\n=== Group A เสร็จ ({len(group_a_results)} combos) — เลือก pattern ที่ดีที่สุดด้วย PF (tie: avg/day) ===")
    valid_a = [(lbl, pat, c, s) for lbl, pat, c, s in group_a_results if s and s["trades"] >= 20]
    valid_a.sort(key=lambda x: (x[3]["profit_factor"], x[3]["avg_per_day_span"]), reverse=True)
    for lbl, pat, c, s in valid_a[:8]:
        print(f"  {lbl} [{pat}]: PF={s['profit_factor']} avg/day=${s['avg_per_day_span']:.2f} "
              f"WR={s['wr']}% avgR={s['avg_r_multiple']} trades={s['trades']}")

    if not valid_a:
        print("!! ไม่มี pattern ใดมี trades>=20 ใน Group A — ใช้ ema_bounce(locked S27 baseline) แทน")
        best_pattern_cfg = dict(S29_DEFAULTS)
        best_pattern_cfg["DD_CONTROL"] = "none"
    else:
        best_lbl, best_pat, best_pattern_cfg, best_s = valid_a[0]
        print(f"\n>>> Best entry pattern จาก Group A: [{best_pat}] (label={best_lbl}) "
              f"PF={best_s['profit_factor']} avg/day=${best_s['avg_per_day_span']:.2f}")

    # ── Group B: DD control sweep บน pattern ที่ดีที่สุดจาก A ──
    group_b_results = []

    for risk in (0.3, 0.5, 0.8, 1.0):
        combo_idx += 1
        cfg = dict(best_pattern_cfg)
        cfg["DD_CONTROL"] = "none"
        cfg["RISK_PCT"] = risk
        lbl = f"grid{combo_idx:03d}_ddnone_risk{risk}"
        s = run_one(cfg, lbl)
        group_b_results.append((lbl, cfg.copy(), s))

    for trig in (3, 5):
        for rr_risk in (0.3, 0.5):
            combo_idx += 1
            cfg = dict(best_pattern_cfg)
            cfg["DD_CONTROL"] = "dynamic_risk"
            cfg["RISK_PCT"] = 1.0
            cfg["CONSEC_LOSS_TRIGGER"] = trig
            cfg["REDUCED_RISK_PCT"] = rr_risk
            lbl = f"grid{combo_idx:03d}_dynrisk_trig{trig}_red{rr_risk}"
            s = run_one(cfg, lbl)
            group_b_results.append((lbl, cfg.copy(), s))

    for trig in (3, 5):
        for cooldown in (5, 10):
            combo_idx += 1
            cfg = dict(best_pattern_cfg)
            cfg["DD_CONTROL"] = "circuit_breaker"
            cfg["RISK_PCT"] = 1.0
            cfg["CONSEC_LOSS_TRIGGER"] = trig
            cfg["COOLDOWN_TRADES"] = cooldown
            lbl = f"grid{combo_idx:03d}_cb_trig{trig}_cool{cooldown}"
            s = run_one(cfg, lbl)
            group_b_results.append((lbl, cfg.copy(), s))

    print(f"\n=== Group B เสร็จ ({len(group_b_results)} combos) — เลือก DD control ที่ดีที่สุด "
          f"(maxDD ต่ำสุดในกลุ่มที่ avg/day ยังเป็นบวก) ===")
    valid_b = [(lbl, c, s) for lbl, c, s in group_b_results if s and s["trades"] >= 10]
    positive_b = [x for x in valid_b if x[2]["avg_per_day_span"] > 0]
    pool_b = positive_b if positive_b else valid_b
    pool_b.sort(key=lambda x: x[2]["max_dd_pct"])
    for lbl, c, s in pool_b[:8]:
        print(f"  {lbl}: maxDD={s['max_dd_pct']}% avg/day=${s['avg_per_day_span']:.2f} "
              f"PF={s['profit_factor']} WR={s['wr']}%")

    if pool_b:
        best_dd_lbl, best_dd_cfg, best_dd_s = pool_b[0]
        print(f"\n>>> Best DD control จาก Group B: label={best_dd_lbl} "
              f"DD_CONTROL={best_dd_cfg['DD_CONTROL']} maxDD={best_dd_s['max_dd_pct']}%")
    else:
        best_dd_cfg = dict(best_pattern_cfg)
        best_dd_cfg["DD_CONTROL"] = "none"

    # ── Group D: cross-check pattern+DD ที่ดีที่สุดข้าม SL_ATR_MULT x TP_RR ──
    group_d_results = []
    for sl in (0.5, 0.8):
        for rr in (0.8, 1.0, 1.2, 1.5, 2.0):
            combo_idx += 1
            cfg = dict(best_dd_cfg)
            cfg["SL_ATR_MULT"] = sl
            cfg["TP_RR"] = rr
            lbl = f"grid{combo_idx:03d}_final_sl{sl}_rr{rr}"
            s = run_one(cfg, lbl)
            group_d_results.append((lbl, cfg.copy(), s))

    print(f"\n=== Group D เสร็จ ({len(group_d_results)} combos) ===")
    valid_d = [(lbl, c, s) for lbl, c, s in group_d_results if s]
    valid_d.sort(key=lambda x: x[2]["profit_factor"], reverse=True)
    for lbl, c, s in valid_d[:10]:
        print(f"  {lbl}: PF={s['profit_factor']} avg/day=${s['avg_per_day_span']:.2f} "
              f"maxDD={s['max_dd_pct']}% WR={s['wr']}% avgR={s['avg_r_multiple']}")

    print(f"\n=== รวมทั้งหมด {combo_idx} combinations ===")

    all_results = group_a_results + [(l, "?", c, s) for l, c, s in group_b_results] + \
                  [(l, "?", c, s) for l, c, s in group_d_results]
    valid_all = [(lbl, c, s) for lbl, _, c, s in all_results if s]
    valid_all.sort(key=lambda x: x[2]["avg_per_day_span"], reverse=True)
    print("\nTop 10 ทั้งหมดโดย avg_per_day_span:")
    for lbl, c, s in valid_all[:10]:
        print(f"  {lbl}: avg/day=${s['avg_per_day_span']:.2f} PF={s['profit_factor']} "
              f"WR={s['wr']}% maxDD={s['max_dd_pct']}% avgR={s['avg_r_multiple']}")

    valid_all.sort(key=lambda x: x[2]["profit_factor"], reverse=True)
    print("\nTop 10 ทั้งหมดโดย profit_factor:")
    for lbl, c, s in valid_all[:10]:
        print(f"  {lbl}: PF={s['profit_factor']} avg/day=${s['avg_per_day_span']:.2f} "
              f"WR={s['wr']}% maxDD={s['max_dd_pct']}% avgR={s['avg_r_multiple']}")


if __name__ == "__main__":
    main()
