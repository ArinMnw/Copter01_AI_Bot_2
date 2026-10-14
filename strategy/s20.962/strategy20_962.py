# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.962",
    "name": "Mixed 614 x HF Donchian Filter",
    "concept": "เข้าเทรดด้วยสัญญาณ 614 เฉพาะเมื่อทิศทาง Breakout ตรงกับ 210 (HF Donchian) ในแท่งเดียวกัน",
    "logic": "614 มีจุดเด่นด้าน Continuation จาก Inside Bar เราจึงใช้ 210 ซึ่งเป็นสัญญาณเบรกกรอบราคาสูง/ต่ำสุดระยะสั้นมาเป็นตัวกรอง (FILTER) ทำให้เราเข้าเฉพาะออเดอร์ที่ Breakout สอดคล้องกับการทำ High/Low ใหม่ของช่วงเวลานั้นๆ จริงๆ เป็นการรีดประสิทธิภาพสูงสุดจากจังหวะพุ่งแรง",
    "parents": ["20.614", "20.210"],
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
    sA = load_strategy("20.614").generate(df, tf)
    sB = load_strategy("20.210").generate(df, tf)
    
    sig = np.zeros(len(df), dtype=np.int8)
    
    buy_cond = (sA == 1) & (sB == 1)
    sell_cond = (sA == -1) & (sB == -1)
    
    sig[buy_cond] = 1
    sig[sell_cond] = -1
    return sig
