# -*- coding: utf-8 -*-
"""S20.202 — R-Breaker Intraday Reversal

แนวคิด: R-Breaker (CTA จีน): จาก HLC งวดก่อนคำนวณ observation/reversal levels; ถ้างวดนี้ high เคยเกิน Observation-Sell (H+0.35·(C−L)) แล้วราคาปิดหลุด Reversal-Sell (1.07/2·(H+C)−0.07·L) → SELL; กลับด้านสำหรับ BUY
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.202', 'name': 'R-Breaker Intraday Reversal', 'concept': 'R-Breaker (CTA จีน): จาก HLC งวดก่อนคำนวณ observation/reversal levels; ถ้างวดนี้ high เคยเกิน Observation-Sell (H+0.35·(C−L)) แล้วราคาปิดหลุด Reversal-Sell (1.07/2·(H+C)−0.07·L) → SELL; กลับด้านสำหรับ BUY', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    key = I.period_key(df, tf)
    ph, pl, pc, _ = I.prev_period_hl(df, key)
    s_setup = ph + 0.35 * (pc - pl)
    b_setup = pl - 0.35 * (ph - pc)
    s_enter = 1.07 / 2 * (ph + pl) - 0.07 * pl
    b_enter = 1.07 / 2 * (ph + pl) - 0.07 * ph
    rh, rl, _ = I.period_running(df, key)
    c = df["close"]
    sell = (rh.shift(1) > s_setup) & (c < s_enter) & (c.shift(1) >= s_enter)
    buy = (rl.shift(1) < b_setup) & (c > b_enter) & (c.shift(1) <= b_enter)
    same = key == key.shift(1)
    return I.sig_from(buy & same, sell & same)
