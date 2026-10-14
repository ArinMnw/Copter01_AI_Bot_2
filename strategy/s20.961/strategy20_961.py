# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.961",
    "name": "Mixed 937 x Rainbow Filter",
    "concept": "เข้าเทรดด้วยสัญญาณ 937 (BB Breakout x Bulls/Bears) เฉพาะเมื่อ 242 (Rainbow MA) มีเทรนด์ตรงกันในแท่งเดียวกัน",
    "logic": "937 อาศัยพลังจากการ Breakout ของ Bollinger Band เราจึงนำ 242 (Rainbow) มาเป็นตัวกรองทิศทางหลัก (FILTER) เพื่อให้แน่ใจว่า Breakout นั้นเกิดสอดคล้องกับแนวโน้มเส้นค่าเฉลี่ยระยะยาว ไม่ใช่แค่การสะบัดหลอกสวนเทรนด์",
    "parents": ["20.937", "20.242"],
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
    sA = load_strategy("20.937").generate(df, tf)
    sB = load_strategy("20.242").generate(df, tf)
    
    sig = np.zeros(len(df), dtype=np.int8)
    
    buy_cond = (sA == 1) & (sB == 1)
    sell_cond = (sA == -1) & (sB == -1)
    
    sig[buy_cond] = 1
    sig[sell_cond] = -1
    return sig
