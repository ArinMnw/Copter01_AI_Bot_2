# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.955",
    "name": "Mixed 471 x 277 CONFIRM",
    "concept": "เข้าเทรดตาม 471 (Triple MA Breakout x HMA Turn) เฉพาะเมื่อมีการเปลี่ยนความโค้ง 277 (Curvature Turn) ในระยะ 12 แท่ง",
    "logic": "471 ให้จุดเข้าที่มีประสิทธิภาพด้วยการผสาน Breakout เข้ากับการวกกลับของเส้นค่าเฉลี่ย เรายกระดับความแม่นยำด้วยการรอสัญญาณนำร่องจากการเร่งตัวของเทรนด์ผ่านความโค้ง 277 (Quadratic Regression) ภายใน 12 แท่งล่าสุด (CONFIRM) เพื่อกัน false breakout",
    "parents": ["20.471", "20.277"],
    "mix": "CONFIRM",
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
    sA = load_strategy("20.471").generate(df, tf)
    sB = load_strategy("20.277").generate(df, tf)
    
    sig = np.zeros(len(df), dtype=np.int8)
    
    b_buy = (sB == 1).astype(int)
    b_sell = (sB == -1).astype(int)
    
    k = 12
    b_buy_recent = pd.Series(b_buy).rolling(window=k, min_periods=1).sum() > 0
    b_sell_recent = pd.Series(b_sell).rolling(window=k, min_periods=1).sum() > 0
    
    buy_cond = (sA == 1) & b_buy_recent
    sell_cond = (sA == -1) & b_sell_recent
    
    sig[buy_cond] = 1
    sig[sell_cond] = -1
    return sig
