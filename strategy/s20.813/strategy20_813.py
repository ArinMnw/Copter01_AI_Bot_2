# -*- coding: utf-8 -*-
"""S20.813 — S20.258 x S20.153 (CONFIRM)

logic: A (258 SAR Breakout) เข้าเร็วตามเทรนด์ B (153 Keltner Breakout) ยืนยันด้วยการระเบิดของ Volatility
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

s_A = _load("mix_a_813", "258")
s_B = _load("mix_b_813", "153")

META = {
    "sid": "20.813",
    "name": "SAR Trend x Keltner Confirm",
    "concept": "เข้าเทรดด้วย Parabolic SAR (258) เฉพาะเมื่อมีการเกิด Keltner Breakout (153) ในช่วงเวลาใกล้เคียง",
    "logic": "A (258) เป็นตัวบอกการเปลี่ยนเทรนด์อย่างรวดเร็ว แต่มักเกิดสัญญาณหลอกในช่วงที่ตลาด Volatility ต่ำ เราจะใช้ B (153) ซึ่งดักการระเบิดตัวออกนอก Keltner Channel เป็นตัวยืนยัน หากมี B เกิดขึ้นใน 5 แท่งล่าสุดแปลว่าเทรนด์ใหม่มี Volatility สูงพอให้เกาะเทรนด์",
    "parents": ["20.258", "20.153"],
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
