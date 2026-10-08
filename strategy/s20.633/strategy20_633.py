# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_143", "strategy/s20.143/strategy20_143.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_168", "strategy/s20.168/strategy20_168.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.633",
    "name": "S20.143 x S20.168 (FILTER)",
    "concept": "Elder Impulse (A) filtered by Ehlers Smoother Trend (B)",
    "logic": "S20.143 provides Elder Impulse System signals (MACD hist + EMA13 momentum bursts). We FILTER these signals using the state of S20.168 (Ehlers Super Smoother 10/40). We only take the Elder Impulse buy if the Ehlers Super Smoother trend is currently bullish (+1 state). This aligns short-term momentum bursts with a high-fidelity, zero-lag structural trend.",
    "parents": ["20.143", "20.168"],
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
    
    # FILTER: B's continuous state must align
    state_b = pd.Series(sig_b).replace(0, np.nan).ffill().fillna(0).values
    
    buy = buy_a & (state_b == 1)
    sell = sell_a & (state_b == -1)
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
