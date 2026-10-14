# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.970",
    "name": "Mixed 512 x Hikkake Filter",
    "concept": "เข้าเทรดด้วยสัญญาณ 512 (MACD Div x HalfTrend) เฉพาะเมื่อสอดคล้องกับ 255 (Hikkake False Breakout) ในแท่งนั้น",
    "logic": "512 พยายามจับการกลับตัวจากโมเมนตัม แต่บ่อยครั้งที่เจอการกลับตัวหลอก การเอา 255 มากรอง (FILTER) แท่งต่อแท่ง จะทำให้ 512 ทำงานก็ต่อเมื่อมีการสะบัดตัวหลอกล่อเอาสภาพคล่อง (False Breakout) เกิดขึ้นในทิศทางเดียวกันพอดี ซึ่งจะช่วยคัดกรองจุดต่ำสุด/สูงสุดที่แท้จริงได้ดีขึ้น",
    "parents": ["20.512", "20.255"],
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
    sB = load_strategy("20.255").generate(df, tf)
    
    sig = np.zeros(len(df), dtype=np.int8)
    
    buy_cond = (sA == 1) & (sB == 1)
    sell_cond = (sA == -1) & (sB == -1)
    
    sig[buy_cond] = 1
    sig[sell_cond] = -1
    return sig
