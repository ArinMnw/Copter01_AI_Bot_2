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
parent_b = load_parent("766")

META = {
    "sid": "20.772",
    "name": "Mixed 339 x 766 FILTER",
    "concept": "FILTER mix of 20.339 and 20.766",
    "logic": "339 provides the primary setup, 766 acts as FILTER to improve timing.",
    "parents": ["20.339", "20.766"],
    "mix": "FILTER",
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
    
    b_state = pd.Series(sig_b).replace(0, np.nan).ffill().fillna(0)
    
    buy_sig = buy_a & (b_state == 1)
    sell_sig = sell_a & (b_state == -1)
    return ind.sig_from(buy_sig, sell_sig)
