# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.848",
    "name": "Chande Kroll x NY Lunch Filter",
    "concept": "194 (Chande Kroll Stop) พลิกฝั่งเข้าเทรดเมื่อมี 265 (NY Lunch Reversal) สนับสนุนอยู่ในขณะนั้น (FILTER)",
    "logic": "194 จับจังหวะราคาเบรกเส้น Chande Kroll เปลี่ยนฝั่งเทรนด์ เพื่อเพิ่มความได้เปรียบในเชิงพฤติกรรมเวลาของตลาด (Seasonality) เราจะ FILTER โดยอนุญาตให้เข้าเทรดก็ต่อเมื่อการพลิกกลับนี้มีทิศทางสอดคล้องกับสัญญาณ NY Lunch Reversal (แรงขายทำกำไรพักเที่ยงนิวยอร์ก) ที่กำลังเกิดอิทธิพลอยู่ในช่วงเวลาเดียวกัน",
    "parents": ["20.194", "20.265"],
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
mod_b = load_strategy("265")

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    
    out = np.zeros(len(df), dtype=np.int8)
    
    sig_b_s = pd.Series(sig_b).replace(0, np.nan).ffill().fillna(0)
    
    out[(sig_a == 1) & (sig_b_s == 1)] = 1
    out[(sig_a == -1) & (sig_b_s == -1)] = -1
    return out
