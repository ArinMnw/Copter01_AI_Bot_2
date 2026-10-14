# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.839",
    "name": "Chande Kroll x Schaff Confirm",
    "concept": "194 (Chande Kroll Stop Flip) เข้าเทรดเมื่อ 163 (Schaff Trend Cycle) เพิ่งพลิกบอกเทรนด์ใหม่นำมาก่อน (CONFIRM)",
    "logic": "194 จับจังหวะที่ราคาเบรกเส้น Chande Kroll กลับทิศทาง แต่การพลิกฝั่งนี้จะแข็งแรงที่สุดเมื่อเกิดตามหลังรอบโมเมนตัมของ 163 (STC) ที่เพิ่งพลิก cycle กลับตัวนำมาก่อนไม่เกิน 5 แท่ง เพื่อเป็นการยืนยันความแข็งแกร่งของเทรนด์ระยะกลาง",
    "parents": ["20.194", "20.163"],
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
