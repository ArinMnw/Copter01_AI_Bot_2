# -*- coding: utf-8 -*-
"""S20.938 — Mixed 169 x 210 CONFIRM"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.938',
    'name': 'Mixed 169 x 210 CONFIRM',
    'concept': 'Mix of S20.169 (Woodie CCI Reject) and S20.210 (Accelerator Two-Green) via CONFIRM',
    'logic': 'A ให้จุดเข้าจากการย่อตัวแล้วเด้งกลับ (Reject) ที่ Zero-Line ของ Woodie CCI ส่วน B ให้โมเมนตัมเร่งตัวจาก Accelerator Oscillator (ความเร่งของราคากลับมาทิศเดิม) ทำหน้าที่เป็นตัวยืนยัน (CONFIRM) ถ้า CCI สร้างจังหวะเข้าเทรดแล้วมีการเร่งตัวยืนยันจาก AC ภายใน 5 แท่ง จะทำให้จุดเข้ามีความหนักแน่นยิ่งขึ้น',
    'parents': ['20.169', '20.210'],
    'mix': 'CONFIRM',
    'sl_atr': 1.5,
    'rr': 2.0,
    'max_hold': 24
}

def generate(df, tf):
    pA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.169"))
    pB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "s20.210"))
    if pA not in sys.path: sys.path.insert(0, pA)
    if pB not in sys.path: sys.path.insert(0, pB)
    
    import strategy20_169 as sA
    import strategy20_210 as sB
    
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
