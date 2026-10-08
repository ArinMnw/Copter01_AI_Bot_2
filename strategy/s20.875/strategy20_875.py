import numpy as np
import pandas as pd
import importlib.util

def load_strategy(sid):
    path = f'strategy/s20.{sid}/strategy20_{sid}.py'
    spec = importlib.util.spec_from_file_location(f"s20_{sid}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

parent_a = load_strategy("161")
parent_b = load_strategy("237")

META = {
    "sid": "20.875",
    "name": "Mixed 161 x 237 FILTER",
    "concept": "Hybrid Strategy",
    "logic": "161 momentum shift only traded if 237 FRAMA confirms the trend direction.",
    "parents": ["20.161", "20.237"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 20,
    "be_r": 1.0
}

def generate(df, tf) -> np.ndarray:
    sig_a = parent_a.generate(df, tf)
    sig_b = parent_b.generate(df, tf)
    
    out = np.zeros(len(df), dtype=np.int8)
    
    # FILTER: เข้าตาม A เฉพาะเมื่อ B ชี้ไปทิศเดียวกัน
    # หาทิศทางล่าสุดของ B
    state_b = np.zeros(len(df), dtype=np.int8)
    curr = 0
    for i in range(len(df)):
        if sig_b[i] != 0:
            curr = sig_b[i]
        state_b[i] = curr
        
    for i in range(len(df)):
        if sig_a[i] == 1 and state_b[i] == 1:
            out[i] = 1
        elif sig_a[i] == -1 and state_b[i] == -1:
            out[i] = -1
    return out
