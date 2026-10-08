# -*- coding: utf-8 -*-
"""S20.201 — Dual Thrust Range Breakout (CTA)

แนวคิด: Dual Thrust (Michael Chalek): Range = max(HH−LC, HC−LL) ของ 4 งวดก่อน; ปิดเหนือ open งวด + 0.5·Range → BUY, ใต้ open − 0.5·Range → SELL (ครั้งแรกของงวด)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.201', 'name': 'Dual Thrust Range Breakout (CTA)', 'concept': 'Dual Thrust (Michael Chalek): Range = max(HH−LC, HC−LL) ของ 4 งวดก่อน; ปิดเหนือ open งวด + 0.5·Range → BUY, ใต้ open − 0.5·Range → SELL (ครั้งแรกของงวด)', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 24}


def generate(df, tf):
    key = I.period_key(df, tf)
    g = df.groupby(key)
    agg = pd.DataFrame({"h": g["high"].max(), "l": g["low"].min(), "c": g["close"].last()})
    hh = agg["h"].rolling(4).max().shift(1); ll = agg["l"].rolling(4).min().shift(1)
    hc = agg["c"].rolling(4).max().shift(1); lc = agg["c"].rolling(4).min().shift(1)
    rg = key.map(np.maximum(hh - lc, hc - ll))
    _, _, po = I.period_running(df, key)
    c = df["close"]
    up = c > po + 0.5 * rg; dn = c < po - 0.5 * rg
    return I.sig_from(up & (up.astype(int).groupby(key).cumsum() == 1), dn & (dn.astype(int).groupby(key).cumsum() == 1))
