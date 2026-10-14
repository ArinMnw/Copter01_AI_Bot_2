# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.965",
    "name": "Mixed 854 x Hikkake Confirm",
    "concept": "เข้าเทรดด้วยสัญญาณ 854 (Rainbow x KST) เฉพาะเมื่อเกิด 255 (Hikkake False Breakout) นำร่องใน 12 แท่ง",
    "logic": "854 อาศัยการเรียงตัวของ Rainbow และความแรงจาก KST ในการเข้าเทรดตามเทรนด์ การที่เราเอา 255 มาใช้เพื่อหาตัวยืนยัน (CONFIRM) จะเป็นการจำกัดการเข้าเฉพาะจุดที่เทรนด์เกิดจากการเขย่าราคาหลอก (False Breakout) แล้วพลิกกลับมาในทิศทางของเทรนด์ใหญ่ ซึ่งจะเป็นจุดที่มีแรงซื้อขายสนับสนุนมหาศาลจากฝั่งที่ติดกับดัก",
    "parents": ["20.854", "20.255"],
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
    sB = load_strategy("20.255").generate(df, tf)
    
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
