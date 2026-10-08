# -*- coding: utf-8 -*-
"""S20.828 — S20.242 x S20.237 (CONFIRM)

logic: A (242 Rainbow MA) เข้าเทรนด์เรียงตัว B (237 FRAMA Cross) ยืนยันด้วยการตัดกันของ Fractal Adaptive MA
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

s_A = _load("mix_a_828", "242")
s_B = _load("mix_b_828", "237")

META = {
    "sid": "20.828",
    "name": "Rainbow MA x FRAMA Confirm",
    "concept": "เข้าเทรดเมื่อ Rainbow MA เรียงตัวกัน (242) เฉพาะเมื่อมีการเกิด FRAMA Cross (237) นำมาก่อนหน้า",
    "logic": "A (242) จับเทรนด์ได้อย่างมั่นคงจากการเรียงตัวของ MA หลายเส้น แต่สัญญาณอาจมาช้า เราจึงนำ B (237) ซึ่งจับเทรนด์ด้วย Fractal Adaptive MA ที่ปรับตัวเข้ากับความผันผวนได้อย่างรวดเร็ว มาคอย Confirm หากใน 5 แท่งล่าสุดเพิ่งมี FRAMA ตัดกันในทิศทางเดียวกัน เราถึงจะมั่นใจว่าเทรนด์ของ A เพิ่งเริ่มต้นและยังสดใหม่",
    "parents": ["20.242", "20.237"],
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
