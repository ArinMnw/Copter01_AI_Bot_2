# -*- coding: utf-8 -*-
"""S20.930 — Mixed 148 x 169 CONFIRM"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.930',
    'name': 'Mixed 148 x 169 CONFIRM',
    'concept': 'Mix of S20.148 (Inside-Bar Breakout) and S20.169 (Woodie CCI Reject) via CONFIRM',
    'logic': 'A ให้สัญญาณการเบรคกรอบการพักตัวแบบ Inside-Bar ไปตามแนวโน้ม EMA50 ส่วน B ให้จุด Reject ที่ Zero Line ของ Woodie CCI (บ่งบอกว่าการย่อจบแล้วและกลับเข้าเทรนด์) โดยใช้ B เป็นตัวยืนยัน (CONFIRM) ว่าถ้าเกิดเบรคของ A แล้วมีการดีดของ CCI ภายใน 5 แท่ง จะเป็นการเข้าไม้แบบสมบูรณ์ของการไปต่อตามเทรนด์',
    'parents': ['20.148', '20.169'],
    'mix': 'CONFIRM',
    'sl_atr': 1.2,
    'rr': 2.0,
    'max_hold': 24
}

def generate(df, tf):
    pA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.148"))
    pB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.169"))
    if pA not in sys.path: sys.path.insert(0, pA)
    if pB not in sys.path: sys.path.insert(0, pB)
    
    import strategy20_148 as sA
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
