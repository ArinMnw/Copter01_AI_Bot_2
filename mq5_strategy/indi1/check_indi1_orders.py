# -*- coding: utf-8 -*-
"""ตรวจออเดอร์ INDI1 (magic 994001) ของบัญชี 2459 แบบอ่านอย่างเดียว

ตรวจต่อออเดอร์: magic/symbol/comment, SL อยู่ถูกฝั่งและห่างไม่ต่ำกว่า buffer, TP = entry +/- RR x ระยะ SL,
lot ตรงกับ Risk % ของ balance ตามระยะ SL (ปัดลงตาม step), Fibo breakeven (ถ้าแท่ง M5 ปิดเลย 50% ของ
entry->TP หลังเข้าไม้ SL ต้องถูกย้ายไป entry +/- 50 จุด)

ใช้: python check_indi1_orders.py [--need 3] [--profile demo-iux-2101182459]
บรรทัดสุดท้ายขึ้นต้นด้วย STATUS: ... และ DONE_OK เมื่อครบ --need ออเดอร์และถูกต้องทั้งหมด
"""
import argparse
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAGIC = 994001
RISK_PCT, RR, BUF_PRICE, BE_FIB, BE_LOCK_PRICE = 0.1, 2.5, 1.0, 0.5, 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--need", type=int, default=3)
    ap.add_argument("--profile", default="demo-iux-2101182459")
    args = ap.parse_args()
    os.environ["BOT_PROFILE"] = args.profile
    sys.path.insert(0, ROOT)
    os.chdir(ROOT)
    import config
    import MetaTrader5 as mt5

    if not config.mt5_initialize(mt5):
        print("STATUS: MT5_INIT_FAILED")
        return
    try:
        # ค่าคงที่จริงจาก config ที่บอทใช้ (กันค่าที่ตั้งในสคริปต์ไม่ตรง)
        risk = float(getattr(config, "INDI1_RISK_PCT", RISK_PCT))
        rr = float(getattr(config, "INDI1_RR", RR))
        buf_price = float(getattr(config, "INDI1_SL_BUFFER_PRICE", BUF_PRICE))
        be_fib = float(getattr(config, "INDI1_BE_FIB", BE_FIB))
        be_lock = float(getattr(config, "INDI1_BE_LOCK_PRICE", BE_LOCK_PRICE))
        sym = config.resolve_mt5_symbol(mt5, "XAUUSD", set_runtime=False)
        info = mt5.symbol_info(sym)
        acct = mt5.account_info()
        tick_size, tick_val = float(info.trade_tick_size), float(info.trade_tick_value_loss or info.trade_tick_value)
        step, point = float(info.volume_step), float(info.point)
        digits = int(info.digits)

        now = datetime.now(timezone.utc)
        _t = mt5.symbol_info_tick(sym)
        # offset เวลาเซิร์ฟเวอร์เทียบ UTC (IUX = +1h, Exness อาจต่างกัน) ปัดเป็นชั่วโมงเต็ม
        srv_off = int(round((float(_t.time) - time.time()) / 3600.0)) * 3600 if _t else 3600
        deals = mt5.history_deals_get(now - timedelta(days=5), now + timedelta(days=1)) or []
        entries = [d for d in deals if d.magic == MAGIC and d.entry == mt5.DEAL_ENTRY_IN]
        # ไม้ที่ยังเปิดอยู่แต่ history ยังไม่อัปเดต
        open_pos = {p.ticket: p for p in (mt5.positions_get(symbol=sym) or []) if p.magic == MAGIC}
        entries.sort(key=lambda d: d.time)

        problems, notes = [], []
        for n, d in enumerate(entries, 1):
            pid = d.position_id
            orders = mt5.history_orders_get(position=pid) or []
            op = next((o for o in orders if o.position_id == pid), None)
            is_buy = d.type == mt5.DEAL_TYPE_BUY
            entry, vol = float(d.price), float(d.volume)
            sl0 = float(op.sl) if op else 0.0
            tp0 = float(op.tp) if op else 0.0
            tag = f"#{n} pos={pid} {'BUY' if is_buy else 'SELL'} lot={vol:.2f} entry={entry:.{digits}f} sl={sl0:.{digits}f} tp={tp0:.{digits}f}"
            errs = []
            if d.symbol != sym:
                errs.append(f"symbol {d.symbol}")
            if not str(d.comment).startswith("M5-INDI1"):
                errs.append(f"comment '{d.comment}'")
            if sl0 <= 0 or tp0 <= 0:
                errs.append("ไม่มี SL/TP")
            else:
                dist = abs(entry - sl0)
                if (is_buy and sl0 >= entry) or ((not is_buy) and sl0 <= entry):
                    errs.append("SL ผิดฝั่ง")
                if dist + 1e-9 < buf_price * 0.98:
                    errs.append(f"SL ใกล้เกิน buffer (dist={dist:.2f})")
                exp_tp = entry + rr * dist if is_buy else entry - rr * dist
                if abs(tp0 - exp_tp) > 0.10:
                    errs.append(f"TP {tp0:.{digits}f} != {exp_tp:.{digits}f} (R:R {rr})")
                exp_lot = math.floor(acct.balance * risk / 100.0 / (dist / tick_size * tick_val) / step + 1e-9) * step
                if abs(vol - exp_lot) > max(step * 1.01, exp_lot * 0.03):
                    errs.append(f"lot {vol:.2f} != คาด {exp_lot:.2f} (risk {risk}% bal {acct.balance:,.0f})")
                # Fibo breakeven: ถ้าแท่ง M5 ปิดเลย fib 50% หลังเข้าไม้ SL ต้องย้ายแล้ว
                level = entry + (tp0 - entry) * be_fib
                bars = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, datetime.fromtimestamp(d.time, tz=timezone.utc) - timedelta(minutes=10), now + timedelta(hours=2)) or []
                crossed = None
                for b in bars:
                    if int(b["time"]) + 300 <= d.time or int(b["time"]) + 300 > time.time() + srv_off - 300:
                        continue  # แท่งที่ปิดก่อนเข้าไม้ / แท่งที่ยังไม่ปิด (time เป็นเวลาเซิร์ฟเวอร์ +1h)
                    c = float(b["close"])
                    if (is_buy and c > level) or ((not is_buy) and c < level):
                        crossed = int(b["time"])
                        break
                p = open_pos.get(pid)
                if p is not None:
                    want = entry + be_lock if is_buy else entry - be_lock
                    moved = abs(float(p.sl) - want) < 0.02
                    if crossed and not moved and time.time() + srv_off - (crossed + 300) > 150:
                        errs.append("แท่งปิดเลย fibo แล้วแต่ SL ยังไม่ถูกย้าย")
                    elif moved:
                        notes.append(f"{tag}: BE ย้าย SL แล้ว -> {float(p.sl):.{digits}f}")
                    elif not crossed:
                        notes.append(f"{tag}: ยังไม่ถึง fibo {be_fib:.0%} ({level:.{digits}f})")
            if errs:
                problems.append((n, tag, errs))
            else:
                notes.append(f"{tag}: OK")
        n_ord = len(entries)
        first = entries[:args.need]
        bad_first = [p for p in problems if p[0] <= args.need]
        for line in notes:
            print("  ", line)
        for n, tag, errs in problems:
            print("  ❌", tag, "|", "; ".join(errs))
        done = n_ord >= args.need and not bad_first
        print(f"STATUS: orders={n_ord}/{args.need} problems={len(problems)} open_indi1={len(open_pos)} "
              f"balance={acct.balance:,.0f} " + ("DONE_OK" if done else ("NEED_FIX" if bad_first else "WAITING")))
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
