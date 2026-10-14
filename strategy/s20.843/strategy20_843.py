# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.843",
    "name": "Chande Kroll x Qstick Confirm",
    "concept": "194 (Chande Kroll Stop Flip) พลิกฝั่งเข้าเทรดเมื่อมีแรงซื้อ/ขายสุทธิจากเนื้อเทียน 200 (Qstick) ชี้ทิศทางนำมาก่อนหน้า (CONFIRM)",
    "logic": "194 จับจังหวะราคาเบรกเส้น Chande Kroll เปลี่ยนฝั่ง เพื่อลดสวิงหลอก การทะลุจะถูกยอมรับก็ต่อเมื่อถูก CONFIRM โดย 200 (Qstick) ว่ามีแรงสะสมจากเนื้อเทียน (Body Pressure) ที่ตัดเส้นศูนย์นำร่องมาก่อนหน้านี้ไม่เกิน 5 แท่ง เพื่อเป็นเครื่องยืนยันโมเมนตัมที่แท้จริง",
    "parents": ["20.194", "20.200"],
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
mod_b = load_strategy("200")

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
