# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.364",
    "name": "Stoch ADX Trend Sync",
    "concept": "หาจังหวะพักตัวสั้นๆในเทรนด์ที่มีพลังขับเคลื่อนสูง (ADX) โดยใช้ Stochastic",
    "logic": "ในขณะที่เทรนด์หลักแข็งแกร่งและมีแรงส่ง (ADX > 25 และเชิดหัวขึ้น) การที่ Stochastic ตัดกันขึ้นในโซนครึ่งล่าง (< 50) หมายถึงการจบการพักตัวและเตรียมพุ่งทะยานตามเทรนด์เดิม, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    k, d = ind.stoch(df, 14, 3, 3)
    pdi, ndi, adx = ind.dmi(df, 14)
    ema200 = ind.ema(df["close"], 200)
    
    adx_trend = (adx > 25.0) & (adx > adx.shift(1))
    
    buy_cond = ind.cross_up(k, d) & (k < 50.0) & adx_trend & (df["close"] > ema200)
    sell_cond = ind.cross_dn(k, d) & (k > 50.0) & adx_trend & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
