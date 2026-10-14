import numpy as np
import pandas as pd
import importlib.util

META = {
    "sid": "20.907",
    "name": "Mixed 194 x 471 CONFIRM",
    "concept": "เทรดจุดพลิกกลับเทรนด์พร้อมยืนยันความผันผวน",
    "logic": "A ให้จุดพลิกกลับเทรนด์จาก Chande Kroll Stop Flip, B ช่วยยืนยันว่าการเบรกเอาต์ความผันผวน (422) ร่วมกับโครงสร้างราคา (158) สอดคล้องไปในทางเดียวกันใน 15 แท่งที่ผ่านมา ช่วยกรองสัญญาณเท็จจาก A",
    "parents": ["20.194", "20.471"],
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
        mod_a = load_strategy("194")
        mod_b = load_strategy("471")
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
