# -*- coding: utf-8 -*-
"""S20.927 — Mixed 148 x 177 CONFIRM"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.927',
    'name': 'Mixed 148 x 177 CONFIRM',
    'concept': 'Mix of S20.148 (Inside-Bar Breakout) and S20.177 (Tweezer at 20-Bar Extreme) via CONFIRM',
    'logic': 'A ให้จุดเข้าหลักจากการเบรคกรอบ Inside-Bar ตามแนวโน้ม EMA50 ส่วน B ให้ Price Action กลับตัวแบบสุดโต่ง (Tweezer ที่จุดต่ำสุด/สูงสุด) เป็นตัวยืนยัน (CONFIRM) ถ้าจุดเข้าของ A ได้รับการยืนยันจาก B ภายใน 15 แท่ง จะเป็นการเข้าไม้แบบตามเทรนด์ที่มาจากจุดกลับตัวสุดโต่ง (Trend continuation from extreme rejection)',
    'parents': ['20.148', '20.177'],
    'mix': 'CONFIRM',
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
    
    s_a = pd.Series(sig_a, index=df.index)
    s_b = pd.Series(sig_b, index=df.index)
    
    b_up = (s_b == 1).rolling(15, min_periods=1).max() == 1
    b_dn = (s_b == -1).rolling(15, min_periods=1).max() == 1
    
    final_sig = np.zeros(len(df), dtype=np.int8)
    final_sig[(s_a == 1) & b_up] = 1
    final_sig[(s_a == -1) & b_dn] = -1
    return final_sig
