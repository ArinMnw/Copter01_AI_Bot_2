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

s339_mod = load_mod("s339", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.339", "strategy20_339.py"))
s316_mod = load_mod("s316", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.316", "strategy20_316.py"))

META = {
    "sid": "20.516",
    "name": "Supertrend Heikin-Ashi Confirm",
    "concept": "เทรด Supertrend (A) ที่ถูก Confirm ว่ามีสัญญาณจาก Heikin-Ashi DMI (B) ภายใน 5 แท่ง",
    "logic": "A (339) ให้สัญญาณ Supertrend พลิกฝั่ง บ่งบอกการเริ่มต้นเทรนด์ใหม่ ส่วน B (316) คือการใช้ Heikin-Ashi ลด noise แล้วเช็ค ADX ว่าเทรนด์แข็งแกร่งพอ การผสมแบบ CONFIRM จะกรอง Supertrend ที่เกิดจาก noise ออก และเข้าเฉพาะเทรนด์ที่มีพลังยืนยันจาก DMI บนราคาที่สมูทด้วย HA แล้ว",
    "parents": ["20.339", "20.316"],
    "mix": "CONFIRM",
    "sl_atr": 2.0,
    "rr": 2.0,
    "max_hold": 36,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s339_mod.generate(df, tf)
    sig_b = s316_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 5 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(5).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(5).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
