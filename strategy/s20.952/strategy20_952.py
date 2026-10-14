# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.952",
    "name": "Rainbow KST x HMA Turn Confirm",
    "concept": "เข้าเทรดด้วยสัญญาณ 854 (Rainbow x KST) เมื่อมีการคอนเฟิร์มรอบการพักตัวของราคาจาก 158 (HMA-21 Turn) ภายใน 12 แท่งที่ผ่านมา",
    "logic": "854 ให้สัญญาณบอกความแข็งแกร่งของเทรนด์ใหญ่ผ่าน Rainbow MA ที่ซ้อนทับกัน และแรงหนุนจาก KST เราใช้ 158 (HMA-21 วกกลับในทิศเดียวกับ HMA-100) ที่เกิดก่อนหน้าเพื่อบ่งบอกว่าเป็นการวกกลับเข้าสู่เทรนด์หลังจบการพักตัว (CONFIRM 12 แท่ง)",
    "parents": ["20.854", "20.158"],
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
    sA = load_strategy("20.854").generate(df, tf)
    sB = load_strategy("20.158").generate(df, tf)
    
    sig = np.zeros(len(df), dtype=np.int8)
    # CONFIRM: A and (B happened recently)
    # create rolling window of B
    # Since B has +1, -1, 0, we can use rolling max for buy and min for sell
    
    b_buy = (sB == 1).astype(int)
    b_sell = (sB == -1).astype(int)
    
    # We want B to have fired within last 12 bars (including current bar)
    k = 12
    # rolling sum > 0 means it fired at least once
    b_buy_recent = pd.Series(b_buy).rolling(window=k, min_periods=1).sum() > 0
    b_sell_recent = pd.Series(b_sell).rolling(window=k, min_periods=1).sum() > 0
    
    buy_cond = (sA == 1) & b_buy_recent
    sell_cond = (sA == -1) & b_sell_recent
    
    sig[buy_cond] = 1
    sig[sell_cond] = -1
    return sig
