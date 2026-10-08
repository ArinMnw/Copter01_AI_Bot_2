# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_342", "strategy/s20.342/strategy20_342.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_161", "strategy/s20.161/strategy20_161.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.655",
    "name": "S20.342 x S20.161 (CONFIRM)",
    "concept": "ADX Breakout (A) confirmed by UO Oversold Dip (B)",
    "logic": "S20.342 provides ADX Low Volatility Breakout signals. We CONFIRM these breakouts with S20.161 (Ultimate Oscillator Mean-Reversion Dip) within the last 30 bars. This creates a powerful setup where we enter a momentum breakout ONLY if it emerges immediately following a deep oversold condition, capturing the explosive reversal phase of the market cycle.",
    "parents": ["20.342", "20.161"],
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
    
    # CONFIRM: B gave same signal within k=30 bars (prior to A)
    buy_b_recent = pd.Series(buy_b).rolling(30).max().fillna(0).astype(bool).values
    sell_b_recent = pd.Series(sell_b).rolling(30).max().fillna(0).astype(bool).values
    
    buy = buy_a & buy_b_recent
    sell = sell_a & sell_b_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
