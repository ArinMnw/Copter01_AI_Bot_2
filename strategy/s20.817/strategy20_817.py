# -*- coding: utf-8 -*-
"""S20.817 — S20.168 x S20.420 (CONFIRM)

logic: A (168 HMA Trend) หาเทรนด์ระยะสั้น B (420 SAR Reversal x MACD) ยืนยันด้วยการกลับตัวของ SAR ที่มี MACD หนุน
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

s_A = _load("mix_a_817", "168")
s_B = _load("mix_b_817", "420")

META = {
    "sid": "20.817",
    "name": "HMA Trend x SAR-MACD Confirm",
    "concept": "เข้าเทรดด้วยเส้นค่าเฉลี่ย HMA (168) เฉพาะเมื่อมีการเกิด SAR Reversal ที่ยืนยันโดย MACD (420) นำมาก่อนหน้า",
    "logic": "A (168) จับการเปลี่ยนรอบของเทรนด์ได้ไวมาก แต่มีโอกาสเจอสัญญาณหลอกสูงในตลาด Sideway เรานำ B (420) ซึ่งเป็นระบบเทรดกลับตัวที่แม่นยำสูง (มี MACD ช่วยกรอง) มาคอย Confirm หากใน 5 แท่งล่าสุดเพิ่งมีสัญญาณกลับตัวจาก B เราถึงจะเชื่อสัญญาณ HMA ว่าเป็นการเริ่มต้นเทรนด์ใหม่ที่แข็งแกร่ง",
    "parents": ["20.168", "20.420"],
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
