import numpy as np
import pandas as pd
import importlib.util

META = {
    "sid": "20.917",
    "name": "Mixed 158 x 161 FILTER",
    "concept": "เทรด HMA วกกลับกรองด้วยสถานะ UO",
    "logic": "A ให้สัญญาณหลักตามการวกกลับของ Hull MA, B กรองเฉพาะเมื่อสถานะของ Ultimate Oscillator สนับสนุนทิศทางเดียวกันในปัจจุบัน เพื่อกรองสัญญาณวกกลับหลอกในช่วงที่โมเมนตัมขัดแย้ง",
    "parents": ["20.158", "20.161"],
    "mix": "FILTER",
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
    
    state_b = sig_b_s.replace(0, np.nan).ffill().fillna(0).values
    
    out[(sig_a == 1) & (state_b == 1)] = 1
    out[(sig_a == -1) & (state_b == -1)] = -1

    return out
