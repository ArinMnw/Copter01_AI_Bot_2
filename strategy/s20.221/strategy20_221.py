# -*- coding: utf-8 -*-
"""S20.221 — Balance of Power Smoothed Zero Cross

แนวคิด: Igor Livshin Balance of Power = (close−open)/(high−low) เฉลี่ย SMA14: ตัดขึ้นเหนือ +0.1 จากใต้ศูนย์ภายใน 5 แท่ง → BUY (ผู้ซื้อยึดแท่ง); ตัดลงใต้ −0.1 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.221', 'name': 'Balance of Power Smoothed Zero Cross', 'concept': 'Igor Livshin Balance of Power = (close−open)/(high−low) เฉลี่ย SMA14: ตัดขึ้นเหนือ +0.1 จากใต้ศูนย์ภายใน 5 แท่ง → BUY (ผู้ซื้อยึดแท่ง); ตัดลงใต้ −0.1 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    bop = I.sma((df["close"] - df["open"]) / (df["high"] - df["low"]).replace(0, np.nan), 14)
    return I.sig_from(I.cross_up(bop, 0.1) & (bop.rolling(5).min() < 0), I.cross_dn(bop, -0.1) & (bop.rolling(5).max() > 0))
