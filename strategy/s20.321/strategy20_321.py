# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.321",
    "name": "Heikin-Ashi Keltner Exhaustion",
    "concept": "เข้าเทรดสวนเมื่อ Heikin-Ashi วิ่งออกนอก Keltner Channel จนหมดแรง (แท่งเทียนเปลี่ยนสี) ในสภาวะ Volatility สูง",
    "logic": "HA ที่เปลี่ยนสีนอกขอบ Keltner บ่งบอกถึงการหมดรอบของเทรนด์ย่อย (Exhaustion), ATR Z-Score > 1.0 ช่วยกรองช่วงที่ตลาดยังมีแรงผลักดัน, SL 1.5 ATR ปกป้อง, RR 1.5 หวัง Mean Reversion, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ho, hh, hl, hc = ind.heikin_ashi(df)
    kl, km, ku = ind.keltner(df, n=20, k=2.0, atr_n=14)
    
    atr_val = ind.atr(df, 14)
    atr_z = ind.zscore(atr_val, 50)
    
    high_vol = atr_z > 1.0
    
    # HA closed outside Keltner in the previous bar
    was_above = hc.shift(1) > ku.shift(1)
    was_below = hc.shift(1) < kl.shift(1)
    
    # HA color changes
    bearish_ha = hc < ho
    bullish_ha = hc > ho
    
    buy_cond = high_vol & was_below & bullish_ha
    sell_cond = high_vol & was_above & bearish_ha
    
    return ind.sig_from(buy_cond, sell_cond)
