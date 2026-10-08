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

s422_mod = load_mod("s422", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.422", "strategy20_422.py"))
s228_mod = load_mod("s228", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.228", "strategy20_228.py"))

META = {
    "sid": "20.491",
    "name": "Volatility Breakout Low-Volume PB",
    "concept": "เทรด Breakout (A) ที่ถูก Confirm ว่าเกิดขึ้นหลังจาก Low-Volume Pullback (B) ภายใน 2 แท่ง",
    "logic": "A (422) เข้าเมื่อเกิด Volatility Breakout ส่วน B (228) คือการพักตัว 3 แท่งด้วย Volume ต่ำในเทรนด์ แล้วงัดกลับ การ Confirm กันภายใน 2 แท่ง ช่วยรับประกันว่า Breakout เกิดขึ้นหลังจากตลาดพักตัวซับแรงขาย/ซื้อเสร็จสิ้นแล้วจริงๆ",
    "parents": ["20.422", "20.228"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s422_mod.generate(df, tf)
    sig_b = s228_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 2 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(2).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(2).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
