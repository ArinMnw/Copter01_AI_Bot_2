# -*- coding: utf-8 -*-
import sys, os
import importlib.util
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, sid):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, "..", "s20." + sid, "strategy20_" + sid + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_A = _load("mix_a_521", "422")
_B = _load("mix_b_521", "223")

META = {
    "sid": "20.521",
    "name": 'Triple MA Breakout + Volume PVT Confirm',
    "concept": 'Bollinger breakout ที่มี Price-Volume Trend ตัด signal ยืนยันแรงซื้อขายจริง',
    "logic": 'breakout ของ A มักล้มเหลวเมื่อเป็น fakeout จากสภาพคล่องบาง (ราคาวิ่งแต่ไม่มี volume ตาม) B (223) คือ PVT ตัด signal EMA21 ซึ่งสะสม volume ถ่วงน้ำหนักด้วยการเปลี่ยนราคา CONFIRM k=3: รับ breakout เฉพาะที่ volume flow เพิ่งเปลี่ยนมาทิศเดียวกันภายใน 3 แท่ง = มี participation ยืนยัน',
    "parents": ["20.422", "20.223"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

K = 3


def generate(df, tf):
    sig_a = _A.generate(df, tf)
    sig_b = _B.generate(df, tf)
    # CONFIRM: A ให้สัญญาณที่แท่ง i และ B ให้สัญญาณทิศเดียวกันในช่วง [i-K+1, i] (ปิดแล้วทั้งหมด ไม่มองอนาคต)
    b_buy = pd.Series(sig_b == 1).rolling(K, min_periods=1).max().to_numpy() == 1
    b_sell = pd.Series(sig_b == -1).rolling(K, min_periods=1).max().to_numpy() == 1
    buy = pd.Series((sig_a == 1) & b_buy)
    sell = pd.Series((sig_a == -1) & b_sell)
    return ind.sig_from(buy, sell)
