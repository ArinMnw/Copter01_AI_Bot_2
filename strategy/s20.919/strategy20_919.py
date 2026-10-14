import numpy as np
import pandas as pd
import importlib.util

META = {
    "sid": "20.919",
    "name": "Mixed 148 x 379 CONFIRM",
    "concept": "เทรด IB Breakout ยืนยันด้วย Fisher",
    "logic": "A ให้สัญญาณจุดเข้าจากการเบรกกรอบ Inside-Bar ตามแนวโน้ม EMA50, B ช่วยยืนยันโดยต้องมีการพลิกกลับของ Fisher Transform ใน 15 แท่งที่ผ่านมา เพื่อยืนยันโมเมนตัมเบรกเอาต์",
    "parents": ["20.148", "20.379"],
    "mix": "CONFIRM",
    "sl_atr": 1.2,
    "rr": 2.0,
    "max_hold": 24
}

def load_strategy(sid):
    path = f'strategy/s20.{sid}/strategy20_{sid}.py'
    spec = importlib.util.spec_from_file_location(f"s20_{sid}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    try:
        mod_a = load_strategy("148")
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
