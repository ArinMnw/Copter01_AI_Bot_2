# -*- coding: utf-8 -*-
"""S20.196 — Chande Momentum Oscillator ±50 Reversal

แนวคิด: Chande Momentum Oscillator(14): ต่ำกว่า −50 แล้วตัดกลับขึ้นเหนือ −50 → BUY; สูงกว่า +50 แล้วตัดลงใต้ +50 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.196', 'name': 'Chande Momentum Oscillator ±50 Reversal', 'concept': 'Chande Momentum Oscillator(14): ต่ำกว่า −50 แล้วตัดกลับขึ้นเหนือ −50 → BUY; สูงกว่า +50 แล้วตัดลงใต้ +50 → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    d = df["close"].diff()
    su = d.clip(lower=0).rolling(14).sum(); sd = (-d).clip(lower=0).rolling(14).sum()
    cmo = 100 * (su - sd) / (su + sd).replace(0, np.nan)
    return I.sig_from(I.cross_up(cmo, -50), I.cross_dn(cmo, 50))
