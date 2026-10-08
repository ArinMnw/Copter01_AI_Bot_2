# -*- coding: utf-8 -*-
"""S20.811 — S20.179 x S20.422 (CONFIRM)

logic: A (179 Parabolic SAR) จับจังหวะกลับตัว B (422 S20.320 x S20.355) ยืนยันด้วยโมเมนตัม
"""
import sys, os
import importlib.util
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))

def _load(name, sid):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, "..", "s20." + sid, "strategy20_" + sid + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

s_A = _load("mix_a_811", "179")
s_B = _load("mix_b_811", "422")

META = {
    "sid": "20.811",
    "name": "SAR Reversal x Momentum Confirm",
    "concept": "หาจุดเปลี่ยนเทรนด์ด้วย Parabolic SAR (179) ยืนยันด้วยโมเมนตัมที่แข็งแกร่ง (422)",
    "logic": "A (179) จับสัญญาณการเปลี่ยนเทรนด์ในระยะแรกเริ่ม แต่มีโอกาสโดน Whipsaw สูง นำมาผูกกับ B (422) ซึ่งเป็นตัวกรองที่แข็งแกร่งจากตัวแม่ที่ดีที่สุดตัวหนึ่ง โดยใช้การยืนยันแบบย้อนหลัง 5 แท่ง เพื่อเข้าตอนที่ตลาดมีทิศทางชัดเจนหลังจากการกลับตัว",
    "parents": ["20.179", "20.422"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_A = s_A.generate(df, tf)
    sig_B = s_B.generate(df, tf)
    
    sig = np.zeros(len(df), dtype=np.int8)
    
    b_buy_recent = pd.Series(sig_B == 1).rolling(5).max().fillna(0).astype(bool)
    b_sell_recent = pd.Series(sig_B == -1).rolling(5).max().fillna(0).astype(bool)
    
    sig[(sig_A == 1) & b_buy_recent] = 1
    sig[(sig_A == -1) & b_sell_recent] = -1
    
    return sig
