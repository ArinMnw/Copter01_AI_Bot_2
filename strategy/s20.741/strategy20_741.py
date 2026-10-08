# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_162", "strategy/s20.162/strategy20_162.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_406", "strategy/s20.406/strategy20_406.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.741",
    "name": "S20.162 x S20.406 (CONFIRM w15)",
    "concept": "Alligator (B) confirmed by Aroon (A) - w15",
    "logic": "S20.406 provides Bill Williams' Alligator breakouts (Moving Averages fanning out). We CONFIRM these breakouts with S20.162 (Aroon Oscillator) signals within the last 15 bars. The Alligator is prone to false breakouts in choppy markets when the moving averages slowly drift apart without true momentum. Aroon measures the strict time since the highest high or lowest low. By requiring Aroon to signal right before the Alligator breakout, we guarantee that the breakout is accompanied by fresh structural extremes (new highs/lows) rather than just sideways drift. The 15-bar window preserves Jaccard uniqueness.",
    "parents": ["20.162", "20.406"],
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
