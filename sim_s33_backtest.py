"""
sim_s33_backtest.py — S33: Equity-curve dynamic sizing (+ optional combine กับ circuit_breaker)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ RESEARCH / BACKTEST-ONLY — reuse detect_s31 (engulfing+htf_trend) entry เดิมจาก S31 (champion
SL1.2/RR1.0) ไม่เปลี่ยน entry — ทดสอบแค่ position-sizing lever ใหม่บน equity curve เอง

EQUITY_DD_SIZING: ลด risk_pct ตาม % drawdown ปัจจุบันจาก peak equity (ไม่ใช่นับไม้แพ้ติดกันแบบ
circuit_breaker) — เป็น "anti-martingale": ยิ่ง equity ตกจาก peak มาก ยิ่งลด exposure ลง
  - tiers: [(dd_pct_threshold, risk_multiplier), ...] เรียงจากน้อยไปมาก
  - default: dd<5% -> 1.0x, dd 5-15% -> 0.7x, dd>=15% -> 0.4x ของ base risk_pct

ใช้ entry/replay เดียวกับ sim_s31 (engulfing+htf_trend) — import มาตรงๆ ไม่เขียนซ้ำ
"""

import argparse
import csv
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy31 import S31_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim

START_EQUITY = 1000.0
DEFAULT_TIERS = [(5.0, 1.0), (15.0, 0.7), (100.0, 0.4)]  # (dd_pct_upper_bound, risk_multiplier)


def _risk_mult_for_dd(dd_pct, tiers):
    for upper, mult in tiers:
        if dd_pct < upper:
            return mult
    return tiers[-1][1]


def simulate_equity_dd_sizing(all_trades, cfg, tiers, use_circuit_breaker=False):
    """
    เดินตามลำดับเวลาจริง + ลด risk_pct ตาม %DD ปัจจุบันจาก peak (คำนวณก่อนเปิดไม้ใหม่ทุกไม้)
    ถ้า use_circuit_breaker=True จะรวม cooldown หลังแพ้ติดกัน (เดียวกับ S29-S31) ด้วย
    """
    base_risk_pct = float(cfg["RISK_PCT"])
    trigger = int(cfg.get("CONSEC_LOSS_TRIGGER", 3))
    cooldown_trades = int(cfg.get("COOLDOWN_TRADES", 10))
    MIN_LOT, LOT_STEP = s30sim.MIN_LOT, s30sim.LOT_STEP
    ASSUMED_LEVERAGE, MAX_MARGIN_USAGE_PCT, CONTRACT_OZ = (
        s30sim.ASSUMED_LEVERAGE, s30sim.MAX_MARGIN_USAGE_PCT, s30sim.CONTRACT_OZ)

    ordered = sorted(all_trades, key=lambda t: t["fill_time_ts"])
    equity = START_EQUITY; peak = equity
    max_dd_usd = 0.0; max_dd_pct = 0.0
    out = []; lots_used = []
    consec_loss = 0; cooldown_remaining = 0; skipped_by_cb = 0

    for t in ordered:
        if use_circuit_breaker and cooldown_remaining > 0:
            cooldown_remaining -= 1; skipped_by_cb += 1
            continue

        cur_dd_pct = ((peak - equity) / peak * 100.0) if peak > 0 else 0.0
        risk_mult = _risk_mult_for_dd(cur_dd_pct, tiers)
        risk_pct = base_risk_pct * risk_mult

        risk_usd = equity * risk_pct / 100.0
        risk_distance = t["risk_distance"]
        if risk_distance <= 0:
            continue
        lot = max(MIN_LOT, round((risk_usd / risk_distance) * 0.01 / LOT_STEP) * LOT_STEP)
        max_margin_usd = equity * MAX_MARGIN_USAGE_PCT / 100.0
        max_lot_by_margin = max(MIN_LOT, round(((max_margin_usd * ASSUMED_LEVERAGE) /
                                                (CONTRACT_OZ * t["entry"])) / LOT_STEP) * LOT_STEP)
        if lot > max_lot_by_margin:
            lot = max_lot_by_margin
        lot_001_units = lot / 0.01
        pnl = (t["diff_usd_per_001lot"] - t["spread"]) * lot_001_units
        equity += pnl; peak = max(peak, equity)
        dd_usd = peak - equity
        dd_pct = (dd_usd / peak * 100.0) if peak > 0 else 0.0
        max_dd_usd = max(max_dd_usd, dd_usd); max_dd_pct = max(max_dd_pct, dd_pct)
        lots_used.append(lot)

        if pnl <= 0:
            consec_loss += 1
            if use_circuit_breaker and consec_loss >= trigger:
                cooldown_remaining = cooldown_trades; consec_loss = 0
        else:
            consec_loss = 0

        row = dict(t)
        row["lot"] = lot; row["risk_pct_used"] = round(risk_pct, 3)
        row["risk_usd"] = round(risk_usd, 2); row["pnl_usd"] = round(pnl, 2)
        row["equity_after"] = round(equity, 2); row["dd_pct_at_entry"] = round(cur_dd_pct, 2)
        out.append(row)

    return out, {"final_equity": round(equity, 2), "max_dd_usd": round(max_dd_usd, 2),
                 "max_dd_pct": round(max_dd_pct, 2),
                 "lot_min": round(min(lots_used), 2) if lots_used else 0.0,
                 "lot_max": round(max(lots_used), 2) if lots_used else 0.0,
                 "skipped_by_circuit_breaker": skipped_by_cb}


