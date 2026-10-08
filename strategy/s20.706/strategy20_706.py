# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_165", "strategy/s20.165/strategy20_165.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_277", "strategy/s20.277/strategy20_277.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.706",
    "name": "S20.165 x S20.277 (CONFIRM w15)",
    "concept": "Quad Regression (B) confirmed by Woodies CCI (A) - w15",
    "logic": "S20.277 provides Quadratic Regression trend crossovers (statistical reversal). We CONFIRM these crosses with S20.165 (Woodies CCI) within the last 15 bars. Quadratic Regression is excellent at predicting smooth, curved reversals, but can trigger prematurely in strong linear trends. By requiring a Woodies CCI signal (which captures momentum divergence and zero-line trend shifts) to occur right before the crossover, we ensure the statistical reversal is backed by an actual underlying momentum shift. The 15-bar window strictly preserves Jaccard uniqueness while maximizing PF.",
    "parents": ["20.165", "20.277"],
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
    
    # CONFIRM: A gave same signal within k=15 bars
    buy_a_recent = pd.Series(buy_a).rolling(15).max().fillna(0).astype(bool).values
    sell_a_recent = pd.Series(sell_a).rolling(15).max().fillna(0).astype(bool).values
    
    # Base is B, Confirmed by A
    buy = buy_b & buy_a_recent
    sell = sell_b & sell_a_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
