# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.861",
    "name": "Rainbow MA x Elder Confirm",
    "concept": "242 (Rainbow MA) เรียงตัวสมบูรณ์และเข้าเทรดเมื่อมี 248 (Elder Triple Screen) นำมาก่อนหน้า (CONFIRM)",
    "logic": "242 ระบุสภาวะเทรนด์ที่ชัดเจนจากการเรียงตัวของเส้น Rainbow 10 ชั้น เพื่อหาจุดเข้าที่ปลอดภัยและแม่นยำสูง เราจะยืนยันด้วย 248 (Elder Triple Screen ซึ่งมีการกรอง 3 ระดับ: เทรนด์หลัก, การย่อด้วย Stochastic, และการเบรคราคากลับทิศ) โดยต้องพบสัญญาณจาก Elder Triple Screen เกิดขึ้นนำร่องมาก่อนการตั้งลำของ Rainbow ภายใน 5 แท่งล่าสุด",
    "parents": ["20.242", "20.248"],
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
mod_b = load_strategy("248")

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
