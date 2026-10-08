# -*- coding: utf-8 -*-
"""v2_zone_ltf_trigger.py
S20.300 v2 — ออกแบบใหม่เพื่อแก้บั๊ก "fill ก่อนแท่งสัญญาณปิด" ของ run_s20_300_m5_verified.py (v1)
โดยไม่ต้องรอแท่ง TF ใหญ่ปิด (ซึ่งทำให้สัญญาณเน่าเมื่อรอนาน) — ดู 2026-10-03 ใน memory/project
สำหรับเหตุผลที่ fill ก่อนปิดเป็นการรู้อนาคต และทำไมดีไซน์นี้แก้ได้ถูกต้องตามกฎข้อ 2

หลักการ: แยก "โซน" ออกจาก "สัญญาณยืนยัน"
  - โซน: จาก TF ใหญ่ (H4,H3,H2,H1,M30,M20,M15,M12) เอาเฉพาะคอลัมน์ shift(1)/shift(2) ที่มาจากแท่ง
    ที่ปิดไปแล้วก่อนหน้าเท่านั้น (swing high/low, session H/L, FVG, Fibo, Value Area, PDH/PDL)
    ไม่แตะ is_spring/is_utad/OB/BPR/absorption/IFVG/breaker เพราะต้องใช้ข้อมูลแท่ง TF ใหญ่ที่ยังไม่ปิด
  - สัญญาณยืนยัน: วัดไส้/close/volume จากแท่ง M5 ที่ปิดแล้วจริง (ไม่ยืมจากแท่ง TF ใหญ่ที่ยังก่อตัว)
    entry/SL คำนวณจาก M5 แท่งนั้น -> ไม่ต้องรอ TF ใหญ่ปิดเลย

Robustness ที่ผ่านแล้ว (365 วัน XAUUSD.iux, พารามิเตอร์ default ในไฟล์นี้):
  - Walk-forward (IS70%/OOS30%): PF 1.78 -> 1.65 (strategy/backtest-summary/s20_300_v2_walk_forward.md)
  - Rolling walk-forward 6 ช่วง: ทุกช่วงบวก PF 1.54-2.14 (s20_300_v2_rolling_walk_forward.md)
  - Sensitivity (ข้อ 14): PF 1.55-1.90 ทุกค่าที่ขยับ ไม่มี knife-edge (s20_300_v2_sensitivity_test.md)

ยังไม่ทำ: grid search หลายพารามิเตอร์พร้อมกัน, ทดสอบข้ามปี/สินทรัพย์อื่น, ยังไม่ขึ้น live/demo
"""
import sys, os
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from goal_s20_53_to_100 import run_simulation, init_mt5, compute_indicators  # noqa: E402
from run_master_s20_marathon_201_to_300 import make_stages  # noqa: E402

ZONE_TFS = ["H4", "H3", "H2", "H1", "M30", "M20", "M15", "M12"]
ZONE_COLS = ["swing_low_12", "swing_high_12", "asian_low", "asian_high",
             "fvg_bull_zone", "fvg_bear_zone", "fibo_discount_382", "fibo_premium_618",
             "val_proxy", "vah_proxy", "pdl", "pdh"]

# ค่า default ที่ผ่าน walk-forward/rolling/sensitivity แล้ว (ดู docstring ด้านบน)
DEFAULT_CFG = dict(min_vol=1.17, min_wick=0.14, retest_depth=0.125, sl_mult=0.195,
                   tp_r=13.43, stages=make_stages(55))


def fetch_data(symbol, start_dt, now_dt):
    """ดึงราคาจาก MT5: โซน TF ใหญ่ทั้ง 8 ตัว + M5 (ต้อง mt5.initialize() ไว้ก่อนเรียก)"""
    rates_zone = {tf: mt5.copy_rates_range(symbol, getattr(mt5, f"TIMEFRAME_{tf}"), start_dt, now_dt) for tf in ZONE_TFS}
    m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 75000)
    return rates_zone, m5


def build_merged_zones(rates_zone, m5):
    """คำนวณ indicator ของ M5 เอง + โซนของทุก TF ใหญ่ แล้ว merge_asof (backward) เข้ากับ M5
    คืน (m5_df, merged_per_tf) — merged_per_tf[tf] = m5_df + คอลัมน์ z_* ของโซน TF นั้น
    """
    m5_df = compute_indicators(m5, True, True, True, fvg_depth=5)
    merged_per_tf = {}
    for tf in ZONE_TFS:
        zdf = compute_indicators(rates_zone[tf], True, True, True, fvg_depth=5)[["time"] + ZONE_COLS].copy()
        zdf = zdf.rename(columns={c: f"z_{c}" for c in ZONE_COLS})
        merged_per_tf[tf] = pd.merge_asof(m5_df.sort_values("time"), zdf.sort_values("time"), on="time", direction="backward")
    return m5_df, merged_per_tf


