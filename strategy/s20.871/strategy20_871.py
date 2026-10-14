# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.871",
    "name": "Rainbow MA x HalfTrend Filter",
    "concept": "242 (Rainbow MA) เรียงตัวสมบูรณ์และเข้าเทรดเมื่อมี 292 (HalfTrend) สวิงไปในทิศทางเดียวกัน (FILTER)",
    "logic": "242 บอกทิศทางหลักที่แข็งแกร่งด้วยการวางตัวของแนวรับแนวต้านแบบไดนามิกจากเส้น Rainbow 10 ชั้น เพื่อหาจังหวะเข้าเทรดที่ปลอดภัยและว่องไวตามรอบสวิงระยะสั้น เราจะนำ 292 (HalfTrend ซึ่งตรวจจับการสวิงของราคา High/Low ได้อย่างเฉียบขาด) มาเป็นตัว FILTER กรองทิศทาง ช่วยให้ได้จุดเข้าตอนที่การแกว่งตัวของราคาสอดคล้องกับเทรนด์หลักพอดี",
    "parents": ["20.242", "20.292"],
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
mod_b = load_strategy("292")

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    
    out = np.zeros(len(df), dtype=np.int8)
    
    sig_b_s = pd.Series(sig_b).replace(0, np.nan).ffill().fillna(0)
    
    out[(sig_a == 1) & (sig_b_s == 1)] = 1
    out[(sig_a == -1) & (sig_b_s == -1)] = -1
    return out
