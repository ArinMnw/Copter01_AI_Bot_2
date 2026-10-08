# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.331",
    "name": "Volume Spike Keltner Breakout",
    "concept": "เข้าเทรดตามการ Breakout กรอบ Keltner Channel ที่มาพร้อมกับปริมาณการซื้อขาย (Volume) ที่พุ่งสูงผิดปกติ",
    "logic": "Volume Spike (Z-Score > 2.5) ยืนยันว่าการ Breakout ไม่ใช่สัญญาณหลอก และมีรายใหญ่เข้าดันราคา, กรองทิศทางด้วย EMA200, SL 2.0 ATR เผื่อความผันผวน, RR 1.5 หวังกำไรจากการไล่ราคา, ถือ 24 แท่ง",
    "sl_atr": 2.0,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    vol_z = ind.zscore(df["tick_volume"], 50)
    kl, km, ku = ind.keltner(df, n=20, k=2.0, atr_n=14)
    ema200 = ind.ema(df["close"], 200)
    
    vol_spike = vol_z > 2.5
    
    buy_cond = vol_spike & (df["close"] > ku) & (df["close"] > ema200)
    sell_cond = vol_spike & (df["close"] < kl) & (df["close"] < ema200)
    
    # ensure it's a cross
    buy_sig = ind.cross_up(df["close"], ku) & buy_cond
    sell_sig = ind.cross_dn(df["close"], kl) & sell_cond
    
    return ind.sig_from(buy_sig, sell_sig)
