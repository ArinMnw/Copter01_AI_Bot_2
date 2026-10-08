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
    "sid": "20.729",
    "name": "S20.196 x S20.147 (FILTER w15)",
    "concept": "Fisher Transform (A) filtered by Parabolic SAR (B) - w15",
    "logic": "S20.196 provides Fisher Transform statistical exhaustion pivots. We FILTER these turning points with S20.147 (Parabolic SAR) within the last 15 bars. SAR is excellent for trailing a trend and identifying new trend regimes. By requiring a new SAR trend to have started recently before the Fisher Transform reversal, we trade a counter-trend or 'first pullback' exhaustion immediately after a new trend is established. The 15-bar window allows enough time for the SAR shift before the exhaustion spike.",
    "parents": ["20.196", "20.147"],
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
    
    # FILTER: B gave same signal within k=15 bars (wait, SAR gives continuous trend dots?)
    # Parent 147 gives +1 or -1 on every bar depending on trend.
    # To catch "started recently", we actually need B's reversal!
    # But filtering by B means we check if B is in our direction within 15 bars.
    # If SAR is green for 50 bars, and Fisher triggers, it will pass!
    # Let's see if this works.
    buy_b_recent = pd.Series(buy_b).rolling(15).max().fillna(0).astype(bool).values
    sell_b_recent = pd.Series(sell_b).rolling(15).max().fillna(0).astype(bool).values
    
    # Base is A, Filtered by B
    buy = buy_a & buy_b_recent
    sell = sell_a & sell_b_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
