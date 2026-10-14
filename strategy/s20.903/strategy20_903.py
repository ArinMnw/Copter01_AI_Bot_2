import numpy as np
import pandas as pd
import importlib

META = {
    "sid": "20.903",
    "name": "Mixed 339 x 732 FILTER",
    "concept": "เทรด Breakout ต่อเนื่องเมื่อเทรนด์หลักยืนยัน",
    "logic": "A ให้จุดเข้า Continuation Breakout ตามโมเมนตัม MACD, B กรองเฉพาะเมื่อสถานะเทรนด์ระยะกลางที่ยืนยันจากการรวมกันของ Elder Impulse และระบบ Trend หลักยังคงสนับสนุน",
    "parents": ["20.339", "20.732"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    try:
        mod_a = importlib.import_module("strategy.s20.339.strategy20_339")
        mod_b = importlib.import_module("strategy.s20.732.strategy20_732")
    except ImportError:
        return np.zeros(len(df), dtype=np.int8)

    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)

    sig = np.zeros(len(df), dtype=np.int8)
    
    # Track state of B
    state_b = 0
    for i in range(len(df)):
        if sig_b[i] != 0:
            state_b = sig_b[i]
            
        if sig_a[i] == 1 and state_b == 1:
            sig[i] = 1
        elif sig_a[i] == -1 and state_b == -1:
            sig[i] = -1

    return sig
