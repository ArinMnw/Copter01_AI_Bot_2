import numpy as np
import pandas as pd
from typing import Dict, Any

META: Dict[str, Any] = {
    "sid": "20.943",
    "name": "Mixed 143 x 854 CONFIRM",
    "concept": "Elder Impulse Color Shift confirmed by Rainbow/KST",
    "logic": "A (143) ให้สัญญาณเปลี่ยนสีของ Elder Impulse (แรงโมเมนตัมระยะสั้น), B (854) ยืนยันด้วยโครงสร้างเทรนด์และโมเมนตัมจาก Rainbow MA + KST. การนำ B มา CONFIRM ภายใน 5 แท่งช่วยเน้นให้การเข้าเทรดจาก Elder Impulse เกิดขึ้นในจังหวะที่มีรอบโมเมนตัมของ KST และโครงสร้างเทรนด์เรียงตัวสมบูรณ์แล้ว",
    "parents": ["20.143", "20.854"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 2.0,
    "max_hold": 30,
    "be_r": 0.0,
}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    import importlib.util
    import sys

    # Load Parent A (143)
    spec_a = importlib.util.spec_from_file_location("mod_a", "strategy/s20.143/strategy20_143.py")
    mod_a = importlib.util.module_from_spec(spec_a)
    spec_a.loader.exec_module(mod_a)
    sig_a = mod_a.generate(df, tf)

    # Load Parent B (854)
    spec_b = importlib.util.spec_from_file_location("mod_b", "strategy/s20.854/strategy20_854.py")
    mod_b = importlib.util.module_from_spec(spec_b)
    spec_b.loader.exec_module(mod_b)
    sig_b = mod_b.generate(df, tf)

    out = np.zeros(len(df), dtype=np.int8)
    
    # CONFIRM method
    for i in range(5, len(df)):
        if sig_a[i] == 1:
            if np.any(sig_b[i-5:i+1] == 1):
                out[i] = 1
        elif sig_a[i] == -1:
            if np.any(sig_b[i-5:i+1] == -1):
                out[i] = -1
                
    return out
