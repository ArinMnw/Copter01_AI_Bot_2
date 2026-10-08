# -*- coding: utf-8 -*-
"""S20.160 — Know Sure Thing (KST) Momentum Cross

แนวคิด: Pring KST: ผลรวมถ่วงน้ำหนัก ROC 10/15/20/30 ที่ smooth แล้ว ตัด signal SMA9 ขึ้นใต้ศูนย์ → BUY (momentum ฟื้นหลายรอบเวลา), ตัดลงเหนือศูนย์ → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.160', 'name': 'Know Sure Thing (KST) Momentum Cross', 'concept': 'Pring KST: ผลรวมถ่วงน้ำหนัก ROC 10/15/20/30 ที่ smooth แล้ว ตัด signal SMA9 ขึ้นใต้ศูนย์ → BUY (momentum ฟื้นหลายรอบเวลา), ตัดลงเหนือศูนย์ → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 40}


def generate(df, tf):
    c = df["close"]
    roc = lambda n: 100 * c.pct_change(n)
    kst = I.sma(roc(10), 10) + 2 * I.sma(roc(15), 10) + 3 * I.sma(roc(20), 10) + 4 * I.sma(roc(30), 15)
    sg = I.sma(kst, 9)
    return I.sig_from(I.cross_up(kst, sg) & (kst < 0), I.cross_dn(kst, sg) & (kst > 0))
