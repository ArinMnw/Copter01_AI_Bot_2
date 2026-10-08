# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_250", "strategy/s20.250/strategy20_250.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_196", "strategy/s20.196/strategy20_196.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.721",
    "name": "S20.250 x S20.196 (FILTER w15)",
    "concept": "DEMA (A) filtered by Fisher Transform (B) - w15",
    "logic": "S20.250 provides DEMA (Double Exponential Moving Average) trend crossovers. We FILTER these crosses with S20.196 (Fisher Transform) within the last 15 bars. DEMA is extremely fast and responsive to trend changes, but can get chopped in low volatility. By requiring a Fisher Transform signal (which identifies sharp price turning points using Gaussian probability) to occur right before the DEMA crossover, we ensure the new trend is ignited by a true structural extreme rather than slow noise. The 15-bar window allows enough time for the crossover to form after the exhaustion spike, ensuring strict Jaccard uniqueness.",
    "parents": ["20.250", "20.196"],
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
    
    # FILTER: B gave same signal within k=15 bars
    buy_b_recent = pd.Series(buy_b).rolling(15).max().fillna(0).astype(bool).values
    sell_b_recent = pd.Series(sell_b).rolling(15).max().fillna(0).astype(bool).values
    
    # Base is A, Filtered by B
    buy = buy_a & buy_b_recent
    sell = sell_a & sell_b_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
