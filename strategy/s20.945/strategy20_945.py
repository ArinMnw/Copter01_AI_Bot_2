import numpy as np
import pandas as pd
from typing import Dict, Any

META: Dict[str, Any] = {
    "sid": "20.945",
    "name": "Mixed 379 x 168 CONFIRM 24",
    "concept": "First Pullback after Super Smoother Crossover",
    "logic": "A (379) คือ DMI Pullback Re-entry (เทรดจังหวะย่อ), B (168) คือ Ehlers Super Smoother Crossover (จุดเริ่มต้นเทรนด์ใหม่). การใช้ CONFIRM 24 แท่ง จะทำให้เราเข้าเทรด Pullback (A) เฉพาะเมื่อเพิ่งเกิด Crossover (B) ขึ้นในช่วง 24 แท่งที่ผ่านมา (หา First Pullback)",
    "parents": ["20.379", "20.168"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0,
}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    import importlib.util
    import sys

    # Load Parent A (379)
    spec_a = importlib.util.spec_from_file_location("mod_a", "strategy/s20.379/strategy20_379.py")
    mod_a = importlib.util.module_from_spec(spec_a)
    spec_a.loader.exec_module(mod_a)
    sig_a = mod_a.generate(df, tf)

    # Load Parent B (168)
    spec_b = importlib.util.spec_from_file_location("mod_b", "strategy/s20.168/strategy20_168.py")
    mod_b = importlib.util.module_from_spec(spec_b)
    spec_b.loader.exec_module(mod_b)
    sig_b = mod_b.generate(df, tf)

    out = np.zeros(len(df), dtype=np.int8)
    
    # CONFIRM method (N = 24)
    for i in range(24, len(df)):
        if sig_a[i] == 1:
            if np.any(sig_b[i-24:i+1] == 1):
                out[i] = 1
        elif sig_a[i] == -1:
            if np.any(sig_b[i-24:i+1] == -1):
                out[i] = -1
                
    return out
