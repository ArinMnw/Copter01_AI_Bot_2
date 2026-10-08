# -*- coding: utf-8 -*-
"""S20.825 — S20.258 x S20.471 (CONFIRM)

logic: A (258 SAR Breakout) เข้าเบรคเอาท์ B (471 Squeeze Breakout x RSI) ยืนยันด้วย Squeeze Breakout ที่เพิ่งเกิด
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

s_A = _load("mix_a_825", "258")
s_B = _load("mix_b_825", "471")

META = {
    "sid": "20.825",
    "name": "SAR Breakout x Squeeze Confirm",
    "concept": "เข้าเทรดเมื่อเกิด SAR Breakout (258) เฉพาะเมื่อมีการเกิด Squeeze Breakout (471) นำมาก่อนหน้า",
    "logic": "A (258) จับการเบรคเอาท์ของราคาตาม SAR แต่มักมีโอกาสเป็น False Breakout สูง เราจึงนำ B (471) ซึ่งเป็นการเบรคจากช่วงสะสมพลัง (Squeeze) ที่ได้รับการกรองด้วย RSI มาคอย Confirm หากเพิ่งมีสัญญาณการระเบิดจากช่วง Squeeze เกิดขึ้นใน 5 แท่งล่าสุด เราถึงจะมั่นใจว่า Breakout ของ A มีพลังมากพอ",
    "parents": ["20.258", "20.471"],
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
