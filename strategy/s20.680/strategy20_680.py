# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_169", "strategy/s20.169/strategy20_169.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_153", "strategy/s20.153/strategy20_153.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.680",
    "name": "S20.169 x S20.153 (CONFIRM w20)",
    "concept": "ATR Breakout (B) confirmed by BB %b Divergence (A)",
    "logic": "S20.153 provides ATR Volatility Breakout signals. We CONFIRM these breakouts with S20.169 (Bollinger Bands %b Divergence) within the last 20 bars. BB %b Divergence indicates structural momentum exhaustion at the extremes. By only taking an ATR breakout if a structural divergence just occurred, we isolate the most explosive V-shape reversals while dropping all the late continuation breakouts. This maximizes risk-reward and strictly drops >50% of trades to ensure uniqueness.",
    "parents": ["20.169", "20.153"],
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
    
    # CONFIRM: A gave same signal within k=20 bars (prior to B)
    buy_a_recent = pd.Series(buy_a).rolling(20).max().fillna(0).astype(bool).values
    sell_a_recent = pd.Series(sell_a).rolling(20).max().fillna(0).astype(bool).values
    
    # Base is B, Confirmed by A
    buy = buy_b & buy_a_recent
    sell = sell_b & sell_a_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
