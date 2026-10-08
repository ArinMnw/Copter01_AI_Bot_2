# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.341",
    "name": "HA Keltner Breakout Trend",
    "concept": "เทรด Breakout กรอบ Keltner Channel โดยใช้แท่งเทียน Heikin-Ashi ยืนยันความแข็งแกร่งของโมเมนตัม",
    "logic": "การทะลุ Keltner Channel หมายถึงการระเบิดของราคา การใช้แท่ง Heikin-Ashi (hc > ho) ช่วยกรองสัญญาณหลอกที่เกิดจาก Noise, กรองเทรนด์ด้วย EMA200 และความแข็งแกร่งด้วย ADX, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ho, hh, hl, hc = ind.heikin_ashi(df)
    kl, km, ku = ind.keltner(df, n=20, k=1.5, atr_n=14)
    ema200 = ind.ema(df["close"], 200)
    pdi, ndi, adx = ind.dmi(df, 14)
    
    ha_bull = hc > ho
    ha_bear = hc < ho
    
    trend_strong = adx > 20
    
    buy_cond = ind.cross_up(df["close"], ku) & ha_bull & (df["close"] > ema200) & trend_strong
    sell_cond = ind.cross_dn(df["close"], kl) & ha_bear & (df["close"] < ema200) & trend_strong
    
    return ind.sig_from(buy_cond, sell_cond)
