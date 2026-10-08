# -*- coding: utf-8 -*-
"""S20.277 — Quadratic-Regression Curvature Turn

แนวคิด: ฟิต quadratic กับ close 30 แท่ง: ความโค้ง (2a) เปลี่ยนจากลบเป็นบวก (ราคาเริ่มเร่งขึ้น) และ slope ปลายเส้นเป็นบวก → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.277', 'name': 'Quadratic-Regression Curvature Turn', 'concept': 'ฟิต quadratic กับ close 30 แท่ง: ความโค้ง (2a) เปลี่ยนจากลบเป็นบวก (ราคาเริ่มเร่งขึ้น) และ slope ปลายเส้นเป็นบวก → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    c = df["close"].to_numpy(); n = 30; m = len(c)
    x = np.arange(n, dtype=float)
    A = np.vstack([x ** 2, x, np.ones(n)]).T
    P = np.linalg.pinv(A)
    cur = np.full(m, np.nan); slp = np.full(m, np.nan)
    for i in range(n - 1, m):
        a2, b1, _ = P @ c[i - n + 1:i + 1]
        cur[i] = a2; slp[i] = 2 * a2 * (n - 1) + b1
    cs, ss = pd.Series(cur, index=df.index), pd.Series(slp, index=df.index)
    return I.sig_from((cs > 0) & (cs.shift(1) <= 0) & (ss > 0), (cs < 0) & (cs.shift(1) >= 0) & (ss < 0))
