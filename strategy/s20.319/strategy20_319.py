# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.319",
    "name": "Keltner Squeeze MACD Breakout",
    "concept": "เข้าเทรดเมื่อความกว้างของ Keltner Channel หดตัวกว่าปกติ (Squeeze) แล้วเกิดการทะลุขอบพร้อม MACD ยืนยัน",
    "logic": "Squeeze แสดงถึงการสะสมพลังงาน การทะลุพร้อมโมเมนตัม MACD ชี้ว่าจะเป็นเทรนด์ยาว, SL 2.0 ATR ให้เผื่อ Volatility ตอนระเบิด, RR 2.0 หวังผลจากการเปลี่ยน Regime, ถือ 48 แท่ง",
    "sl_atr": 2.0,
    "rr": 2.0,
    "max_hold": 48,
    "be_r": 1.0
}

def generate(df, tf):
    kl, km, ku = ind.keltner(df, n=20, k=1.5, atr_n=14)
    width = ku - kl
    width_sma = ind.sma(width, 20)
    
    squeeze = width < width_sma
    # We want squeeze in recent past (e.g. 5 bars) and now breaking out
    squeeze_recently = squeeze.rolling(5).max() > 0
    
    macd, macd_sig, macd_hist = ind.macd(df["close"])
    
    buy_cond = squeeze_recently & (df["close"] > ku) & (macd > macd_sig) & (macd_hist > 0)
    sell_cond = squeeze_recently & (df["close"] < kl) & (macd < macd_sig) & (macd_hist < 0)
    
    # Just to ensure it's a new breakout, we can cross
    buy_sig = ind.cross_up(df["close"], ku) & buy_cond
    sell_sig = ind.cross_dn(df["close"], kl) & sell_cond
    
    return ind.sig_from(buy_sig, sell_sig)
