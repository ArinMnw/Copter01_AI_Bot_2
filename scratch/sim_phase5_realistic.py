"""
sim_phase5_realistic.py  (v2 — ใช้ raw cache โดยตรง)
=======================================================
Phase 5: Per-Trade Floating Loss Cap — Realistic Simulation

ตรวจ Maximum Adverse Excursion (MAE) ด้วย bar data จริงต่อแต่ละ trade
เพื่อประเมินว่า Phase 5 จะตัด trade ไหนก่อน TP/SL บ้าง

MAE คำนวณจาก:
  BUY  → worst floating PnL = (bar_low  - entry) / pt * lot * LOT_MULT
  SELL → worst floating PnL = (entry - bar_high) / pt * lot * LOT_MULT
"""
import sys, os, pickle
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

import config
config.IN_BACKTEST = True
import MetaTrader5 as mt5
import demo_portfolio as dp
from optimize_s88_allin4s_fast import _make_s84, _make_s86, _grid_s84, _grid_s86
import itertools

if not mt5.initialize():
    print("MT5 init failed"); sys.exit(1)

BKK = timezone(timedelta(hours=7))
SYMBOL = config.SYMBOL
POINT = 0.01
LOT_MULT = 100  # 1 lot = 100 USD per 1.0 price move

TF_MAP = {
    "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1,
}

CACHE_FILE = "strategy/demo_portfolio/backtest-sim/raw_trades_cache.pkl"


def load_cache():
    with open(CACHE_FILE, "rb") as f:
        return pickle.load(f)


def pnl_per_lot_per_point(lot):
    return lot * LOT_MULT * POINT


def calc_pnl(entry, exit_price, signal, lot):
    pt = pnl_per_lot_per_point(lot)
    if signal == "BUY":
        return (exit_price - entry) / POINT * pt
    else:
        return (entry - exit_price) / POINT * pt


def get_bars_for_period(tf_str, fill_ts, exit_ts, bar_cache):
    bars = bar_cache.get(tf_str, [])
    return [b for b in bars if fill_ts <= b["time"] <= exit_ts]


