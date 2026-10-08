# -*- coding: utf-8 -*-
"""S20.810 — S20.161 x S20.685 (CONFIRM)

logic: A (161 Ultimate Oscillator) หาจังหวะวงสวิงกลับตัวระยะสั้น B (685 S20.158 x S20.194) ยืนยันว่าเทรนด์ยังไปได้ด้วย Chande Kroll Stop
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

s_A = _load("mix_a_810", "161")
s_B = _load("mix_b_810", "685")

META = {
    "sid": "20.810",
    "name": "Oscillator Dip Buy x Chande Kroll Confirm",
    "concept": "เข้าซื้อตอนย่อตัวด้วย Ultimate Oscillator (161) เมื่อมีการยืนยันโครงสร้างจาก Chande Kroll Stop (685)",
    "logic": "A (161) ให้จังหวะกลับตัวที่มีความถี่สูงและบ่อย นำมากรองด้วย B (685) ซึ่งตรวจจับการยืนยันโครงสร้างราคาแบบหยุดความผันผวน หาก B ส่งสัญญาณสอดคล้องกันในช่วง 5 แท่งล่าสุด จึงจะเข้าเทรด",
    "parents": ["20.161", "20.685"],
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
