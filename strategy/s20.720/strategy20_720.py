# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_196", "strategy/s20.196/strategy20_196.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_147", "strategy/s20.147/strategy20_147.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.720",
    "name": "S20.196 x S20.147 (CONFIRM w15)",
    "concept": "Parabolic SAR (B) confirmed by Fisher Transform (A) - w15",
    "logic": "S20.147 provides Parabolic SAR trend reversals. We CONFIRM these reversals with S20.196 (Fisher Transform) within the last 15 bars. SAR is excellent for trailing a trend, but can get chopped to pieces during sideways drift. By requiring a Fisher Transform signal (which identifies sharp price turning points using Gaussian probability) to occur right before the SAR reversal, we ensure the new SAR trend is ignited by a true structural extreme rather than low-volatility noise. The 15-bar window allows enough time for the SAR to reverse after the exhaustion spike, ensuring strict Jaccard uniqueness.",
    "parents": ["20.196", "20.147"],
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
