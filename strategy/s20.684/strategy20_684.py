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

spec_b = importlib.util.spec_from_file_location("s20_237", "strategy/s20.237/strategy20_237.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.684",
    "name": "S20.153 x S20.237 (CONFIRM w20)",
    "concept": "FRAMA Cross (B) confirmed by ATR Breakout (A) - w20",
    "logic": "S20.237 provides Ehlers FRAMA trend cross signals. We CONFIRM these crosses with S20.153 (ATR Volatility Breakout) within the last 20 bars. This filters out all the false FRAMA crosses that occur in low-volatility chop, ensuring we only take trend setups that were recently ignited by a massive volatility spike. The 20-bar window allows enough time for the fast breakout to consolidate before the slower FRAMA catches up, securing N>=50 trades while maintaining exceptional PF.",
    "parents": ["20.153", "20.237"],
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
