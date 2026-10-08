# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_169", "strategy/s20.169/strategy20_169.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_356", "strategy/s20.356/strategy20_356.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.763",
    "name": 'S20.169 x S20.356 (CONFIRM w5)',
    "concept": 'Woodie CCI zero-line reject (A) confirmed by Bollinger volatility Z-score breakout (B)',
    "logic": 'A จับการปฏิเสธเส้นศูนย์ของ CCI (เด้งตามทิศ) ซึ่งพลาดเมื่อความผันผวนหด; B ยืนยันว่าความกว้าง Bollinger ขยายผิดปกติพร้อม break ทิศเดียวกันภายใน 5 แท่ง เพื่อเข้าเฉพาะการเด้งที่มีแรงขยายตัว',
    "parents": ["20.169", "20.356"],
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
