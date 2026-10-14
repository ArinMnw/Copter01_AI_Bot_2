# -*- coding: utf-8 -*-
"""S20.925 — Mixed 342 x 356 CONFIRM"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.925',
    'name': 'Mixed 342 x 356 CONFIRM',
    'concept': 'Mix of S20.342 (ADX Low Vol Breakdown) and S20.356 (BB Volatility Z-Score) via CONFIRM',
    'logic': 'A จับการระเบิดตัวจากภาวะซึมผ่าน ADX Squeeze Breakout ส่วน B จับ Volatility Breakout แบบสุดโต่งด้วย BB Z-Score ถ้าจุดเข้าของ A ได้รับการยืนยันจากการระเบิดความผันผวนของ B ภายใน 5 แท่ง จะเป็นการเข้าไม้แบบ Double Volatility Breakout ที่รุนแรงมาก',
    'parents': ['20.342', '20.356'],
    'mix': 'CONFIRM',
    'sl_atr': 1.5,
    'rr': 1.5,
    'max_hold': 24,
    'be_r': 1.0
}

def generate(df, tf):
    pA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.342"))
    pB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.356"))
    if pA not in sys.path: sys.path.insert(0, pA)
    if pB not in sys.path: sys.path.insert(0, pB)
    
    import strategy20_342 as sA
    import strategy20_356 as sB
    
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
