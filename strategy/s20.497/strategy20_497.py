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
s160_mod = load_mod("s160", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.160", "strategy20_160.py"))

META = {
    "sid": "20.497",
    "name": "Inside Bar Breakout KST Confirm",
    "concept": "เทรด Breakout จาก Inside Bar (A) ที่ถูก Confirm ว่ามี KST Momentum Cross (B) เกิดขึ้นภายใน 5 แท่ง",
    "logic": "A (339) เข้าเทรด Breakout จากแท่ง Inside Bar เมื่อ MACD ยืนยัน ส่วน B (160) คือ KST Momentum Cross ซึ่งเป็นการกลับตัวของโมเมนตัมแบบหลายกรอบเวลา การผสมแบบ CONFIRM (5 แท่ง) หมายถึงเราจะเข้าเบรกเอาท์จาก Inside Bar เฉพาะในจังหวะที่โมเมนตัมภาพรวม (KST) เพิ่งจะฟื้นตัวตัดเส้น Signal สดๆ ร้อนๆ เท่านั้น",
    "parents": ["20.339", "20.160"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s339_mod.generate(df, tf)
    sig_b = s160_mod.generate(df, tf)
    
    # CONFIRM: B ต้องมีสัญญาณทิศเดียวกับ A ใน 5 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(5).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(5).max() == 1
    
    return ind.sig_from(pd.Series((sig_a == 1) & b_buy_recent), pd.Series((sig_a == -1) & b_sell_recent))
