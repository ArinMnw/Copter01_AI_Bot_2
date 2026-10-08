import sys, os
sys.path.insert(0, os.path.abspath('.'))
import numpy as np
import pandas as pd
from strategy.s20_gen.ind import *
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_148", "strategy/s20.148/strategy20_148.py")
parent_A = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(parent_A)

spec_b = importlib.util.spec_from_file_location("s20_255", "strategy/s20.255/strategy20_255.py")
parent_B = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(parent_B)

META = {
    "sid": "20.767",
    "name": "S20.148 x S20.255 (CONFIRM)",
    "concept": "CONFIRM",
    "logic": "148 (Inside Bar) confirmed by 255 (Hikkake Inside Bar False Breakout)",
    "sl_atr": 1.2,
    "rr": 2.0,
    "max_hold": 24,
    "be_r": 0.0,
    "parents": ["20.148", "20.255"],
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
