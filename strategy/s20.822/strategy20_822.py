# -*- coding: utf-8 -*-
"""S20.822 — S20.339 x S20.421 (CONFIRM)

logic: A (339 Supertrend) ตัวแม่ตามเทรนด์ B (421 RSI Divergence x Vol) ยืนยันว่าเพิ่งเกิด Divergence
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

s_A = _load("mix_a_822", "339")
s_B = _load("mix_b_822", "421")

META = {
    "sid": "20.822",
    "name": "Supertrend x RSI Div Confirm",
    "concept": "เข้าเทรดด้วย Supertrend (339) เฉพาะเมื่อมีการเกิด RSI Divergence พร้อมวอลุ่มหนุน (421) นำมาก่อนหน้า",
    "logic": "A (339) เป็นตัวแม่เกาะเทรนด์ แต่เพื่อป้องกันการเข้าช้าตอนปลายเทรนด์ เรานำ B (421) มา Confirm ว่าเทรนด์ที่เรากำลังเข้านั้น เพิ่งจะเริ่มต้นขึ้นจากการกลับตัวด้วย Divergence หากไม่มี Divergence ใน 5 แท่งล่าสุด เราจะไม่เข้าเทรดเลย",
    "parents": ["20.339", "20.421"],
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
