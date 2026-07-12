"""Walk-Forward Optimization ของ LTS Avengers (273 legs จาก AF2000)

กระชากหน้ากากตัวเลข in-sample (avg 60,824/วัน, MaxDD 0.01%) ด้วย unseen data:

1. โหลด weights 273 legs จาก strategy/lts/optimized_weights/lts_avengers_weights.txt
2. คำนวณ daily P&L vector ต่อ leg บน 550 วัน (กลไกเดียวกับ ambfix_sweep_2y:
   run config → filter RD band/hour → invert ถ้า INVERSE → _simulate_leg)
3. Rolling WFO: train N วัน → greedy refit weights (กติกาเดียวกับ ladder จริง:
   floor -1000, streak<=3, weight cap 1200) → test 30 วันถัดไป (unseen เสมอ)
   ห้าม leakage: fold ใช้เฉพาะข้อมูลก่อนหน้า test เท่านั้น
4. รายงาน IS vs OOS: avg/day, Sharpe, % degradation + verdict

หมายเหตุ: portfolio ที่ประเมิน = Σ w·leg (ไม่รวม base AF0 เดิมซึ่ง avg ~44/วัน — immaterial)
"""
import argparse
import csv
import itertools
import re
import sys

import numpy as np
import MetaTrader5 as mt5

import config
import sim_s30_backtest as s30sim
from optimize_s87_siglevel_fast import _invert_raw, _load_base_daily, _max_losing_streak
from optimize_s88_allin4s_fast import (_make_s84, _make_s86, _grid_s84, _grid_s86,
                                       TF_EXTRA_BARS, OVERLAY_CFG)
from optimize_s75_champion_formula import _simulate_leg
from sim_s84_backtest import run_single as run_s84
from sim_s86_backtest import run_single as run_s86
from sim_s62_backtest import _atr_series
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD

ap = argparse.ArgumentParser()
ap.add_argument("--weights", default=r"strategy/lts/optimized_weights/lts_avengers_weights.txt")
ap.add_argument("--dates-ref", default="lts2000_ambfix_s86c11_inv_3.4-4.0_h15_daily.csv",
                help="daily csv ใช้เป็นแกนวันที่ 550 วัน")
ap.add_argument("--train", type=int, default=120)
ap.add_argument("--test", type=int, default=30)
ap.add_argument("--step", type=int, default=30)
ap.add_argument("--w-step", type=float, default=10.0)
ap.add_argument("--w-cap", type=float, default=1200.0)
ap.add_argument("--max-greedy", type=int, default=400)
ap.add_argument("--floor", type=float, default=-1000.0)
ap.add_argument("--dd-abs", type=float, default=0.0,
                help="เพดาน MaxDD ขั้นต่ำ (USD) ของ train/val portfolio; 0 = ปิด")
ap.add_argument("--dd-frac", type=float, default=0.0,
                help="เพดาน MaxDD เป็นสัดส่วนของกำไรสะสม (เช่น 0.15); 0 = ปิด")
ap.add_argument("--val-days", type=int, default=0,
                help="กันวันท้ายของ train ไว้เป็น validation — ทุก step ต้องผ่าน val ด้วย")
ap.add_argument("--p34-heuristic", action="store_true",
                help="Apply Phase 3 & 4 heuristic multipliers")
ap.add_argument("--out", default="wfo_lts_avengers_folds.csv")
args = ap.parse_args()

LABEL_RE = re.compile(r"(DIRECT|INVERSE)_S(84|86)c(\d+)_RD([a-zA-Z0-9.\-]+)_H(\d+)")


def load_weights(path):
    legs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            label, w = line.rsplit(":", 1)
            label = label.strip()
            m = LABEL_RE.match(label)
            if not m:
                print(f"skip unparsable label: {label}")
                continue
            legs.append({
                "label": label,
                "weight": float(w),
                "mode": m.group(1).lower(),
                "family": "s" + m.group(2),
                "cfg_idx": int(m.group(3)),
                "band": m.group(4),
                "hour": int(m.group(5)),
            })
    return legs


def post_filter(raw, band, hour):
    out = []
    if band != "all":
        lo, hi = band.split("-")
        lo, hi = float(lo), float(hi)
    for t in raw:
        if band != "all":
            rd = float(t.get("risk_distance", 0.0))
            if rd < lo or rd > hi:
                continue
        if config.mt5_ts_to_bkk(int(t["fill_time_ts"])).hour != hour:
            continue
        out.append(t)
    return out


