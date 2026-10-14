# -*- coding: utf-8 -*-
"""S20.921 — Mixed 210 x 255 CONFIRM"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.921',
    'name': 'Mixed 210 x 255 CONFIRM',
    'concept': 'Mix of S20.210 (Accelerator Oscillator) and S20.255 (Hikkake) via CONFIRM',
    'logic': 'A ให้ความเร่งโมเมนตัมแบบ Oscillator ส่วน B ให้ Price Action แบบ False Breakout (Hikkake) เมื่อเกิดความเร่ง (A) ที่ยืนยันด้วย False Breakout (B) จะได้จุดเข้าที่มีทั้งโมเมนตัมและ Price Action สนับสนุน',
    'parents': ['20.210', '20.255'],
    'mix': 'CONFIRM',
    'sl_atr': 1.5,
    'rr': 2.0,
    'max_hold': 24
}

def generate(df, tf):
    pA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.210"))
    pB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.255"))
    if pA not in sys.path: sys.path.insert(0, pA)
    if pB not in sys.path: sys.path.insert(0, pB)
    
    import strategy20_210 as sA
    import strategy20_255 as sB
    
    sig_a = sA.generate(df, tf)
    sig_b = sB.generate(df, tf)
    
    s_a = pd.Series(sig_a, index=df.index)
    s_b = pd.Series(sig_b, index=df.index)
    
    b_up = (s_b == 1).rolling(5, min_periods=1).max() == 1
    b_dn = (s_b == -1).rolling(5, min_periods=1).max() == 1
    
    final_sig = np.zeros(len(df), dtype=np.int8)
    final_sig[(s_a == 1) & b_up] = 1
    final_sig[(s_a == -1) & b_dn] = -1
    return final_sig
