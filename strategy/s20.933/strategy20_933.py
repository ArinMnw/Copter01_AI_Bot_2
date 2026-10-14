# -*- coding: utf-8 -*-
"""S20.933 — Mixed 168 x 169 CONFIRM"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.933',
    'name': 'Mixed 168 x 169 CONFIRM',
    'concept': 'Mix of S20.168 (Ehlers Super Smoother Cross) and S20.169 (Woodie CCI Reject) via CONFIRM',
    'logic': 'A ให้จุดเข้าหลักเมื่อ Super Smoother Crossover (Zero-Lag Trend Reversal) ส่วน B ให้ Woodie CCI Reject เป็นสัญญาณการย่อตัวแล้วไปต่อ โดยใช้ B เป็นตัวยืนยัน (CONFIRM) ถ้าจุดเข้าของการเปลี่ยนเทรนด์ของ A ได้รับการยืนยันจากการพักตัวจบของ CCI ภายใน 5 แท่ง จะเป็นการเข้าไม้ในจังหวะย่อแรกหลังจากเปลี่ยนเทรนด์ (Pullback after Reversal)',
    'parents': ['20.168', '20.169'],
    'mix': 'CONFIRM',
    'sl_atr': 1.5,
    'rr': 2.0,
    'max_hold': 40
}

def generate(df, tf):
    pA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.168"))
    pB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.169"))
    if pA not in sys.path: sys.path.insert(0, pA)
    if pB not in sys.path: sys.path.insert(0, pB)
    
    import strategy20_168 as sA
    import strategy20_169 as sB
    
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
