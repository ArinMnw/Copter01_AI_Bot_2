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

spec_b = importlib.util.spec_from_file_location("s20_242", "strategy/s20.242/strategy20_242.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.700",
    "name": "S20.162 x S20.242 (CONFIRM w10)",
    "concept": "Rainbow MA (B) confirmed by Aroon Oscillator (A) - w10",
    "logic": "S20.242 provides Rainbow MA trend crosses. We CONFIRM these crosses with S20.162 (Aroon Oscillator) within the last 10 bars. Rainbow MA can trigger false crossovers during slow, low-momentum chop. By requiring an Aroon Oscillator signal (which triggers when the trend decisively shifts on a time-basis) to occur right before the crossover, we ensure the trend change is backed by actual momentum. The 10-bar window allows enough time for the MA crossover to follow the oscillator, maximizing PF and ensuring strict Jaccard uniqueness.",
    "parents": ["20.162", "20.242"],
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
    
    # CONFIRM: A gave same signal within k=10 bars
    buy_a_recent = pd.Series(buy_a).rolling(10).max().fillna(0).astype(bool).values
    sell_a_recent = pd.Series(sell_a).rolling(10).max().fillna(0).astype(bool).values
    
    # Base is B, Confirmed by A
    buy = buy_b & buy_a_recent
    sell = sell_b & sell_a_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
