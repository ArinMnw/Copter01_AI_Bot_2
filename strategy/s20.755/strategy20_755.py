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

spec_b = importlib.util.spec_from_file_location("s20_228", "strategy/s20.228/strategy20_228.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.755",
    "name": "S20.339 x S20.228 (CONFIRM w15)",
    "concept": "เข้า Breakout แบบ Inside Bar (A) โดยมีสัญญาณ Low-Volume Pullback (B) เกิดขึ้นในทิศเดียวกันภายใน 15 แท่ง",
    "logic": "A (339) ให้จุดเข้า Breakout ของการพักตัวแบบ Inside Bar ที่ยืนยันทิศทางด้วย MACD ส่วน B (228) เป็นสัญญาณการพักตัว Low-Volume สนับสนุนเทรนด์. หากทั้งคู่เกิดไล่เลี่ยกันในระยะ 15 แท่ง หมายความว่าตลาดมีการสะสมพลังแบบไร้แรงขายแล้วระเบิดไปในทิศทางเดียวกันอย่างแข็งแรง",
    "parents": ["20.339", "20.228"],
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
    
    # CONFIRM: A and B both signal within 15 bars
    buy_b_recent = pd.Series(buy_b).rolling(15).max().fillna(0).astype(bool).values
    sell_b_recent = pd.Series(sell_b).rolling(15).max().fillna(0).astype(bool).values
    
    buy = buy_a & buy_b_recent
    sell = sell_a & sell_b_recent
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
