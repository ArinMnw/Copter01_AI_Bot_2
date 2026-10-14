import numpy as np
import pandas as pd
import importlib

META = {
    "sid": "20.904",
    "name": "Mixed 194 x 148 CONFIRM",
    "concept": "เทรดจุดพลิกกลับเทรนด์ที่มีการระเบิดจากกรอบ",
    "logic": "A ให้จุดพลิกกลับของเทรนด์ตาม Chande Kroll Stop Flip, B ยืนยันว่าก่อนหน้าหรือพร้อมกันนั้นมีการบีบตัวและระเบิดออกจาก Inside-Bar เพื่อเป็นตัวยืนยันโมเมนตัมที่แท้จริง ไม่ใช่การพลิกเทรนด์หลอก",
    "parents": ["20.194", "20.148"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 2.0,
    "max_hold": 30
}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    try:
        mod_a = importlib.import_module("strategy.s20.194.strategy20_194")
        mod_b = importlib.import_module("strategy.s20.148.strategy20_148")
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
