import numpy as np
import pandas as pd
from typing import Dict, Any

META: Dict[str, Any] = {
    "sid": "20.950",
    "name": "Mixed 854 x 168 CONFIRM 48",
    "concept": "Early Trend Momentum Burst",
    "logic": "A (854) เป็นสัญญาณเข้าเทรดที่มีโมเมนตัม KST รองรับ, B (168) คือจุดเริ่มต้นเทรนด์ใหม่จาก Ehlers Super Smoother Crossover การใช้ CONFIRM 48 แท่ง จะทำให้เราเข้าเทรดโมเมนตัมของ A ได้เฉพาะในช่วงต้นเทรนด์ (ภายใน 48 แท่งหลังจากเกิดเทรนด์ครอส B) เป็นการเน้นเก็บ Early Trend",
    "parents": ["20.854", "20.168"],
    "mix": "CONFIRM",
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

    # Load Parent B (168)
    spec_b = importlib.util.spec_from_file_location("mod_b", "strategy/s20.168/strategy20_168.py")
    mod_b = importlib.util.module_from_spec(spec_b)
    spec_b.loader.exec_module(mod_b)
    sig_b = mod_b.generate(df, tf)

    out = np.zeros(len(df), dtype=np.int8)
    
    # CONFIRM method (N = 48)
    for i in range(48, len(df)):
        if sig_a[i] == 1:
            if np.any(sig_b[i-48:i+1] == 1):
                out[i] = 1
        elif sig_a[i] == -1:
            if np.any(sig_b[i-48:i+1] == -1):
                out[i] = -1
                
    return out
