"""
sim_s31_backtest.py — Backtest S31 (consistency-focused: SL grid + portfolio blend)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ RESEARCH / BACKTEST-ONLY — strategy31.py ไม่ถูก wire เข้า live ใดๆ ไม่แก้ S1-S30

โครงสร้างเหมือน sim_s30_backtest.py (กัน look-ahead 2 ชั้นเหมือนกัน) เพิ่ม:
  --blend: รัน 2 sub-config พร้อมกัน แบ่งทุนคนละครึ่ง (START_EQUITY/2 ต่อตัว) แล้วรวม equity
           curve รายวัน — จำลอง "กระจายความเสี่ยงข้าม sub-strategy ที่ไม่ relate กัน"
"""

import argparse
import csv
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy31 import S31_DEFAULTS, detect_s31
import sim_s30_backtest as s30sim  # reuse fetch_bars / build_htf_series / htf_lookup

SYMBOL = config.SYMBOL
DEFAULT_SPREAD = 0.20
START_EQUITY = 1000.0


def _cfg_get(cfg, key):
    return cfg[key] if (cfg and key in cfg) else S31_DEFAULTS[key]


def replay31(bars, htf_series, spread, cfg):
    """เหมือน s30sim.replay แต่เรียก detect_s31"""
    ema_fast = int(cfg["EMA_FAST"])
    win_size = ema_fast + 40
    conf_type = cfg["CONFIRMATION_TYPE"]
    min_gap_bars = int(_cfg_get(cfg, "MIN_GAP_BARS"))

    trades = []
    last_fire_idx = -10
    n = len(bars)
    start_j = win_size + 5
    for j in range(start_j, n - 1):
        if j - last_fire_idx < min_gap_bars:
            continue
        entry_bar = bars[j + 1]
        live = {"time": int(entry_bar["time"]), "open": float(entry_bar["open"]),
                "high": float(entry_bar["open"]), "low": float(entry_bar["open"]),
                "close": float(entry_bar["open"])}
        lo = max(0, j + 1 - win_size)
        window = list(bars[lo:j + 1]) + [live]
        dt_bkk = config.mt5_ts_to_bkk(int(entry_bar["time"]))
        htf_ctx = s30sim.htf_lookup(htf_series, int(entry_bar["time"])) if conf_type != "none" else None

        res = detect_s31(window, tf=cfg["ENTRY_TF"], dt_bkk=dt_bkk, cfg=cfg, htf_ctx=htf_ctx)
        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue
        last_fire_idx = j

        entry, tp, sl = float(res["entry"]), float(res["tp"]), float(res["sl"])
        fill_idx = j + 1
        outcome, exit_price, exit_idx = "OPEN", None, None
        for m in range(fill_idx, n):
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
                exit_idx = m
                break
        if outcome == "OPEN":
            continue
        risk_distance = abs(entry - sl)
        diff = (exit_price - entry) if sig == "BUY" else (entry - exit_price)
        trades.append({
            "signal": sig, "outcome": outcome, "signal_time_ts": int(entry_bar["time"]),
            "fill_time_ts": int(bars[fill_idx]["time"]), "exit_time_ts": int(bars[exit_idx]["time"]),
            "entry": round(entry, 2), "tp": round(tp, 2), "sl": round(sl, 2),
            "exit_price": round(exit_price, 2), "risk_distance": round(risk_distance, 4),
            "diff_usd_per_001lot": round(diff, 4), "spread": spread,
        })
    return trades


def simulate_equity_substream(all_trades, cfg, start_equity):
    """เหมือน s30sim.simulate_equity_v2 แต่รับ start_equity แยก (สำหรับ blend)"""
    dd_control = cfg.get("DD_CONTROL", "none")
    base_risk_pct = float(cfg["RISK_PCT"])
    trigger = int(_cfg_get(cfg, "CONSEC_LOSS_TRIGGER"))
    reduced_risk_pct = float(_cfg_get(cfg, "REDUCED_RISK_PCT"))
    cooldown_trades = int(_cfg_get(cfg, "COOLDOWN_TRADES"))
    MIN_LOT, LOT_STEP = s30sim.MIN_LOT, s30sim.LOT_STEP
    ASSUMED_LEVERAGE, MAX_MARGIN_USAGE_PCT, CONTRACT_OZ = (
        s30sim.ASSUMED_LEVERAGE, s30sim.MAX_MARGIN_USAGE_PCT, s30sim.CONTRACT_OZ)

    ordered = sorted(all_trades, key=lambda t: t["fill_time_ts"])
    equity = start_equity; peak = equity
    max_dd_usd = 0.0; max_dd_pct = 0.0
    out = []; lots_used = []
    consec_loss = 0; cooldown_remaining = 0; skipped_by_cb = 0

    for t in ordered:
        if dd_control == "circuit_breaker" and cooldown_remaining > 0:
            cooldown_remaining -= 1; skipped_by_cb += 1
            continue
        risk_pct = base_risk_pct
        if dd_control == "dynamic_risk" and consec_loss >= trigger:
            risk_pct = reduced_risk_pct
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
            if dd_control == "circuit_breaker" and consec_loss >= trigger:
                cooldown_remaining = cooldown_trades; consec_loss = 0
        else:
            consec_loss = 0
        row = dict(t)
        row["lot"] = lot; row["risk_pct_used"] = round(risk_pct, 3)
        row["risk_usd"] = round(risk_usd, 2); row["pnl_usd"] = round(pnl, 2)
        row["equity_after"] = round(equity, 2)
        out.append(row)
    return out, {"final_equity": round(equity, 2), "max_dd_usd": round(max_dd_usd, 2),
                 "max_dd_pct": round(max_dd_pct, 2),
                 "lot_min": round(min(lots_used), 2) if lots_used else 0.0,
                 "lot_max": round(max(lots_used), 2) if lots_used else 0.0,
                 "skipped_by_circuit_breaker": skipped_by_cb}


