import sys, os
import numpy as np
import pandas as pd
import importlib.util

META = {
    "sid": "20.881",
    "name": "Mix 339 + 265 (FILTER)",
    "concept": "Combining Inside Bar MACD Continuation Breakout and NY Lunch Trend Reversal.",
    "logic": "Parent A (Inside Bar MACD Continuation Breakout) provides the primary setup. Parent B (NY Lunch Trend Reversal) acts as FILTER.",
    "parents": ["20.339", "20.265"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    def load_mod(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    mod_A = load_mod("mod_A", os.path.join(os.path.dirname(os.path.abspath(__file__)), f"../s20.339/strategy20_339.py"))
    mod_B = load_mod("mod_B", os.path.join(os.path.dirname(os.path.abspath(__file__)), f"../s20.265/strategy20_265.py"))

    sig_A = mod_A.generate(df, tf)
    sig_B = mod_B.generate(df, tf)
    
    out = np.zeros(len(df), dtype=np.int8)
    
    # FILTER method: A provides signal, but B's CURRENT STATE must align
    state_b = pd.Series(sig_B).replace(0, np.nan).ffill().fillna(0).values
    
    out[(sig_A == 1) & (state_b == 1)] = 1
    out[(sig_A == -1) & (state_b == -1)] = -1
                
    return out
