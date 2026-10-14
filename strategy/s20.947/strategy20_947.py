import numpy as np
import pandas as pd
from typing import Dict, Any

META: Dict[str, Any] = {
    "sid": "20.947",
    "name": "Mixed 379 x 342 CONFIRM 24",
    "concept": "First Pullback after Volatility Breakout",
    "logic": "A (379) ให้จังหวะ Pullback Re-entry ขณะมีเทรนด์แรง, B (342) คือ ADX Volatility Breakout จากสภาวะบีบตัว. การใช้ CONFIRM 24 แท่ง จะเป็นการเข้าเทรดเฉพาะจังหวะย่อตัว (A) ที่เพิ่งเกิดหลังจากมี Breakout การขยายตัวของความผันผวนใหม่ๆ (B) ภายใน 24 แท่งที่ผ่านมา เป็นการดักเทรดชุดย่อแรกหลังการระเบิดของราคา",
    "parents": ["20.379", "20.342"],
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

    # Load Parent B (342)
    spec_b = importlib.util.spec_from_file_location("mod_b", "strategy/s20.342/strategy20_342.py")
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
