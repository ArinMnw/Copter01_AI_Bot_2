# -*- coding: utf-8 -*-
"""S20.829 — S20.210 x S20.161 (CONFIRM)

logic: A (210 Accelerator) เข้าตามโมเมนตัม B (161 Ultimate Oscillator) ยืนยันด้วยจุดกลับตัว
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

s_A = _load("mix_a_829", "210")
s_B = _load("mix_b_829", "161")

META = {
    "sid": "20.829",
    "name": "Accelerator x Ultimate Osc Confirm",
    "concept": "เข้าเทรดเมื่อโมเมนตัมเร่งตัว (210) เฉพาะเมื่อมีการเกิดสัญญาณกลับตัวจาก Ultimate Oscillator (161) นำมาก่อนหน้า",
    "logic": "A (210) จับจังหวะที่โมเมนตัมเริ่มเร่งตัวในทิศทางใหม่ แต่อาจเกิดจากการสวิงชั่วคราว เราจึงนำ B (161) ซึ่งจับจุดกลับตัวจากสภาวะ Overbought/Oversold ด้วย Ultimate Oscillator มาคอย Confirm หากเพิ่งมีสัญญาณกลับตัวใน 5 แท่งล่าสุด เราถึงจะเชื่อว่าโมเมนตัมของ A นั้นคือการเริ่มต้นเทรนด์ใหม่จริงๆ",
    "parents": ["20.210", "20.161"],
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
