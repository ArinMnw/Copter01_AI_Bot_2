# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.865",
    "name": "Rainbow MA x NY Lunch Filter",
    "concept": "242 (Rainbow MA) เรียงตัวสมบูรณ์และเข้าเทรดเมื่อมี 265 (NY Lunch Reversal) ชี้จังหวะสวนเทรนด์ระยะสั้น (FILTER)",
    "logic": "242 จับโมเมนตัมหลักจากความแข็งแกร่งและเสถียรภาพของ Rainbow MA 10 ชั้น แต่เพื่อให้ได้จุดเข้าที่ได้เปรียบสูงสุด เราจะใช้ 265 (NY Lunch Reversal) มาเป็นตัว FILTER ช่วยบังคับให้ต้องเกิดแรงขายทำกำไรระยะสั้นตามเวลา (Time-based Pullback) ก่อนถึงจะอนุญาตให้เข้าเทรดไปในทิศทางเดียวกับเทรนด์",
    "parents": ["20.242", "20.265"],
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

mod_a = load_strategy("242")
mod_b = load_strategy("265")

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    
    out = np.zeros(len(df), dtype=np.int8)
    
    sig_b_s = pd.Series(sig_b).replace(0, np.nan).ffill().fillna(0)
    
    out[(sig_a == 1) & (sig_b_s == 1)] = 1
    out[(sig_a == -1) & (sig_b_s == -1)] = -1
    return out
