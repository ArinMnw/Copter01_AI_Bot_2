# -*- coding: utf-8 -*-
"""S20.140 — Turtle System-2 Donchian 55 Breakout

แนวคิด: กฎ Turtle ของ Richard Dennis (System 2) — ปิดทะลุ high/low สูงสุด 55 แท่งก่อนหน้า = trend ใหม่
SL = 2N (N = ATR20 แบบ Turtle), TP = 2R, ถือไม่เกิน 60 แท่งของ TF
Causal: highest/lowest คำนวณจากแท่ง i-55..i-1 (shift(1)) เทียบ close ของแท่ง i ที่ปิดแล้ว
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import ind as I

META = {"sid": "20.140", "name": "Turtle System-2 Donchian 55 Breakout",
        "concept": "ปิดทะลุ Donchian 55 แท่งก่อนหน้า (Turtle System 2) SL 2N (ATR20) TP 2R",
        "sl_atr": 2.0, "rr": 2.0, "max_hold": 60, "be_r": 0.0, "atr_n": 20}


def generate(df, tf):
    hh = I.highest(df["high"], 55).shift(1)
    ll = I.lowest(df["low"], 55).shift(1)
    c = df["close"]
    buy = (c > hh) & (c.shift(1) <= hh.shift(1))
    sell = (c < ll) & (c.shift(1) >= ll.shift(1))
    return I.sig_from(buy, sell)
