# -*- coding: utf-8 -*-
"""S20.827 — S20.277 x S20.210 (CONFIRM)

logic: A (277 Quadratic-Regression Turn) เข้าเทรดจุดกลับตัว B (210 Bill Williams Accelerator) ยืนยันด้วยโมเมนตัมเร่งตัว
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

s_A = _load("mix_a_827", "277")
s_B = _load("mix_b_827", "210")

META = {
    "sid": "20.827",
    "name": "Quad-Reg Turn x Accelerator Confirm",
    "concept": "เข้าเทรดเมื่อ Quadratic-Regression เกิดการโค้งกลับตัว (277) เฉพาะเมื่อมีการยืนยันจากความเร่งของโมเมนตัม (210) นำมาก่อนหน้า",
    "logic": "A (277) จับจุดกลับตัวด้วยสมการ Quadratic ซึ่งให้ความสมูทสูง แต่มักจะโดนหลอกถ้าราคากลับตัวแบบไม่มีแรงส่ง เราจึงนำ B (210) ซึ่งใช้ Accelerator Oscillator จับความเร่งของโมเมนตัมมาคอย Confirm หากใน 5 แท่งล่าสุดเพิ่งมีความเร่งในทิศทางเดียวกัน เราถึงจะเชื่อว่าจุดโค้งกลับตัวของ A นั้นเชื่อถือได้",
    "parents": ["20.277", "20.210"],
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