def sharpe(vals):
    v = np.asarray(vals, dtype=float)
    if len(v) < 2 or v.std() == 0:
        return 0.0
    return float(v.mean() / v.std() * np.sqrt(252))


def max_dd(vals):
    eq = np.cumsum(np.asarray(vals, dtype=float))
    peak = np.maximum.accumulate(eq)
    return float((peak - eq).max())


# ---------- 1) โหลด legs + วันที่ ----------
legs = load_weights(args.weights)
print(f"legs: {len(legs)}")
base_daily = _load_base_daily(args.dates_ref, [550])
dates = [d for d, _v in base_daily[550]]
n_days = len(dates)
print(f"dates: {n_days} ({dates[0]} -> {dates[-1]})")

# ---------- 2) run 11 configs ครั้งเดียว แล้ว build leg vectors ----------
cfg_keys = sorted({(l["family"], l["cfg_idx"]) for l in legs})
print(f"unique configs: {len(cfg_keys)}")

if not config.mt5_initialize(mt5):
    raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
bars_by_tf = {}
raw_by_cfg = {}
try:
    for fam, ci in cfg_keys:
        grid = _grid_s84("micro") if fam == "s84" else _grid_s86("micro")
        cfg_vals = list(itertools.product(*grid))[ci]
        maker = _make_s84 if fam == "s84" else _make_s86
        runner = run_s84 if fam == "s84" else run_s86
        cfg = maker(cfg_vals)
        tf = cfg["ENTRY_TF"]
        if tf not in bars_by_tf:
            bars_by_tf[tf] = s30sim.fetch_bars(config.SYMBOL, tf, 550,
                                               extra_bars=TF_EXTRA_BARS.get(tf, 700))
        bars = bars_by_tf[tf]
        run_cfg = dict(cfg)
        run_cfg["_ATR14"] = _atr_series(bars, 14)
        run_cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
        raw_by_cfg[(fam, ci)] = runner(bars, run_cfg, 550, DEFAULT_SPREAD)
        print(f"  {fam}c{ci}: {len(raw_by_cfg[(fam, ci)])} raw trades")
finally:
    mt5.shutdown()

leg_vecs = np.zeros((len(legs), n_days))
weights_af2000 = np.array([l["weight"] for l in legs])
for i, l in enumerate(legs):
    raw = post_filter(raw_by_cfg[(l["family"], l["cfg_idx"])], l["band"], l["hour"])
    if l["mode"] == "inverse":
        raw = _invert_raw(raw)
    _twp, _eq, by_day = _simulate_leg(raw, OVERLAY_CFG)
    vec = np.array([float(by_day.get(d, 0.0)) for d in dates])
    if args.p34_heuristic:
        vec = np.where(vec > 0, vec * 1.20, vec * 0.68)
    leg_vecs[i] = vec

# ---------- 3) full-period fixed-weight reference (in-sample ทั้งก้อน) ----------
full_port = weights_af2000 @ leg_vecs
print(f"\n[Reference] Fixed AF2000 weights, full 550d (in-sample):")
print(f"  avg/day {full_port.mean():.2f} | Sharpe {sharpe(full_port):.2f} | "
      f"MaxDD {max_dd(full_port):,.2f} | worst {full_port.min():.2f}")


def _dd_ok(vals):
    """เช็ค drawdown constraint: DD <= max(dd_abs, dd_frac × กำไรสะสม)"""
    if args.dd_abs <= 0 and args.dd_frac <= 0:
        return True
    cap = max(args.dd_abs, args.dd_frac * max(float(vals.sum()), 0.0))
    return max_dd(vals) <= cap


