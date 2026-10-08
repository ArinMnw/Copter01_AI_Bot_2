# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.791",
    "name": "Mixed 148 x 685 CONFIRM",
    "concept": "S20.148 x S20.685",
    "logic": "148 catches inside bar breakouts aligned with EMA50 trend, while 685 confirms the entry by ensuring MACD and HalfTrend alignment within the last 5 bars.",
    "parents": ["20.148", "20.685"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    d = os.path.dirname(os.path.abspath(__file__))
    p_a = os.path.join(d, "..", "s20.148")
    p_b = os.path.join(d, "..", "s20.685")
    if p_a not in sys.path: sys.path.insert(0, p_a)
    if p_b not in sys.path: sys.path.insert(0, p_b)
    
    import strategy20_148
    import strategy20_685
    
    sig_A = strategy20_148.generate(df, tf)
    sig_B = strategy20_685.generate(df, tf)
    
    buy_B = pd.Series(sig_B == 1).rolling(5).max() == 1
    sell_B = pd.Series(sig_B == -1).rolling(5).max() == 1
    
    buy_cond = pd.Series(sig_A == 1) & buy_B
    sell_cond = pd.Series(sig_A == -1) & sell_B
    
    return ind.sig_from(buy_cond, sell_cond)
