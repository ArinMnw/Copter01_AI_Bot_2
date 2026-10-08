# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.418",
    "name": "Keltner Momentum Reversal",
    "concept": "เข้าเทรดแบบ Mean Reversion ตามเทรนด์หลัก เมื่อราคาย่อตัวหลุดกรอบ Keltner และ Momentum เริ่มกลับตัว",
    "logic": "เช็คเทรนด์หลักด้วย EMA 100 หากราคาในเทรนด์ขาขึ้นย่อตัวจนหลุดขอบล่าง Keltner (Oversold) และ MACD Histogram เริ่มหักหัวขึ้น จะถือเป็นสัญญาณ Buy (Sell กลับกัน)",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ema100 = ind.ema(df["close"], 100)
    kl, km, ku = ind.keltner(df, 20, 1.5)
    macd, macdsig, macdhist = ind.macd(df["close"], 12, 26, 9)

    # Buy: เทรนด์ขึ้น (Close > EMA100), ราคาย่อหลุดกรอบล่าง Keltner, MACD Hist เริ่มหักหัวขึ้นจากแดนลบ
    buy_cond1 = df["close"] > ema100
    buy_cond2 = df["close"] < kl
    buy_cond3 = (macdhist < 0) & (macdhist > macdhist.shift(1)) & (macdhist.shift(1) < macdhist.shift(2))
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3

    # Sell: เทรนด์ลง (Close < EMA100), ราคาดีดทะลุกรอบบน Keltner, MACD Hist เริ่มหักหัวลงจากแดนบวก
    sell_cond1 = df["close"] < ema100
    sell_cond2 = df["close"] > ku
    sell_cond3 = (macdhist > 0) & (macdhist < macdhist.shift(1)) & (macdhist.shift(1) > macdhist.shift(2))
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3

    return ind.sig_from(buy_signal, sell_signal)
