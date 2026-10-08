import numpy as np
import pandas as pd
import importlib.util
import sys

META = {
    "sid": "20.447",
    "name": "Mix 339 + 277 (CONFIRM)",
    "concept": "Mixed Strategy: 339 and 277",
    "logic": "Mixing 339 with 277 using CONFIRM. Confirm 339 with 277 signal within 3 bars.",
    "parents": ["20.339", "20.277"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def load_strategy(sid):
    path = f'strategy/s20.{sid}/strategy20_{sid}.py'
    spec = importlib.util.spec_from_file_location(f"s20_{sid}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

mod_a = load_strategy("339")
mod_b = load_strategy("277")

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)

    sig_b = mod_b.generate(df, tf)
    out = np.zeros(len(df), dtype=np.int8)
    
    sig_b_s = pd.Series(sig_b)
    b_long_recent = sig_b_s.rolling(window=4, min_periods=1).max() == 1
    b_short_recent = sig_b_s.rolling(window=4, min_periods=1).min() == -1
    
    out[(sig_a == 1) & b_long_recent] = 1
    out[(sig_a == -1) & b_short_recent] = -1
    return out
