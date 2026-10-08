# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.372",
    "name": "Keltner Midline Stoch Rejection",
    "concept": "เข้าเทรดเมื่อราคาย่อตัวแตะเส้นกลาง Keltner แล้วเกิดการปฏิเสธราคา (Rejection) พร้อมสัญญาณยืนยันจาก Stochastic",
    "logic": "เส้นกลาง Keltner (EMA 20) ทำหน้าที่เป็นแนวรับในเทรนด์ขาขึ้น หากราคาทะลุลงไปแล้วดึงกลับมาปิดเหนือเส้นได้ และ Stochastic เพิ่งตัดขึ้นในโซนล่าง (<50) แปลว่าแรงขายหมดแล้วและพร้อมวิ่งตามเทรนด์เดิม, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    kl, km, ku = ind.keltner(df, n=20, k=1.5, atr_n=20)
    k, d = ind.stoch(df, 14, 3, 3)
    ema200 = ind.ema(df["close"], 200)
    
    # ย่อแตะเส้นกลาง แล้วปิดกลับไปได้
    bounce_up = (df["low"] < km) & (df["close"] > km)
    bounce_dn = (df["high"] > km) & (df["close"] < km)
    
    buy_cond = bounce_up & ind.cross_up(k, d) & (k < 50.0) & (df["close"] > ema200)
    sell_cond = bounce_dn & ind.cross_dn(k, d) & (k > 50.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
