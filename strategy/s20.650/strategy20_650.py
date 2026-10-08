# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_194", "strategy/s20.194/strategy20_194.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

META = {
    "sid": "20.650",
    "name": "S20.194 x S20.409 (FILTER)",
    "concept": "Chande Kroll Flip (A) filtered by PSAR Keltner State (B)",
    "logic": "S20.194 provides Chande Kroll Stop trend flip signals. We FILTER these flips using the continuous state of S20.409 (PSAR aligned, ADX > 20, and Price beyond Keltner Mid). This filters out weak trend flips that occur during low-volatility chop, ensuring we only trade Chande Kroll reversals that have strong momentum backing.",
    "parents": ["20.194", "20.409"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    
    # B: PSAR Keltner Momentum State
    sar, sar_trend = ind.psar(df, 0.02, 0.2)
    pdi, ndi, adx = ind.dmi(df, 14)
    ku, km, kl = ind.keltner(df, 20, 2.0)
    
    state_b_up = (sar_trend == 1) & (adx > 20) & (df["close"] > km)
    state_b_dn = (sar_trend == -1) & (adx > 20) & (df["close"] < km)
    
    buy_a = sig_a == 1
    sell_a = sig_a == -1
    
    buy = buy_a & state_b_up
    sell = sell_a & state_b_dn
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
