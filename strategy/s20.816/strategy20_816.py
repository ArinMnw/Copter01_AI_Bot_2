# -*- coding: utf-8 -*-
"""S20.816 — S20.258 x S20.614 (CONFIRM)

logic: A (258 SAR Breakout) เข้าเบรคเอาท์ B (614 Williams %R) ยืนยันว่าเบรคจากจุด Oversold/Overbought
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

s_A = _load("mix_a_816", "258")
s_B = _load("mix_b_816", "614")

META = {
    "sid": "20.816",
    "name": "SAR Breakout x Williams Confirm",
    "concept": "เข้าเทรดด้วย SAR Breakout (258) เฉพาะเมื่อมีการฟื้นตัวจากจุด Extreme ของ Williams %R (614) มาก่อนหน้า",
    "logic": "A (258) จับจังหวะที่ราคาระเบิดเปลี่ยนเทรนด์ แต่เพื่อป้องกันการเบรคเอาท์ที่ปลายน้ำ (ไล่ราคาตอนตลาดแพงแล้ว) เราใช้ B (614) มา Confirm ให้เข้าเฉพาะเมื่อการระเบิดนั้นเพิ่งฟื้นตัวมาจากโซน Oversold (สำหรับ Buy) หรือ Overbought (สำหรับ Sell) ในช่วง 5 แท่งที่ผ่านมา",
    "parents": ["20.258", "20.614"],
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
