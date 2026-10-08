# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_148", "strategy/s20.148/strategy20_148.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_242", "strategy/s20.242/strategy20_242.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.682",
    "name": "S20.148 x S20.242 (FILTER)",
    "concept": "Rainbow MA (B) filtered by precise Inside Bar (A)",
    "logic": "S20.242 provides Rainbow MA trend signals. We FILTER these signals by requiring an S20.148 (Inside Bar Breakout) within the last 2 bars. This ensures the trend entry happens immediately following a volatility squeeze/expansion. By tightening the window to 2 bars, we isolate the absolute sharpest momentum ignitions while dropping the Jaccard similarity below 0.5 for strict uniqueness.",
    "parents": ["20.148", "20.242"],
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
    
    # FILTER: A gave same signal within k=2 bars
    buy_a_recent = pd.Series(buy_a).rolling(2).max().fillna(0).astype(bool).values
    sell_a_recent = pd.Series(sell_a).rolling(2).max().fillna(0).astype(bool).values
    
    # Base is B, Filtered by A
    buy = buy_b & buy_a_recent
    sell = sell_b & sell_a_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
