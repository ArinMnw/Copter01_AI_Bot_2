# -*- coding: utf-8 -*-
import sys, os
import importlib.util
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

s275_mod = load_mod("s275", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.275", "strategy20_275.py"))
s281_mod = load_mod("s281", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.281", "strategy20_281.py"))

META = {
    "sid": "20.511",
    "name": "MACD Divergence ZLEMA Confirm",
    "concept": "เทรด MACD Divergence (A) ที่ถูก Confirm ว่ามีการตัดกันของเส้น Zero-Lag EMA (B) ภายใน 5 แท่ง",
    "logic": "A (275) จับจังหวะ Divergence ที่ปลายเทรนด์ ส่วน B (281) คือการตัดกันของ Zero-Lag EMA (เส้นค่าเฉลี่ยที่ลดความหน่วง) การผสมแบบ CONFIRM (5 แท่ง) จะทำให้เข้าออเดอร์สวนเทรนด์เมื่อได้จังหวะ Divergence แล้วราคาขยับจนสามารถพลิกโมเมนตัมแบบ ZLEMA ได้สำเร็จ",
    "parents": ["20.275", "20.281"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s275_mod.generate(df, tf)
    sig_b = s281_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 5 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(5).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(5).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
