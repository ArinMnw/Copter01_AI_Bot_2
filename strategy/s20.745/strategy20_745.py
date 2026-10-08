# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_158", "strategy/s20.158/strategy20_158.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_281", "strategy/s20.281/strategy20_281.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.745",
    "name": "S20.158 x S20.281 (CONFIRM w15)",
    "concept": "Schaff Trend Cycle (B) confirmed by PA U-Turn (A) - w15",
    "logic": "S20.281 provides Schaff Trend Cycle (STC) reversals. We CONFIRM these cycle shifts with S20.158 (Price Action U-Turn) signals within the last 15 bars. STC combines MACD and Stochastic to find cyclical momentum trends with less lag, but can still trigger in ranging markets. PA U-Turn strictly identifies 3-bar candlestick reversal patterns. By requiring a U-Turn to occur right before the STC reversal, we guarantee the mathematical cycle shift is supported by an actual price action bottom or top. The 15-bar window preserves Jaccard uniqueness.",
    "parents": ["20.158", "20.281"],
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
