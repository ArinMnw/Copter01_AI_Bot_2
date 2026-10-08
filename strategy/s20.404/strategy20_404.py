# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.404",
    "name": "Keltner V-Shape Recovery",
    "concept": "เข้าเทรดรอบย่อตัวลึก (Deep Pullback) ที่ฟื้นตัวอย่างรวดเร็วเป็นรูปตัว V ในเทรนด์ขาขึ้น",
    "logic": "เมื่อราคาอยู่ในเทรนด์ขาขึ้นที่แข็งแกร่ง (EMA 20 > 50 > 200) แต่มีจังหวะเทขายอย่างหนักจนราคาทะลุขอบล่างของ Keltner Channel ลงไป (Low < KL) ภายใน 3 แท่งที่ผ่านมา หากราคาสามารถดีดกลับขึ้นมาปิดเหนือเส้นกึ่งกลาง (EMA 20) ได้ ถือเป็นการยืนยันรอบฟื้นตัว V-Shape ที่มีแรงซื้อหนาแน่นรออยู่ด้านล่าง, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    kl, km, ku = ind.keltner(df, n=20, k=1.5, atr_n=20)
    ema20 = ind.ema(df["close"], 20)
    ema50 = ind.ema(df["close"], 50)
    ema200 = ind.ema(df["close"], 200)
    
    bull_trend = (ema20 > ema50) & (ema50 > ema200)
    bear_trend = (ema20 < ema50) & (ema50 < ema200)
    
    # เคยทำ Low ต่ำกว่าขอบล่าง Keltner ภายใน 3 แท่งล่าสุด
    dip_below_kl = df["low"].rolling(3).min() < kl
    surge_above_ku = df["high"].rolling(3).max() > ku
    
    buy_cond = bull_trend & dip_below_kl.shift(1) & ind.cross_up(df["close"], ema20)
    sell_cond = bear_trend & surge_above_ku.shift(1) & ind.cross_dn(df["close"], ema20)
    
    return ind.sig_from(buy_cond, sell_cond)
