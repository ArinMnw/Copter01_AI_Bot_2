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

spec_b = importlib.util.spec_from_file_location("s20_143", "strategy/s20.143/strategy20_143.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.679",
    "name": "S20.153 x S20.143 (SIMULTANEOUS)",
    "concept": "Elder Impulse (B) + ATR Breakout (A) simultaneously",
    "logic": "S20.143 provides Elder Impulse System trend momentum signals (MACD + EMA alignment). We CONFIRM these signals with S20.153 (ATR Volatility Breakout) on the EXACT SAME BAR. By requiring both a trend alignment and a sudden volatility expansion to happen simultaneously, we isolate the most explosive momentum bursts, ensuring high profitability and strict uniqueness (very low Jaccard).",
    "parents": ["20.153", "20.143"],
    "mix": "SIMULTANEOUS",
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
    
    # SIMULTANEOUS: Must happen on the exact same bar
    buy = buy_b & buy_a
    sell = sell_b & sell_a
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
