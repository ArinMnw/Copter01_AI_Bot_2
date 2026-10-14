# -*- coding: utf-8 -*-
"""S20.939 — Mixed 169 x 255 CONFIRM"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.939',
    'name': 'Mixed 169 x 255 CONFIRM',
    'concept': 'Mix of S20.169 (Woodie CCI Reject) and S20.255 (Hikkake False Breakout) via CONFIRM',
    'logic': 'A ให้จุดเข้าตามจังหวะที่ CCI เด้งตัวจาก Zero-Line (สัญญาณ Reject เพื่อไปต่อตามเทรนด์) ส่วน B ให้รูปแบบ Price Action แบบ Hikkake (หลอกว่าจะกลับตัวแต่ไปต่อ) เป็นตัวยืนยัน (CONFIRM) โดยถ้าสัญญาณย่อจบของ A เกิดขึ้นแล้วตามด้วยการหลอกล่อสะบัดเม่าออกของ B ภายใน 5 แท่ง จะเป็นการยืนยันรอบใหญ่',
    'parents': ['20.169', '20.255'],
    'mix': 'CONFIRM',
    'sl_atr': 1.5,
    'rr': 2.0,
    'max_hold': 24
}

def generate(df, tf):
    pA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.169"))
    pB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.255"))
    if pA not in sys.path: sys.path.insert(0, pA)
    if pB not in sys.path: sys.path.insert(0, pB)
    
    import strategy20_169 as sA
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
