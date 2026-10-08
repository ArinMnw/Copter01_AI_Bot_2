# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_227", "strategy/s20.227/strategy20_227.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_143", "strategy/s20.143/strategy20_143.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.716",
    "name": "S20.227 x S20.143 (CONFIRM w15)",
    "concept": "Elder Impulse (B) confirmed by RSI (A) - w15",
    "logic": "S20.143 provides Elder Impulse System signals. We CONFIRM these momentum shifts with S20.227 (RSI Oscillator) within the last 15 bars. Elder Impulse fires frequently during an established trend, often leading to late entries. By requiring an RSI signal (which captures overbought/oversold exhaustion and cycle reversal) to occur right before the momentum surge, we isolate the very first impulse of a newly cycling trend. The 15-bar window allows enough time for the impulse to form after the RSI exhaustion, maximizing PF and ensuring strict Jaccard uniqueness.",
    "parents": ["20.227", "20.143"],
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
