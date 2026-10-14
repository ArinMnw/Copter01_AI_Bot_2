# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.855",
    "name": "Rainbow MA x STC Confirm",
    "concept": "242 (Rainbow MA) เรียงตัวสมบูรณ์และเข้าเทรดเมื่อมี 163 (Schaff Trend Cycle) ตัดโซนนำมาก่อนหน้า (CONFIRM)",
    "logic": "242 อาศัยการเรียงตัวของเส้นเฉลี่ย 10 ชั้นแบบ Rainbow เพื่อตรวจจับเทรนด์ที่มีเสถียรภาพ เพื่อหาจังหวะการเข้าที่สอดคล้องกับรอบ Cycle จริงๆ เราจะยืนยันด้วย 163 (Schaff Trend Cycle ซึ่งนำเอา MACD มาปรับให้เป็น Cycle 0-100) โดยสัญญาณทะลุโซน 25 (ขึ้น) หรือ 75 (ลง) ของ STC จะต้องเกิดขึ้นนำร่องมาก่อนการเรียงตัวของ Rainbow ไม่เกิน 5 แท่ง",
    "parents": ["20.242", "20.163"],
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
mod_b = load_strategy("163")

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
