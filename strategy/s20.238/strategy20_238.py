# -*- coding: utf-8 -*-
"""S20.238 — Ehlers Instantaneous Trendline Trigger

แนวคิด: Ehlers Instantaneous Trendline (alpha 0.07) กับ trigger = 2·IT − IT[2]: trigger ตัด IT ขึ้น → BUY; ตัดลง → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.238', 'name': 'Ehlers Instantaneous Trendline Trigger', 'concept': 'Ehlers Instantaneous Trendline (alpha 0.07) กับ trigger = 2·IT − IT[2]: trigger ตัด IT ขึ้น → BUY; ตัดลง → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    p = ((df["high"] + df["low"]) / 2).to_numpy(); n = len(p); al = 0.07
    it = np.copy(p)
    for i in range(2, n):
        if i < 7:
            it[i] = (p[i] + 2 * p[i - 1] + p[i - 2]) / 4
        else:
            it[i] = ((al - al * al / 4) * p[i] + 0.5 * al * al * p[i - 1] - (al - 0.75 * al * al) * p[i - 2]
                     + 2 * (1 - al) * it[i - 1] - (1 - al) ** 2 * it[i - 2])
    its = pd.Series(it, index=df.index)
    trig = 2 * its - its.shift(2)
    w = pd.Series(np.arange(n) > 50, index=df.index)
    return I.sig_from(I.cross_up(trig, its) & w, I.cross_dn(trig, its) & w)
