# -*- coding: utf-8 -*-
"""S20.826 — S20.471 x S20.421 (CONFIRM)

logic: A (471 Squeeze Breakout) เข้าเบรคเอาท์ B (421 RSI Divergence x Vol) ยืนยันด้วย Divergence ที่เพิ่งเกิด
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

s_A = _load("mix_a_826", "471")
s_B = _load("mix_b_826", "421")

META = {
    "sid": "20.826",
    "name": "Squeeze Breakout x RSI Div Confirm",
    "concept": "เข้าเทรดเมื่อเกิด Squeeze Breakout (471) เฉพาะเมื่อมีการเกิด RSI Divergence พร้อมวอลุ่มหนุน (421) นำมาก่อนหน้า",
    "logic": "A (471) จับการเบรคเอาท์ของราคาหลังจากช่วงสะสมพลัง แต่บางครั้งอาจเป็นการเบรคหลอก (False Breakout) เราจึงนำ B (421) ซึ่งจับจุดกลับตัวด้วย Divergence ของ RSI มาคอย Confirm หากใน 5 แท่งล่าสุดเพิ่งมี Divergence เราถึงจะเชื่อว่า Breakout ของ A เป็นจุดเริ่มต้นเทรนด์ใหม่จริงๆ",
    "parents": ["20.471", "20.421"],
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
