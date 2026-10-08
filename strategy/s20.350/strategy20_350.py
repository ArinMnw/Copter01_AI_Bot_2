# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.350",
    "name": "PSAR ADX Acceleration Trend",
    "concept": "เข้าเทรดเมื่อเทรนด์เปลี่ยนทิศทาง (PSAR Flip) พร้อมกับมีความเร่งของ ADX เข้ามาสนับสนุน",
    "logic": "PSAR ใช้ดักจับการเปลี่ยนหน้าเล่น หากเกิดพร้อมกับ ADX ที่กำลังเชิดหัวขึ้น (adx > adx_prev) และค่าเกิน 20 แปลว่าการเปลี่ยนหน้านั้นมีโมเมนตัมของจริง ไม่ใช่แค่ไซด์เวย์แกว่งตัว, กรองด้วย EMA200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sar, sar_dir = ind.psar(df, 0.02, 0.2)
    pdi, ndi, adx = ind.dmi(df, 14)
    ema200 = ind.ema(df["close"], 200)
    
    adx_accel = (adx > adx.shift(1)) & (adx > 20.0)
    
    buy_cond = ind.cross_up(sar_dir, 0.0) & adx_accel & (df["close"] > ema200)
    sell_cond = ind.cross_dn(sar_dir, 0.0) & adx_accel & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
