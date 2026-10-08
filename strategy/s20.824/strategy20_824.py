# -*- coding: utf-8 -*-
"""S20.824 — S20.153 x S20.421 (CONFIRM)

logic: A (153 Keltner x RSI) เบรคเอาท์ B (421 RSI Divergence x Vol) ยืนยันด้วย Divergence ที่เพิ่งเกิด
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

s_A = _load("mix_a_824", "153")
s_B = _load("mix_b_824", "421")

META = {
    "sid": "20.824",
    "name": "Keltner Breakout x RSI Div Confirm",
    "concept": "เข้าเทรดเมื่อเกิด Keltner Breakout (153) เฉพาะเมื่อมีการเกิด RSI Divergence พร้อมวอลุ่มหนุน (421) นำมาก่อนหน้า",
    "logic": "A (153) จับจังหวะที่ราคาระเบิดกรอบ Keltner Channel เพื่อเกาะเทรนด์ แต่มักจะโดนหลอกให้ไปเข้าที่ปลายเทรนด์หรือ False Breakout เรานำ B (421) ซึ่งจับจุดกลับตัวด้วย Divergence ของ RSI มาคอย Confirm หากใน 5 แท่งล่าสุดเพิ่งมี Divergence เราถึงจะเชื่อว่า Breakout ของ A เป็นจุดเริ่มต้นเทรนด์ใหม่ที่แข็งแรงจริงๆ",
    "parents": ["20.153", "20.421"],
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
