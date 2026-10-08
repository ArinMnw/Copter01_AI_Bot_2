import numpy as np
import pandas as pd
import importlib.util

def load_strategy(sid):
    path = f'strategy/s20.{sid}/strategy20_{sid}.py'
    spec = importlib.util.spec_from_file_location(f"s20_{sid}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

parent_a = load_strategy("277")
parent_b = load_strategy("356")

META = {
    "sid": "20.874",
    "name": "Mixed 277 x 356 CONFIRM",
    "concept": "Hybrid Strategy",
    "logic": "277 curvature reversal confirmed by 356 volatility expansion, ensuring sufficient energy for the reversal move.",
    "parents": ["20.277", "20.356"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 2.0,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf) -> np.ndarray:
    sig_a = parent_a.generate(df, tf)
    sig_b = parent_b.generate(df, tf)
    
    out = np.zeros(len(df), dtype=np.int8)
    
    # CONFIRM: เข้าเมื่อ A มีสัญญาณ และ B มีสัญญาณทิศเดียวกันใน 3 แท่งล่าสุด
    for i in range(3, len(df)):
        if sig_a[i] == 1:
            if 1 in sig_b[i-3:i+1]:
                out[i] = 1
        elif sig_a[i] == -1:
            if -1 in sig_b[i-3:i+1]:
                out[i] = -1
    return out
