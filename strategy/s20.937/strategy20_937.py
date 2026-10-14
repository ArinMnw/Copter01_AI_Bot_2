# -*- coding: utf-8 -*-
"""S20.937 — Mixed 169 x 177 FILTER"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.937',
    'name': 'Mixed 169 x 177 FILTER',
    'concept': 'Mix of S20.169 (Woodie CCI Reject) and S20.177 (Tweezer at Extreme) via FILTER',
    'logic': 'A ให้จุดเข้าตามจังหวะย่อแล้วเด้งกลับ (Reject) ที่ Zero-Line ของ Woodie CCI ส่วน B ให้ Tweezer ที่จุด Extreme ทำหน้าที่เป็นตัวกรองสถานะ (FILTER) โดยจะเข้าไม้ของ A ได้ก็ต่อเมื่อสถานะล่าสุดของ B สนับสนุนโมเมนตัมแบบกลับตัวจากจุดต่ำสุด/สูงสุดสอดคล้องกัน',
    'parents': ['20.169', '20.177'],
    'mix': 'FILTER',
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
    
    # State of B
    state_b = np.zeros(len(df), dtype=np.int8)
    curr = 0
    for i in range(len(sig_b)):
        if sig_b[i] != 0:
            curr = sig_b[i]
        state_b[i] = curr
        
    final_sig = np.zeros(len(df), dtype=np.int8)
    final_sig[(sig_a == 1) & (state_b == 1)] = 1
    final_sig[(sig_a == -1) & (state_b == -1)] = -1
    return final_sig
