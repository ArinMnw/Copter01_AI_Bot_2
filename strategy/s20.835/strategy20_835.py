# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.835",
    "name": "Elder Impulse x KST Filter",
    "concept": "143 (Elder Impulse) เข้าเทรดเมื่อ 160 (KST Momentum) ล่าสุดบอกทิศทางเดียวกัน (FILTER)",
    "logic": "143 จับโมเมนตัมเปลี่ยนสีระยะสั้น การกรองด้วย 160 (KST) ที่คำนวณโมเมนตัมจาก ROC 4 timeframe (10/15/20/30) จะช่วยคัดกรองให้ทิศทางระยะสั้นสอดคล้องกับโมเมนตัมใหญ่ที่ smooth แล้ว เพื่อให้ได้เทรดที่แข็งแรงที่สุด",
    "parents": ["20.143", "20.160"],
    "mix": "FILTER",
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
    
    sig_b_s = pd.Series(sig_b).replace(0, np.nan).ffill().fillna(0)
    
    out[(sig_a == 1) & (sig_b_s == 1)] = 1
    out[(sig_a == -1) & (sig_b_s == -1)] = -1
    return out
