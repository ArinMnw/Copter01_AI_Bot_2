import numpy as np
import pandas as pd
import importlib

META = {
    "sid": "20.905",
    "name": "Mixed 194 x 342 FILTER",
    "concept": "เทรดจุดพลิกกลับเทรนด์ที่มีการระเบิดจากความผันผวนต่ำ",
    "logic": "A ให้สัญญาณหลักจาก Chande Kroll Stop Flip, B กรองเฉพาะเมื่อทิศทางล่าสุดของ ADX Low Volatility Breakout ชี้ไปในทางเดียวกัน ป้องกันสัญญาณ A ที่เกิดในช่วงราคาพักตัวไม่มีทิศทางชัดเจน",
    "parents": ["20.194", "20.342"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 2.0,
    "max_hold": 30
}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    try:
        mod_a = importlib.import_module("strategy.s20.194.strategy20_194")
        mod_b = importlib.import_module("strategy.s20.342.strategy20_342")
    except ImportError:
        return np.zeros(len(df), dtype=np.int8)

    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)

    sig = np.zeros(len(df), dtype=np.int8)
    
    state_b = 0
    for i in range(len(df)):
        if sig_b[i] != 0:
            state_b = sig_b[i]
            
        if sig_a[i] == 1 and state_b == 1:
            sig[i] = 1
        elif sig_a[i] == -1 and state_b == -1:
            sig[i] = -1

    return sig
