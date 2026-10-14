# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.858",
    "name": "Rainbow MA x Seasonality Confirm",
    "concept": "242 (Rainbow MA) เรียงตัวสมบูรณ์และเข้าเทรดเมื่อมี 184 (Hour Seasonality) ยืนยัน Bias ช่วงเวลานั้นนำมาก่อนหน้า (CONFIRM)",
    "logic": "242 อาศัยการเรียงตัวของเส้นค่าเฉลี่ย Rainbow MA 10 ชั้นเพื่อระบุเทรนด์หลัก เพื่อเพิ่มความน่าจะเป็นในการเข้าเทรดให้ถูกช่วงเวลา เราจะพึ่งพาสัญญาณ 184 (Seasonality ระหว่างวัน ที่ใช้สถิติย้อนหลัง 60 วัน) มาเป็นตัว CONFIRM โดยให้มีสัญญาณเชิงสถิติตามเวลาสนับสนุนในทิศทางเดียวกันนำร่องมาก่อนภายใน 5 แท่งล่าสุด",
    "parents": ["20.242", "20.184"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def load_strategy(sid):
    path = os.path.join(os.path.dirname(__file__), "..", f"s20.{sid}", f"strategy20_{sid}.py")
    spec = importlib.util.spec_from_file_location(f"s20_{sid}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

mod_a = load_strategy("242")
mod_b = load_strategy("184")

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    
    out = np.zeros(len(df), dtype=np.int8)
    
    sig_b_s = pd.Series(sig_b)
    # CONFIRM k=5
    b_long_recent = sig_b_s.rolling(window=5, min_periods=1).max() == 1
    b_short_recent = sig_b_s.rolling(window=5, min_periods=1).min() == -1
    
    out[(sig_a == 1) & b_long_recent] = 1
    out[(sig_a == -1) & b_short_recent] = -1
    return out
