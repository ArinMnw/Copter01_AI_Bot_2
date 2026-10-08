# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.391",
    "name": "HA Keltner 2SD Reversion",
    "concept": "เข้าเทรดเมื่อราคากระชากหลุดกรอบ Keltner Channel 2.0 SD แล้วมีแท่งเทียน Heikin-Ashi ชี้ว่ากลับตัวเข้าหาค่าเฉลี่ย",
    "logic": "Keltner ที่กว้างถึง 2.0 SD เป็นระดับที่ราคามักจะเกิด Mean Reversion การใช้ Heikin-Ashi เข้ามายืนยันจังหวะวกกลับเข้าในกรอบ จะช่วยให้การเทรดสวนการกระชากมีจุดเข้าที่สมูทและแม่นยำขึ้น โดยอิงเทรนด์หลักจาก EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ho, hh, hl, hc = ind.heikin_ashi(df)
    kl, km, ku = ind.keltner(df, n=20, k=2.0, atr_n=20)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(hc, kl) & (hc > ho) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(hc, ku) & (hc < ho) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
