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
s248_mod = load_mod("s248", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.248", "strategy20_248.py"))

META = {
    "sid": "20.499",
    "name": "Inside Bar Breakout Elder Confirm",
    "concept": "เทรด Breakout จาก Inside Bar (A) ที่ถูก Confirm ว่ามีสัญญาณ Elder Triple Screen (B) เกิดขึ้นภายใน 5 แท่ง",
    "logic": "A (339) เข้าเทรด Breakout จากแท่ง Inside Bar ส่วน B (248) คือจังหวะที่ Elder Triple Screen ส่งสัญญาณ (EMA ระยะยาวหนุน, Stochastic ในระยะกลางตวัดตัวกลับ, ราคาเบรกในกรอบสั้น) การผสมแบบ CONFIRM จะรับเฉพาะการเบรก Inside Bar ที่สอดรับเป็นจังหวะเดียวกับสัญญาณของระบบ 3 หน้าจอ",
    "parents": ["20.339", "20.248"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s339_mod.generate(df, tf)
    sig_b = s248_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 5 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(5).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(5).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
