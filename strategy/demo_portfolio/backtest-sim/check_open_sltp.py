"""
check_open_sltp.py — ตรวจ (และแก้ ถ้าสั่ง --fix) SL/TP ของ position ที่ยังเปิดอยู่ของ
LTS_AVENGERS_ULTRA_SAFE (LTS_AUS) / LTS_AVENGERS_HIGH_RISK (LTS_AHR) เท่านั้น

เหตุผลที่เช็คแบบนี้ปลอดภัย: ทั้งสองพอร์ตนี้ไม่อยู่ใน MANAGED_PORTFOLIOS ของ demo_portfolio.py
(ไม่มี breakeven/trailing/pyramid) — SL/TP ถูก "ฝากไว้กับ broker ตรงๆ" คงที่ตั้งแต่วางออเดอร์
จนกว่าจะปิด (ดู docstring บนสุดของ demo_portfolio.py) ดังนั้นถ้า position.sl/tp ปัจจุบัน
ต่างจาก SL/TP ที่ order แรกตอนเปิด (entry order) เกิน tolerance แปลว่าผิดปกติจริง (เช่น
โดนแก้มือ หรือ broker ปัดค่า) ไม่ใช่พฤติกรรมที่ตั้งใจ — แก้กลับให้ตรงกับค่าตอนเปิดได้อย่างปลอดภัย
(entry order ใช้ detect_s<N>()/detect_lts() ตัวเดียวกับ backtest เป๊ะ ตามที่ demo_portfolio.py
ระบุไว้ จึงถือเป็นค่า "ตรงกับ backtest" อยู่แล้วตั้งแต่ต้น)
"""
import argparse
import os
import sys
from datetime import datetime, timezone, timedelta

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(root_dir)
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import MetaTrader5 as mt5
from run_backtest_sim import connect_to_actual_profile_for_portfolio, ALIASES
import config
import demo_portfolio as dp

PRICE_TOL = 0.05
TARGET_PORTFOLIOS = ["LTS_AVENGERS_ULTRA_SAFE", "LTS_AVENGERS_HIGH_RISK"]


def audit_portfolio(portfolio_name, apply_fix):
    if not connect_to_actual_profile_for_portfolio(portfolio_name):
        return {"portfolio": portfolio_name, "connected": False, "orders": []}

    magic = dp._portfolio_magic(portfolio_name)
    symbol = config.SYMBOL
    positions = mt5.positions_get(symbol=symbol) or []

    bkk = timezone(timedelta(hours=7))
    order_rows = []
    for pos in positions:
        if int(getattr(pos, "magic", 0) or 0) != magic:
            continue

        hist = mt5.history_orders_get(position=pos.ticket) or []
        hist = sorted(hist, key=lambda o: o.time_setup)
        entry_order = hist[0] if hist else None
        if entry_order is None or (entry_order.sl == 0 and entry_order.tp == 0):
            continue

        orig_sl = round(float(entry_order.sl), 2)
        orig_tp = round(float(entry_order.tp), 2)
        cur_sl = round(float(pos.sl), 2)
        cur_tp = round(float(pos.tp), 2)
        sl_diff = abs(orig_sl - cur_sl)
        tp_diff = abs(orig_tp - cur_tp)
        mismatch = sl_diff > PRICE_TOL or tp_diff > PRICE_TOL

        row = {
            "portfolio": portfolio_name,
            "ticket": pos.ticket,
            "comment": pos.comment,
            "type": "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL",
            "open_time": datetime.fromtimestamp(pos.time, tz=timezone.utc).astimezone(bkk).strftime("%Y-%m-%d %H:%M:%S"),
            "orig_sl": orig_sl, "orig_tp": orig_tp,
            "cur_sl": cur_sl, "cur_tp": cur_tp,
            "mismatch": mismatch,
            "fixed": False,
            "retcode": None,
        }

        if mismatch and apply_fix:
            res = mt5.order_send({
                "action": mt5.TRADE_ACTION_SLTP,
                "position": pos.ticket,
                "symbol": symbol,
                "sl": orig_sl,
                "tp": orig_tp,
            })
            row["fixed"] = res is not None and res.retcode == mt5.TRADE_RETCODE_DONE
            row["retcode"] = getattr(res, "retcode", None)

        order_rows.append(row)

    mt5.shutdown()
    return {"portfolio": portfolio_name, "connected": True, "orders": order_rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="Apply SL/TP correction when a mismatch is found (default: audit only)")
    args = ap.parse_args()

    for pf in TARGET_PORTFOLIOS:
        result = audit_portfolio(pf, apply_fix=args.fix)
        print(f"\n=== {pf} (connected={result['connected']}) ===")
        if not result["orders"]:
            print("  no open position with a recorded entry SL/TP")
            continue
        for row in result["orders"]:
            status = "MISMATCH" if row["mismatch"] else "ok"
            fix_note = ""
            if row["mismatch"]:
                fix_note = f" fixed={row['fixed']} retcode={row['retcode']}" if args.fix else " (dry-run, use --fix to apply)"
            print(f"  ticket={row['ticket']} {row['type']} comment={row['comment']} open={row['open_time']} "
                  f"orig(SL={row['orig_sl']},TP={row['orig_tp']}) cur(SL={row['cur_sl']},TP={row['cur_tp']}) -> {status}{fix_note}")


if __name__ == "__main__":
    main()
