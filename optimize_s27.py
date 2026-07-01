"""
optimize_s27.py — Grid search สำหรับ S27 (entry M1/M5 + HTF confirmation) ตามกฎข้อ 2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESEARCH / BACKTEST-ONLY — ดึง bars จาก MT5 ครั้งเดียวต่อ timeframe แล้วรันกริดทั้งหมดในหน่วย
ความจำ (ไม่ดึงซ้ำทุก combination) เพื่อความเร็ว

ครอบคลุม: entry_tf x confirmation_type x htf_tf x threshold เฉพาะ confirmation นั้นๆ x
SL_ATR_MULT x TP_RR ตามกฎข้อ 2 (>= 50 combination ที่มีความหมาย)
"""

import sys
import time as _time

import MetaTrader5 as mt5

import config
from strategy27 import S27_DEFAULTS
import sim_s27_backtest as sim

DAYS = 30
SPREAD = 0.20


def main():
    if not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return

    symbol = config.SYMBOL
    print(f"=== S27 grid search | symbol={symbol} | days={DAYS} ===")

    # ── ดึง bars ทุก timeframe ที่ต้องใช้ครั้งเดียว ───────────────
    entry_bars_cache = {}
    for etf in ("M1", "M5"):
        bars = sim.fetch_bars(symbol, etf, DAYS, extra_bars=500)
        entry_bars_cache[etf] = bars
        print(f"  fetched entry {etf}: {len(bars) if bars is not None else 0} bars")

    htf_bars_cache = {}
    for htf in ("M15", "H1", "H4"):
        bars = sim.fetch_bars(symbol, htf, DAYS, extra_bars=200)
        htf_bars_cache[htf] = bars
        print(f"  fetched htf {htf}: {len(bars) if bars is not None else 0} bars")

    mt5.shutdown()

    # cache ของ build_htf_series ตาม (htf_tf, ema_period, slope_bars, rsi_period, adx_period, level_lb)
    htf_series_cache = {}

    def get_htf_series(cfg):
        key = (cfg["HTF_TF"], cfg["HTF_EMA_PERIOD"], cfg["HTF_SLOPE_BARS"], cfg["RSI_PERIOD"],
               cfg["ADX_PERIOD"], cfg["LEVEL_LOOKBACK"])
        if key not in htf_series_cache:
            htf_series_cache[key] = sim.build_htf_series(htf_bars_cache[cfg["HTF_TF"]], cfg)
        return htf_series_cache[key]

    results = []

    def run_one(cfg, label):
        t0 = _time.time()
        entry_bars = entry_bars_cache[cfg["ENTRY_TF"]]
        htf_series = get_htf_series(cfg) if cfg["CONFIRMATION_TYPE"] != "none" else None
        raw = sim.replay(entry_bars, htf_series, SPREAD, cfg)
        trades_with_pnl, equity_stats = sim.simulate_equity(raw, cfg["RISK_PCT"])
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

    # ── กลุ่ม A: baseline ไม่มี confirmation (วัด WR ดิบของ entry mechanism เอง) ──
    for etf in ("M1", "M5"):
        for sl in (0.5, 0.8):
            for rr in (0.8, 1.0, 1.5, 2.0):
                combo_idx += 1
                cfg = dict(S27_DEFAULTS)
                cfg["ENTRY_TF"] = etf
                cfg["CONFIRMATION_TYPE"] = "none"
                cfg["SL_ATR_MULT"] = sl
                cfg["TP_RR"] = rr
                run_one(cfg, f"grid{combo_idx:03d}_none_{etf}_sl{sl}_rr{rr}")

    # ── กลุ่ม B: htf_trend (EMA slope ของ M15/H1) ──
    for etf in ("M1", "M5"):
        for htf in ("M15", "H1"):
            for ema_p in (21, 50):
                for sl in (0.5, 0.8):
                    for rr in (1.0, 1.5):
                        combo_idx += 1
                        cfg = dict(S27_DEFAULTS)
                        cfg["ENTRY_TF"] = etf
                        cfg["CONFIRMATION_TYPE"] = "htf_trend"
                        cfg["HTF_TF"] = htf
                        cfg["HTF_EMA_PERIOD"] = ema_p
                        cfg["SL_ATR_MULT"] = sl
                        cfg["TP_RR"] = rr
                        run_one(cfg, f"grid{combo_idx:03d}_trend_{etf}_{htf}_ema{ema_p}_sl{sl}_rr{rr}")

    # ── กลุ่ม C: htf_rsi (zone สวนทาง) ──
    for etf in ("M1", "M5"):
        for htf in ("M15", "H1"):
            for thr in (5.0, 10.0, 15.0):
                for rr in (1.0, 1.5):
                    combo_idx += 1
                    cfg = dict(S27_DEFAULTS)
                    cfg["ENTRY_TF"] = etf
                    cfg["CONFIRMATION_TYPE"] = "htf_rsi"
                    cfg["HTF_TF"] = htf
                    cfg["RSI_THRESHOLD"] = thr
                    cfg["TP_RR"] = rr
                    run_one(cfg, f"grid{combo_idx:03d}_rsi_{etf}_{htf}_thr{thr}_rr{rr}")

    # ── กลุ่ม D: htf_level (key level support/resistance) ──
    for etf in ("M1", "M5"):
        for htf in ("H1", "H4"):
            for zone in (0.15, 0.25):
                for rr in (1.0, 1.5):
                    combo_idx += 1
                    cfg = dict(S27_DEFAULTS)
                    cfg["ENTRY_TF"] = etf
                    cfg["CONFIRMATION_TYPE"] = "htf_level"
                    cfg["HTF_TF"] = htf
                    cfg["LEVEL_ZONE_PCT"] = zone
                    cfg["TP_RR"] = rr
                    run_one(cfg, f"grid{combo_idx:03d}_level_{etf}_{htf}_zone{zone}_rr{rr}")

    print(f"\n=== รวม {combo_idx} combinations ===")

    # ── สรุป top-N ด้วย $/วัน(span) และ PF ──
    valid = [(lbl, c, s) for lbl, c, s in results if s]
    valid.sort(key=lambda x: x[2]["avg_per_day_span"], reverse=True)
    print("\nTop 10 by avg_per_day_span:")
    for lbl, c, s in valid[:10]:
        print(f"  {lbl}: avg/day(span)=${s['avg_per_day_span']:.2f} WR={s['wr']}% "
              f"trades/day={s['trades_per_active_day']} PF={s['profit_factor']} avgR={s['avg_r_multiple']}")

    valid.sort(key=lambda x: x[2]["profit_factor"], reverse=True)
    print("\nTop 10 by profit_factor:")
    for lbl, c, s in valid[:10]:
        print(f"  {lbl}: PF={s['profit_factor']} avg/day(span)=${s['avg_per_day_span']:.2f} WR={s['wr']}% "
              f"trades/day={s['trades_per_active_day']} avgR={s['avg_r_multiple']}")


if __name__ == "__main__":
    main()
