# -*- coding: utf-8 -*-
"""จำลอง S421 แบบ "พอร์ตจริง" — เหมือน strategy/s420/portfolio_sim_s420.py
ทุกจุด (รันทั้ง 5 TF พร้อมกันบนไทม์ไลน์เดียว + จำลอง MAX_POS_PER_LEG stacking
+ คำนวณสัญญาณแบบขนานหลาย process) แค่สลับไปใช้ backtest_s421/strategy421 +
PINE_V4_CFG (rate ของ S421 เอง) — ดู docstring เต็มใน portfolio_sim_s420.py

Usage:
    python portfolio_sim_s421.py --days 5
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time as _time
from datetime import timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_S420_DIR = os.path.join(_ROOT, "strategy", "s420")
for _p in (_ROOT, _S420_DIR, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backtest_s421 import (
    BKK, LOOKBACK_BARS, PINE_V4_CFG,
    bar_time_to_bkk, compute_signals_parallel, fmt_bkk, parse_bkk, prepare_rates,
)

import config as _config

MAX_POS_PER_LEG = _config.demo_portfolio_max_pos_per_leg("S421-O")  # 2026-08-14: ตอนนี้ = 1
TF_LIST = ("M1", "M5", "M15", "M30", "H1")


def simulate_leg(tf_name, bars, start_index, cfg, spread, lot, max_pos_per_leg=MAX_POS_PER_LEG,
                  n_workers=None):
    detector_cfg = dict(PINE_V4_CFG)
    detector_cfg.update(cfg or {})
    cancel_bars = int(detector_cfg.get("CANCEL_BARS", 3))
    contract_multiplier = 100.0 * lot

    t_sig = _time.time()
    precomputed_signals = compute_signals_parallel(
        bars, tf_name, detector_cfg, start_index, len(bars) - 1,
        LOOKBACK_BARS[tf_name], n_workers,
    )
    print(f"  [{tf_name}] คำนวณสัญญาณขนานเสร็จใน {_time.time() - t_sig:.0f}s "
          f"({len(precomputed_signals)} แท่ง)", flush=True)

    positions = []
    pending = None
    trades = []
    events = []  # {"time","type"("open"/"close"),"tf","side","pnl"(close only)}

    for index in range(start_index, len(bars) - 1):
        sig = precomputed_signals[index - start_index]
        if sig is None:
            continue
        bull_name, bear_name, fib_ew, fib_tp, fib_sl = sig[:5]
        event = bars[index]

        for pos in positions[:]:
            side = pos["side"]
            hit_tp = hit_sl = False
            if side > 0:
                if event["low"] <= pos["sl"]:
                    hit_sl = True
                elif event["high"] >= pos["tp"]:
                    hit_tp = True
            else:
                if event["high"] >= pos["sl"]:
                    hit_sl = True
                elif event["low"] <= pos["tp"]:
                    hit_tp = True
            if hit_tp or hit_sl:
                exit_price = pos["tp"] if hit_tp else pos["sl"]
                pnl = (side * (exit_price - pos["entry"]) - spread) * contract_multiplier
                exit_time = bar_time_to_bkk(bars[index + 1]["time"])
                trades.append({
                    "tf": tf_name, "direction": "BUY" if side > 0 else "SELL",
                    "entry": round(pos["entry"], 2), "entry_time": fmt_bkk(pos["entry_time"]),
                    "exit": round(exit_price, 2), "exit_time": fmt_bkk(exit_time),
                    "outcome": "TP" if hit_tp else "SL", "profit": round(pnl, 2),
                })
                events.append({"time": exit_time, "type": "close", "tf": tf_name, "side": side, "pnl": pnl})
                positions.remove(pos)

        if pending is not None:
            side = pending["side"]
            filled = False
            fill_price = None
            if side > 0 and event["low"] <= pending["level"]:
                fill_price = min(pending["level"], event["open"])
                filled = True
            elif side < 0 and event["high"] >= pending["level"]:
                fill_price = max(pending["level"], event["open"])
                filled = True
            if filled:
                entry_time = bar_time_to_bkk(event["time"])
                positions.append({"side": side, "entry": fill_price, "sl": pending["sl"],
                                   "tp": pending["tp"], "entry_time": entry_time})
                events.append({"time": entry_time, "type": "open", "tf": tf_name, "side": side})
                pending = None
            elif index >= pending["cancel_index"]:
                pending = None

        if pending is None and len(positions) < max_pos_per_leg:
            if bull_name is not None and fib_sl < fib_ew:
                pending = {"side": 1, "level": fib_ew, "sl": fib_sl, "tp": fib_tp,
                           "cancel_index": index + cancel_bars}
            elif bear_name is not None and fib_sl > fib_ew:
                pending = {"side": -1, "level": fib_ew, "sl": fib_sl, "tp": fib_tp,
                           "cancel_index": index + cancel_bars}

    return trades, events


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", help="BKK ISO datetime เริ่ม (เช่น 2026-08-09)")
    parser.add_argument("--end", help="BKK ISO datetime สิ้นสุด; default = ตอนนี้")
    parser.add_argument("--days", type=int, default=5, help="จำนวนวันย้อนหลังจาก --end")
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--lot", type=float, default=0.01, help="lot คงที่ต่อไม้ (ทุก leg เท่ากัน)")
    parser.add_argument("--max-pos-per-leg", type=int, default=MAX_POS_PER_LEG,
                         help="override cap ต่อ leg (default = ค่าจาก config.py ปัจจุบัน) "
                              "ใส่เลขสูงๆ เช่น 999 เพื่อจำลอง 'ไม่มี cap'")
    parser.add_argument("--csv", default=os.path.join(_HERE, "s421_portfolio_trades.csv"))
    args = parser.parse_args()

    end_bkk = parse_bkk(args.end)
    start_bkk = parse_bkk(args.start) if args.start else end_bkk - timedelta(days=args.days)
    cfg = {"TP_RATE": 1.618}  # ตรงกับ strategy421.DEFAULT_CFG ที่ live ใช้จริง

    all_trades = []
    all_events = []
    for tf_name in TF_LIST:
        print(f"\n===== simulate leg {tf_name} =====")
        t0 = _time.time()
        try:
            bars, start_index = prepare_rates(tf_name, start_bkk, end_bkk)
        except RuntimeError as exc:
            print(f"ข้าม {tf_name}: {exc}")
            continue
        trades, events = simulate_leg(tf_name, bars, start_index, cfg, args.spread, args.lot,
                                       max_pos_per_leg=args.max_pos_per_leg)
        for t in trades:
            t["leg"] = f"S421-O_{tf_name}"
        all_trades.extend(trades)
        all_events.extend(events)
        print(f"{tf_name}: {len(trades)} ไม้ปิด, ใช้เวลา {_time.time()-t0:.0f}s")

    all_events.sort(key=lambda e: e["time"])

    # --- นับจำนวนไม้เปิดพร้อมกัน (portfolio-wide) ตลอดเส้นเวลา ---
    open_count = 0
    open_by_side = {1: 0, -1: 0}
    max_concurrent = 0
    max_concurrent_time = None
    max_same_dir = 0
    max_same_dir_time = None
    for e in all_events:
        if e["type"] == "open":
            open_count += 1
            open_by_side[e["side"]] += 1
            if open_count > max_concurrent:
                max_concurrent = open_count
                max_concurrent_time = e["time"]
            same_dir = max(open_by_side.values())
            if same_dir > max_same_dir:
                max_same_dir = same_dir
                max_same_dir_time = e["time"]
        else:
            open_count -= 1
            open_by_side[e["side"]] -= 1

    # --- equity curve จาก close events (เรียงตามเวลาปิดจริง) ---
    close_events = sorted((e for e in all_events if e["type"] == "close"), key=lambda e: e["time"])
    equity = peak = max_drawdown = 0.0
    for e in close_events:
        equity += e["pnl"]
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    net_profit = sum(e["pnl"] for e in close_events)

    print("\n\n===== สรุปพอร์ต S421 ทั้ง 5 TF พร้อมกัน (MAX_POS_PER_LEG="
          f"{args.max_pos_per_leg}, lot={args.lot} ต่อไม้) =====")
    print(f"ช่วง: {fmt_bkk(start_bkk)} - {fmt_bkk(end_bkk)}")
    print(f"ไม้ปิดทั้งหมด: {len(all_trades)}")
    print(f"Net P&L: {net_profit:.2f} USD | Max Drawdown: {max_drawdown:.2f} USD")
    print(f"จำนวนไม้เปิดพร้อมกันสูงสุด (รวมทุก TF/leg): {max_concurrent} ไม้ "
          f"(ตอน {max_concurrent_time})")
    print(f"จำนวนไม้ทิศเดียวกันที่เปิดพร้อมกันสูงสุด: {max_same_dir} ไม้ (ตอน {max_same_dir_time})")

    with open(args.csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=(
            "leg", "tf", "direction", "entry_time", "entry", "exit_time", "exit",
            "outcome", "profit",
        ))
        writer.writeheader()
        writer.writerows(sorted(all_trades, key=lambda t: t["entry_time"]))
    print(f"\nเขียน {len(all_trades)} ไม้ลง {args.csv}")


if __name__ == "__main__":
    main()
