# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.852",
    "name": "Chande Kroll x HalfTrend Confirm",
    "concept": "194 (Chande Kroll Stop) พลิกฝั่งเข้าเทรดเมื่อมี 292 (HalfTrend) เปลี่ยนทิศนำมาก่อนหน้า (CONFIRM)",
    "logic": "194 จับจังหวะกลับตัวจากการเบรกเส้น Chande Kroll แต่เพื่อเพิ่มความมั่นใจในการระบุเทรนด์ เราจะใช้ 292 (HalfTrend ซึ่งติดตามโครงสร้าง Max Low / Min High เพื่อหาการเปลี่ยนรอบ) มาช่วยยืนยันโครงสร้าง โดยอนุญาตให้เข้าเทรดก็ต่อเมื่อสัญญาณพลิกเทรนด์จาก HalfTrend เพิ่งเกิดขึ้นนำร่องมาก่อนภายใน 5 แท่งล่าสุด",
    "parents": ["20.194", "20.292"],
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

mod_a = load_strategy("194")
mod_b = load_strategy("292")

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
