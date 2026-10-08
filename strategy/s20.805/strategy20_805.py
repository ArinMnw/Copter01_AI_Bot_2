# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.805",
    "name": "Mixed 356 x 637 CONFIRM",
    "concept": "S20.356 x S20.637",
    "logic": "356 enters on price action aligning with EMA trend and RSI, while 637 confirms the entry by ensuring structural inside-bar breakouts and quadratic regression support the direction within the last 5 bars.",
    "parents": ["20.356", "20.637"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    d = os.path.dirname(os.path.abspath(__file__))
    p_a = os.path.join(d, "..", "s20.356")
    p_b = os.path.join(d, "..", "s20.637")
    if p_a not in sys.path: sys.path.insert(0, p_a)
    if p_b not in sys.path: sys.path.insert(0, p_b)
    
    import strategy20_356
    import strategy20_637
    
    sig_A = strategy20_356.generate(df, tf)
    sig_B = strategy20_637.generate(df, tf)
    
    buy_B = pd.Series(sig_B == 1).rolling(5).max() == 1
    sell_B = pd.Series(sig_B == -1).rolling(5).max() == 1
    
    buy_cond = pd.Series(sig_A == 1) & buy_B
    sell_cond = pd.Series(sig_A == -1) & sell_B
    
    return ind.sig_from(buy_cond, sell_cond)
