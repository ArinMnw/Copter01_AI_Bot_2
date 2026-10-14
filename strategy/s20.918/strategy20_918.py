import numpy as np
import pandas as pd
import importlib.util

META = {
    "sid": "20.918",
    "name": "Mixed 143 x 379 CONFIRM",
    "concept": "เทรด Elder Impulse ยืนยันด้วย Fisher Transform",
    "logic": "A ให้สัญญาณหลักตาม Elder Impulse, B ช่วยยืนยันเมื่อเกิดการพลิกกลับของ Fisher Transform ในเวลาใกล้เคียงกัน (ภายใน 15 แท่ง) เพื่อเพิ่มโอกาสชนะในจังหวะกลับตัวที่มีนัยสำคัญ",
    "parents": ["20.143", "20.379"],
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
        mod_a = load_strategy("143")
        mod_b = load_strategy("379")
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
