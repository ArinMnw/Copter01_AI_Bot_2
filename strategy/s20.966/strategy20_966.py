# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import importlib.util
import os

META = {
    "sid": "20.966",
    "name": "Mixed 854 x Hikkake Filter",
    "concept": "เข้าเทรดด้วยสัญญาณ 854 (Rainbow x KST) เฉพาะเมื่อสอดคล้องกับ 255 (Hikkake False Breakout) ในแท่งเดียวกัน",
    "logic": "854 คัดเลือกจุดที่เทรนด์กำลังไปได้ดีตามเส้น Rainbow การเพิ่มเงื่อนไข FILTER ด้วย 255 จะเจาะจงหาจังหวะที่เกิด False Breakout ของแพทเทิร์น Inside Bar แล้วดีดตัวกลับเข้าทิศทางของเทรนด์หลักพอดี ทำให้ได้รอบวิ่งที่แรงและโอกาสชนะสูง",
    "parents": ["20.854", "20.255"],
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
    sA = load_strategy("20.854").generate(df, tf)
    sB = load_strategy("20.255").generate(df, tf)
    
    sig = np.zeros(len(df), dtype=np.int8)
    
    buy_cond = (sA == 1) & (sB == 1)
    sell_cond = (sA == -1) & (sB == -1)
    
    sig[buy_cond] = 1
    sig[sell_cond] = -1
    return sig
