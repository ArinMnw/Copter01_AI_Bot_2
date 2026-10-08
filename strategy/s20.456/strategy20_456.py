import numpy as np
import pandas as pd
import importlib.util
import sys

META = {
    "sid": "20.456",
    "name": "Mix 422 + 168 (CONFIRM)",
    "concept": "Mixed Strategy: 422 and 168",
    "logic": "Mixing 422 with 168 using CONFIRM. Confirm 422 with 168 signal within 5 bars.",
    "parents": ["20.422", "20.168"],
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

mod_a = load_strategy("422")
mod_b = load_strategy("168")

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)

    sig_b = mod_b.generate(df, tf)
    out = np.zeros(len(df), dtype=np.int8)
    
    sig_b_s = pd.Series(sig_b)
    b_long_recent = sig_b_s.rolling(window=6, min_periods=1).max() == 1
    b_short_recent = sig_b_s.rolling(window=6, min_periods=1).min() == -1
    
    out[(sig_a == 1) & b_long_recent] = 1
    out[(sig_a == -1) & b_short_recent] = -1
    return out
