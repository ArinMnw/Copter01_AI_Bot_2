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

spec_b = importlib.util.spec_from_file_location("s20_237", "strategy/s20.237/strategy20_237.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.669",
    "name": "S20.148 x S20.237 (MTF)",
    "concept": "Ehlers FRAMA Cross (B) confirmed by Inside Bar Breakout (A)",
    "logic": "S20.237 provides Ehlers FRAMA trend crossover signals. We CONFIRM these crossovers with S20.148 (Inside Bar Breakout) within the last 5 bars. An Inside Bar breakout represents a volatility expansion from a tight squeeze. By entering a trend crossover ONLY if a tight consolidation broke out immediately prior, we capture high-probability, high-momentum trend initiations while dropping low-momentum false crossovers.",
    "parents": ["20.148", "20.237"],
    "mix": "MTF",
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
    
    # CONFIRM: A gave same signal within k=5 bars (prior to B)
    buy_a_recent = pd.Series(buy_a).rolling(5).max().fillna(0).astype(bool).values
    sell_a_recent = pd.Series(sell_a).rolling(5).max().fillna(0).astype(bool).values
    
    # Base is B, Confirmed by A
    buy = buy_b & buy_a_recent
    sell = sell_b & sell_a_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
