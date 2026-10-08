# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_255", "strategy/s20.255/strategy20_255.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_242", "strategy/s20.242/strategy20_242.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.667",
    "name": "S20.255 x S20.242 (CONFIRM)",
    "concept": "Rainbow MA Alignment (B) confirmed by Hikkake Trap (A)",
    "logic": "S20.242 provides Rainbow MA Full Alignment trend signals. We CONFIRM these alignments with S20.255 (Hikkake False Breakout Trap) within the last 25 bars. Rainbow MA is a lagging trend confirmation, while a Hikkake trap is an early predictor of a structural reversal. By requiring a structural trap prior to the lagging MA alignment, we filter out late alignments in mature trends.",
    "parents": ["20.255", "20.242"],
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
    
    # CONFIRM: A gave same signal within k=25 bars (prior to B)
    buy_a_recent = pd.Series(buy_a).rolling(25).max().fillna(0).astype(bool).values
    sell_a_recent = pd.Series(sell_a).rolling(25).max().fillna(0).astype(bool).values
    
    # Base is B, Confirmed by A
    buy = buy_b & buy_a_recent
    sell = sell_b & sell_a_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
