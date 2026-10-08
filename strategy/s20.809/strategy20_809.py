# -*- coding: utf-8 -*-
"""S20.809 — S20.342 x S20.614 (CONFIRM)

logic: A (342 Trend Retracement) หาจังหวะย่อซื้อ B (614 S20.339 x S20.409) เป็นตัวยืนยันจังหวะระเบิดของราคา
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

s_A = _load("mix_a_809", "342")
s_B = _load("mix_b_809", "614")

META = {
    "sid": "20.809",
    "name": "Trend Retracement x Continuation Confirm",
    "concept": "เข้าเทรดด้วยจุดพักตัวของเทรนด์ (342) เมื่อมีการยืนยันการไปต่อจาก Inside Bar Breakout (614)",
    "logic": "A (342) มองหาจุดย่อเพื่อเข้าตามเทรนด์ แต่เพื่อป้องกันการย่อแล้วเปลี่ยนเทรนด์ เราจะใช้ B (614) ซึ่งจับการเบรกเอาต์ในทิศทางเดิมมายืนยัน หาก B เพิ่งให้สัญญาณไปต่อใน 5 แท่งล่าสุด จึงจะยอมเข้าเทรดจาก A",
    "parents": ["20.342", "20.614"],
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
