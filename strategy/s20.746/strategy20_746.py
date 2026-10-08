# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_412", "strategy/s20.412/strategy20_412.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_143", "strategy/s20.143/strategy20_143.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.746",
    "name": "S20.412 x S20.143 (CONFIRM w15)",
    "concept": "Elder Impulse (B) confirmed by BB/Keltner Squeeze (A) - w15",
    "logic": "S20.143 provides Elder Impulse System pure directional momentum breakouts. We CONFIRM these momentum bursts with S20.412 (Bollinger Bands / Keltner Channel Squeeze) signals within the last 15 bars. The Squeeze pattern identifies periods of extreme low volatility (consolidation) followed by an explosive volatility breakout. By requiring the Elder Impulse momentum to ignite immediately after a Squeeze fires, we ensure we are trading the powerful momentum of a massive consolidation breakout, filtering out random momentum spikes in already overextended trends. The 15-bar window allows enough time for the fast momentum to trigger right after the volatility expansion.",
    "parents": ["20.412", "20.143"],
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
