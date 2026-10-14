import numpy as np
import pandas as pd
import importlib.util

META = {
    "sid": "20.913",
    "name": "Mixed 161 x 342 FILTER",
    "concept": "เทรดการกลับตัว UO เมื่อออกจาก Choppy Zone",
    "logic": "A ให้สัญญาณหลักจากจุดกลับตัว Oversold/Overbought ของ Ultimate Oscillator, B กรองเฉพาะเมื่อสถานะตลาดทะลุ Choppy Zone ออกมาแล้วและมีโมเมนตัมแข็งแกร่งเท่านั้น เพื่อป้องกันสัญญาณลวงจากการแกว่งตัวแคบ ๆ",
    "parents": ["20.161", "20.342"],
    "mix": "FILTER",
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
        mod_b = load_strategy("342")
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
