# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.963",
    "name": "Mixed 732 x Curvature Confirm",
    "concept": "เข้าเทรดด้วยสัญญาณ 732 (Z-Score x HMA Cross) เฉพาะเมื่อความโค้ง 277 (Curvature) เพิ่งกลับตัวมาล่วงหน้าใน 12 แท่ง",
    "logic": "732 เป็นการตามเทรนด์รอบใหญ่ (แข็งแกร่งใน H4) ซึ่งข้อเสียคืออาจจะเข้าช้าไปบ้าง การนำ 277 ซึ่งใช้ Quadratic Regression จับความโค้งของกราฟมาเป็นตัวคอนเฟิร์มนำร่อง (CONFIRM 12 แท่ง) จะเป็นการบังคับให้จุดเข้าเกิดขึ้นเฉพาะในจังหวะที่เทรนด์เพิ่งผ่านการโค้งกลับตัวมาไม่นาน ทำให้เราได้จุดเข้าที่คมและมี Risk/Reward ที่ดีกว่าการไล่ราคาในช่วงปลายเทรนด์",
    "parents": ["20.732", "20.277"],
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
    sA = load_strategy("20.732").generate(df, tf)
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
