import numpy as np
import pandas as pd
import importlib.util
import sys

META = {
    "sid": "20.452",
    "name": "Mix 339 + 161 (FILTER)",
    "concept": "Mixed Strategy: 339 and 161",
    "logic": "Mixing 339 with 161 using FILTER. Ensure 161 state aligns.",
    "parents": ["20.339", "20.161"],
    "mix": "FILTER",
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
mod_b = load_strategy("161")

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)

    sig_b = mod_b.generate(df, tf)
    out = np.zeros(len(df), dtype=np.int8)
    
    # State of B
    state_b = pd.Series(sig_b).replace(0, np.nan).ffill().fillna(0)
    
    out[(sig_a == 1) & (state_b == 1)] = 1
    out[(sig_a == -1) & (state_b == -1)] = -1
    return out
