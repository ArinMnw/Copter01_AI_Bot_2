# -*- coding: utf-8 -*-
"""S20.924 — Mixed 237 x 356 FILTER"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.924',
    'name': 'Mixed 237 x 356 FILTER',
    'concept': 'Mix of S20.237 (Ehlers FRAMA) and S20.356 (BB Volatility Z-Score) via FILTER',
    'logic': 'A ให้จุดเข้าหลักจากแนวโน้ม (Ehlers FRAMA) ส่วน B ให้ Volatility Breakout (Z-Score) เป็นตัวกรองสถานะ (FILTER) โดยจะเข้าไม้ของ A ได้เมื่อสถานะของ B บ่งบอกถึงการขยายตัวของความผันผวนไปในทิศทางเดียวกัน',
    'parents': ['20.237', '20.356'],
    'mix': 'FILTER',
    'sl_atr': 1.5,
    'rr': 2.0,
    'max_hold': 30
}

def generate(df, tf):
    pA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.237"))
    pB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.356"))
    if pA not in sys.path: sys.path.insert(0, pA)
    if pB not in sys.path: sys.path.insert(0, pB)
    
    import strategy20_237 as sA
    import strategy20_356 as sB
    
    sig_a = sA.generate(df, tf)
    sig_b = sB.generate(df, tf)
    
    # State of B
    state_b = np.zeros(len(df), dtype=np.int8)
    curr = 0
    for i in range(len(sig_b)):
        if sig_b[i] != 0:
            curr = sig_b[i]
        state_b[i] = curr
        
    final_sig = np.zeros(len(df), dtype=np.int8)
    final_sig[(sig_a == 1) & (state_b == 1)] = 1
    final_sig[(sig_a == -1) & (state_b == -1)] = -1
    return final_sig
