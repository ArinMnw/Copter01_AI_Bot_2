# -*- coding: utf-8 -*-
"""S20.936 — Mixed 169 x 177 CONFIRM"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.936',
    'name': 'Mixed 169 x 177 CONFIRM',
    'concept': 'Mix of S20.169 (Woodie CCI Reject) and S20.177 (Tweezer at Extreme) via CONFIRM',
    'logic': 'A ให้จุดเข้าจากการย่อตัวแล้วเด้งกลับ (Reject) ที่ Zero-Line ของ Woodie CCI ส่วน B ให้รูปแบบ Price Action แบบ Tweezer ที่จุด Extreme เพื่อเป็นตัวยืนยัน (CONFIRM) โดยถ้าการพักตัวจบลงตามที่ CCI บอกแล้วตามด้วยการเกิด Tweezer ภายใน 5 แท่ง จะเป็นการยืนยันจุดเข้าที่แม่นยำขึ้นจากแท่งเทียน',
    'parents': ['20.169', '20.177'],
    'mix': 'CONFIRM',
    'sl_atr': 1.5,
    'rr': 2.0,
    'max_hold': 24
}

def generate(df, tf):
    pA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.169"))
    pB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.177"))
    if pA not in sys.path: sys.path.insert(0, pA)
    if pB not in sys.path: sys.path.insert(0, pB)
    
    import strategy20_169 as sA
    import strategy20_177 as sB
    
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
