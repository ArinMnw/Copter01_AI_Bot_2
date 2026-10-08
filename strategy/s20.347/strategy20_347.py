# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.347",
    "name": "HA Doji Keltner Pullback",
    "concept": "หาจังหวะย่อตัวในเทรนด์หลัก โดยใช้แท่งเทียน Heikin-Ashi ทรง Doji นอกขอบ Keltner Channel เพื่อหาจุดพักตัวที่แม่นยำ",
    "logic": "ในเทรนด์ขาขึ้น ถ้าราคาย่อตัวลงมาจนหลุดขอบล่าง Keltner (2.0) และเกิดแท่ง HA Doji (Body < 20% ของแท่ง) แปลว่าแรงขายหมดแล้ว แท่งถัดไปที่เริ่มเป็นขาขึ้น (hc > ho) จะเป็นจุดเข้า Buy, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ho, hh, hl, hc = ind.heikin_ashi(df)
    kl, km, ku = ind.keltner(df, n=20, k=2.0)
    
    ema20 = ind.ema(df["close"], 20)
    ema200 = ind.ema(df["close"], 200)
    
    ha_body = (hc - ho).abs()
    ha_tr = (hh - hl).replace(0, np.nan)
    is_doji = ha_body < (ha_tr * 0.2)
    
    # Doji เกิดที่ขอบในแท่งก่อนหน้า และแท่งปัจจุบันคอนเฟิร์มทิศทาง
    buy_cond = is_doji.shift(1) & (hl.shift(1) < kl.shift(1)) & (hc > ho) & (ema20 > ema200)
    sell_cond = is_doji.shift(1) & (hh.shift(1) > ku.shift(1)) & (hc < ho) & (ema20 < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
