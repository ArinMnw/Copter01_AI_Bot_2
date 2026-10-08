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
    "sid": "20.751",
    "name": "S20.277 x S20.242 (CONFIRM w15)",
    "concept": "Rainbow MA (B) confirmed by Quadratic Regression Curvature (A) - w15",
    "logic": "S20.242 provides Rainbow Moving Average trend breakouts. We CONFIRM these breakouts with S20.277 (Quadratic Regression Curvature Turn) signals within the last 15 bars. Rainbow MA identifies moving averages fanning out to form a new trend, but can trigger late or falsely in a slow chop. Quadratic Regression Curvature mathematically identifies the peak/valley of the price curve (zero-crossing of the second derivative). By requiring the mathematical curve to have bottomed/topped recently before the MAs fan out, we ensure we are trading a structurally confirmed trend reversal. The 15-bar window preserves Jaccard uniqueness.",
    "parents": ["20.277", "20.242"],
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
