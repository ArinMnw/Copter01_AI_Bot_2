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
s169_mod = load_mod("s169", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.169", "strategy20_169.py"))

META = {
    "sid": "20.498",
    "name": "Inside Bar Breakout Woodie CCI Confirm",
    "concept": "เทรด Breakout จาก Inside Bar (A) ที่ถูก Confirm ว่ามี Woodie CCI Zero-Line Reject (B) เกิดขึ้นภายใน 5 แท่ง",
    "logic": "A (339) เข้าเทรด Breakout จากแท่ง Inside Bar ส่วน B (169) คือ Woodie CCI ที่ตีกลับจากเส้น 0 (Zero-Line Reject) ซึ่งเป็นสัญญาณ Continuation Pattern ชั้นยอด การผสมแบบ CONFIRM (5 แท่ง) จะกรองให้การเกิด Inside Bar Breakout เกิดขึ้นพร้อมๆ กับจังหวะพักตัวจบและเริ่มวิ่งต่อของ CCI พอดี",
    "parents": ["20.339", "20.169"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s339_mod.generate(df, tf)
    sig_b = s169_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 5 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(5).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(5).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
