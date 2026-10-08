# -*- coding: utf-8 -*-
"""S20.812 — S20.168 x S20.471 (FILTER)

logic: A (168 HMA Trend) เข้าตามเทรนด์ด้วยความไวสูง B (471 Squeeze Breakout) กรองด้วยสถานะโมเมนตัมระเบิด
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

s_A = _load("mix_a_812", "168")
s_B = _load("mix_b_812", "471")

META = {
    "sid": "20.812",
    "name": "Fast Trend x Momentum Filter",
    "concept": "เข้าตามเทรนด์ด้วยความไวสูงของ HMA (168) แต่เข้าเฉพาะตอนที่มีสถานะโมเมนตัมหนุนหลังจากการระเบิด (471)",
    "logic": "A (168) จับรอบเทรนด์ได้เร็วมากแต่มักโดนหลอกตอนตลาดไม่มีแรง นำมากรองด้วย B (471) ที่ดักจับการระเบิดตัวของราคา (Squeeze Breakout) เพื่อให้มั่นใจว่าเทรนด์ที่เข้าไปนั้นมีแรงโมเมนตัมที่แท้จริงหนุนอยู่",
    "parents": ["20.168", "20.471"],
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
