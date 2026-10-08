# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_194", "strategy/s20.194/strategy20_194.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_277", "strategy/s20.277/strategy20_277.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.629",
    "name": "S20.194 x S20.277 (CONFIRM)",
    "concept": "Chande Kroll Flip (A) confirmed by Quad-Reg Curvature (B)",
    "logic": "S20.194 provides Chande Kroll Stop Flip signals (trend shift). We CONFIRM these signals with S20.277 (Quadratic Regression Curvature Turn) within the last 5 bars. This ensures that the trailing stop flip is backed by a mathematical inflection point in price curvature, proving momentum has structurally shifted.",
    "parents": ["20.194", "20.277"],
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
    
    # CONFIRM: B gave same signal within k=5 bars
    buy_b_recent = pd.Series(buy_b).rolling(5).max().fillna(0).astype(bool).values
    sell_b_recent = pd.Series(sell_b).rolling(5).max().fillna(0).astype(bool).values
    
    buy = buy_a & buy_b_recent
    sell = sell_a & sell_b_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
