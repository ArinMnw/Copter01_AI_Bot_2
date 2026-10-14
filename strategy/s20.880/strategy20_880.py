import numpy as np
import pandas as pd
import importlib.util

def load_strategy(sid):
    path = f'strategy/s20.{sid}/strategy20_{sid}.py'
    spec = importlib.util.spec_from_file_location(f"s20_{sid}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

parent_a = load_strategy("143")
parent_b = load_strategy("277")

META = {
    "sid": "20.880",
    "name": "Mixed 143 x 277 VETO",
    "concept": "Hybrid Strategy",
    "logic": "test",
    "parents": ["20.143", "20.277"],
    "mix": "VETO",
    "sl_atr": 1.5,
    "rr": 2.0,
    "max_hold": 30,
    "be_r": 1.0
}

def generate(df, tf) -> np.ndarray:
    sig_a = parent_a.generate(df, tf)
    sig_b = parent_b.generate(df, tf)
    
    out = np.zeros(len(df), dtype=np.int8)
    
    # VETO: เข้าตาม A ยกเว้นเมื่อ B ให้สัญญาณตรงข้ามภายใน 3 แท่งที่ผ่านมา
    for i in range(3, len(df)):
        if sig_a[i] == 1:
            if -1 not in sig_b[i-3:i+1]:
                out[i] = 1
        elif sig_a[i] == -1:
            if 1 not in sig_b[i-3:i+1]:
                out[i] = -1
    return out
