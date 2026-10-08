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

spec_b = importlib.util.spec_from_file_location("s20_210", "strategy/s20.210/strategy20_210.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.705",
    "name": "S20.153 x S20.210 (FILTER w5)",
    "concept": "Bill Williams AC (B) filtered by ATR Breakout (A) - w5",
    "logic": "S20.210 provides Bill Williams Accelerator Oscillator signals. We FILTER these momentum shifts with S20.153 (ATR Breakout) within the last 5 bars. The Accelerator Oscillator indicates early momentum changes, but can false-trigger in low volatility. By requiring a sudden expansion of volatility (ATR Breakout) to occur right before the momentum shift, we ensure the trend ignition is explosive and highly probable. The tight 5-bar window strictly preserves Jaccard uniqueness.",
    "parents": ["20.153", "20.210"],
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
    
    buy_b = sig_b == 1
    sell_b = sig_b == -1
    
    # FILTER: A gave same signal within k=5 bars
    buy_a_recent = pd.Series(buy_a).rolling(5).max().fillna(0).astype(bool).values
    sell_a_recent = pd.Series(sell_a).rolling(5).max().fillna(0).astype(bool).values
    
    # Base is B, Filtered by A
    buy = buy_b & buy_a_recent
    sell = sell_b & sell_a_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
