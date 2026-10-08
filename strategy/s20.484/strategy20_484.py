# -*- coding: utf-8 -*-
"""S20.484 — Mix 339 + 153 (CONFIRM)

กู้คืนผลที่หายจาก S20.467: antigravity รันคู่นี้ (339+153 CONFIRM) ได้ PASS (M30) จริงเมื่อ 2026-10-05
แต่ reuse sid 467 กับคู่ถัดไปก่อนบันทึก ทำให้ไฟล์ถูกเขียนทับหายไปก่อนเข้า final_gate/mix_check
สร้างใหม่ด้วยสูตร CONFIRM เดียวกัน (เทียบกับ strategy/s20.471/strategy20_471.py ที่เป็นแบบเดียวกัน) ไม่ถือเป็นการลองคู่นี้ครั้งใหม่

แนวคิด: ยืนยันสัญญาณ breakout ของ S20.339 (Inside Bar MACD Continuation Breakout) ด้วยสัญญาณ turning point ของ
S20.153 (Awesome Oscillator Saucer) ที่เกิดภายใน 3 แท่งที่ผ่านมา — เหตุผลเดียวกับ S20.483 แต่ใช้ 339 เป็นตัวแม่หลักแทน
"""
import os
import sys
import importlib.util

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))

META = {
    "sid": "20.484",
    "name": "Mix 339 + 153 (CONFIRM)",
    "concept": "Mixed Strategy: 339 and 153",
    "logic": "AO saucer (153) ภายใน 3 แท่งก่อนหรือพร้อมกับ breakout ของ 339 ยืนยันว่าโมเมนตัมกลับมาเดินตามเทรนด์จริง ไม่ใช่ breakout หลอก",
    "parents": ["20.339", "20.153"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0,
}


def load_strategy(sid):
    path = os.path.join(HERE, "..", f"s20.{sid}", f"strategy20_{sid}.py")
    spec = importlib.util.spec_from_file_location(f"s20_{sid}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod_a = load_strategy("339")
mod_b = load_strategy("153")


def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    out = np.zeros(len(df), dtype=np.int8)
    sig_b_s = pd.Series(sig_b)
    b_long_recent = sig_b_s.rolling(window=4, min_periods=1).max() == 1
    b_short_recent = sig_b_s.rolling(window=4, min_periods=1).min() == -1
    out[(sig_a == 1) & b_long_recent] = 1
    out[(sig_a == -1) & b_short_recent] = -1
    return out
