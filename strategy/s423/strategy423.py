# -*- coding: utf-8 -*-
"""S423 - "The Always Winning Holy Grail Strategy - Not" (ต้นฉบับ © ChartArt,
Pine v2) — สคริปต์ตัวอย่าง/มุกตลกที่จงใจโชว์ว่า backtest "ชนะทุกไม้" ปลอมได้
ยังไงง่ายๆ: เข้า long ตลอดเวลา (เงื่อนไข `1+1==2` จริงเสมอ), TP แคบมาก (default
100 points) แต่ SL ตั้งไว้ใหญ่โตจนแทบเป็นไปไม่ได้ที่จะโดน (999999999999999
points) — ผลคือดู equity curve จะขึ้นเรื่อยๆ ทีละก้าวเล็กๆ (ชนะเกือบทุกไม้)
จนกว่าจะเจอวิกฤตราคาตกแรงพอที่จะกิน SL มหาศาลนั้นจริงๆ ครั้งเดียวก็ล้างพอร์ต —
นี่คือ "มุก" ของสคริปต์: win-rate สูงปลอมๆ ซ่อน tail-risk มหาศาลไว้

port ตรงตัวตาม logic เดิม (ไม่ได้ใส่ indicator ใดๆเพิ่ม เพราะต้นฉบับไม่มี):
  - pyramiding=0 → ถือได้ทีละไม้เดียว
  - ไม่มีเงื่อนไขเข้าไม้เลย (เข้าเสมอ) → "ถ้าไม่มีไม้เปิดอยู่ ให้เข้า BUY ทันที"
  - TP = TP_POINTS * POINT_VALUE ระยะราคาห่างจาก entry (default 100 points
    ตาม Pine default, POINT_VALUE=0.01 ตาม convention ของโปรเจกต์นี้สำหรับ
    XAUUSD — ดู config.S20_8_POINTS_MULTIPLIER)
  - SL: **ไม่มีจริง** (ตรงกับที่ Pine ตั้งค่าใหญ่จนไม่มีทางโดนในทางปฏิบัติ) —
    ตำแหน่งจะถือค้างไปเรื่อยๆ จนกว่าจะโดน TP เท่านั้น ไม่มี stop-out เลย

ข้อควรระวัง: strategy นี้ "ตั้งใจ" ไม่มี risk management จริง เป็นเครื่องมือ
สอน/สาธิตเท่านั้น ไม่ควรใช้เทรดจริงโดยเด็ดขาด (ผลตอบแทนระยะสั้นดูดีเพราะ
win-rate สูงปลอมๆ แต่มี unbounded tail-risk เดียวที่ล้างพอร์ตได้ทุกเมื่อ)
"""

from __future__ import annotations

import os
import sys

# strategy119.py อยู่ที่ root ของโปรเจกต์ ไม่ใช่ในโฟลเดอร์นี้ (strategy/s423/)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from strategy119 import _bars, _wait

DEFAULT_CFG = {
    "TP_POINTS": 100,               # ตรงกับ Pine default TakeProfit=100
    "SL_POINTS": 999999999999999,   # ตรงกับ Pine default StopLoss=999999999999999 เป๊ะ (ใหญ่จนแทบเป็นไปไม่ได้ที่จะโดน แต่ไม่ใช่ None — เป็น SL จริงตามต้นฉบับ)
    "POINT_VALUE": 0.01,            # points -> price distance (ตาม convention ของโปรเจกต์นี้สำหรับ XAUUSD)
    "ALLOW_BUY": True,               # ต้นฉบับ long อย่างเดียว (ไม่มี short เลย)
}


def detect_s423(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S423 — เข้า BUY เสมอ (ไม่มีเงื่อนไข) TP แคบ ไม่มี SL จริง (ดู docstring
    บนสุดของไฟล์นี้). ใช้ได้กับ engine กลางเป็นสัญญาณ "market" เสมอ — แต่เพราะ
    ไม่มี SL จริง จึงไม่ผ่าน validate_signal ที่ต้องการ sl/tp คู่กัน (RR ไม่มี
    ความหมายเมื่อ SL ไม่มีจริง) → backtest_s423.py มีลูปของตัวเองที่ไม่ผ่าน
    engine กลาง เพื่อจำลองพฤติกรรม "ไม่มี SL" ได้ตรงต้นฉบับ ฟังก์ชันนี้ไว้
    สำหรับ preview สัญญาณเฉยๆ (ไม่ได้ใช้ backtest จริง)"""
    del dt_bkk, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    if not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    try:
        bars = _bars(rates)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid rates: {exc}")
    if not bars:
        return _wait("Not enough data")

    entry = round(bars[-1]["close"], 2)
    tp = round(entry + float(c["TP_POINTS"]) * float(c["POINT_VALUE"]), 2)
    sl_points = c["SL_POINTS"]
    sl = round(entry - float(sl_points) * float(c["POINT_VALUE"]), 2) if sl_points is not None else None
    sl_desc = f"{sl_points}pt (={entry - sl:.2f})" if sl is not None else "none"
    return {
        "signal": "BUY",
        "entry": entry,
        "sl": sl,  # None = ไม่มี SL จริง (ดู docstring) — ผู้เรียกต้องรองรับ sl=None เอง
        "tp": tp,
        "order_type": "market",
        "pattern": "S423 Always-Long" + (" (no SL)" if sl is None else ""),
        "reason": f"Unconditional entry, TP={c['TP_POINTS']}pt (={tp - entry:.2f}), SL={sl_desc}",
        "be_rr": None,
        "cancel_bars": None,
    }
