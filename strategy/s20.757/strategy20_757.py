# -*- coding: utf-8 -*-
import sys, os
import importlib.util
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

spec_a = importlib.util.spec_from_file_location("s20_339", "strategy/s20.339/strategy20_339.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_183", "strategy/s20.183/strategy20_183.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.757",
    "name": "S20.339 x S20.183 (CONFIRM w15)",
    "concept": "เทรด Breakout (A) ที่เพิ่งได้รับการยืนยันการเด้งจากฐาน Weekly Open (B)",
    "logic": "A (339) ให้จุดเข้า Breakout ของการพักตัวแบบ Inside Bar ที่ยืนยันทิศทางด้วย MACD ส่วน B (183) ให้สัญญาณการเด้งกลับจากฐาน Weekly Open (Bias สัปดาห์). การใช้ B เป็นตัว CONFIRM ในระยะ 15 แท่งจะช่วยกรองให้เทรดเฉพาะรอบ Breakout ที่เพิ่งได้รับแรงส่งจากการทดสอบฐานสำคัญของสัปดาห์มาแล้วเท่านั้น ทำให้การระเบิดมีโอกาสไปต่อสูง",
    "parents": ["20.339", "20.183"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    
    buy_a = sig_a == 1
    sell_a = sig_a == -1
    
    buy_b = sig_b == 1
    sell_b = sig_b == -1
    
    # CONFIRM w15: B fired within last 15 bars
    buy_b_recent = pd.Series(buy_b).rolling(15).max().fillna(0).astype(bool).values
    sell_b_recent = pd.Series(sell_b).rolling(15).max().fillna(0).astype(bool).values
    
    final_buy = buy_a & buy_b_recent
    final_sell = sell_a & sell_b_recent
    
    return ind.sig_from(pd.Series(final_buy), pd.Series(final_sell))
