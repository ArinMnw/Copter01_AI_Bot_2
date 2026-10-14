# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.964",
    "name": "Mixed 732 x Curvature Filter",
    "concept": "เข้าเทรดด้วยสัญญาณ 732 เฉพาะเมื่อทิศทางของ 277 (Curvature Turn) สอดคล้องในแท่งเดียวกัน",
    "logic": "732 อาศัยการตัดกันของ HMA ที่กรองด้วย Z-Score ซึ่งเป็นกลยุทธ์ตามเทรนด์รอบกว้าง การเพิ่ม 277 มาเป็นตัวกรองทิศทางในปัจจุบัน (FILTER) จะช่วยคัดออกเฉพาะจุดที่ HMA ขัดแย้งกับความโค้งของโครงสร้างราคา ทำให้ทนทานต่อช่วงตลาด Sideway ได้ดียิ่งขึ้น",
    "parents": ["20.732", "20.277"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def load_strategy(sid):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", f"s20.{sid.split('.')[1]}", f"strategy{sid.replace('.', '_')}.py")
    spec = importlib.util.spec_from_file_location(f"strategy_{sid.replace('.', '_')}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def generate(df, tf):
    sA = load_strategy("20.732").generate(df, tf)
    sB = load_strategy("20.277").generate(df, tf)
    
    sig = np.zeros(len(df), dtype=np.int8)
    
    buy_cond = (sA == 1) & (sB == 1)
    sell_cond = (sA == -1) & (sB == -1)
    
    sig[buy_cond] = 1
    sig[sell_cond] = -1
    return sig
