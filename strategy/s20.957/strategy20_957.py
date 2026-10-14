# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.957",
    "name": "Mixed 512 x Curvature Confirm",
    "concept": "เข้าเทรดด้วยสัญญาณ 512 (MACD Div x HalfTrend) เฉพาะเมื่อ 277 (Curvature Turn) มีสัญญาณกลับตัวใน 12 แท่งที่ผ่านมา",
    "logic": "512 จับการกลับตัวจากแรงส่งที่อ่อนลงของ Divergence การที่เรานำ 277 (ความโค้งแบบ Quadratic) มาคอนเฟิร์มล่วงหน้า 12 แท่ง (CONFIRM) จะช่วยให้เราเข้าเทรดเฉพาะเมื่อเห็นลักษณะการเร่งตัวของกราฟที่เป็นรูปโค้งขึ้น/ลงชัดเจนแล้ว เป็นการหนีช่วง false breakout ของ Divergence ได้ดี",
    "parents": ["20.512", "20.277"],
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
    sA = load_strategy("20.512").generate(df, tf)
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
