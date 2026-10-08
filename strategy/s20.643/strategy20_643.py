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

spec_b = importlib.util.spec_from_file_location("s20_356", "strategy/s20.356/strategy20_356.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.643",
    "name": "S20.148 x S20.356 (CONFIRM)",
    "concept": "Inside Bar Trend (A) confirmed by Volatility Explosion (B)",
    "logic": "S20.148 provides Inside-Bar Trend Breakout signals. We CONFIRM these breakouts with S20.356 (Bollinger Z-Score Volatility Explosion) within the last 10 bars. We only enter the inside bar breakout if a severe volatility expansion recently occurred, ensuring the breakout has enough institutional energy to sustain a move.",
    "parents": ["20.148", "20.356"],
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
    
    # CONFIRM: B gave same signal within k=10 bars
    buy_b_recent = pd.Series(buy_b).rolling(10).max().fillna(0).astype(bool).values
    sell_b_recent = pd.Series(sell_b).rolling(10).max().fillna(0).astype(bool).values
    
    buy = buy_a & buy_b_recent
    sell = sell_a & sell_b_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
