# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_148", "strategy/s20.148/strategy20_148.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_277", "strategy/s20.277/strategy20_277.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.637",
    "name": "S20.148 x S20.277 (FILTER)",
    "concept": "Inside-Bar Breakout (A) filtered by Quad-Reg Curvature (B)",
    "logic": "S20.148 provides Inside-Bar Breakout signals aligned with EMA50 slope (velocity). We FILTER these breakouts using the state of S20.277 (Quadratic Regression Curvature, which measures price acceleration). We only enter the breakout if the mathematical curvature of price is also accelerating in our direction. By requiring both velocity and acceleration to agree, we filter out false breakouts.",
    "parents": ["20.148", "20.277"],
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
    
    # FILTER: B's continuous state must align
    state_b = pd.Series(sig_b).replace(0, np.nan).ffill().fillna(0).values
    
    buy = buy_a & (state_b == 1)
    sell = sell_a & (state_b == -1)
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
