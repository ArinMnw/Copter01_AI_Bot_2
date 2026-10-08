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
s350_mod = load_mod("s350", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.350", "strategy20_350.py"))

META = {
    "sid": "20.496",
    "name": "Volatility Breakout PSAR ADX Confirm",
    "concept": "เทรด Breakout (A) ที่ถูก Confirm ว่ามี PSAR Flip พร้อม ADX เร่งตัว (B) เกิดขึ้นภายใน 4 แท่ง",
    "logic": "A (422) เข้าเมื่อเกิด Volatility Breakout ส่วน B (350) คือจุดที่ PSAR พลิกกลับหน้าเล่นพร้อมกับ ADX เร่งตัว การ Confirm ใน 4 แท่งช่วยคัดเฉพาะ Breakout ที่มีจุดเริ่มต้นการเปลี่ยนเทรนด์ (PSAR Flip) แบบมีแรงขับเคลื่อนจริงหนุนหลัง",
    "parents": ["20.422", "20.350"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s422_mod.generate(df, tf)
    sig_b = s350_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 4 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(4).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(4).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
