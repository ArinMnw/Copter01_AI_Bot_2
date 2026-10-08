# -*- coding: utf-8 -*-
"""S20.149 — Larry Williams Volatility Breakout (Open + k·Range)

แนวคิด: Larry Williams: ราคาปิดทะลุ open ของงวด + 0.6×range ของงวดก่อน → BUY (ลบ = SELL) งวด=วันสำหรับ TF≤H1 / สัปดาห์ H4 / 4 สัปดาห์ D1; เข้าครั้งแรกของงวดเท่านั้น
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.149', 'name': 'Larry Williams Volatility Breakout (Open + k·Range)', 'concept': 'Larry Williams: ราคาปิดทะลุ open ของงวด + 0.6×range ของงวดก่อน → BUY (ลบ = SELL) งวด=วันสำหรับ TF≤H1 / สัปดาห์ H4 / 4 สัปดาห์ D1; เข้าครั้งแรกของงวดเท่านั้น', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 24}


def generate(df, tf):
    key = I.period_key(df, tf)
    ph, pl, _, _ = I.prev_period_hl(df, key)
    _, _, po = I.period_running(df, key)
    k = 0.6 * (ph - pl)
    up = df["close"] > po + k
    dn = df["close"] < po - k
    fu = up & (up.astype(int).groupby(key).cumsum() == 1)
    fd = dn & (dn.astype(int).groupby(key).cumsum() == 1)
    return I.sig_from(fu, fd)
