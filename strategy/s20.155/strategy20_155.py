# -*- coding: utf-8 -*-
"""S20.155 — Vortex Indicator Cross

แนวคิด: Vortex (VI+ / VI−, 14): VI+ ตัดขึ้นเหนือ VI− โดยช่องห่าง > 0.05 (ยืนยันแรง) → BUY; VI− ตัดขึ้น → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.155', 'name': 'Vortex Indicator Cross', 'concept': 'Vortex (VI+ / VI−, 14): VI+ ตัดขึ้นเหนือ VI− โดยช่องห่าง > 0.05 (ยืนยันแรง) → BUY; VI− ตัดขึ้น → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    h, l, c = df["high"], df["low"], df["close"]
    vp = (h - l.shift(1)).abs().rolling(14).sum()
    vm = (l - h.shift(1)).abs().rolling(14).sum()
    tr = I.true_range(df).rolling(14).sum()
    vip, vim = vp / tr, vm / tr
    return I.sig_from(I.cross_up(vip, vim) & ((vip - vim) > 0.05), I.cross_up(vim, vip) & ((vim - vip) > 0.05))
