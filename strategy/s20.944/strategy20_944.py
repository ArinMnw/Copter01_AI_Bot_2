import numpy as np
import pandas as pd
from typing import Dict, Any

META: Dict[str, Any] = {
    "sid": "20.944",
    "name": "Mixed 708 x 210 FILTER",
    "concept": "Elder/Fisher filtered by Bill Williams AC",
    "logic": "A (708) คือสัญญาณที่กรองมาจาก Elder Impulse และ Fisher Transform, B (210) คือ Bill Williams Accelerator Oscillator (AC) ที่ใช้บอกโมเมนตัมของการเร่งตัว การใช้ FILTER จะทำให้เราเปิดออร์เดอร์ตาม A ก็ต่อเมื่อ AC ชี้ว่าทิศทางนั้นกำลังมีความเร่งอยู่จริงเท่านั้น",
    "parents": ["20.708", "20.210"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0,
}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    import importlib.util
    import sys

    # Load Parent A (708)
    spec_a = importlib.util.spec_from_file_location("mod_a", "strategy/s20.708/strategy20_708.py")
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
