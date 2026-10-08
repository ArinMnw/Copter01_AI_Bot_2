# -*- coding: utf-8 -*-
"""S20.215 — Slow Stochastic OB/OS Cross with SMA100 Trend

แนวคิด: Slow Stochastic (14,3,3): %K ตัด %D ขึ้นในโซน < 20 ขณะ close > SMA100 → BUY; %K ตัดลงในโซน > 80 ขณะ close < SMA100 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.215', 'name': 'Slow Stochastic OB/OS Cross with SMA100 Trend', 'concept': 'Slow Stochastic (14,3,3): %K ตัด %D ขึ้นในโซน < 20 ขณะ close > SMA100 → BUY; %K ตัดลงในโซน > 80 ขณะ close < SMA100 → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    k, d = I.stoch(df, 14, 3, 3)
    s100 = I.sma(df["close"], 100)
    return I.sig_from(I.cross_up(k, d) & (d < 20) & (df["close"] > s100), I.cross_dn(k, d) & (d > 80) & (df["close"] < s100))
