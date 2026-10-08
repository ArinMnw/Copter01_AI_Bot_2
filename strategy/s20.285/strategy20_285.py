# -*- coding: utf-8 -*-
"""S20.285 — McGinley Dynamic Cross

แนวคิด: McGinley Dynamic (14) — MA ที่ปรับความเร็วตามอัตราส่วน close/MD: ราคาปิดตัด MD ขึ้นและ MD ขึ้นเทียบ 3 แท่งก่อน → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.285', 'name': 'McGinley Dynamic Cross', 'concept': 'McGinley Dynamic (14) — MA ที่ปรับความเร็วตามอัตราส่วน close/MD: ราคาปิดตัด MD ขึ้นและ MD ขึ้นเทียบ 3 แท่งก่อน → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"].to_numpy(); n = len(c); N = 14
    md = np.full(n, np.nan); md[0] = c[0]
    for i in range(1, n):
        md[i] = md[i - 1] + (c[i] - md[i - 1]) / (N * (c[i] / md[i - 1]) ** 4)
    m = pd.Series(md, index=df.index); cs = df["close"]
    w = pd.Series(np.arange(n) > 50, index=df.index)
    return I.sig_from(I.cross_up(cs, m) & (m > m.shift(3)) & w, I.cross_dn(cs, m) & (m < m.shift(3)) & w)
