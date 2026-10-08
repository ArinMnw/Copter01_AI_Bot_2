# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_194", "strategy/s20.194/strategy20_194.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_342", "strategy/s20.342/strategy20_342.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.761",
    "name": 'S20.194 x S20.342 (CONFIRM w3)',
    "concept": 'Chande Kroll Stop Flip (A) confirmed by ADX low-volatility expansion (B)',
    "logic": 'A ให้จุดกลับทิศของเส้น stop ตามความผันผวน แต่การพลิกในช่วงตลาดซึมมักเป็น whipsaw; B (ADX พุ่งจากระดับต่ำมาก) ยืนยันว่าตลาดเพิ่งระเบิดออกจากภาวะนิ่งภายใน 3 แท่ง จึงเข้า A เฉพาะ flip ที่มีแรงขยายตัวรองรับ',
    "parents": ["20.194", "20.342"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 2.0,
    "max_hold": 30,
    "be_r": 1.0
}


def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    final_sig = np.zeros_like(sig_a)
    w = 3
    b_buy = pd.Series(sig_b == 1).rolling(window=w, min_periods=1).max().astype(bool).values
    b_sell = pd.Series(sig_b == -1).rolling(window=w, min_periods=1).max().astype(bool).values
    final_sig[(sig_a == 1) & b_buy] = 1
    final_sig[(sig_a == -1) & b_sell] = -1
    return final_sig
