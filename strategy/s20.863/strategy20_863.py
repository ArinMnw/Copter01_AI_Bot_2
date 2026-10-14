# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.863",
    "name": "Rainbow MA x Three Inside Confirm",
    "concept": "242 (Rainbow MA) เรียงตัวสมบูรณ์และเข้าเทรดเมื่อมี 261 (Three Inside Confirmation) นำมาก่อนหน้า (CONFIRM)",
    "logic": "242 ตรวจสอบระดับเทรนด์ที่แข็งแกร่งผ่านการเรียงตัวของ Rainbow MA ทั้ง 10 ชั้น เพื่อหาจังหวะการเปิดออเดอร์ที่มีนัยยะสำคัญทาง Price Action เราจะใช้รูปแบบ 261 (Three Inside Up/Down ซึ่งเป็นการยืนยันการกลับตัวของ Harami) มาเป็นตัว CONFIRM โดยจังหวะเบรคกลับตัวนี้ต้องเกิดขึ้นนำร่องมาก่อนการตั้งลำของ Rainbow ภายใน 5 แท่งล่าสุด",
    "parents": ["20.242", "20.261"],
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
mod_b = load_strategy("261")

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
