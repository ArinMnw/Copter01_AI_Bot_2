# -*- coding: utf-8 -*-
"""S20.173 — Ease of Movement Zero-Line Cross

แนวคิด: Arms Ease of Movement (14, SMA) ตัดศูนย์ขึ้น = ราคาขยับขึ้นได้ง่ายด้วย volume น้อย + ราคาเหนือ SMA50 → BUY; ตัดลง + ใต้ SMA50 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.173', 'name': 'Ease of Movement Zero-Line Cross', 'concept': 'Arms Ease of Movement (14, SMA) ตัดศูนย์ขึ้น = ราคาขยับขึ้นได้ง่ายด้วย volume น้อย + ราคาเหนือ SMA50 → BUY; ตัดลง + ใต้ SMA50 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    h, l = df["high"], df["low"]
    mid = (h + l) / 2
    br = (df["volume"] / 1e4) / (h - l).replace(0, np.nan)
    emv = I.sma(mid.diff() / br, 14)
    s50 = I.sma(df["close"], 50)
    return I.sig_from(I.cross_up(emv, 0) & (df["close"] > s50), I.cross_dn(emv, 0) & (df["close"] < s50))
