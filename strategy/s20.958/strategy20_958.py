# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.958",
    "name": "Mixed 512 x HF Donchian Filter",
    "concept": "เข้าเทรดด้วยสัญญาณ 512 เฉพาะเมื่อทิศทางการทะลุกรอบของ 210 (HF Donchian) ตรงกับฝั่งที่จะเข้า",
    "logic": "512 จับจังหวะกลับตัวด้วย Divergence และ HalfTrend แต่เพื่อป้องกันการเข้าสวนเทรนด์ที่ยังไม่ระเบิดพลังออก เราจึงใช้ 210 (HF Donchian) มาเป็นตัวกรอง (FILTER) ให้เทรดเฉพาะเมื่อมีการทะลุกรอบราคาในทิศทางเดียวกันในแท่งนั้น",
    "parents": ["20.512", "20.210"],
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
    sB = load_strategy("20.210").generate(df, tf)
    
    sig = np.zeros(len(df), dtype=np.int8)
    
    buy_cond = (sA == 1) & (sB == 1)
    sell_cond = (sA == -1) & (sB == -1)
    
    sig[buy_cond] = 1
    sig[sell_cond] = -1
    return sig
