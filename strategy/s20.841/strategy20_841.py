# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.841",
    "name": "Chande Kroll x Weekly Open Confirm",
    "concept": "194 (Chande Kroll Stop Flip) พลิกฝั่งเข้าเทรดเมื่อมี 183 (Weekly-Open Bias Retest) เด้งออกจากราคาเปิดสัปดาห์มาก่อนหน้า (CONFIRM)",
    "logic": "194 บอกจุดเปลี่ยนเทรนด์จากการเบรกเส้น Chande Kroll Stop แต่เพื่อลดสวิงหลอก การกลับตัวนี้จะถูก CONFIRM ว่ามีนัยสำคัญก็ต่อเมื่อราคายังอยู่ในรอบของแรงผลักจากการเด้งแนวราคาเปิดสัปดาห์ (Weekly-Open Bias Retest ของ 183) ที่เพิ่งเกิดขึ้นในช่วง 5 แท่งที่ผ่านมา ทำให้รอบนี้มีโอกาสเป็นเทรนด์หลักของสัปดาห์สูง",
    "parents": ["20.194", "20.183"],
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
mod_b = load_strategy("183")

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
