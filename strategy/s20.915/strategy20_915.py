import numpy as np
import pandas as pd
import importlib.util

META = {
    "sid": "20.915",
    "name": "Mixed 158 x 210 CONFIRM",
    "concept": "เทรด HMA วกกลับยืนยันด้วย AC",
    "logic": "A ให้จุดเข้าเมื่อ Hull MA เกิดการวกกลับพร้อมกับ Bias หลัก, B ช่วยยืนยันว่าในช่วง 15 แท่งที่ผ่านมา โมเมนตัมจากการเร่งตัวของ AC เป็นใจให้กับการวกกลับนั้น",
    "parents": ["20.158", "20.210"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 2.0,
    "max_hold": 30
}

def load_strategy(sid):
    path = f'strategy/s20.{sid}/strategy20_{sid}.py'
    spec = importlib.util.spec_from_file_location(f"s20_{sid}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    try:
        mod_a = load_strategy("158")
        mod_b = load_strategy("210")
    except Exception:
        return np.zeros(len(df), dtype=np.int8)

    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)

    out = np.zeros(len(df), dtype=np.int8)
    sig_b_s = pd.Series(sig_b)
    
    b_long_recent = sig_b_s.rolling(window=15, min_periods=1).max() == 1
    b_short_recent = sig_b_s.rolling(window=15, min_periods=1).min() == -1
    
    out[(sig_a == 1) & b_long_recent] = 1
    out[(sig_a == -1) & b_short_recent] = -1

    return out