def generate_setups(merged_per_tf, cfg=DEFAULT_CFG, zone_tfs=ZONE_TFS):
    """สร้างสัญญาณ: สวีปเข้าโซนของ TF ใหญ่ (ค่า z_* ที่ merge มาแล้ว ปลอดภัยเพราะมาจากแท่งปิดก่อนหน้า)
    + ยืนยันด้วยไส้/close/volume ของแท่ง M5 เอง entry/SL มาจาก M5 เท่านั้น
    รวมสัญญาณจากทุก TF ใน zone_tfs แล้ว dedup ซ้ำ (time, signal) เก็บตัวแรกที่เจอ
    """
    all_setups = []
    for tf in zone_tfs:
        recs = merged_per_tf[tf].to_dict("records")
        for cur in recs[45:]:
            atr = cur["atr"]
            if pd.isna(atr) or atr <= 0.05 or cur["range"] < 0.45 * atr or cur["vol_ratio"] < cfg["min_vol"]:
                continue
            swept_low = (cur["low"] <= cur.get("z_swing_low_12", np.nan)) or (cur["low"] <= cur.get("z_asian_low", np.nan)) or \
                        (not pd.isna(cur.get("z_fvg_bull_zone")) and cur["low"] <= cur["z_fvg_bull_zone"]) or \
                        (not pd.isna(cur.get("z_fibo_discount_382")) and cur["low"] <= cur["z_fibo_discount_382"]) or \
                        (not pd.isna(cur.get("z_val_proxy")) and cur["low"] <= cur["z_val_proxy"]) or \
                        (not pd.isna(cur.get("z_pdl")) and cur["low"] <= cur["z_pdl"])
            swept_high = (cur["high"] >= cur.get("z_swing_high_12", np.nan)) or (cur["high"] >= cur.get("z_asian_high", np.nan)) or \
                         (not pd.isna(cur.get("z_fvg_bear_zone")) and cur["high"] >= cur["z_fvg_bear_zone"]) or \
                         (not pd.isna(cur.get("z_fibo_premium_618")) and cur["high"] >= cur["z_fibo_premium_618"]) or \
                         (not pd.isna(cur.get("z_vah_proxy")) and cur["high"] >= cur["z_vah_proxy"]) or \
                         (not pd.isna(cur.get("z_pdh")) and cur["high"] >= cur["z_pdh"])
            if not (swept_low or swept_high):
                continue
            mw = cfg["min_wick"]
            has_wick_buy = (cur["lower_wick_pct"] >= mw) or (cur["lower_wick"] >= 1.1 * cur["body"])
            has_wick_sell = (cur["upper_wick_pct"] >= mw) or (cur["upper_wick"] >= 1.1 * cur["body"])
            closed_high = cur["close"] >= (cur["low"] + 0.45 * cur["range"])
            closed_low = cur["close"] <= (cur["high"] - 0.45 * cur["range"])
            sig = "BUY" if (swept_low and has_wick_buy and closed_high) else \
                  ("SELL" if (swept_high and has_wick_sell and closed_low) else None)
            if not sig:
                continue
            sl_buf = max(cfg["sl_mult"] * atr, 0.22)
            ad = cfg["retest_depth"]
            entry = round(cur["low"] + ad * cur["lower_wick"], 2) if sig == "BUY" else round(cur["high"] - ad * cur["upper_wick"], 2)
            sl = round(cur["low"] - sl_buf, 2) if sig == "BUY" else round(cur["high"] + sl_buf, 2)
            risk = entry - sl if sig == "BUY" else sl - entry
            if risk > 0:
                all_setups.append({"time": int(cur["time"]), "signal": sig, "entry": entry, "sl": sl,
                                    "risk": risk, "atr": atr, "tf": "M5"})
    seen = set()
    dedup = []
    for s in sorted(all_setups, key=lambda x: x["time"]):
        k = (s["time"], s["signal"])
        if k in seen:
            continue
        seen.add(k)
        dedup.append(s)
    return dedup


def run_backtest(m5, setups, cfg=DEFAULT_CFG):
    """รัน pessimistic SL-first sequential sim ผ่าน engine กลาง (goal_s20_53_to_100.run_simulation)"""
    m5_times = [int(r["time"]) for r in m5]
    return run_simulation(m5, m5_times, setups, tp_r=cfg["tp_r"], stages=cfg["stages"])
