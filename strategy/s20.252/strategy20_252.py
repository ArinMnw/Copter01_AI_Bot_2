# -*- coding: utf-8 -*-
"""S20.252 — Crabel Stretch Breakout

แนวคิด: Toby Crabel Stretch: stretch = ค่าเฉลี่ย 10 งวดของ min(|open−high|, |open−low|) ของงวด; ราคาปิดเกิน open งวด + stretch → BUY, ต่ำกว่า open − stretch → SELL (ครั้งแรกของงวด)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.252', 'name': 'Crabel Stretch Breakout', 'concept': 'Toby Crabel Stretch: stretch = ค่าเฉลี่ย 10 งวดของ min(|open−high|, |open−low|) ของงวด; ราคาปิดเกิน open งวด + stretch → BUY, ต่ำกว่า open − stretch → SELL (ครั้งแรกของงวด)', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 24}


def generate(df, tf):
    key = I.period_key(df, tf)
    g = df.groupby(key)
    agg = pd.DataFrame({"o": g["open"].first(), "h": g["high"].max(), "l": g["low"].min()})
    st = pd.concat([(agg["o"] - agg["h"]).abs(), (agg["o"] - agg["l"]).abs()], axis=1).min(axis=1).rolling(10).mean().shift(1)
    s = key.map(st)
    _, _, po = I.period_running(df, key)
    c = df["close"]
    up = c > po + s; dn = c < po - s
    return I.sig_from(up & (up.astype(int).groupby(key).cumsum() == 1), dn & (dn.astype(int).groupby(key).cumsum() == 1))
