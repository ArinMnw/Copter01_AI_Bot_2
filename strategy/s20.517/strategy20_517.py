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
s315_mod = load_mod("s315", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.315", "strategy20_315.py"))

META = {
    "sid": "20.517",
    "name": "MACD Divergence Saucer Confirm",
    "concept": "เทรด MACD Divergence (A) ที่ถูก Confirm ว่ามีรูปแบบ Awesome Oscillator Saucer (B) เกิดขึ้นภายใน 5 แท่ง",
    "logic": "A (275) จับการเกิด Divergence บน MACD ปกติ (EMA 12, 26) ส่วน B (315) จับรูปแบบ Saucer บน Awesome Oscillator (SMA 5, 34) การผสมแบบ CONFIRM (5 แท่ง) จะบังคับให้การกลับตัวต้องมีทั้งสัญญาณ Divergence ก่อนหน้า และตามมาด้วยโมเมนตัมแบบ Saucer ที่ชัดเจน เป็นการกรอง False Breakout ที่แข็งแกร่งมาก",
    "parents": ["20.275", "20.315"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s275_mod.generate(df, tf)
    sig_b = s315_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 5 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(5).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(5).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
