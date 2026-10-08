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

s275_mod = load_mod("s275", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.275", "strategy20_275.py"))
s277_mod = load_mod("s277", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.277", "strategy20_277.py"))

META = {
    "sid": "20.510",
    "name": "MACD Divergence Curvature Confirm",
    "concept": "เทรด MACD Divergence (A) ที่ถูก Confirm ว่ามีสัญญาณ Quadratic Curvature Turn (B) เกิดขึ้นภายใน 5 แท่ง",
    "logic": "A (275) ให้สัญญาณ MACD Divergence เพื่อดักการกลับตัว ส่วน B (277) คือ Quadratic-Regression ที่ชี้ว่าความโค้ง (Curvature) ของกราฟราคากำลังเปลี่ยนทิศทาง การผสมแบบ CONFIRM (5 แท่ง) จะกรองเฉพาะสัญญาณที่เกิด Divergence ควบคู่ไปกับเส้นโค้งของราคาจริง (Price Action Curve) ที่ทำท่าหักหัวกลับแล้ว",
    "parents": ["20.275", "20.277"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s275_mod.generate(df, tf)
    sig_b = s277_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 5 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(5).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(5).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
