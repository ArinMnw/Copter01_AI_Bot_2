# -*- coding: utf-8 -*-
"""S20.821 — S20.168 x S20.267 (FILTER)

logic: A (168 HMA Trend) หาเทรนด์ระยะสั้น B (267 Aroon Trend) กรองด้วยความแข็งแกร่งของเทรนด์เพื่อหลีกเลี่ยง Sideway
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

s_A = _load("mix_a_821", "168")
s_B = _load("mix_b_821", "267")

META = {
    "sid": "20.821",
    "name": "HMA Trend x Aroon Filter",
    "concept": "เข้าเทรดตามเส้นค่าเฉลี่ย HMA (168) เฉพาะในช่วงที่สถานะความแข็งแกร่งของเทรนด์จาก Aroon (267) ให้ทิศทางเดียวกัน",
    "logic": "A (168) จับการเปลี่ยนเทรนด์ได้ไว แต่มักโดนหลอกในตลาดแกว่งตัว (Sideway) เรานำ B (267) ซึ่งประเมินความแข็งแกร่งของเทรนด์จากระยะเวลาทำ High/Low มาเป็น Filter หาก Aroon ไม่มีเทรนด์ชัดเจน หรือชี้ไปคนละทาง เราจะมองข้ามสัญญาณของ HMA เพื่อลด Loss",
    "parents": ["20.168", "20.267"],
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
