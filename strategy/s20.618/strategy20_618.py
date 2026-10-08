# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_339", "strategy/s20.339/strategy20_339.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_156", "strategy/s20.156/strategy20_156.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.618",
    "name": "S20.339 x S20.156 (CONFIRM)",
    "concept": "Inside Bar Breakout (A) confirmed by CMF Thrust (B)",
    "logic": "S20.339 provides Inside Bar MACD Continuation Breakout signals. We CONFIRM these signals with S20.156 (Chaikin Money Flow Zero-Line Thrust) within the last 3 bars. This ensures that the continuation breakout is supported by a recent influx of buying/selling volume, increasing the reliability of the breakout.",
    "parents": ["20.339", "20.156"],
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
    
    # CONFIRM: B gave same signal within k=3 bars
    buy_b_recent = pd.Series(buy_b).rolling(3).max().fillna(0).astype(bool).values
    sell_b_recent = pd.Series(sell_b).rolling(3).max().fillna(0).astype(bool).values
    
    buy = buy_a & buy_b_recent
    sell = sell_a & sell_b_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
