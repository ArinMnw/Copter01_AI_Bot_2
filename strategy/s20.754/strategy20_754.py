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

spec_b = importlib.util.spec_from_file_location("s20_148", "strategy/s20.148/strategy20_148.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.754",
    "name": "S20.194 x S20.148 (CONFIRM w15)",
    "concept": "Inside Bar Breakout (B) confirmed by Chande Kroll Stop (A) - w15",
    "logic": "S20.148 provides Inside Bar breakouts (volatility expansion). We CONFIRM these breakouts with S20.194 (Chande Kroll Stop Flip) signals within the last 15 bars. Inside Bars can break out falsely in choppy markets. Chande Kroll Stop identifies the dominant directional trend using high/low volatility bands. By requiring the Chande Kroll Stop to have flipped in our direction recently before the Inside Bar breakout, we ensure we are trading a volatility expansion in the direction of a newly established, high-volatility trend. The 15-bar window preserves Jaccard uniqueness.",
    "parents": ["20.194", "20.148"],
    "mix": "CONFIRM",
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
    
    # CONFIRM: A gave same signal within k=15 bars
    buy_a_recent = pd.Series(buy_a).rolling(15).max().fillna(0).astype(bool).values
    sell_a_recent = pd.Series(sell_a).rolling(15).max().fillna(0).astype(bool).values
    
    # Base is B, Confirmed by A
    buy = buy_b & buy_a_recent
    sell = sell_b & sell_a_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
