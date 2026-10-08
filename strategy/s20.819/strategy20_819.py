# -*- coding: utf-8 -*-
"""S20.819 — S20.420 x S20.267 (FILTER)

logic: A (420 SAR Reversal x MACD) หาการกลับตัว B (267 Aroon Trend) กรองด้วยความแข็งแกร่งเทรนด์ฝั่งใหม่
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

s_A = _load("mix_a_819", "420")
s_B = _load("mix_b_819", "267")

META = {
    "sid": "20.819",
    "name": "SAR-MACD Reversal x Aroon Filter",
    "concept": "เข้าเทรดสวนแนวโน้มด้วยการกลับตัวของ SAR และ MACD (420) เฉพาะในช่วงที่สถานะความแข็งแกร่งของเทรนด์ใหม่จาก Aroon (267) ให้ทิศทางเดียวกัน",
    "logic": "A (420) เป็นระบบหาจุดสิ้นสุดเทรนด์เพื่อเล่นกลับตัวที่มีอัตราแม่นยำสูง แต่บางครั้งอาจเข้าเร็วเกินไปตอนที่เทรนด์เดิมยังแข็งมาก เราจะใช้ B (267) ซึ่งประเมินความแข็งแกร่งของเทรนด์จากระยะเวลาทำ High/Low มาเป็น Filter เพื่อให้แน่ใจว่าจังหวะที่ A สั่งเข้า เป็นจุดที่เทรนด์ฝั่งใหม่เริ่มก่อตัวและมีความแข็งแกร่งเพียงพอแล้ว",
    "parents": ["20.420", "20.267"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_A = s_A.generate(df, tf)
    sig_B = s_B.generate(df, tf)
    
    # FILTER: หาสถานะเทรนด์ปัจจุบันของ B (ffill สัญญาณล่าสุดที่เกิด)
    b_status = pd.Series(sig_B).replace(0, np.nan).ffill().fillna(0)
    
    sig = np.zeros(len(df), dtype=np.int8)
    sig[(sig_A == 1) & (b_status == 1)] = 1
    sig[(sig_A == -1) & (b_status == -1)] = -1
    
    return sig
