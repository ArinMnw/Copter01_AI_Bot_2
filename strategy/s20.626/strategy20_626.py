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

spec_b = importlib.util.spec_from_file_location("s20_258", "strategy/s20.258/strategy20_258.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.626",
    "name": "S20.422 x S20.258 (CONFIRM)",
    "concept": "Volatility Breakout (A) confirmed by Belt-Hold Reversal (B)",
    "logic": "S20.422 provides Volatility Breakout signals. We CONFIRM these signals with S20.258 (Belt-Hold Opening Marubozu at Extreme) within the last 5 bars. This setup ensures that the breakout occurs immediately following a powerful, climactic Belt-Hold reversal pattern at a local extreme, combining deep mean-reversion with fresh breakout momentum.",
    "parents": ["20.422", "20.258"],
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
