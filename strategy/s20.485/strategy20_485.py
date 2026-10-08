# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

META = {
    "sid": "20.485",
    "name": "Mix 422 + 161 (CONFIRM)",
    "concept": "Mix Strategy",
    "logic": "A ให้ทิศของเทรนด์ใหญ่, B ให้จังหวะเข้าซ้อนยืนยันภายใน 5 แท่ง เพื่อกรอง false breakout",
    "parents": ["20.422", "20.161"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    def load_mod(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    mod_A = load_mod("parent_A", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", f"s20.422", f"strategy20_422.py"))
    mod_B = load_mod("parent_B", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", f"s20.161", f"strategy20_161.py"))
    sig_A = mod_A.generate(df, tf)
    sig_B = mod_B.generate(df, tf)

    sig_B_bull = pd.Series(sig_B == 1).rolling(5).max() == 1
    sig_B_bear = pd.Series(sig_B == -1).rolling(5).max() == 1
    buy = (sig_A == 1) & sig_B_bull
    sell = (sig_A == -1) & sig_B_bear

    return ind.sig_from(buy, sell)
