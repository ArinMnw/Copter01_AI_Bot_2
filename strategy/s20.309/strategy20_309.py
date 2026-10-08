# -*- coding: utf-8 -*-
"""S20.309 — Stochastic Pop Momentum Breakout

แนวคิด: Jake Bernstein's Stochastic Pop
เข้าซื้อ (Pop) เมื่อ Stochastic %K ตัดทะลุ 80 ขึ้นไป (ไม่ใช่ Oversold แต่แปลว่ามี Momentum ขาขึ้นรุนแรงมาก)
และขายเมื่อตัดทะลุ 20 ลงมา โดยกรองด้วย ADX > 25 เพื่อยืนยันว่ามีเทรนด์
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.309',
    'name': 'Stochastic Pop Momentum Breakout',
    'concept': 'Stochastic %K ตัด 80 ขึ้น (BUY) หรือ 20 ลง (SELL) โดยมี ADX > 25 ยืนยันความแรงของเทรนด์ (เทรดสวนแนวคิด Overbought/Oversold ทั่วไป)',
    'logic': 'Momentum Breakout แบบรุนแรง ใช้ SL กว้างปานกลาง (2.0) RR 1.5 และรอบทำกำไรสั้นๆ 16 แท่ง',
    'sl_atr': 2.0,
    'rr': 1.5,
    'max_hold': 16,
    'be_r': 1.0
}

def generate(df, tf):
    k, d = I.stoch(df, 14, 3, 3)
    _, _, adx = I.dmi(df, 14)
    
    buy = I.cross_up(k, 80) & (adx > 25)
    sell = I.cross_dn(k, 20) & (adx > 25)
    
    return I.sig_from(buy, sell)
