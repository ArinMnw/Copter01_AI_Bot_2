# -*- coding: utf-8 -*-
"""S20.928 — Mixed 148 x 177 FILTER"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.928',
    'name': 'Mixed 148 x 177 FILTER',
    'concept': 'Mix of S20.148 (Inside-Bar Breakout) and S20.177 (Tweezer at 20-Bar Extreme) via FILTER',
    'logic': 'A ให้จุดเข้าจากการเบรคกรอบ Inside-Bar ตามแนวโน้ม EMA50 ส่วน B ให้ Tweezer กลับตัวเป็นตัวกรองสถานะ (FILTER) โดยจะเข้าไม้ของ A ได้เมื่อสถานะของ B สนับสนุนว่าเกิดการกลับตัวที่ปลายสุดไปในทิศทางเดียวกัน',
    'parents': ['20.148', '20.177'],
    'mix': 'FILTER',
    'sl_atr': 1.2,
    'rr': 2.0,
    'max_hold': 24
}

def generate(df, tf):
    pA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.148"))
    pB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.177"))
    if pA not in sys.path: sys.path.insert(0, pA)
    if pB not in sys.path: sys.path.insert(0, pB)
    
    import strategy20_148 as sA
    import strategy20_177 as sB
    
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
