import sys, os
sys.path.insert(0, os.path.abspath('.'))
import numpy as np
import pandas as pd
from strategy.s20_gen.ind import *
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_194", "strategy/s20.194/strategy20_194.py")
parent_A = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(parent_A)

spec_b = importlib.util.spec_from_file_location("s20_168", "strategy/s20.168/strategy20_168.py")
parent_B = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(parent_B)

META = {
    "sid": "20.766",
    "name": "S20.194 x S20.168 (CONFIRM)",
    "concept": "CONFIRM",
    "logic": "194 (Chande Kroll) combined with 168 (Ehlers Super Smoother) for confirmation within 5 bars",
    "sl_atr": 1.5,
    "rr": 2.0,
    "max_hold": 30,
    "be_r": 0.0,
    "parents": ["20.194", "20.168"],
    "mix": "CONFIRM"
}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    out_A = parent_A.generate(df, tf)
    sig_A = out_A[0] if isinstance(out_A, tuple) else out_A
    out_B = parent_B.generate(df, tf)
    sig_B = out_B[0] if isinstance(out_B, tuple) else out_B
    out = np.zeros(len(df), dtype=np.int8)
    
    s_b_buy = pd.Series(sig_B == 1).rolling(5, min_periods=1).max().astype(bool).values
    s_b_sell = pd.Series(sig_B == -1).rolling(5, min_periods=1).max().astype(bool).values
    out = np.where((sig_A == 1) & s_b_buy, 1, np.where((sig_A == -1) & s_b_sell, -1, 0))
    return out
