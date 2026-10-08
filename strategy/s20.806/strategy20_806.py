# -*- coding: utf-8 -*-
"""S20.806 — S20.471 x S20.637 (CONFIRM)

logic: A (471) Squeeze Breakout + RSI B (637) S20.148 x S20.277 ยืนยันว่าโมเมนตัมไม่หลอก
"""
import sys, os
import importlib.util
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))

def _load(name, sid):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, "..", "s20." + sid, "strategy20_" + sid + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

s_A = _load("mix_a_806", "471")
s_B = _load("mix_b_806", "637")

META = {
    "sid": "20.806",
    "name": "Squeeze Breakout x Quadratic Confirm",
    "concept": "เข้าเทรด Squeeze Breakout (471) เมื่อมีการยืนยันทิศทางจาก Quadratic Curve และ EMA50 (637)",
    "logic": "A (471) ให้สัญญาณเข้าจากการระเบิดของ Momentum Squeeze B (637) ยืนยันว่าก่อนหน้าการระเบิดนี้มีแนวโน้มชัดเจนจาก EMA50 และ Quadratic Regression เพื่อหลีกเลี่ยง False Breakout",
    "parents": ["20.471", "20.637"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_A = s_A.generate(df, tf)
    sig_B = s_B.generate(df, tf)
    
    sig = np.zeros(len(df), dtype=np.int8)
    
    b_buy_recent = pd.Series(sig_B == 1).rolling(5).max().fillna(0).astype(bool)
    b_sell_recent = pd.Series(sig_B == -1).rolling(5).max().fillna(0).astype(bool)
    
    sig[(sig_A == 1) & b_buy_recent] = 1
    sig[(sig_A == -1) & b_sell_recent] = -1
    
    return sig
