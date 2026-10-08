# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_163", "strategy/s20.163/strategy20_163.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_143", "strategy/s20.143/strategy20_143.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.714",
    "name": "S20.163 x S20.143 (FILTER w15)",
    "concept": "Stochastic (A) filtered by Elder Impulse (B) - w15",
    "logic": "S20.163 provides Stochastic Oscillator cycles. We FILTER these signals with S20.143 (Elder Impulse) within the last 15 bars. The Stochastic Oscillator triggers when price reverses out of overbought/oversold levels. By requiring a strong momentum surge (Elder Impulse) to have occurred recently before the reversal, we ensure we are trading a sharp exhaustion climax of a highly active move, rather than a slow sideways drift. The 15-bar window strictly preserves Jaccard uniqueness.",
    "parents": ["20.163", "20.143"],
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
    
    # FILTER: B gave same signal within k=15 bars (wait, Elder Impulse has colors, buy_b is green)
    buy_b_recent = pd.Series(buy_b).rolling(15).max().fillna(0).astype(bool).values
    sell_b_recent = pd.Series(sell_b).rolling(15).max().fillna(0).astype(bool).values
    
    # Base is A, Filtered by B
    buy = buy_a & buy_b_recent
    sell = sell_a & sell_b_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
