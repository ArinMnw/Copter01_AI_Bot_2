# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_242", "strategy/s20.242/strategy20_242.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_194", "strategy/s20.194/strategy20_194.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.678",
    "name": "S20.242 x S20.194 (VETO)",
    "concept": "Chande Kroll (B) VETOED by Rainbow MA (A)",
    "logic": "S20.194 provides Chande Kroll Stop flip signals. S20.242 (Rainbow MA) provides the prevailing trend. We apply a VETO: we only take the Chande Kroll flip if the Rainbow MA has NOT YET flipped in that direction. By isolating these early disagreements, we catch the exact moment of reversal before the slower moving averages catch up, maximizing risk-reward and ensuring strict uniqueness from both parents.",
    "parents": ["20.242", "20.194"],
    "mix": "VETO",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    
    buy_b = sig_b == 1
    sell_b = sig_b == -1
    
    # Convert A's event signals into a continuous state
    state_a = pd.Series(sig_a).replace(0, np.nan).ffill().fillna(0).values
    
    # VETO: Base is B, but we VETO if A is ALREADY in the same direction
    buy = buy_b & (state_a != 1)
    sell = sell_b & (state_a != -1)
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
