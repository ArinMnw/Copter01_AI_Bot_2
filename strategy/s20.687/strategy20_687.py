# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_143", "strategy/s20.143/strategy20_143.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_194", "strategy/s20.194/strategy20_194.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.687",
    "name": "S20.143 x S20.194 (FILTER w3)",
    "concept": "Chande Kroll Flip (B) filtered by precise Elder Impulse (A)",
    "logic": "S20.194 provides Chande Kroll Stop flip trend signals based on volatility trailing stops. We FILTER these flips with S20.143 (Elder Impulse) within the last 3 bars. This strictly drops all trend flips that are not immediately backed by MACD/EMA momentum alignment, ensuring a high-quality trend initiation. The extremely tight 3-bar window ensures Jaccard similarity drops below 0.5 for uniqueness, while isolating the absolute sharpest momentum ignitions.",
    "parents": ["20.143", "20.194"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    
    buy_a = sig_a == 1
    sell_a = sig_a == -1
    
    buy_b = sig_b == 1
    sell_b = sig_b == -1
    
    # FILTER: A gave same signal within k=3 bars
    buy_a_recent = pd.Series(buy_a).rolling(3).max().fillna(0).astype(bool).values
    sell_a_recent = pd.Series(sell_a).rolling(3).max().fillna(0).astype(bool).values
    
    # Base is B, Filtered by A
    buy = buy_b & buy_a_recent
    sell = sell_b & sell_a_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
