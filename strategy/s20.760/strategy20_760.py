# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_422", "strategy/s20.422/strategy20_422.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_751", "strategy/s20.751/strategy20_751.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.760",
    "name": 'S20.422 x S20.751 (CONFIRM w5)',
    "concept": 'Triple MA Volatility Breakout (A) confirmed by Curvature+Rainbow momentum turn (B)',
    "logic": 'A ให้จุดทะลุกรอบ volatility ตามเทรนด์ใหญ่ B (Rainbow MA ที่ยืนยันด้วย curvature ของ quadratic regression) ยืนยันว่าแรงเร่งของราคากำลังเปิดทิศเดียวกันภายใน 5 แท่ง เพื่อตัด breakout ที่ไม่มีโมเมนตัมเร่งตาม',
    "parents": ["20.422", "20.751"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}


def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    final_sig = np.zeros_like(sig_a)
    w = 5
    b_buy = pd.Series(sig_b == 1).rolling(window=w, min_periods=1).max().astype(bool).values
    b_sell = pd.Series(sig_b == -1).rolling(window=w, min_periods=1).max().astype(bool).values
    final_sig[(sig_a == 1) & b_buy] = 1
    final_sig[(sig_a == -1) & b_sell] = -1
    return final_sig
