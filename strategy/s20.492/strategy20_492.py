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
s283_mod = load_mod("s283", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.283", "strategy20_283.py"))

META = {
    "sid": "20.492",
    "name": "Volatility Breakout TEMA Confirm",
    "concept": "เทรด Breakout (A) ที่ถูก Confirm ว่า TEMA เพิ่งตัด DEMA ไปในทิศทางเดียวกัน ภายใน 3 แท่ง",
    "logic": "A (422) เข้าเมื่อ Volatility Breakout ส่วน B (283) คือ TEMA/DEMA Cross ซึ่งตอบสนองไวมากต่อการเปลี่ยนเทรนด์ การ Confirm ด้วย B ภายใน 3 แท่ง หมายถึง Breakout เกิดขึ้นพร้อมๆ กับการที่เทรนด์ระยะสั้น-กลางเพิ่งจะเปลี่ยนทิศสนับสนุน",
    "parents": ["20.422", "20.283"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s422_mod.generate(df, tf)
    sig_b = s283_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 3 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(3).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(3).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
