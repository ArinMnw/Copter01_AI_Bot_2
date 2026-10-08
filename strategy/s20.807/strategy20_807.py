# -*- coding: utf-8 -*-
"""S20.807 — S20.161 x S20.471 (FILTER)

logic: A (161 Ultimate Oscillator) จับจังหวะกลับตัว B (471 Squeeze Breakout) กรองเฉพาะช่วงที่โมเมนตัมหลักสนับสนุน
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

s_A = _load("mix_a_807", "161")
s_B = _load("mix_b_807", "471")

META = {
    "sid": "20.807",
    "name": "Oscillator Dip Buy in Squeeze Momentum",
    "concept": "เข้าซื้อตอนย่อตัวด้วยสัญญาณจาก Oscillator (161) เมื่อมีโมเมนตัมหลักสนับสนุนจาก Squeeze Breakout (471)",
    "logic": "A (161) สัญญาณ Ultimate Oscillator ที่เกิดบ่อยและจับจังหวะสวิงได้ดี นำมากรองด้วย B (471) ที่จับโมเมนตัมระเบิดรุนแรง ทำให้เราเข้าจังหวะย่อตัวในเทรนด์แข็งแกร่ง (Buy the dip during strong breakout)",
    "parents": ["20.161", "20.471"],
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
