# -*- coding: utf-8 -*-
import sys, os
import importlib.util
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

s339_mod = load_mod("s339", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.339", "strategy20_339.py"))
s163_mod = load_mod("s163", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.163", "strategy20_163.py"))

META = {
    "sid": "20.488",
    "name": "Inside Breakout STC Confirm",
    "concept": "เทรด Breakout (A) ที่ถูก Confirm ด้วย Schaff Trend Cycle (B) ภายใน 2 แท่ง",
    "logic": "A (339) เข้าเมื่อ Inside Bar Breakout ส่วน B (163) คือ STC (MACD ผ่าน Stoch 2 ชั้น) ที่ smooth มาก การ Confirm กันภายใน 2 แท่ง ช่วยรับประกันว่า Breakout เกิดขึ้นพร้อมกับการพุ่งขึ้น/ลงของโมเมนตัมระดับลึก",
    "parents": ["20.339", "20.163"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s339_mod.generate(df, tf)
    sig_b = s163_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 2 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(2).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(2).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
