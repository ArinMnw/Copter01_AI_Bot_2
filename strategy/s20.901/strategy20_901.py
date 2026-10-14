import numpy as np
import pandas as pd
import importlib

META = {
    "sid": "20.901",
    "name": "Mixed 422 x 689 CONFIRM",
    "concept": "เทรด Breakout พร้อมยืนยันเทรนด์ระยะกลาง",
    "logic": "A ให้จุดเข้าจากการระเบิดของความผันผวนพร้อมแรงส่ง ADX, B ช่วยยืนยันว่าโครงสร้างเทรนด์ทั้งระยะสั้น (Rainbow MA) และระยะกลางสอดคล้องกัน ป้องกันการเบรกเอาต์หลอก",
    "parents": ["20.422", "20.689"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    try:
        mod_a = importlib.import_module("strategy.s20.422.strategy20_422")
        mod_b = importlib.import_module("strategy.s20.689.strategy20_689")
    except ImportError:
        return np.zeros(len(df), dtype=np.int8)

    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)

    sig = np.zeros(len(df), dtype=np.int8)
    
    # CONFIRM window 5 bars
    for i in range(5, len(df)):
        if sig_a[i] == 1:
            if np.any(sig_b[i-5:i+1] == 1):
                sig[i] = 1
        elif sig_a[i] == -1:
            if np.any(sig_b[i-5:i+1] == -1):
                sig[i] = -1

    return sig
