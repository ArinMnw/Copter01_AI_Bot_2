# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.968",
    "name": "Mixed 689 x Hikkake Confirm",
    "concept": "เข้าเทรดด้วยสัญญาณ 689 (HMA x Rainbow) เฉพาะเมื่อเกิดพฤติกรรม 255 (Hikkake False Breakout) นำร่องใน 12 แท่ง",
    "logic": "689 ผสมผสานความไวของ HMA เข้ากับแนวโน้มหลักของ Rainbow การเพิ่ม 255 (Hikkake) เข้ามาเป็นตัวยืนยันนำร่อง (CONFIRM) จะช่วยให้สัญญาณ 689 ทำงานเฉพาะตอนที่มีการทำ False Breakout เขย่าตลาดเสร็จแล้ว ทำให้ได้จุดเข้าที่มีแรงส่งมหาศาลจากการโดนบังคับปิด position ของฝั่งตรงข้าม",
    "parents": ["20.689", "20.255"],
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
    sA = load_strategy("20.689").generate(df, tf)
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
