# -*- coding: utf-8 -*-
"""S20.814 — S20.339 x S20.258 (CONFIRM)

logic: A (339 Supertrend) หาเทรนด์ที่แข็งแกร่ง B (258 SAR Breakout) ยืนยันว่าเพิ่งมี Breakout ส่งแรงมา
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

s_A = _load("mix_a_814", "339")
s_B = _load("mix_b_814", "258")

META = {
    "sid": "20.814",
    "name": "Supertrend x SAR Confirm",
    "concept": "เข้าเทรดด้วย Supertrend (339) เฉพาะเมื่อมีการเกิด SAR Breakout (258) ในช่วงเวลาใกล้เคียง",
    "logic": "A (339) เป็นตัวหาจังหวะเทรนด์หลัก แต่ในบางครั้งอาจเป็นเทรนด์อ่อนๆ ที่ไม่มีแรงส่ง เราจะใช้ B (258) ซึ่งจับ Breakout ที่ไวและรุนแรงมาเป็นตัวยืนยัน หากมี B เกิดขึ้นใน 5 แท่งล่าสุดแปลว่าเทรนด์ของ A นั้นมีแรงเฉื่อยจาก Breakout หนุนอยู่",
    "parents": ["20.339", "20.258"],
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
