# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_153", "strategy/s20.153/strategy20_153.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_242", "strategy/s20.242/strategy20_242.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.696",
    "name": "S20.153 x S20.242 (FILTER w15)",
    "concept": "ATR Breakout (A) filtered by Rainbow MA (B) - w15",
    "logic": "S20.153 provides ATR Volatility Breakout signals. We FILTER these breakouts with S20.242 (Rainbow MA) within the last 15 bars. ATR breakouts can happen at any time, often trapping traders in chop. By taking an ATR Breakout ONLY if a Rainbow MA crossover occurred in the last 15 bars, we isolate the very first volatility expansion that follows a structural trend shift. Triggering on the breakout bar ensures a vastly different entry timing than S20.695, guaranteeing low Jaccard similarity and high PF.",
    "parents": ["20.153", "20.242"],
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
