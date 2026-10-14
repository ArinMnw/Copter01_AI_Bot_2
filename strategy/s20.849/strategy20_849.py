# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.849",
    "name": "Chande Kroll x Donchian Confirm",
    "concept": "194 (Chande Kroll Stop) พลิกฝั่งเข้าเทรดเมื่อมี 274 (Donchian Cross) นำมาก่อนหน้า (CONFIRM)",
    "logic": "194 บอกจังหวะเปลี่ยนเทรนด์จากการเบรกเส้น Chande Kroll เพื่อลดปัญหา False Breakout และยืนยันความแข็งแกร่งของเทรนด์ใหญ่ เราจะรอตรวจสอบว่าการเบรกเทรนด์นี้ เกิดขึ้นตามหลัง 274 (การทะลุเส้นกลาง Donchian 20 ที่สอดคล้องกับ Bias หลัก 55) ซึ่งเป็นสัญญาณบอกแนวโน้มที่แข็งแกร่งที่เพิ่งเกิดขึ้นนำร่องมาก่อนภายใน 5 แท่งล่าสุด",
    "parents": ["20.194", "20.274"],
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
mod_b = load_strategy("274")

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