def run_one(days, tiers, use_cb, spread=0.20, sl_mult=1.2, rr=1.0, risk_pct=0.5):
    entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=400)
    htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)
    cfg = dict(S31_DEFAULTS)
    cfg.update(SL_ATR_MULT=sl_mult, TP_RR=rr, RISK_PCT=risk_pct)
    raw = s31sim.run_single(entry_bars, htf_bars, cfg, days, spread)
    twp, eq = simulate_equity_dd_sizing(raw, cfg, tiers, use_circuit_breaker=use_cb)
    if not twp:
        return None, None
    s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days)
    by_day = s31sim.daily_series_from_trades(twp)
    c = s31sim.consistency_metrics(by_day)
    return s, c


def append_csv(label, s, c, tiers, use_cb):
    path = os.path.join(os.path.dirname(__file__), "s33_backtest_summary.csv")
    is_new = not os.path.exists(path)
    fields = ["timestamp", "label", "tiers", "use_circuit_breaker", "trades", "wr",
              "avg_per_day_span", "avg_per_month", "max_dd_pct", "profit_factor",
              "pct_pos_days", "max_losing_day_streak", "sharpe_like", "final_equity"]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        w.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "label": label,
            "tiers": str(tiers), "use_circuit_breaker": use_cb, "trades": s["trades"],
            "wr": s["wr"], "avg_per_day_span": s["avg_per_day_span"],
            "avg_per_month": round(s["avg_per_day_span"] * 30, 2),
            "max_dd_pct": s["max_dd_pct"], "profit_factor": s["profit_factor"],
            "pct_pos_days": c["pct_pos_days"], "max_losing_day_streak": c["max_losing_day_streak"],
            "sharpe_like": c["sharpe_like"], "final_equity": s["final_equity"],
        })
    print(f"  -> appended to {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--cb", action="store_true", help="combine กับ circuit_breaker")
    ap.add_argument("--label", default="baseline")
    args = ap.parse_args()
    if not mt5.initialize():
        print("MT5 init fail"); return
    s, c = run_one(args.days, DEFAULT_TIERS, args.cb)
    if s:
        print(f"n={s['trades']} $/d={s['avg_per_day_span']:.2f} $/mo={s['avg_per_day_span']*30:.1f} "
              f"DD={s['max_dd_pct']:.1f}% PF={s['profit_factor']:.2f} posDay={c['pct_pos_days']}% "
              f"maxStreak={c['max_losing_day_streak']}d sharpe={c['sharpe_like']}")
        append_csv(args.label, s, c, DEFAULT_TIERS, args.cb)
    mt5.shutdown()


if __name__ == "__main__":
    main()
