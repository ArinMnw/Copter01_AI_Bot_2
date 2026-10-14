import numpy as np
import pandas as pd
from typing import Dict, Any

META: Dict[str, Any] = {
    "sid": "20.948",
    "name": "Mixed 854 x 210 FILTER",
    "concept": "Rainbow/KST filtered by Accelerator Oscillator",
    "logic": "A (854) เป็นเทรนด์ที่มีโมเมนตัม KST คอนเฟิร์ม, B (210) เป็น Bill Williams Accelerator Oscillator การใช้ FILTER เพื่อจำกัดให้เข้าเทรดเฉพาะเวลาที่ความเร่ง (AC) มีทิศทางเดียวกับเทรนด์และโมเมนตัมเท่านั้น (ตัดจังหวะที่เทรนด์ยังอยู่แต่ความเร่งเริ่มหมดลง)",
    "parents": ["20.854", "20.210"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0,
}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    import importlib.util
    import sys

    # Load Parent A (854)
    spec_a = importlib.util.spec_from_file_location("mod_a", "strategy/s20.854/strategy20_854.py")
    mod_a = importlib.util.module_from_spec(spec_a)
    spec_a.loader.exec_module(mod_a)
    sig_a = mod_a.generate(df, tf)

    # Load Parent B (210)
    spec_b = importlib.util.spec_from_file_location("mod_b", "strategy/s20.210/strategy20_210.py")
    mod_b = importlib.util.module_from_spec(spec_b)
    spec_b.loader.exec_module(mod_b)
    sig_b = mod_b.generate(df, tf)

    out = np.zeros(len(df), dtype=np.int8)
    
    # FILTER method
    state_b = np.zeros(len(df), dtype=np.int8)
    curr_state = 0
    for i in range(len(df)):
        if sig_b[i] != 0:
            curr_state = sig_b[i]
        state_b[i] = curr_state
        
    for i in range(len(df)):
        if sig_a[i] == 1 and state_b[i] == 1:
            out[i] = 1
        elif sig_a[i] == -1 and state_b[i] == -1:
            out[i] = -1
                
    return out
