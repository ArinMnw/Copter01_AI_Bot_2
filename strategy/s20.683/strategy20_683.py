# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_237", "strategy/s20.237/strategy20_237.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_143", "strategy/s20.143/strategy20_143.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.683",
    "name": "S20.237 x S20.143 (VETO)",
    "concept": "Elder Impulse (B) VETOED by FRAMA Cross (A)",
    "logic": "S20.143 provides Elder Impulse System trend momentum signals. S20.237 provides Ehlers FRAMA cross trend state. We apply a VETO: we only take the Elder Impulse signal if the FRAMA cross has NOT YET aligned in that direction. This isolates the earliest momentum bursts at structural turning points before the slower adaptive moving averages catch up, maximizing R:R and strictly dropping >50% of late trend trades for uniqueness.",
    "parents": ["20.237", "20.143"],
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
