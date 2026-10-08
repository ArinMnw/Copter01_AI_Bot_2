# -*- coding: utf-8 -*-
"""S20.239 — Ehlers Decycler Oscillator Zero Cross

แนวคิด: Ehlers Decycler Oscillator: high-pass (cut-off 100) ลบด้วย high-pass (cut-off 125) ของราคา ตัดศูนย์ขึ้น → BUY; ตัดลง → SELL (trend ที่ตัด cycle สั้นออก)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.239', 'name': 'Ehlers Decycler Oscillator Zero Cross', 'concept': 'Ehlers Decycler Oscillator: high-pass (cut-off 100) ลบด้วย high-pass (cut-off 125) ของราคา ตัดศูนย์ขึ้น → BUY; ตัดลง → SELL (trend ที่ตัด cycle สั้นออก)', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 40}


def generate(df, tf):
    c = df["close"].to_numpy(); n = len(c)
    def hp(x, per):
        a1 = (np.cos(0.707 * 2 * np.pi / per) + np.sin(0.707 * 2 * np.pi / per) - 1) / np.cos(0.707 * 2 * np.pi / per)
        y = np.zeros(n)
        for i in range(2, n):
            y[i] = (1 - a1 / 2) ** 2 * (x[i] - 2 * x[i - 1] + x[i - 2]) + 2 * (1 - a1) * y[i - 1] - (1 - a1) ** 2 * y[i - 2]
        return y
    osc = pd.Series(hp(c, 125) - hp(c, 100), index=df.index)
    w = pd.Series(np.arange(n) > 250, index=df.index)
    return I.sig_from(I.cross_up(osc, 0) & w, I.cross_dn(osc, 0) & w)
