# -*- coding: utf-8 -*-
"""เทียบค่า buffer จริงของ indicator GenoSmartSignal (dump โดย DumpGeno.mq5) กับ Python (Indi1_strategy.compute_signals)

ขั้นตอน: 1) ลาก script DumpGeno ไปวางบนชาร์ตของ terminal โปรไฟล์นั้น (สร้าง geno_dump_H1.csv / _M5.csv
ใน MQL5\\Files)  2) python mq5_strategy/indi1/compare_geno_buffers.py [--profile demo-exness-434237129]

Python ใช้หน้าต่างแท่งเท่ากับที่บอทใช้จริง (M5 2500 / H1 700) ส่วน indicator คำนวณย้อน 5000 แท่ง
-> ถ้าต่างกันที่แท่งล่าสุดแปลว่า warm-up/โค้ดไม่ตรง ถ้าตรงทั้งคู่ก็ยืนยันว่า Python = indicator
"""
import argparse
import csv
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BKK = timezone(timedelta(hours=7))


def read_dump(path):
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def num(x):
    return float(x) if x not in ("", None) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="demo-exness-434237129")
    ap.add_argument("--last", type=int, default=400, help="จำนวนแท่งปิดล่าสุดที่เทียบ")
    args = ap.parse_args()
    os.environ["BOT_PROFILE"] = args.profile
    sys.path.insert(0, ROOT)
    os.chdir(ROOT)
    import config
    import MetaTrader5 as mt5
    import strategy_indi1_live as I

    files_dir = os.path.join(ROOT, "profiles", "demo", args.profile, "mt5", "MQL5", "Files")
    if not config.mt5_initialize(mt5):
        print("MT5 init failed")
        return
    sym = config.resolve_mt5_symbol(mt5, "XAUUSD", set_runtime=False)
    info = mt5.symbol_info(sym)
    import time
    tick = mt5.symbol_info_tick(sym)
    off = int(round((float(tick.time) - time.time()) / 3600.0)) * 3600
    to_bkk = lambda raw: datetime.fromtimestamp(int(raw) - off, tz=timezone.utc).astimezone(BKK).strftime("%m-%d %H:%M")
    core = I._load_core()
    cfg = I.core_cfg(rr=2.5, tick_size=info.trade_tick_size, point=info.point)
    tfs = [("H1", mt5.TIMEFRAME_H1, I.HTF_BARS), ("M5", mt5.TIMEFRAME_M5, I.LTF_BARS)]
    all_ok = True
    for name, tf, nbars in tfs:
        path = os.path.join(files_dir, f"geno_dump_{name}.csv")
        if not os.path.exists(path):
            print(f"[{name}] ไม่พบไฟล์ {path} — ยังไม่ได้รัน DumpGeno")
            all_ok = False
            continue
        age = (time.time() - os.path.getmtime(path)) / 60
        rows = read_dump(path)[:-1]                       # ตัดแท่งที่กำลังวิ่ง
        rates = mt5.copy_rates_from_pos(sym, tf, 0, nbars)
        py = core.compute_signals(list(rates[:-1]), cfg)
        ptime = {int(r["time"]): k for k, r in enumerate(rates[:-1])}
        rows = [r for r in rows if int(r["time"]) in ptime][-args.last:]
        # ตัดแท่งที่ Python ยังมองไม่เห็น/ใหม่เกินกว่าไฟล์ dump (กรณีแท่งใหม่ปิดหลัง dump)
        print(f"\n===== {name}: เทียบ {len(rows)} แท่งปิด ({to_bkk(rows[0]['time'])} -> {to_bkk(rows[-1]['time'])} BKK) | ไฟล์ dump อายุ {age:.0f} นาที")
        mism = {k: [] for k in ("BB", "MA", "K", "smart_buy", "smart_sell", "swing_low", "swing_high")}
        for r in rows:
            k = ptime[int(r["time"])]
            fl1, c1, fl2, c2, ker, ck = num(r["fl1"]), num(r["fl1c"]), num(r["fl2"]), num(r["fl2c"]), num(r["ker"]), num(r["kerc"])
            mt = {"BB": ("G" if (fl1 is not None and c1 == 0) else "R" if fl1 is not None else "-"),
                  "MA": ("G" if (fl2 is not None and c2 == 0) else "R" if fl2 is not None else "-"),
                  "K": ("G" if (ker is not None and ck == 0) else "R" if ker is not None else "-")}
            pc = lambda g, rr_: "G" if py[g][k] else ("R" if py[rr_][k] else "-")
            pv = {"BB": pc("g1", "r1"), "MA": pc("g2", "r2"), "K": pc("gk", "rk")}
            for key in ("BB", "MA", "K"):
                if mt[key] != pv[key]:
                    mism[key].append((r["time"], mt[key], pv[key]))
            if (r["buy2"] != "") != bool(py["smart_buy"][k]):
                mism["smart_buy"].append((r["time"], r["buy2"] != "", bool(py["smart_buy"][k])))
            if (r["sell2"] != "") != bool(py["smart_sell"][k]):
                mism["smart_sell"].append((r["time"], r["sell2"] != "", bool(py["smart_sell"][k])))
            for key, col, pk in (("swing_low", "swl", "swing_low"), ("swing_high", "swh", "swing_high")):
                a, b = num(r[col]), py[pk][k]
                if (a is None) != (b != b) or (a is not None and b == b and abs(a - b) > 0.01):
                    mism[key].append((r["time"], a, b))
        for key, lst in mism.items():
            status = "OK  " if not lst else "DIFF"
            all_ok &= not lst
            extra = ""
            if lst:
                extra = " | ต่าง " + str(len(lst)) + " แท่ง ล่าสุด: " + ", ".join(f"{to_bkk(t)} MT5={a} Py={b}" for t, a, b in lst[-3:])
            print(f"  {status} {key:11s}{extra}")
        print("  ล่าสุด 6 แท่ง (MT5 | Python):")
        for r in rows[-6:]:
            k = ptime[int(r["time"])]
            fl1, c1, fl2, c2, ker, ck = num(r["fl1"]), num(r["fl1c"]), num(r["fl2"]), num(r["fl2c"]), num(r["ker"]), num(r["kerc"])
            m = lambda v, c: "-" if v is None else ("G" if c == 0 else "R")
            pc = lambda g, rr_: "G" if py[g][k] else ("R" if py[rr_][k] else "-")
            print(f"    {to_bkk(r['time'])}  MT5 BB={m(fl1, c1)} MA={m(fl2, c2)} K={m(ker, ck)}  |  Py BB={pc('g1', 'r1')} MA={pc('g2', 'r2')} K={pc('gk', 'rk')}")
    mt5.shutdown()
    print("\nRESULT:", "MATCH — Python ตรงกับ indicator จริง" if all_ok else "MISMATCH หรือยังไม่มีไฟล์ dump")


if __name__ == "__main__":
    main()
