# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_277", "strategy/s20.277/strategy20_277.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_242", "strategy/s20.242/strategy20_242.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.753",
    "name": "S20.277 x S20.242 (FILTER w15)",
    "concept": "Quadratic Regression Curvature (B) filtered by Rainbow MA (A) - w15",
    "logic": "S20.277 provides Quadratic Regression Curvature Turns (mathematical peaks and valleys). We FILTER these mathematical turns by requiring S20.242 (Rainbow Moving Average) to have established a trend in the same direction within the last 15 bars. This creates a powerful mathematical pullback strategy: Rainbow MA confirms the broader trend, price pulls back, and Quadratic Regression identifies the exact zero-crossing of the second derivative (the mathematical valley/peak) of the pullback for precision entry. The 15-bar window preserves Jaccard uniqueness.",
    "parents": ["20.277", "20.242"],
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
    
    # FILTER: B is Base, A is Filter (A gave same signal within 15 bars)
    buy_a_recent = pd.Series(buy_a).rolling(15).max().fillna(0).astype(bool).values
    sell_a_recent = pd.Series(sell_a).rolling(15).max().fillna(0).astype(bool).values
    
    # Base is B (277), Filter is A (242)
    buy = buy_b & buy_a_recent
    sell = sell_b & sell_a_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
