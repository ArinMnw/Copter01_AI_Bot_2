# -*- coding: utf-8 -*-
"""S20.240 — Ehlers Cyber Cycle Trigger Cross

แนวคิด: Ehlers Cyber Cycle (alpha 0.07) ของราคาที่ smooth แล้ว: cycle ตัด trigger (cycle[1]) ขึ้นขณะอยู่ใต้ศูนย์ → BUY; ตัดลงเหนือศูนย์ → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.240', 'name': 'Ehlers Cyber Cycle Trigger Cross', 'concept': 'Ehlers Cyber Cycle (alpha 0.07) ของราคาที่ smooth แล้ว: cycle ตัด trigger (cycle[1]) ขึ้นขณะอยู่ใต้ศูนย์ → BUY; ตัดลงเหนือศูนย์ → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    p = ((df["high"] + df["low"]) / 2).to_numpy(); n = len(p); al = 0.07
    sm = np.copy(p); cy = np.zeros(n)
    for i in range(3, n):
        sm[i] = (p[i] + 2 * p[i - 1] + 2 * p[i - 2] + p[i - 3]) / 6
    for i in range(6, n):
        cy[i] = (1 - 0.5 * al) ** 2 * (sm[i] - 2 * sm[i - 1] + sm[i - 2]) + 2 * (1 - al) * cy[i - 1] - (1 - al) ** 2 * cy[i - 2]
    cs = pd.Series(cy, index=df.index); tg = cs.shift(1)
    w = pd.Series(np.arange(n) > 50, index=df.index)
    return I.sig_from((cs > tg) & (cs.shift(1) <= tg.shift(1)) & (cs < 0) & w, (cs < tg) & (cs.shift(1) >= tg.shift(1)) & (cs > 0) & w)
