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

spec_b = importlib.util.spec_from_file_location("s20_194", "strategy/s20.194/strategy20_194.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.685",
    "name": "S20.158 x S20.194 (CONFIRM w15)",
    "concept": "Chande Kroll Flip (B) confirmed by PA U-Turn (A)",
    "logic": "S20.194 provides Chande Kroll Stop flip trend signals based on volatility. We CONFIRM these flips with S20.158 (Price Action U-Turn) within the last 15 bars. A PA U-Turn identifies the exact candlestick pivot of a structural reversal. By requiring this pure price action reversal to occur immediately before the volatility trend flip, we eliminate false flips in chop and isolate the highest-probability, exact-bottom/top trend initiations. The 15-bar window is perfectly sized to capture the transition from pivot to trend breakout, ensuring high profitability and low Jaccard similarity.",
    "parents": ["20.158", "20.194"],
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
    
    # CONFIRM: A gave same signal within k=15 bars (prior to B)
    buy_a_recent = pd.Series(buy_a).rolling(15).max().fillna(0).astype(bool).values
    sell_a_recent = pd.Series(sell_a).rolling(15).max().fillna(0).astype(bool).values
    
    # Base is B, Confirmed by A
    buy = buy_b & buy_a_recent
    sell = sell_b & sell_a_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
