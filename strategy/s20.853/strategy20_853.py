# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.853",
    "name": "Chande Kroll x Pivot Regime Confirm",
    "concept": "194 (Chande Kroll Stop) พลิกฝั่งเข้าเทรดเมื่อมี 294 (Pivot Regime Cross) ตัดเปลี่ยนแนวโน้มใหญ่นำมาก่อนหน้า (CONFIRM)",
    "logic": "194 จับจุดเปลี่ยนเทรนด์จากการทะลุเส้น Chande Kroll แต่เพื่อเพิ่มความมั่นใจในการเข้าเทรดรอบใหญ่ระดับสัปดาห์/เดือน เราจะรอให้เกิดสัญญาณกลับตัวจาก 294 (ราคาตัดข้ามเส้น Pivot กลางของรอบเวลาที่ใหญ่กว่าขึ้นไป/ลงมา เพื่อเปลี่ยน Regime ของเทรนด์) นำร่องมาก่อนหน้านี้ไม่เกิน 5 แท่ง",
    "parents": ["20.194", "20.294"],
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
mod_b = load_strategy("294")

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
