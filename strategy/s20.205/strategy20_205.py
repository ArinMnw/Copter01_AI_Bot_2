# -*- coding: utf-8 -*-
"""S20.205 — DiNapoli Single Penetration of DMA 3x3

แนวคิด: Joe DiNapoli: thrust = ปิดเหนือ Displaced MA 3x3 (SMA3 เลื่อน 3 แท่ง) ≥ 8 แท่งติด แล้วแท่งแรกที่ปิดใต้ DMA → BUY (pullback แรกใน thrust); กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.205', 'name': 'DiNapoli Single Penetration of DMA 3x3', 'concept': 'Joe DiNapoli: thrust = ปิดเหนือ Displaced MA 3x3 (SMA3 เลื่อน 3 แท่ง) ≥ 8 แท่งติด แล้วแท่งแรกที่ปิดใต้ DMA → BUY (pullback แรกใน thrust); กลับด้าน → SELL', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    c = df["close"]
    dma = I.sma(c, 3).shift(3)
    above = (c > dma).astype(int); below = (c < dma).astype(int)
    ra = above.groupby((above == 0).cumsum()).cumsum(); rb = below.groupby((below == 0).cumsum()).cumsum()
    return I.sig_from((ra.shift(1) >= 8) & (c < dma), (rb.shift(1) >= 8) & (c > dma))
