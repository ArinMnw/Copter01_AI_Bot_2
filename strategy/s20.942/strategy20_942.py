import numpy as np
import pandas as pd
from typing import Dict, Any

META: Dict[str, Any] = {
    "sid": "20.942",
    "name": "Mixed 339 x 708 CONFIRM",
    "concept": "Inside Bar Breakout confirmed by Elder Impulse/Fisher",
    "logic": "A (339) ให้สัญญาณ breakout จาก Inside Bar ตามเทรนด์ MACD, B (708) คือ Elder Impulse+Fisher ที่วัด momentum ระยะสั้น. การใช้ B มา CONFIRM ภายใน 5 แท่งช่วยกรองสัญญาณเข้าเมื่อ breakout เกิดพร้อมกับแรงขับเคลื่อนที่แข็งแกร่งเท่านั้น",
    "parents": ["20.339", "20.708"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0,
}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    import importlib.util
    import sys

    # Load Parent A (339)
    spec_a = importlib.util.spec_from_file_location("mod_a", "strategy/s20.339/strategy20_339.py")
    mod_a = importlib.util.module_from_spec(spec_a)
    spec_a.loader.exec_module(mod_a)
    sig_a = mod_a.generate(df, tf)

    # Load Parent B (708)
    spec_b = importlib.util.spec_from_file_location("mod_b", "strategy/s20.708/strategy20_708.py")
    mod_b = importlib.util.module_from_spec(spec_b)
    spec_b.loader.exec_module(mod_b)
    sig_b = mod_b.generate(df, tf)

    out = np.zeros(len(df), dtype=np.int8)
    
    # CONFIRM method: Enter if A triggers and B triggered in same direction within 5 bars
    for i in range(5, len(df)):
        if sig_a[i] == 1:
            # Check if B gave +1 within last 5 bars (i-5 to i)
            if np.any(sig_b[i-5:i+1] == 1):
                out[i] = 1
        elif sig_a[i] == -1:
            if np.any(sig_b[i-5:i+1] == -1):
                out[i] = -1
                
    return out
