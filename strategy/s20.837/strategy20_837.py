# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.837",
    "name": "Chande Kroll x KST Confirm",
    "concept": "194 (Chande Kroll Stop Flip) เข้าเทรดเมื่อ 160 (KST Momentum Cross) ยืนยันมาก่อนใน 5 แท่ง (CONFIRM)",
    "logic": "194 จับจุด Trailing Stop แบบ Chande-Kroll ที่ราคาเพิ่งพลิกฝั่ง (Flip) แต่เพื่อให้รอดจากการโดนสวิงหลอก การ breakout พลิกฝั่งนั้นจะต้องเกิดตามหลังโมเมนตัม KST (160) ที่เพิ่งสะสมพลังและเกิดการ Cross ชี้ทิศเดียวกันมาก่อน (CONFIRM)",
    "parents": ["20.194", "20.160"],
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
