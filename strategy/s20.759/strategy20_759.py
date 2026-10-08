# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_339", "strategy/s20.339/strategy20_339.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_177", "strategy/s20.177/strategy20_177.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.759",
    "name": 'S20.339 x S20.177 (FILTER)',
    "concept": 'Inside Bar MACD Breakout (A) gated by last Tweezer extreme turn (B)',
    "logic": 'A ให้จุดระเบิดหลังพักตัว B (Tweezer ที่ extreme 20 แท่ง) บอกทิศของจุดกลับตัวโครงสร้างล่าสุดที่ยังไม่ถูกหักล้าง; เข้า A เฉพาะเมื่อ breakout ไปทางเดียวกับจุดกลับตัวล่าสุด เพื่อตัด breakout สวนโครงสร้างที่มักเป็น false break',
    "parents": ["20.339", "20.177"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}


def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    final_sig = np.zeros_like(sig_a)
    w = 0
    # state ของ B = ทิศสัญญาณล่าสุดที่ยังไม่กลับทิศ (ffill แบบ causal)
    st = pd.Series(np.where(sig_b != 0, sig_b, np.nan)).ffill().fillna(0).values
    final_sig[(sig_a == 1) & (st == 1)] = 1
    final_sig[(sig_a == -1) & (st == -1)] = -1
    return final_sig
