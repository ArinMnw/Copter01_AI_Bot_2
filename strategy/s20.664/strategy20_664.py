# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_168", "strategy/s20.168/strategy20_168.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_155", "strategy/s20.155/strategy20_155.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.664",
    "name": "S20.168 x S20.155 (CONFIRM)",
    "concept": "Ehlers Crossover (A) confirmed by MACD Divergence (B)",
    "logic": "S20.168 provides Ehlers Super Smoother trend crossovers. We CONFIRM these crossovers with S20.155 (MACD Divergence) within the last 20 bars. Trend crossovers are most reliable when they mark the beginning of a new cycle. By ensuring a MACD Divergence predicted the reversal just prior to the crossover, we filter out late or sideways crossovers, focusing only on high-probability structural turns.",
    "parents": ["20.168", "20.155"],
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
    
    # CONFIRM: B gave same signal within k=20 bars (prior to A)
    buy_b_recent = pd.Series(buy_b).rolling(20).max().fillna(0).astype(bool).values
    sell_b_recent = pd.Series(sell_b).rolling(20).max().fillna(0).astype(bool).values
    
    buy = buy_a & buy_b_recent
    sell = sell_a & sell_b_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
