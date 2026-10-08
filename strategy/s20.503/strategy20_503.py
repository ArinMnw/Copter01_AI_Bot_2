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
s184_mod = load_mod("s184", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20.184", "strategy20_184.py"))

META = {
    "sid": "20.503",
    "name": "MACD Divergence Seasonality Filter",
    "concept": "เทรด MACD Divergence (A) แต่ต้องมี Seasonality (B) สนับสนุนทิศทางในช่วงเวลานั้น",
    "logic": "A (275) ให้สัญญาณ MACD Divergence เพื่อดักการกลับตัว ส่วน B (184) คือ Seasonality รายชั่วโมงที่วิเคราะห์จาก 60 วันที่ผ่านมา การนำ B มาเป็น FILTER จะช่วยกรองให้เราสวนเทรนด์ในลักษณะ Divergence เฉพาะในช่วงเวลาของวันที่มีสถิติหนุนว่าราคามักจะวิ่งไปในทิศทางนั้น",
    "parents": ["20.275", "20.184"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = s275_mod.generate(df, tf)
    sig_b = s184_mod.generate(df, tf)
    
    # FILTER: แปลง sig_b (ที่เป็นพัลส์) ให้เป็นสถานะ (State) ต่อเนื่อง (แต่ seasonality จะรีเซ็ตเมื่อหมดชั่วโมง จริงๆ แล้วมันจะออก signal ต่อเนื่องตราบที่ยังอยู่ใน block)
    b_state = pd.Series(sig_b).replace(0, np.nan).ffill().fillna(0)
    
    return ind.sig_from(pd.Series((sig_a == 1) & (b_state == 1)), pd.Series((sig_a == -1) & (b_state == -1)))
