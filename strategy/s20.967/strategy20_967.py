# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.967",
    "name": "Mixed 512 x Rainbow Filter",
    "concept": "เข้าเทรดด้วยสัญญาณ 512 (MACD Div x HalfTrend) เฉพาะเมื่อสอดคล้องกับ 242 (Rainbow MA) ในแท่งนั้น",
    "logic": "512 อาศัย Divergence ในการจับการกลับตัว ซึ่งมักจะเป็นจุดเริ่มเทรนด์ใหม่ แต่เพื่อหลีกเลี่ยง False Reversal เราจึงเสริม 242 (Rainbow) เป็นตัวกรอง (FILTER) ให้แน่ใจว่าค่าเฉลี่ยระยะกลางและยาวตอบสนองทิศทางนั้นแล้วในแท่งเดียวกัน เป็นการเข้าที่รัดกุมขึ้น",
    "parents": ["20.512", "20.242"],
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
    sA = load_strategy("20.512").generate(df, tf)
    sB = load_strategy("20.242").generate(df, tf)
    
    sig = np.zeros(len(df), dtype=np.int8)
    
    buy_cond = (sA == 1) & (sB == 1)
    sell_cond = (sA == -1) & (sB == -1)
    
    sig[buy_cond] = 1
    sig[sell_cond] = -1
    return sig
