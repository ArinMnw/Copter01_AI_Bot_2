import numpy as np
import pandas as pd
import importlib.util

META = {
    "sid": "20.908",
    "name": "Mixed 161 x 277 CONFIRM",
    "concept": "เทรด Overbought/Oversold Reversal พร้อมการยืนยัน Curvature",
    "logic": "A ให้สัญญาณเมื่อเกิดเงื่อนไข Overbought/Oversold Reversal จาก Ultimate Oscillator, B ช่วยยืนยันว่าโครงสร้างราคากำลังเกิด Curvature Turn (Quadratic Regression) ไปในทิศทางเดียวกันใน 15 แท่งที่ผ่านมา เพื่อป้องกันการซื้อสวนเทรนด์ที่แข็งแกร่งเกินไป",
    "parents": ["20.161", "20.277"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 20
}

def load_strategy(sid):
    path = f'strategy/s20.{sid}/strategy20_{sid}.py'
    spec = importlib.util.spec_from_file_location(f"s20_{sid}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    try:
        mod_a = load_strategy("161")
        mod_b = load_strategy("277")
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
