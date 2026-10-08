# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_422", "strategy/s20.422/strategy20_422.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_173", "strategy/s20.173/strategy20_173.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.627",
    "name": "S20.422 x S20.173 (CONFIRM)",
    "concept": "Volatility Breakout (A) confirmed by Ease of Movement (B)",
    "logic": "S20.422 provides Volatility Breakout signals. We CONFIRM these signals with S20.173 (Arms Ease of Movement Zero-Line Cross) within the last 5 bars. This ensures the volatility breakout occurs exactly when the path of least resistance (EMV) opens in the breakout direction, maximizing momentum efficiency.",
    "parents": ["20.422", "20.173"],
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
