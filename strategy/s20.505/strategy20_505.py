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
s250_mod = load_mod("s250", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.250", "strategy20_250.py"))

META = {
    "sid": "20.505",
    "name": "MACD Divergence Anti Hook Confirm",
    "concept": "เทรด MACD Divergence (A) ที่ถูก Confirm ว่ามีสัญญาณ Stochastic Hook (B) เกิดขึ้นภายใน 5 แท่ง",
    "logic": "A (275) ให้สัญญาณ MACD Divergence เพื่อหาจุดอ่อนแรงของเทรนด์เดิม ส่วน B (250) คือ Stochastic Hook (Raschke Anti) ที่ช่วยยืนยันว่าการอ่อนแรงนั้นส่งผลให้เกิดการม้วนตัวกลับของรอบ Stochastic เรียบร้อยแล้ว การผสมแบบ CONFIRM (5 แท่ง) จะทำให้เข้าเทรดก็ต่อเมื่อการกลับตัวมีทั้งแรงหนุนระดับกลาง (MACD) และระดับสั้น (Stoch)",
    "parents": ["20.275", "20.250"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s275_mod.generate(df, tf)
    sig_b = s250_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 5 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(5).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(5).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
