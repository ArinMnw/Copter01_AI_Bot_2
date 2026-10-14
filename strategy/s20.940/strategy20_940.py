# -*- coding: utf-8 -*-
"""S20.940 — Mixed 169 x 277 CONFIRM"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.940',
    'name': 'Mixed 169 x 277 CONFIRM',
    'concept': 'Mix of S20.169 (Woodie CCI Reject) and S20.277 (Quad-Reg Curvature) via CONFIRM',
    'logic': 'A ให้จุดเข้าจังหวะย่อตัวแล้วเด้งกลับจากเส้นศูนย์ของ Woodie CCI ส่วน B ให้โมเมนตัมแบบความโค้ง (Curvature) ของ Quadratic Regression เป็นตัวยืนยัน (CONFIRM) โดยถ้าการย่อตัวจบลงตามที่ CCI บอกแล้วตามด้วยการเร่งความโค้งกลับทิศจาก B ภายใน 5 แท่ง จะเป็นการยืนยันจุดเข้าด้วยการพลิกกลับของสมการเส้นโค้ง',
    'parents': ['20.169', '20.277'],
    'mix': 'CONFIRM',
    'sl_atr': 1.5,
    'rr': 2.0,
    'max_hold': 24
}

def generate(df, tf):
    pA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.169"))
    pB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.277"))
    if pA not in sys.path: sys.path.insert(0, pA)
    if pB not in sys.path: sys.path.insert(0, pB)
    
    import strategy20_169 as sA
    import strategy20_277 as sB
    
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
