import numpy as np
import pandas as pd
from typing import Dict, Any

META: Dict[str, Any] = {
    "sid": "20.949",
    "name": "Mixed 255 x 210 FILTER",
    "concept": "Hikkake filtered by Accelerator Oscillator",
    "logic": "A (255) คือ Hikkake Inside-Bar False Breakout, B (210) คือ Bill Williams Accelerator Oscillator การใช้ FILTER เพื่อให้เราเข้าเทรดทิศทาง Hikkake เฉพาะเมื่อความเร่ง (AC) ชี้ไปในทิศทางเดียวกันเท่านั้น ช่วยกรองสัญญาณหลอกที่ไม่มีแรงเหวี่ยงสนับสนุน",
    "parents": ["20.255", "20.210"],
    "mix": "FILTER",
    "sl_atr": 1.2,
    "rr": 2.0,
    "max_hold": 20,
    "be_r": 0.0,
}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    import importlib.util
    import sys

    # Load Parent A (255)
    spec_a = importlib.util.spec_from_file_location("mod_a", "strategy/s20.255/strategy20_255.py")
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
