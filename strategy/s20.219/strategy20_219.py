# -*- coding: utf-8 -*-
"""S20.219 — Chande Dynamic Momentum Index

แนวคิด: DMI แบบ Chande: ความยาว RSI ปรับตาม volatility (5–30 แท่ง ตามอัตราส่วน stdev5/avg stdev10) ตัดขึ้นจาก < 30 → BUY; ตัดลงจาก > 70 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.219', 'name': 'Chande Dynamic Momentum Index', 'concept': 'DMI แบบ Chande: ความยาว RSI ปรับตาม volatility (5–30 แท่ง ตามอัตราส่วน stdev5/avg stdev10) ตัดขึ้นจาก < 30 → BUY; ตัดลงจาก > 70 → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    c = df["close"]
    sd = c.rolling(5).std(); vi = sd / I.sma(sd, 10)
    td = (14 / vi).clip(5, 30).fillna(14).round().astype(int).to_numpy()
    d = c.diff().to_numpy()
    n = len(c); out = np.full(n, np.nan)
    for i in range(31, n):
        w = d[i - td[i] + 1:i + 1]
        up, dn = w[w > 0].sum(), -w[w < 0].sum()
        out[i] = 100 * up / (up + dn) if up + dn > 0 else 50
    dmi = pd.Series(out, index=df.index)
    return I.sig_from(I.cross_up(dmi, 30), I.cross_dn(dmi, 70))
