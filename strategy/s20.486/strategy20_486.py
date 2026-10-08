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
s158_mod = load_mod("s158", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.158", "strategy20_158.py"))

META = {
    "sid": "20.486",
    "name": "Inside Breakout Hull Confirmation",
    "concept": "เทรด Breakout จากแท่ง Inside Bar (A) โดยรอให้ HMA สั้นกลับมาทิศเดียวกับ HMA ยาว (B) เพื่อยืนยันโมเมนตัม",
    "logic": "A (339) จับจุดระเบิดจาก Inside Bar ส่วน B (158) จับจุดหมุนของ Hull MA ที่ตามทิศใหญ่ ใช้ CONFIRM ให้ HMA เพิ่งเปลี่ยนทิศใน 3 แท่งที่ผ่านมาพร้อมการระเบิด",
    "parents": ["20.339", "20.158"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s339_mod.generate(df, tf)
    sig_b = s158_mod.generate(df, tf)
    
    # CONFIRM: A มีสัญญาณ และ B มีสัญญาณทิศเดียวกันภายใน 3 แท่งที่ผ่านมา
    b_buy_recent = pd.Series(sig_b == 1).rolling(3).max() == 1
    b_sell_recent = pd.Series(sig_b == -1).rolling(3).max() == 1
    
    return ind.sig_from((sig_a == 1) & b_buy_recent, (sig_a == -1) & b_sell_recent)
