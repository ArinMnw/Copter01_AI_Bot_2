# -*- coding: utf-8 -*-
"""S20.183 — Weekly-Open Bias Retest

แนวคิด: ราคาอยู่เหนือ open ของสัปดาห์ (Monday open) มากกว่า 1 ATR แล้วย่อกลับมาแตะ week-open และปิดเหนือ → BUY (bias สัปดาห์ยังอยู่); กลับด้าน → SELL (D1 ใช้ open ของเดือนแทน)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.183', 'name': 'Weekly-Open Bias Retest', 'concept': 'ราคาอยู่เหนือ open ของสัปดาห์ (Monday open) มากกว่า 1 ATR แล้วย่อกลับมาแตะ week-open และปิดเหนือ → BUY (bias สัปดาห์ยังอยู่); กลับด้าน → SELL (D1 ใช้ open ของเดือนแทน)', 'sl_atr': 1.0, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    key = I.week_key(df) if tf != "D1" else (I.week_key(df) // 4).astype(np.int64)
    rh, rl, wo = I.period_running(df, key)
    a = I.atr(df, 14)
    c, l, h = df["close"], df["low"], df["high"]
    was_above = (rh.shift(1) - wo) > a
    was_below = (wo - rl.shift(1)) > a
    same = key == key.shift(1)
    buy = same & was_above & (l <= wo) & (c > wo) & (c.shift(1) > wo)
    sell = same & was_below & (h >= wo) & (c < wo) & (c.shift(1) < wo)
    return I.sig_from(buy, sell)
