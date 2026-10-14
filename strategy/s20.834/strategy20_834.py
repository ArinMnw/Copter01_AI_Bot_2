# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.834",
    "name": "Elder Impulse x KST Confirm",
    "concept": "143 (Elder Impulse) เข้าเทรดเมื่อมี 160 (KST Momentum Cross) ตัดเปลี่ยนเทรนด์นำมาก่อนหน้า (CONFIRM)",
    "logic": "143 จับโมเมนตัมเปลี่ยนสีระยะสั้น ซึ่งจะแม่นยำขึ้นถ้ารอบโมเมนตัมใหญ่ (KST ของ 160) เพิ่งมีการ Cross ชี้ทิศทางเดียวกันในไม่เกิน 5 แท่งที่ผ่านมา ทำให้ลด noise ได้ดี",
    "parents": ["20.143", "20.160"],
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

mod_a = load_strategy("143")
mod_b = load_strategy("160")

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
