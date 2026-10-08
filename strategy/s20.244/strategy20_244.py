# -*- coding: utf-8 -*-
"""S20.244 — Ulcer Index Calm-Regime Trend Entry

แนวคิด: Peter Martin Ulcer Index(14) ต่ำกว่าเปอร์เซ็นไทล์ 20 ของ 200 แท่ง (drawdown ต่ำ = ตลาดสงบ) + ราคาปิดทำ high ใหม่ 20 แท่ง → BUY; ในทางกลับกันใช้ 'ulcer ของขาขึ้น' ต่ำ + low ใหม่ → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.244', 'name': 'Ulcer Index Calm-Regime Trend Entry', 'concept': "Peter Martin Ulcer Index(14) ต่ำกว่าเปอร์เซ็นไทล์ 20 ของ 200 แท่ง (drawdown ต่ำ = ตลาดสงบ) + ราคาปิดทำ high ใหม่ 20 แท่ง → BUY; ในทางกลับกันใช้ 'ulcer ของขาขึ้น' ต่ำ + low ใหม่ → SELL", 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"]
    dd = 100 * (c - I.highest(c, 14)) / I.highest(c, 14)
    ui = np.sqrt((dd ** 2).rolling(14).mean())
    du = 100 * (c - I.lowest(c, 14)) / I.lowest(c, 14)
    ui_s = np.sqrt((du ** 2).rolling(14).mean())
    calm_b = ui < ui.rolling(200).quantile(0.2); calm_s = ui_s < ui_s.rolling(200).quantile(0.2)
    nh = c > I.highest(c, 20).shift(1); nl = c < I.lowest(c, 20).shift(1)
    return I.sig_from(calm_b & nh, calm_s & nl)
