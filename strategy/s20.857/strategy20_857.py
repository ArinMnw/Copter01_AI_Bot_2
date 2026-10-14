# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.857",
    "name": "Rainbow MA x Weekly Retest Confirm",
    "concept": "242 (Rainbow MA) เรียงตัวสมบูรณ์และเข้าเทรดเมื่อมี 183 (Weekly-Open Retest) เป็นสัญญาณทดสอบแนวนำมาก่อนหน้า (CONFIRM)",
    "logic": "242 ชี้ถึงความแข็งแกร่งของเทรนด์จากการเรียงตัวเป็นตับของ Rainbow MA 10 ชั้น เพื่อหาจุดเข้าที่ปลอดภัยและมีนัยยะ เราจะจับจังหวะเข้าเทรดเฉพาะเมื่อมี 183 (การที่ราคาย่อตัวลงมาทดสอบราคาเปิดของสัปดาห์แล้วเกิดการเด้งกลับไปในทิศทางเดิม) เกิดขึ้นนำร่องเป็นสัญญาณยืนยันล่วงหน้าภายใน 5 แท่งล่าสุด",
    "parents": ["20.242", "20.183"],
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
mod_b = load_strategy("183")

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
