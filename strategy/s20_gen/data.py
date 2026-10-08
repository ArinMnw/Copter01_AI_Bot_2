# -*- coding: utf-8 -*-
"""data.py — ดึงแท่งราคา XAUUSD จาก MT5 แล้ว freeze เป็น snapshot ใน .cache/

แคมเปญ S20.140–S20.299 ใช้ snapshot เดียวกันทุกตัว เพื่อให้ผลเทียบกันได้ตรงๆ
(ถ้าดึงสดทุกครั้ง ข้อมูลปลายช่วงจะเลื่อนไปเรื่อยๆ ทำให้ตัวเลขข้ามกลยุทธ์ไม่ comparable)

ข้อจำกัดที่รู้แล้ว: terminal ทุกตัวตั้ง maxbars=100000 → M1 ย้อนหลังได้แค่ ~100 วัน
TF อื่น (M5 ขึ้นไป) ได้ครบ 365 วัน+
"""
import os
import sys
import json
import numpy as np
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CACHE = os.path.join(HERE, ".cache")
TFS = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
TF_SEC = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}
DEFAULT_PROFILE = "demo-exness-434237129"


def _connect(profile):
    for p in (ROOT, os.path.join(ROOT, "strategy")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import MetaTrader5 as mt5
    from s20_compare_engine import connect_profile_mt5
    if not connect_profile_mt5(profile, root_dir=ROOT):
        if not mt5.initialize():
            raise RuntimeError("MT5 initialize failed")
    return mt5


def refresh(profile=DEFAULT_PROFILE, days=430):
    mt5 = _connect(profile)
    try:
        names = [s.name for s in (mt5.symbols_get() or [])]
        sym = next((n for n in ("XAUUSDm", "XAUUSD.iux", "XAUUSD") if n in names), None)
        if sym is None:
            raise RuntimeError("ไม่พบ XAUUSD ใน terminal")
        mt5.symbol_select(sym, True)
        si = mt5.symbol_info(sym)
        end = datetime.now(timezone.utc)
        meta = {"symbol": sym, "profile": profile, "point": si.point, "digits": si.digits,
                "contract_size": si.trade_contract_size, "spread_pts": si.spread,
                "swap_long": si.swap_long, "swap_short": si.swap_short, "swap_mode": si.swap_mode,
                "swap_rollover3days": si.swap_rollover3days,
                "fetched_utc": end.strftime("%Y-%m-%d %H:%M:%S"), "bars": {}}
        for tf in TFS:
            # HTF ดึงยาวกว่าเพื่อ warm-up indicator (เช่น SMA200 บน D1) ก่อนช่วงทดสอบ 365 วัน
            tf_days = {"H1": 800, "H4": 1500, "D1": 3000}.get(tf, days)
            parts, t = [], end - timedelta(days=tf_days)
            while t < end:
                t2 = min(t + timedelta(days=30), end)
                r = mt5.copy_rates_range(sym, getattr(mt5, "TIMEFRAME_" + tf), t, t2)
                if r is not None and len(r):
                    parts.append(r)
                t = t2
            a = np.unique(np.concatenate(parts))
            np.save(os.path.join(CACHE, f"XAUUSD_{tf}.npy"), a)
            meta["bars"][tf] = [int(len(a)), int(a[0]["time"]), int(a[-1]["time"])]
            print(f"  {tf}: {len(a)} bars {datetime.utcfromtimestamp(a[0]['time'])} -> {datetime.utcfromtimestamp(a[-1]['time'])}")
        with open(os.path.join(CACHE, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        return meta
    finally:
        mt5.shutdown()


def load_meta():
    p = os.path.join(CACHE, "meta.json")
    if not os.path.exists(p):
        return refresh()
    with open(p, encoding="utf-8") as f:
        return json.load(f)


_BARS = {}


def load_bars(tf):
    if tf not in _BARS:
        p = os.path.join(CACHE, f"XAUUSD_{tf}.npy")
        if not os.path.exists(p):
            refresh()
        _BARS[tf] = np.load(p)
    return _BARS[tf]


if __name__ == "__main__":
    os.makedirs(CACHE, exist_ok=True)
    print(json.dumps({k: v for k, v in refresh().items() if k != "bars"}, indent=2))
