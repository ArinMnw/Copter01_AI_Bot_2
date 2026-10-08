# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.801",
    "name": "Mixed 210 x 648 CONFIRM",
    "concept": "S20.210 x S20.648",
    "logic": "210 enters on consecutive Bill Williams Accelerator Oscillator colors, while 648 confirms the entry by ensuring a breakout from an inside bar is aligned with FRAMA within the last 5 bars.",
    "parents": ["20.210", "20.648"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    d = os.path.dirname(os.path.abspath(__file__))
    p_a = os.path.join(d, "..", "s20.210")
    p_b = os.path.join(d, "..", "s20.648")
    if p_a not in sys.path: sys.path.insert(0, p_a)
    if p_b not in sys.path: sys.path.insert(0, p_b)
    
    import strategy20_210
    import strategy20_648
    
    sig_A = strategy20_210.generate(df, tf)
    sig_B = strategy20_648.generate(df, tf)
    
    buy_B = pd.Series(sig_B == 1).rolling(5).max() == 1
    sell_B = pd.Series(sig_B == -1).rolling(5).max() == 1
    
    buy_cond = pd.Series(sig_A == 1) & buy_B
    sell_cond = pd.Series(sig_A == -1) & sell_B
    
    return ind.sig_from(buy_cond, sell_cond)
