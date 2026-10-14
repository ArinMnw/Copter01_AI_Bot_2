# -*- coding: utf-8 -*-
"""S20.923 — Mixed 237 x 356 CONFIRM"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.923',
    'name': 'Mixed 237 x 356 CONFIRM',
    'concept': 'Mix of S20.237 (Ehlers FRAMA) and S20.356 (BB Volatility Z-Score) via CONFIRM',
    'logic': 'A ให้จุดเข้าหลักจาก FRAMA ที่ปรับตาม fractal dimension ส่วน B ให้สัญญาณ Volatility Breakout (BB Z-Score > 2.0) เป็นตัวยืนยัน (CONFIRM) ถ้าจุดเข้าของ A ได้รับการยืนยันจาก B ภายใน 15 แท่ง จะเป็นการเข้าไม้ที่มีทั้งแนวโน้มระดับ fractal และ volatility expansion สูงผิดปกติสนับสนุน',
    'parents': ['20.237', '20.356'],
    'mix': 'CONFIRM',
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
    
    s_a = pd.Series(sig_a, index=df.index)
    s_b = pd.Series(sig_b, index=df.index)
    
    b_up = (s_b == 1).rolling(15, min_periods=1).max() == 1
    b_dn = (s_b == -1).rolling(15, min_periods=1).max() == 1
    
    final_sig = np.zeros(len(df), dtype=np.int8)
    final_sig[(s_a == 1) & b_up] = 1
    final_sig[(s_a == -1) & b_dn] = -1
    return final_sig