def run_single(entry_bars, htf_bars, cfg, days, spread):
    htf_series = s30sim.build_htf_series(htf_bars, cfg) if cfg["CONFIRMATION_TYPE"] != "none" else None
    raw = replay31(entry_bars, htf_series, spread, cfg)
    return raw


def daily_series_from_trades(trades_with_pnl):
    by_day = {}
    for t in trades_with_pnl:
        d = config.mt5_ts_to_bkk(t["exit_time_ts"]).strftime("%Y-%m-%d")
        by_day[d] = by_day.get(d, 0.0) + t["pnl_usd"]
    return by_day


def consistency_metrics(by_day_combined):
    import statistics
    if not by_day_combined:
        return None
    vals = list(by_day_combined.values())
    pos_days = sum(1 for v in vals if v > 0)
    pct_pos_days = 100.0 * pos_days / len(vals)
    sorted_days = sorted(by_day_combined.keys())
    streak = max_streak = 0
    for d in sorted_days:
        if by_day_combined[d] < 0:
            streak += 1; max_streak = max(max_streak, streak)
        else:
            streak = 0
    mean_d = statistics.mean(vals)
    std_d = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    sharpe_like = (mean_d / std_d) if std_d > 0 else 0.0
    return {"pct_pos_days": round(pct_pos_days, 1), "max_losing_day_streak": max_streak,
            "sharpe_like": round(sharpe_like, 3)}


def run_backtest(cfg, days, spread, label, blend_cfg=None, verbose=True):
    if not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return None
    symbol = config.SYMBOL
    entry_bars = s30sim.fetch_bars(symbol, cfg["ENTRY_TF"], days, extra_bars=max(300, int(cfg["EMA_FAST"]) + 60))
    htf_bars = s30sim.fetch_bars(symbol, cfg["HTF_TF"], days,
                                  extra_bars=max(int(cfg["HTF_EMA_PERIOD"]), 28) + 60) if cfg["CONFIRMATION_TYPE"] != "none" else None
    if entry_bars is None:
        print("! fetch entry bars fail"); mt5.shutdown(); return None

    if blend_cfg is None:
        raw = run_single(entry_bars, htf_bars, cfg, days, spread)
        twp, eq = simulate_equity_substream(raw, cfg, START_EQUITY)
        by_day = daily_series_from_trades(twp)
        c = consistency_metrics(by_day)
        s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days)
        if s and c:
            s.update(c)
            s30sim.append_summary_csv(label, s, cfg) if False else _append_s31_csv(label, s, cfg, blend=False)
        if verbose and s:
            print(f"{label:<32} n={s['trades']:>4} $/d={s['avg_per_day_span']:>6.2f} "
                  f"$/mo={s['avg_per_day_span']*30:>7.1f} DD={s['max_dd_pct']:>5.1f}% PF={s['profit_factor']:>4.2f} "
                  f"posDay={c['pct_pos_days']:>5.1f}% maxStreak={c['max_losing_day_streak']:>2}d sharpe={c['sharpe_like']:>6.3f}")
        mt5.shutdown()
        return s
    else:
        # blend: รัน 2 sub-config, แบ่งทุนคนละครึ่ง, รวม equity/วัน
        raw_a = run_single(entry_bars, htf_bars, cfg, days, spread)
        raw_b = run_single(entry_bars, htf_bars, blend_cfg, days, spread)
        twp_a, eq_a = simulate_equity_substream(raw_a, cfg, START_EQUITY / 2)
        twp_b, eq_b = simulate_equity_substream(raw_b, blend_cfg, START_EQUITY / 2)
        day_a = daily_series_from_trades(twp_a)
        day_b = daily_series_from_trades(twp_b)
        all_days = set(day_a) | set(day_b)
        combined_by_day = {d: day_a.get(d, 0.0) + day_b.get(d, 0.0) for d in all_days}
        c = consistency_metrics(combined_by_day)
        total_pnl = sum(combined_by_day.values())
        final_equity = eq_a["final_equity"] + eq_b["final_equity"]
        max_dd_combined = max(eq_a["max_dd_pct"], eq_b["max_dd_pct"])  # ประมาณ (อนุรักษ์นิยม)
        avg_day = total_pnl / max(days, 1)
        n_total = len(twp_a) + len(twp_b)
        if verbose:
            print(f"{label:<32} n={n_total:>4}(A{len(twp_a)}+B{len(twp_b)}) $/d={avg_day:>6.2f} "
                  f"$/mo={avg_day*30:>7.1f} DD(approx)={max_dd_combined:>5.1f}% "
                  f"posDay={c['pct_pos_days']:>5.1f}% maxStreak={c['max_losing_day_streak']:>2}d "
                  f"sharpe={c['sharpe_like']:>6.3f} final=${final_equity:.2f}")
        _append_s31_csv(label, {
            "trades": n_total, "avg_per_day_span": round(avg_day, 3), "max_dd_pct": max_dd_combined,
            "profit_factor": 0.0, "pct_pos_days": c["pct_pos_days"],
            "max_losing_day_streak": c["max_losing_day_streak"], "sharpe_like": c["sharpe_like"],
            "wr": 0.0, "final_equity": round(final_equity, 2), "risk_pct": cfg["RISK_PCT"],
        }, cfg, blend=True, blend_b=blend_cfg)
        mt5.shutdown()
        return {"avg_per_day_span": avg_day, "max_dd_pct": max_dd_combined, **c,
                "final_equity": final_equity, "trades": n_total}


