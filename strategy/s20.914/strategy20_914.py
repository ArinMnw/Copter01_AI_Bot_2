import numpy as np
import pandas as pd
import importlib.util

META = {
    "sid": "20.914",
    "name": "Mixed 158 x 161 CONFIRM",
    "concept": "เทรด HMA วกกลับร่วมกับการกลับตัวของ UO",
    "logic": "A ให้จุดเข้าหลักเมื่อ Hull MA ทำการวกกลับและสอดคล้องกับ Bias, B ช่วยยืนยันว่าการกลับตัวนี้เกิดขึ้นพร้อมกับสัญญาณกลับตัวจากโซน Overbought/Oversold ของ Ultimate Oscillator ใน 15 แท่งที่ผ่านมา เพื่อความแม่นยำของการกลับตัว",
    "parents": ["20.158", "20.161"],
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
        mod_b = load_strategy("161")
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
