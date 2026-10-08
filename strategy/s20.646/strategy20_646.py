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

spec_b = importlib.util.spec_from_file_location("s20_356", "strategy/s20.356/strategy20_356.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.646",
    "name": "S20.168 x S20.356 (CONFIRM)",
    "concept": "Ehlers Crossover (A) confirmed by Volatility Explosion (B) - W25",
    "logic": "S20.168 provides Ehlers Super Smoother trend crossover signals. We CONFIRM these structural trend shifts with S20.356 (Bollinger Z-Score Volatility Explosion) within the last 25 bars. We only enter the trend if a severe volatility expansion recently occurred, filtering out false crossovers in low-volume chop.",
    "parents": ["20.168", "20.356"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 2.0,
    "max_hold": 40
}

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    
    buy_a = sig_a == 1
    sell_a = sig_a == -1
    
    buy_b = sig_b == 1
    sell_b = sig_b == -1
    
    # CONFIRM: B gave same signal within k=25 bars
    buy_b_recent = pd.Series(buy_b).rolling(25).max().fillna(0).astype(bool).values
    sell_b_recent = pd.Series(sell_b).rolling(25).max().fillna(0).astype(bool).values
    
    buy = buy_a & buy_b_recent
    sell = sell_a & sell_b_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