def _append_s31_csv(label, s, cfg, blend=False, blend_b=None):
    path = os.path.join(os.path.dirname(__file__), "s31_backtest_summary.csv")
    is_new = not os.path.exists(path)
    fields = ["timestamp", "label", "blend", "sl_atr_mult_a", "tp_rr_a", "sl_atr_mult_b", "tp_rr_b",
              "risk_pct", "trades", "wr", "avg_per_day_span", "avg_per_month", "max_dd_pct",
              "profit_factor", "pct_pos_days", "max_losing_day_streak", "sharpe_like", "final_equity"]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        w.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "label": label,
            "blend": blend, "sl_atr_mult_a": cfg.get("SL_ATR_MULT"), "tp_rr_a": cfg.get("TP_RR"),
            "sl_atr_mult_b": blend_b.get("SL_ATR_MULT") if blend_b else "",
            "tp_rr_b": blend_b.get("TP_RR") if blend_b else "",
            "risk_pct": cfg.get("RISK_PCT"), "trades": s.get("trades"), "wr": s.get("wr", 0.0),
            "avg_per_day_span": s.get("avg_per_day_span"),
            "avg_per_month": round(s.get("avg_per_day_span", 0.0) * 30, 2),
            "max_dd_pct": s.get("max_dd_pct"), "profit_factor": s.get("profit_factor", 0.0),
            "pct_pos_days": s.get("pct_pos_days"), "max_losing_day_streak": s.get("max_losing_day_streak"),
            "sharpe_like": s.get("sharpe_like"), "final_equity": s.get("final_equity"),
        })
    print(f"  -> appended to {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--spread", type=float, default=DEFAULT_SPREAD)
    ap.add_argument("--risk", type=float, default=S31_DEFAULTS["RISK_PCT"])
    ap.add_argument("--slmult", type=float, default=None)
    ap.add_argument("--rr", type=float, default=None)
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--blend-slmult-b", type=float, default=None)
    ap.add_argument("--blend-rr-b", type=float, default=None)
    args = ap.parse_args()

    cfg = dict(S31_DEFAULTS)
    cfg["RISK_PCT"] = args.risk
    if args.slmult is not None:
        cfg["SL_ATR_MULT"] = args.slmult
    if args.rr is not None:
        cfg["TP_RR"] = args.rr

    blend_cfg = None
    if args.blend_slmult_b is not None:
        blend_cfg = dict(S31_DEFAULTS)
        blend_cfg["RISK_PCT"] = args.risk
        blend_cfg["SL_ATR_MULT"] = args.blend_slmult_b
        blend_cfg["TP_RR"] = args.blend_rr_b if args.blend_rr_b is not None else cfg["TP_RR"]

    run_backtest(cfg, args.days, args.spread, args.label, blend_cfg=blend_cfg)


if __name__ == "__main__":
    main()
