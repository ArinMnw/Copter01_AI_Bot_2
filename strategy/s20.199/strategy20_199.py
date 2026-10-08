# -*- coding: utf-8 -*-
"""S20.199 — Vertical Horizontal Filter Trend Onset

แนวคิด: VHF(28) = (HH−LL)/Σ|Δclose|: ตัดขึ้นเหนือ 0.40 จากต่ำกว่า 0.30 ใน 15 แท่งก่อน (congestion → trending) → เข้าตามทิศ close เทียบ SMA28
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.199', 'name': 'Vertical Horizontal Filter Trend Onset', 'concept': 'VHF(28) = (HH−LL)/Σ|Δclose|: ตัดขึ้นเหนือ 0.40 จากต่ำกว่า 0.30 ใน 15 แท่งก่อน (congestion → trending) → เข้าตามทิศ close เทียบ SMA28', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"]
    vhf = (I.highest(c, 28) - I.lowest(c, 28)) / c.diff().abs().rolling(28).sum().replace(0, np.nan)
    on = I.cross_up(vhf, 0.40) & (vhf.shift(1).rolling(15).min() < 0.30)
    s = I.sma(c, 28)
    return I.sig_from(on & (c > s), on & (c < s))
