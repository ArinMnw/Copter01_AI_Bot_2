# -*- coding: utf-8 -*-
"""S20.808 — S20.168 x S20.685 (CONFIRM)

logic: A (168 HMA Trend) หาจังหวะเข้าตามเทรนด์ B (685 S20.158 x S20.194) ยืนยันด้วย Chande Kroll Stop
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

s_A = _load("mix_a_808", "168")
s_B = _load("mix_b_808", "685")

META = {
    "sid": "20.808",
    "name": "HMA Trend x Chande Kroll Confirm",
    "concept": "เข้าเทรดตาม Hull Moving Average (168) โดยยืนยันด้วยโครงสร้าง Chande Kroll Stop (685)",
    "logic": "A (168) จับรอบเทรนด์ด้วยความไวสูงของ HMA B (685) อาศัย Chande Kroll Stop เพื่อยืนยันว่าการเปลี่ยนเทรนด์ของ A นั้นทะลุโครงสร้าง Stop-loss สำคัญแล้ว (กรอง Whipsaw)",
    "parents": ["20.168", "20.685"],
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
