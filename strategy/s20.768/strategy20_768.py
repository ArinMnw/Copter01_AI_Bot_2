import sys, os
sys.path.insert(0, os.path.abspath('.'))
import numpy as np
import pandas as pd
from strategy.s20_gen.ind import *
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_161", "strategy/s20.161/strategy20_161.py")
parent_A = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(parent_A)

spec_b = importlib.util.spec_from_file_location("s20_242", "strategy/s20.242/strategy20_242.py")
parent_B = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(parent_B)

META = {
    "sid": "20.768",
    "name": "S20.161 x S20.242 (FILTER)",
    "concept": "FILTER",
    "logic": "161 (Ultimate Osc) filtered by 242 (Rainbow MA) trend",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 20,
    "be_r": 0.0,
    "parents": ["20.161", "20.242"],
    "mix": "FILTER"
}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    out_A = parent_A.generate(df, tf)
    sig_A = out_A[0] if isinstance(out_A, tuple) else out_A
    out_B = parent_B.generate(df, tf)
    sig_B = out_B[0] if isinstance(out_B, tuple) else out_B
    out = np.zeros(len(df), dtype=np.int8)
    
    s_b = pd.Series(sig_B).replace(0, np.nan).ffill().fillna(0).values
    out = np.where((sig_A == 1) & (s_b == 1), 1, np.where((sig_A == -1) & (s_b == -1), -1, 0))
    return out
