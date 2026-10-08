# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import ind
import importlib.util

def load_parent(sid):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", f"s20.{sid}", f"strategy20_{sid}.py")
    spec = importlib.util.spec_from_file_location(f"strategy20_{sid}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

parent_a = load_parent("339")
parent_b = load_parent("762")

META = {
    "sid": "20.779",
    "name": "Mixed 339 x 762 CONFIRM",
    "concept": "CONFIRM mix of 20.339 and 20.762",
    "logic": "339 provides the primary setup, 762 acts as CONFIRM to improve timing.",
    "parents": ["20.339", "20.762"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = parent_a.generate(df, tf)
    sig_b = parent_b.generate(df, tf)

    import pandas as pd
    buy_a = (sig_a == 1)
    sell_a = (sig_a == -1)
    
    b_buy_recent = pd.Series(sig_b == 1).rolling(4, min_periods=1).max() > 0
    b_sell_recent = pd.Series(sig_b == -1).rolling(4, min_periods=1).max() > 0
    
    buy_sig = buy_a & b_buy_recent
    sell_sig = sell_a & b_sell_recent
    return ind.sig_from(buy_sig, sell_sig)
