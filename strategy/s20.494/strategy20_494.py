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

s422_mod = load_mod("s422", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.422", "strategy20_422.py"))
s353_mod = load_mod("s353", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.353", "strategy20_353.py"))

META = {
    "sid": "20.494",
    "name": "Volatility Breakout Stoch MACD Sync",
    "concept": "เทรด Breakout (A) ที่ถูก Confirm ว่ามี Stochastic MACD Continuation (B) เกิดขึ้นภายใน 5 แท่ง",
    "logic": "A (422) เข้าเมื่อเกิด Volatility Breakout ส่วน B (353) คือจังหวะที่ Stochastic ตัดกลับไปในทิศเดียวกับ MACD Trend การ Confirm ภายใน 5 แท่ง ช่วยคัดให้เราเข้า Breakout เฉพาะตอนที่เกิดจังหวะ Continuation ที่มีแรงหนุนเชิงเทรนด์หลักชัดเจนเท่านั้น",
    "parents": ["20.422", "20.353"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s422_mod.generate(df, tf)
    sig_b = s353_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 5 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(5).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(5).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
