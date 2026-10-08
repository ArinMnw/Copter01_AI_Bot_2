# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.313', 'name': 'Bollinger Band Squeeze Percent B Breakout', 'concept': 'BB Width below 20MA implies squeeze, wait for %B > 1 (buy) or < 0 (sell) breakout', 'logic': 'Squeeze contraction leads to explosive expansion upon %B breakout', 'sl_atr': 2.0, 'rr': 2.5, 'max_hold': 40, 'be_r': 1.0}

def generate(df, tf):
    lower, mid, upper = I.bbands(df["close"], 20, 2.0)
    bb_w = upper - lower
    sqz = bb_w < I.sma(bb_w, 20)
    
    pct_b = (df["close"] - lower) / bb_w.replace(0, np.nan)
    
    buy = sqz & (pct_b > 1.0) & (pct_b.shift(1) <= 1.0)
    sell = sqz & (pct_b < 0.0) & (pct_b.shift(1) >= 0.0)
    
    return I.sig_from(buy, sell)
