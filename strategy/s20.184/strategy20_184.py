# -*- coding: utf-8 -*-
"""S20.184 — Rolling Hour-of-Day Seasonality

แนวคิด: Intraday seasonality แบบ causal: แต่ละชั่วโมง (H4 = บล็อก 4 ชม.) ใช้ผลตอบแทนเฉลี่ยของช่วงเดียวกันใน 60 วันก่อนหน้า (เฉพาะวันที่จบแล้ว) ถ้า t-stat > 2 → เข้าที่ต้นช่วงนั้นตามทิศ ถือจนจบช่วง (D1 ไม่มีสัญญาณ)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.184', 'name': 'Rolling Hour-of-Day Seasonality', 'concept': 'Intraday seasonality แบบ causal: แต่ละชั่วโมง (H4 = บล็อก 4 ชม.) ใช้ผลตอบแทนเฉลี่ยของช่วงเดียวกันใน 60 วันก่อนหน้า (เฉพาะวันที่จบแล้ว) ถ้า t-stat > 2 → เข้าที่ต้นช่วงนั้นตามทิศ ถือจนจบช่วง (D1 ไม่มีสัญญาณ)', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 1, 'max_hold_tf': {'M1': 60, 'M5': 12, 'M15': 4, 'M30': 2, 'H1': 1, 'H4': 1}}


def generate(df, tf):
    if tf == "D1":
        return np.zeros(len(df), dtype=np.int8)
    bucket = 14400 if tf == "H4" else 3600
    tfs = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}[tf]
    t = df["time"]
    slot = (t % 86400) // bucket
    day = t // 86400
    blk = pd.DataFrame({"day": day, "slot": slot, "o": df["open"], "c": df["close"]})
    g = blk.groupby(["day", "slot"]).agg(o=("o", "first"), c=("c", "last")).reset_index()
    g["r"] = g["c"] / g["o"] - 1
    g = g.sort_values(["slot", "day"])
    rs = g.groupby("slot")["r"]
    g["m"] = rs.transform(lambda s: s.rolling(60, min_periods=40).mean())
    g["sd"] = rs.transform(lambda s: s.rolling(60, min_periods=40).std())
    g["tstat"] = g["m"] / (g["sd"] / np.sqrt(60))
    # สัญญาณ ณ แท่งสุดท้ายก่อนเข้า slot ใหม่ → ใช้สถิติของ slot นั้นจากวันที่ < วันเข้าเทรด (ข้อมูลที่จบแล้วเท่านั้น)
    nxt = t + tfs
    starts_new = ((nxt % 86400) // bucket) != slot
    q = pd.DataFrame({"i": np.arange(len(df)), "day": (nxt // 86400).astype(np.int64), "slot": ((nxt % 86400) // bucket).astype(np.int64)})
    q = q[starts_new.to_numpy()].sort_values("day")
    g2 = g[["day", "slot", "tstat"]].astype({"day": np.int64, "slot": np.int64}).sort_values("day")
    mm = pd.merge_asof(q, g2, on="day", by="slot", allow_exact_matches=False)
    tv = pd.Series(np.nan, index=df.index)
    tv.iloc[mm["i"].to_numpy()] = mm["tstat"].to_numpy()
    return I.sig_from(tv > 2.0, tv < -2.0)