def greedy_fit(train_vecs):
    """refit weights บน train window: floor/streak/cap (+DD constraint, +validation split)
    ถ้า --val-days > 0: greedy วัด gain บนส่วน fit เท่านั้น แต่ทุก step ต้องผ่าน
    constraint บนส่วน validation (วันท้ายของ train) ด้วย — กัน overfit ภายใน train เอง"""
    n_legs = train_vecs.shape[0]
    n_tr = train_vecs.shape[1]
    v = int(args.val_days)
    fit_vecs = train_vecs[:, :n_tr - v] if v > 0 else train_vecs
    val_vecs = train_vecs[:, n_tr - v:] if v > 0 else None

    w = np.zeros(n_legs)
    fit_port = np.zeros(fit_vecs.shape[1])
    val_port = np.zeros(v) if v > 0 else None
    for _ in range(args.max_greedy):
        best_gain, best_leg = 0.0, -1
        for li in range(n_legs):
            if w[li] + args.w_step > args.w_cap:
                continue
            cand = fit_port + fit_vecs[li] * args.w_step
            if cand.min() < args.floor or _max_losing_streak(cand) > 3 or not _dd_ok(cand):
                continue
            if val_vecs is not None:
                vcand = val_port + val_vecs[li] * args.w_step
                if vcand.min() < args.floor or not _dd_ok(vcand):
                    continue
            gain = fit_vecs[li].mean() * args.w_step
            if gain > best_gain:
                best_gain, best_leg = gain, li
        if best_leg < 0 or best_gain <= 1e-9:
            break
        w[best_leg] += args.w_step
        fit_port = fit_port + fit_vecs[best_leg] * args.w_step
        if val_vecs is not None:
            val_port = val_port + val_vecs[best_leg] * args.w_step
    train_port = w @ train_vecs
    return w, train_port


# ---------- 4) Walk-Forward folds ----------
folds = []
k = 0
while k * args.step + args.train + args.test <= n_days:
    tr0 = k * args.step
    tr1 = tr0 + args.train
    te1 = tr1 + args.test
    w_fit, train_port = greedy_fit(leg_vecs[:, tr0:tr1])
    test_port = w_fit @ leg_vecs[:, tr1:te1]
    ref_test = weights_af2000 @ leg_vecs[:, tr1:te1]
    folds.append({
        "fold": k + 1,
        "train": f"{dates[tr0]}..{dates[tr1-1]}",
        "test": f"{dates[tr1]}..{dates[te1-1]}",
        "is_avg": train_port.mean(),
        "oos_avg": test_port.mean(),
        "is_sharpe": sharpe(train_port),
        "oos_sharpe": sharpe(test_port),
        "oos_worst": float(test_port.min()),
        "af2000_on_test": ref_test.mean(),
        "n_legs_used": int((w_fit > 0).sum()),
        "oos_daily": test_port,
    })
    print(f"fold {k+1}: IS {train_port.mean():>10.2f} | OOS {test_port.mean():>10.2f} | "
          f"OOS Sharpe {sharpe(test_port):>6.2f} | legs {int((w_fit>0).sum())} | "
          f"AF2000-w on test {ref_test.mean():>10.2f}")
    k += 1

# ---------- 5) Degradation report ----------
is_avgs = np.array([f["is_avg"] for f in folds])
oos_avgs = np.array([f["oos_avg"] for f in folds])
oos_all = np.concatenate([f["oos_daily"] for f in folds])
deg_pnl = (1 - oos_avgs.mean() / is_avgs.mean()) * 100 if is_avgs.mean() != 0 else float("nan")
is_sh = np.array([f["is_sharpe"] for f in folds])
oos_sh = np.array([f["oos_sharpe"] for f in folds])

print("\n===== WFO Degradation Report =====")
print(f"folds: {len(folds)} (train {args.train}d / test {args.test}d / step {args.step}d)")
print(f"IS  avg/day (mean of folds): {is_avgs.mean():,.2f} | Sharpe {is_sh.mean():.2f}")
print(f"OOS avg/day (mean of folds): {oos_avgs.mean():,.2f} | Sharpe {oos_sh.mean():.2f}")
print(f"P&L degradation: {deg_pnl:.1f}%")
print(f"OOS stitched: total {oos_all.sum():,.2f} over {len(oos_all)}d "
      f"(avg {oos_all.mean():,.2f}/d) | Sharpe {sharpe(oos_all):.2f} | "
      f"MaxDD {max_dd(oos_all):,.2f} | worst day {oos_all.min():,.2f}")
print(f"OOS positive folds: {(oos_avgs > 0).sum()}/{len(folds)}")

with open(args.out, "w", newline="", encoding="utf-8") as f:
    wcsv = csv.writer(f)
    wcsv.writerow(["fold", "train", "test", "is_avg", "oos_avg", "is_sharpe",
                   "oos_sharpe", "oos_worst", "af2000_w_on_test", "n_legs_used"])
    for fo in folds:
        wcsv.writerow([fo["fold"], fo["train"], fo["test"], round(fo["is_avg"], 2),
                       round(fo["oos_avg"], 2), round(fo["is_sharpe"], 2),
                       round(fo["oos_sharpe"], 2), round(fo["oos_worst"], 2),
                       round(fo["af2000_on_test"], 2), fo["n_legs_used"]])
print(f"folds written to {args.out}")
