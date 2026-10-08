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

spec_b = importlib.util.spec_from_file_location("s20_288", "strategy/s20.288/strategy20_288.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.734",
    "name": "S20.196 x S20.288 (CONFIRM w15)",
    "concept": "Gann HiLo Activator (B) confirmed by Fisher Transform (A) - w15",
    "logic": "S20.288 provides Gann HiLo Activator Flip trend breakouts. We CONFIRM these breakouts with S20.196 (Fisher Transform) within the last 15 bars. Gann HiLo is a very sensitive trailing trend channel that flips when price closes outside the SMA of highs/lows. By requiring a Fisher Transform signal (which identifies sharp, statistically significant price turning points) to occur right before the Gann HiLo flip, we ensure the new trend is ignited by a true structural extreme rather than a false breakout in a choppy market. The 15-bar window preserves strict Jaccard uniqueness.",
    "parents": ["20.196", "20.288"],
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
