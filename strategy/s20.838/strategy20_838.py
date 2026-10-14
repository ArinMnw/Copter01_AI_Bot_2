# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.838",
    "name": "Chande Kroll x Ultimate Osc Filter",
    "concept": "194 (Chande Kroll Stop Flip) เข้าเทรดเมื่อ 161 (Ultimate Osc Reversal) ล่าสุดบอกทิศทางเดียวกัน (FILTER)",
    "logic": "194 จะจับจังหวะที่ราคาเบรกเส้น Chande Kroll กลับทิศทาง แต่เพื่อป้องกันการเปลี่ยนฝั่งหลอกกลางทาง จะใช้ 161 มาช่วย FILTER โดยจะเทรดก็ต่อเมื่อการเปลี่ยนฝั่งนั้นสอดคล้องกับจังหวะที่ราคาเพิ่งดีดออกจากโซนสุดโต่ง (Oversold/Overbought) ของ Ultimate Oscillator (7/14/28) เพื่อยืนยันแรงส่ง",
    "parents": ["20.194", "20.161"],
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

mod_a = load_strategy("194")
mod_b = load_strategy("161")

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    
    out = np.zeros(len(df), dtype=np.int8)
    
    sig_b_s = pd.Series(sig_b).replace(0, np.nan).ffill().fillna(0)
    
    out[(sig_a == 1) & (sig_b_s == 1)] = 1
    out[(sig_a == -1) & (sig_b_s == -1)] = -1
    return out
