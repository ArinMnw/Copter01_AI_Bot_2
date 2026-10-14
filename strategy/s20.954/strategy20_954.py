# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.954",
    "name": "Rainbow KST x HF Donchian Confirm",
    "concept": "เข้าเทรดด้วยสัญญาณ 854 (Rainbow x KST) เมื่อมีการทะลุกรอบของ 210 (HF Donchian) ภายใน 24 แท่งที่ผ่านมา",
    "logic": "210 เป็นเทคนิค Breakout รอบเล็กที่มีความถี่สูง การเอา 854 ที่เน้นโมเมนตัมและเทรนด์ยาวมาเข้าเทรดหลังเกิด Breakout เล็กนำร่อง (CONFIRM 24 แท่ง) เป็นการยืนยันจังหวะระเบิดของราคาว่าจะมีทิศทางตรงกับเทรนด์ใหญ่",
    "parents": ["20.854", "20.210"],
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
    sB = load_strategy("20.210").generate(df, tf)
    
    sig = np.zeros(len(df), dtype=np.int8)
    
    b_buy = (sB == 1).astype(int)
    b_sell = (sB == -1).astype(int)
    
    k = 24
    b_buy_recent = pd.Series(b_buy).rolling(window=k, min_periods=1).sum() > 0
    b_sell_recent = pd.Series(b_sell).rolling(window=k, min_periods=1).sum() > 0
    
    buy_cond = (sA == 1) & b_buy_recent
    sell_cond = (sA == -1) & b_sell_recent
    
    sig[buy_cond] = 1
    sig[sell_cond] = -1
    return sig
