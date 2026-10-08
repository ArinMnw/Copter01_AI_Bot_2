# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.359",
    "name": "HA Volatility Expansion Breakout",
    "concept": "เข้าเทรดเมื่อแท่งเทียน Heikin-Ashi มีการหดตัวต่อเนื่อง (Volatility Contraction) แล้วเกิดการขยายตัวพร้อมแท่งสีที่ชัดเจนตามเทรนด์",
    "logic": "ความยาวแท่ง Heikin-Ashi (High-Low) ที่สั้นลงต่อเนื่องแสดงถึงการสะสมพลัง หากแท่งปัจจุบันยาวขึ้นกว่าแท่งก่อนพร้อมกับเป็นสีตามเทรนด์ EMA200 มักจะเป็นการระเบิดตัวครั้งใหม่, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ho, hh, hl, hc = ind.heikin_ashi(df)
    ema200 = ind.ema(df["close"], 200)
    
    ha_tr = (hh - hl).replace(0, np.nan)
    
    # หดตัวต่อเนื่องอย่างน้อย 2 แท่ง
    contracted = (ha_tr < ha_tr.shift(1)) & (ha_tr.shift(1) < ha_tr.shift(2))
    
    # ขยายตัว
    expanded = ha_tr > ha_tr.shift(1)
    
    buy_cond = contracted.shift(1) & expanded & (hc > ho) & (df["close"] > ema200)
    sell_cond = contracted.shift(1) & expanded & (hc < ho) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
