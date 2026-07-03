import argparse
import sys, os
import subprocess
from datetime import datetime, timedelta

script_dir   = os.path.dirname(os.path.abspath(__file__))
strategy_dir = os.path.dirname(script_dir)
root_dir     = os.path.dirname(os.path.dirname(strategy_dir))

sys.path.insert(0, strategy_dir)
sys.path.insert(0, root_dir)

import MetaTrader5 as mt5
from mt5_utils import connect_mt5
import config
from sim_core import run_sim

config.S20_12_ENABLED = True
for tf in config.S20_12_TF_ENABLED:
    config.S20_12_TF_ENABLED[tf] = True


def parse_args():
    parser = argparse.ArgumentParser(description="Backtest S20.12 Candle Strength")
    parser.add_argument("--tf",       type=str,   default="all", help="Timeframe: all | M1 | M1,M5,M15 | [M1,M5,M15,M30,H1]")
    parser.add_argument("--symbol",   type=str,   default="",    help="Symbol (default: profile SYMBOL)")
    parser.add_argument("--days",     type=int,   default=0,     help="Days to backtest (0 = run multiple)")
    parser.add_argument("--compound", type=float, default=2.0,   help="Risk percentage for compounding (default 2)")
    parser.add_argument("--start",    type=str,   default=None,  help="Start time dd-MM-yyyy HH:mm (BKK) — วิ่งจากเวลานี้จนถึงปัจจุบัน (override --days)")
    parser.add_argument("--end",      type=str,   default=None,  help="End time dd-MM-yyyy HH:mm (BKK) — จำกัดขอบเขตท้าย ถ้าไม่ระบุ = ปัจจุบัน")
    parser.add_argument("--compare",  action="store_true",       help="รัน compare_mt5_orders.py อัตโนมัติหลัง backtest เสร็จ")
    return parser.parse_args()


def main():
    args = parse_args()

    if not connect_mt5():
        print("MT5 initialize failed")
        return

    args.symbol = config.profile_symbol(args.symbol or config.SYMBOL, mt5, set_runtime=True)
    mt5.symbol_select(args.symbol, True)

    if not mt5.symbol_info(args.symbol):
        print(f"Symbol {args.symbol} not found")
        mt5.shutdown()
        return

    start_dt_bkk = None
    end_dt_bkk   = None
    if args.end:
        end_dt_bkk = datetime.strptime(args.end, "%d-%m-%Y %H:%M")
    if args.start:
        start_dt_bkk = datetime.strptime(args.start, "%d-%m-%Y %H:%M")
        days_list = ["custom"]
    elif args.days > 0:
        days_list = [args.days]
    else:
        days_list = [30, 60, 90, 120, 180]

    for days in days_list:
        if start_dt_bkk is not None:
            _start = start_dt_bkk
        else:
            _end   = end_dt_bkk or datetime.now()
            _start = _end - timedelta(days=days)
        run_sim(args.symbol, _start, end_dt_bkk, tf=args.tf, compound=args.compound)

    mt5.shutdown()

    # ── รัน compare อัตโนมัติถ้าใส่ --compare ──────────────────────────────
    if args.compare:
        print("\n" + "=" * 60)
        print("▶ รัน compare_mt5_orders.py...")
        compare_cmd = [sys.executable, os.path.join(script_dir, "compare_mt5_orders.py")]
        if args.start:
            compare_cmd += ["--start", args.start]
        if args.end:
            compare_cmd += ["--end", args.end]
        subprocess.run(compare_cmd)


if __name__ == "__main__":
    main()
