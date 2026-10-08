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

spec_b = importlib.util.spec_from_file_location("s20_184", "strategy/s20.184/strategy20_184.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.756",
    "name": "S20.339 x S20.184 (FILTER)",
    "concept": "เข้า Breakout แบบ Inside Bar (A) โดยมี Seasonality สถิติรายชั่วโมง (B) สนับสนุนทิศทาง",
    "logic": "A (339) ให้จุดเข้า Breakout ของการพักตัวแบบ Inside Bar ที่ยืนยันทิศทางด้วย MACD ส่วน B (184) คำนวณสถิติ Rolling Seasonality ว่าในชั่วโมงนี้มักจะไปทิศทางไหนอย่างมีนัยสำคัญ. จะเข้า Breakout ก็ต่อเมื่อทิศทางสอดคล้องกับสถิติผลตอบแทนเฉลี่ยของชั่วโมงนั้น เป็นการผสม Price Action กับเวลาของวัน",
    "parents": ["20.339", "20.184"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    if tf == "D1":
        return np.zeros(len(df), dtype=np.int8)

    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    
    buy_a = sig_a == 1
    sell_a = sig_a == -1
    
    buy_b = sig_b == 1
    sell_b = sig_b == -1
    
    # 184 generates signal at the bar BEFORE the slot starts. The slot holds for 1 hour (4h for H4).
    # Since we enter at open of i+1, sig_b at i means the slot applies to i+1 onwards.
    holds = {"M1": 60, "M5": 12, "M15": 4, "M30": 2, "H1": 1, "H4": 1}
    h = holds.get(tf, 1)
    
    buy_season = pd.Series(buy_b).rolling(h).max().fillna(0).astype(bool).values
    sell_season = pd.Series(sell_b).rolling(h).max().fillna(0).astype(bool).values
    
    final_buy = buy_a & buy_season
    final_sell = sell_a & sell_season
    
    return ind.sig_from(pd.Series(final_buy), pd.Series(final_sell))
