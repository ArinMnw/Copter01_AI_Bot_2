import numpy as np
import pandas as pd
import importlib

META = {
    "sid": "20.906",
    "name": "Mixed 143 x 210 FILTER",
    "concept": "เทรด Elder Impulse เมื่อโมเมนตัมของ AC ยืนยัน",
    "logic": "A ให้สัญญาณ Elder Impulse, B ให้โมเมนตัม Bill Williams AC. กรองการเทรดโดยอนุญาตเฉพาะเมื่อสถานะโมเมนตัมของ B สนับสนุนสัญญาณของ A เพื่อป้องกัน False Breakout ในช่วงที่ AC ไม่ยืนยัน",
    "parents": ["20.143", "20.210"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 2.0,
    "max_hold": 30
}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    try:
        mod_a = importlib.import_module("strategy.s20.143.strategy20_143")
        mod_b = importlib.import_module("strategy.s20.210.strategy20_210")
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
