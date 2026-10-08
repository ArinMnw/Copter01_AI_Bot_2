# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_205", "strategy/s20.205/strategy20_205.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_307", "strategy/s20.307/strategy20_307.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.750",
    "name": "S20.205 x S20.307 (CONFIRM w15)",
    "concept": "Bollinger Band Breakout (B) confirmed by Ultimate Oscillator (A) - w15",
    "logic": "S20.307 provides pure Bollinger Band Breakouts (price closing outside the bands). We CONFIRM these volatility expansions with S20.205 (Ultimate Oscillator) signals within the last 15 bars. BB breakouts can often be fakeouts in ranging markets. The Ultimate Oscillator combines short, medium, and long-term periods (7, 14, 28) to identify robust oversold/overbought extremes. By requiring an Ultimate Oscillator extreme right before the BB breakout, we ensure the volatility expansion is backed by a true multi-timeframe cyclical pivot, filtering out random spikes. The 15-bar window preserves Jaccard uniqueness.",
    "parents": ["20.205", "20.307"],
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