def simulate_phase5(portfolio_name, thresholds, days=550):
    print(f"{'='*70}")
    print(f"  PHASE 5 REALISTIC — {portfolio_name}  ({days} days)")
    print(f"{'='*70}")

    cache = load_cache()

    actual_name = portfolio_name
    keys = dp.PORTFOLIOS.get(actual_name, [])
    legs = [dp.AF_DEFS[k] for k in keys if k in dp.AF_DEFS]
    if not legs:
        print(f"  No legs found"); return

    # ─── ดึง bar cache สำหรับทุก TF ─────────────────────────────────────────
    unique_tfs = set(leg["cfg"]["ENTRY_TF"] for leg in legs)
    bar_cache = {}
    for tf_str in unique_tfs:
        mt5_tf = TF_MAP.get(tf_str)
        if not mt5_tf:
            continue
        # 550 days * 288 bars/day (M5) = 158400 bars. Let's fetch 300,000
        bars = mt5.copy_rates_from_pos(SYMBOL, mt5_tf, 0, 300000)
        if bars is not None:
            bar_cache[tf_str] = [
                {"time": int(b["time"]), "high": float(b["high"]), "low": float(b["low"])}
                for b in sorted(bars, key=lambda x: x["time"])
            ]

    # ─── รวม raw trades ตาม leg definition ─────────────────────────────────
    all_trades = []
    for leg in legs:
        cache_key = (leg["family"], leg["cfg_idx"], leg["cfg"]["ENTRY_TF"], days, None, None)
        raw = cache.get(cache_key, [])
        if not raw:
            continue

        rd_min = leg.get("rd_min")
        rd_max = leg.get("rd_max")
        fill_hour = leg.get("hour")
        weight = leg.get("weight", 1.0)
        mode = leg.get("mode", "direct")

        for t in raw:
            rd = float(t.get("risk_distance", 0))
            if rd_min is not None and rd < rd_min: continue
            if rd_max is not None and rd > rd_max: continue
            if fill_hour is not None:
                fill_dt = datetime.fromtimestamp(int(t["fill_time_ts"]), tz=BKK)
                if fill_dt.hour != fill_hour: continue

            if "entry" not in t:
                continue

            # Handle inverse mode
            signal = t.get("signal", "BUY")
            if mode == "inverse":
                signal = "SELL" if signal == "BUY" else "BUY"
                sl, tp = t.get("tp", 0), t.get("sl", 0)
                outcome = "SL" if t.get("outcome") == "TP" else ("TP" if t.get("outcome") == "SL" else t.get("outcome",""))
            else:
                sl, tp = t.get("sl", 0), t.get("tp", 0)
                outcome = t.get("outcome", "")

            lot = weight  # weight IS the effective lot for these legs
            entry = float(t["entry"])
            exit_price = float(t.get("exit_price", sl if outcome == "SL" else tp))

            all_trades.append({
                "tf": leg["cfg"]["ENTRY_TF"],
                "signal": signal,
                "fill_ts": int(t["fill_time_ts"]),
                "exit_ts": int(t["exit_time_ts"]),
                "entry": entry,
                "sl": float(sl),
                "tp": float(tp),
                "exit_price": exit_price,
                "outcome": outcome,
                "lot": lot,
                "base_pnl": calc_pnl(entry, exit_price, signal, lot),
            })

    total = len(all_trades)
    print(f"  Total trades: {total}")
    if total == 0:
        print("  No trades found"); return

    # ─── Baseline ──────────────────────────────────────────────────────────
    baseline_pnls = [t["base_pnl"] for t in all_trades]
    tot0 = sum(baseline_pnls)
    sl_c = sum(1 for t in all_trades if t["outcome"] == "SL")
    tp_c = sum(1 for t in all_trades if t["outcome"] == "TP")
    worst0 = min(baseline_pnls)

    print(f"\n  [BASELINE — Phase 5 OFF]")
    print(f"    TP={tp_c}  SL={sl_c}")
    print(f"    Total PnL : {tot0:+,.2f} USD")
    print(f"    Win Rate  : {tp_c/total*100:.1f}%")
    print(f"    Worst SL  : {worst0:+,.2f} USD")

    # ─── คำนวณ MAE ต่อ trade ───────────────────────────────────────────────
    print(f"\n  Computing MAE for {total} trades using bar data...")
    maes = []
    no_bar_count = 0
    for t in all_trades:
        bars = get_bars_for_period(t["tf"], t["fill_ts"], t["exit_ts"], bar_cache)
        if not bars:
            no_bar_count += 1
            maes.append(None)
            continue
        lot = t["lot"]
        entry = t["entry"]
        pt = pnl_per_lot_per_point(lot)
        min_fl = 0.0
        for b in bars:
            if t["signal"] == "BUY":
                fl = (b["low"] - entry) / POINT * pt
            else:
                fl = (entry - b["high"]) / POINT * pt
            if fl < min_fl:
                min_fl = fl
        maes.append(min_fl)

    bars_found = total - no_bar_count
    print(f"  MAE computed: {bars_found}/{total} trades have bar data")
    if no_bar_count > 0:
        print(f"  (Trades without bar data use baseline PnL as-is)")

    # ─── Phase 5 Simulation ────────────────────────────────────────────────
    print(f"\n  [PHASE 5 REALISTIC SIMULATION]")
    print(f"  {'Threshold':>12}  {'Total PnL':>16}  {'vs Baseline':>14}  "
          f"{'Cut TP->Loss':>12}  {'Cut SL->Less':>12}  {'Win%':>6}")
    print(f"  {'-'*80}")

    for threshold in thresholds:
        th = -abs(threshold)
        new_pnls = []
        cut_tp = 0  # TP trades that MAE hit threshold → converted to -threshold
        cut_sl = 0  # SL trades that loss > threshold → capped at -threshold
        no_change = 0

        for t, mae, base_pnl in zip(all_trades, maes, baseline_pnls):
            if mae is None:
                new_pnls.append(base_pnl)
                no_change += 1
                continue

            if mae < th:  # MAE went below threshold
                new_pnls.append(th)
                if t["outcome"] == "TP":
                    cut_tp += 1
                elif t["outcome"] == "SL":
                    cut_sl += 1
                else:
                    no_change += 1
            else:
                new_pnls.append(base_pnl)
                no_change += 1

        tot = sum(new_pnls)
        diff = tot - tot0
        diff_pct = diff / abs(tot0) * 100 if tot0 else 0
        wins = sum(1 for p in new_pnls if p > 0)
        wr = wins / len(new_pnls) * 100

        print(f"  {th:>12,.0f}  {tot:>16,.2f}  {diff:>+13,.2f}({diff_pct:+.0f}%)  "
              f"{cut_tp:>12}  {cut_sl:>12}  {wr:>6.1f}%")

    print()


# ─── Main ──────────────────────────────────────────────────────────────────
portfolios_cfg = [
    ("LTS_AVENGERS_ULTRA_SAFE", [200, 500, 1000, 2000, 5000]),
    ("LTS_AVENGERS_HIGH_RISK",  [2000, 5000, 10000, 20000, 50000]),
]

for pf_name, thresholds in portfolios_cfg:
    simulate_phase5(pf_name, thresholds, days=550)

mt5.shutdown()
print("Done.")
