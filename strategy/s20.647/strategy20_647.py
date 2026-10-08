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

spec_b = importlib.util.spec_from_file_location("s20_339", "strategy/s20.339/strategy20_339.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.647",
    "name": "S20.422 x S20.339 (CONFIRM)",
    "concept": "Triple MA Breakout (A) confirmed by Inside Bar Continuation (B)",
    "logic": "S20.422 provides Triple MA Volatility Breakout signals (trend resumption). We CONFIRM these breakouts with S20.339 (Inside Bar MACD Continuation) within the last 15 bars. We only enter the breakout if the market recently formed a valid inside-bar pause (pullback) that aligned with MACD momentum. This ensures we are trading true trend continuations from a valid structural base.",
    "parents": ["20.422", "20.339"],
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
    
    # CONFIRM: B gave same signal within k=15 bars
    buy_b_recent = pd.Series(buy_b).rolling(15).max().fillna(0).astype(bool).values
    sell_b_recent = pd.Series(sell_b).rolling(15).max().fillna(0).astype(bool).values
    
    buy = buy_a & buy_b_recent
    sell = sell_a & sell_b_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
