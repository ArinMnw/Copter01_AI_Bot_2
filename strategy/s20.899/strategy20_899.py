import sys, os
import numpy as np
import pandas as pd
import importlib.util

META = {
    "sid": "20.899",
    "name": "Mix 422 + 205 (CONFIRM)",
    "concept": "Combining Triple MA Volatility Breakout and DiNapoli Single Penetration of DMA 3x3.",
    "logic": "Parent A (Triple MA Volatility Breakout) provides the primary setup. Parent B (DiNapoli Single Penetration of DMA 3x3) acts as CONFIRM.",
    "parents": ["20.422", "20.205"],
    "mix": "CONFIRM",
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

    mod_A = load_mod("mod_A", os.path.join(os.path.dirname(os.path.abspath(__file__)), f"../s20.422/strategy20_422.py"))
    mod_B = load_mod("mod_B", os.path.join(os.path.dirname(os.path.abspath(__file__)), f"../s20.205/strategy20_205.py"))

    sig_A = mod_A.generate(df, tf)
    sig_B = mod_B.generate(df, tf)
    
    out = np.zeros(len(df), dtype=np.int8)
    
    # CONFIRM method: enter on A's signal if B has same signal within last 5 bars
    for i in range(5, len(df)):
        if sig_A[i] == 1:
            if any(sig_B[i-k] == 1 for k in range(5)):
                out[i] = 1
        elif sig_A[i] == -1:
            if any(sig_B[i-k] == -1 for k in range(5)):
                out[i] = -1
                
    return out
