# -*- coding: utf-8 -*-
"""S20.151 — Williams Alligator Awakening

แนวคิด: Bill Williams Alligator (SMMA13/8/5 เลื่อนไปข้างหน้าแบบ causal = ใช้ค่าเก่า 8/5/3 แท่ง) เส้นพันกัน (sleeping) ≥10 แท่งแล้วแยกตัวเรียง Lips>Teeth>Jaw พร้อมราคาปิดเหนือ Lips → BUY (กลับด้าน SELL)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.151', 'name': 'Williams Alligator Awakening', 'concept': 'Bill Williams Alligator (SMMA13/8/5 เลื่อนไปข้างหน้าแบบ causal = ใช้ค่าเก่า 8/5/3 แท่ง) เส้นพันกัน (sleeping) ≥10 แท่งแล้วแยกตัวเรียง Lips>Teeth>Jaw พร้อมราคาปิดเหนือ Lips → BUY (กลับด้าน SELL)', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 40}


def generate(df, tf):
    med = (df["high"] + df["low"]) / 2
    jaw = I.rma(med, 13).shift(8); teeth = I.rma(med, 8).shift(5); lips = I.rma(med, 5).shift(3)
    a = I.atr(df, 14)
    spread = (pd.concat([jaw, teeth, lips], axis=1).max(axis=1) - pd.concat([jaw, teeth, lips], axis=1).min(axis=1))
    sleep = spread < 0.3 * a
    slept = sleep.shift(1).rolling(10).sum() >= 8
    bull = (lips > teeth) & (teeth > jaw) & (df["close"] > lips) & ~sleep
    bear = (lips < teeth) & (teeth < jaw) & (df["close"] < lips) & ~sleep
    return I.sig_from(bull & slept, bear & slept)
