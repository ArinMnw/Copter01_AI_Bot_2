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
s210_mod = load_mod("s210", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.210", "strategy20_210.py"))

META = {
    "sid": "20.502",
    "name": "MACD Divergence Accelerator Confirm",
    "concept": "เทรด MACD Divergence (A) ที่ถูก Confirm ว่ามีความเร่งของ Momentum เปลี่ยนทิศสนับสนุน (B) ภายใน 5 แท่ง",
    "logic": "A (275) เข้าเทรดตาม MACD Divergence ส่วน B (210) คือ Accelerator Oscillator ที่แท่งฮิสโตแกรมเปลี่ยนสีเป็นทิศทางเดียวกับ Divergence ติดต่อกัน 2 แท่ง การผสมแบบ CONFIRM (5 แท่ง) จะทำให้เข้าเทรดเฉพาะจังหวะที่ Divergence ก่อตัวเสร็จและมีโมเมนตัมเร่งตัว (Acceleration) ตามมาจริงๆ",
    "parents": ["20.275", "20.210"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s275_mod.generate(df, tf)
    sig_b = s210_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 5 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(5).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(5).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
