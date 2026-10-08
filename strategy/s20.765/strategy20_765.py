# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_210", "strategy/s20.210/strategy20_210.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_356", "strategy/s20.356/strategy20_356.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.765",
    "name": 'S20.210 x S20.356 (CONFIRM w5)',
    "concept": 'Accelerator Oscillator two-green (A) confirmed by Bollinger Z-score breakout (B)',
    "logic": 'A จับการเร่งของโมเมนตัม (AC สองแท่งเขียว) ที่เร็วแต่มี noise; B ยืนยันว่าการเร่งนั้นมาพร้อมการขยายความผันผวนผิดปกติทิศเดียวกันภายใน 5 แท่ง',
    "parents": ["20.210", "20.356"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 2.0,
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
