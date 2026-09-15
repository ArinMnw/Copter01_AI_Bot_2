# -*- coding: utf-8 -*-
"""S424 - "Daily Close Comparison Strategy" (ต้นฉบับ © ChartArt, Pine v2) —
เทียบ close ของแท่ง Daily ล่าสุดกับแท่ง Daily ก่อนหน้า ถ้าวันนี้ปิดสูงกว่าเมื่อวาน
เกิน threshold ให้ถือ Long ถ้าต่ำกว่าให้ถือ Short (ไม่มี exit เอง นอกจากสลับทิศ
ตามการเปรียบเทียบวันถัดไป) — ไม่มี stop loss/take profit ในต้นฉบับเลย
("This simple strategy does not have any stop loss or take profit money
management logic")

ข้อแตกต่างจาก Pine ต้นฉบับ ที่ต้อง "ปรับให้เข้ากับ backtest engine ของโปรเจกต์":
  1) Pine ใช้ `security(tickerid, 'D', close)` แบบไม่ตั้ง lookahead=off ทำให้
     "close ของวันนี้" อัปเดตแบบ real-time ตลอดวันที่ยังไม่ปิด (repaint — เจอ
     pattern เดียวกับ OCC Strategy/S420 มาก่อนแล้วในโปรเจกต์นี้) เวอร์ชันนี้ใช้
     เฉพาะแท่ง Daily ที่ปิดสมบูรณ์แล้วเท่านั้น (non-repaint): เปรียบเทียบแท่ง
     Daily ล่าสุดที่ปิดแล้ว กับแท่ง Daily ก่อนหน้านั้น (ไม่ใช่แท่งที่กำลังก่อตัว)
  2) threshold=0 (ค่า default ของ Pine) ทำให้ช่วง "close เท่ากันเป๊ะ" (คง
     สถานะเดิมจาก buying[1]) แทบไม่มีทางเกิดขึ้นจริงกับราคาจริง — เวอร์ชันนี้เลย
     ไม่ implement การ "จำสถานะข้ามวัน" แบบ Pine (ซึ่งต้องมี state สะสม) ถ้า
     threshold ตั้งเป็นค่าอื่นที่ทำให้เข้าโซนนี้บ่อยขึ้น จะได้ WAIT แทนการคงสถานะ
     เดิม — เป็นการลดความซับซ้อนโดยตั้งใจ
  3) ไม่มี SL/TP ในต้นฉบับ — ใช้ ATR-based SL/TP แทน (SL_ATR_MULT/TP_RR ใน
     DEFAULT_CFG) ตาม convention ของ strategy อื่นในโปรเจกต์นี้ที่พอร์ตมาจาก
     Pine ที่ไม่มี stop (ดู strategy422.py) — order_type="market" (ไม่ใช่
     "limit" แบบ S420/S421 เพราะ exit ที่แท้จริงของกลยุทธ์นี้คือ reversal
     ทันทีที่สัญญาณสลับทิศ ซึ่งฝั่ง market มี logic reversal พร้อมใช้อยู่แล้ว)
"""

from __future__ import annotations

import os
import sys

# strategy119.py อยู่ที่ root ของโปรเจกต์ ไม่ใช่ในโฟลเดอร์นี้ (strategy/s424/)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from strategy119 import _atr, _bars, _wait

TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60}
DAY_MINUTES = 1440

DEFAULT_CFG = {
    "THRESHOLD": 0.0,       # ตรงกับ Pine default (สัดส่วน เช่น 0.001 = 0.1%)
    "ATR_PERIOD": 14,
    "SL_ATR_MULT": 2.0,     # กว้างกว่าปกติ เพราะกลยุทธ์นี้ตั้งใจถือยาวตามเทรนด์รายวัน
    "TP_RR": 1.5,           # ค่าต่ำสุดที่ engine กลางต้องการ — เป็น safety cap ไม่ใช่เป้าหมายจริง
    # ⚠️ ยืนยันจริงกับ TradingView แล้ว (2026-08-13, M1 03-13 ส.ค.): ต้นฉบับ Pine
    # ไม่มี SL/TP เลย ถือไม้จนกว่าจะสลับทิศ (reversal ล้วนๆ) — TV มีแค่ 6 ไม้ใน
    # 10 วัน ขณะที่ตอนแรกผมใส่ ATR SL/TP เข้าไปเป็น safety net ทำให้ M1 ได้ 725
    # ไม้ (โดน SL แคบกวาดซ้ำๆ ในทิศเดิมทั้งวัน) ผิดจากของจริงมาก — USE_ATR_STOP
    # จึง default False ใน backtest_s424.py (reversal-only ตรงต้นฉบับ) เปิดได้
    # ผ่าน cfg ถ้าอยากทดลองแบบมี stop เทียบดู
    "USE_ATR_STOP": False,
    "ALLOW_BUY": True,
    "ALLOW_SELL": True,
    "BE_RR": None,
    "CANCEL_BARS": None,
}


    # จุดตัดวัน (daily rollover) ของ raw MT5 epoch — ยืนยันด้วยข้อมูลจริงเทียบ
    # TradingView (2026-08-13): TV entry ทุกไม้ตรงกับ true BKK 05:00 (= rollover
    # 17:00 New York ตามธรรมเนียม FX/gold ทั่วไป ไม่ใช่ UTC midnight) และ true
    # BKK 05:00 ตรงกับ raw epoch ชั่วโมงที่ 23 พอดี (ยืนยันด้วย
    # bar_time_to_bkk() ของ backtest_s420.py) — ต้อง bucket ตามจุดนี้ ไม่ใช่
    # raw-epoch UTC midnight (hour 0) แบบเดิม ไม่งั้น daily close จะผิดวันไปหลาย
    # ชั่วโมง ทำให้ signal ผิดทิศได้ (พิสูจน์แล้วจริง: ตอนใช้ UTC midnight ได้
    # sequence BUY/SELL/BUY/SELL/BUY ผิดจาก TV ที่เป็น BUY/SELL/BUY/SELL/BUY
    # เหมือนกันแต่ timing/ราคาต่างกันจนทิศพลิกไม้หนึ่งไม้)
_ROLLOVER_RAW_HOUR = 23


def _aggregate_daily(bars, base_minutes):
    """รวมแท่ง base-TF เป็นแท่ง Daily (rollover ที่ raw epoch hour=23 =
    true BKK 05:00 — ดู comment เหนือ _ROLLOVER_RAW_HOUR) ตัดทิ้ง bucket ที่แท่ง
    base ขาดหายเกินเกณฑ์ผ่อนปรน (เหมือน strategy420._aggregate_alt_tf แต่ผ่อนปรน
    กว่า H1-bucket ของ S420 เพราะ broker นี้มี maintenance gap ประจำวัน ~65 นาที
    (03:57-05:02 BKK ยืนยันแล้วตอนพอร์ต S420 — ดู memory
    project_s420_zigzagpa_status.md) ทำให้แทบไม่มีวันไหน "ครบ 100%" เลยสักวัน
    ถ้าใช้เกณฑ์เป๊ะแบบ S420 จะตัดทิ้งทุก bucket หมด — ยอมให้ขาดได้ถึง ~90 นาที/วัน
    (ครอบคลุม gap ที่รู้จักไว้ + กันชนเล็กน้อย) ยังคงตัดทิ้งวันที่ยังไม่จบจริง/ข้อมูล
    ขาดหายผิดปกติ (เช่น แท่งเดียวทั้งวัน) ได้เหมือนเดิม."""
    bucket_seconds = DAY_MINUTES * 60
    rollover_offset = _ROLLOVER_RAW_HOUR * 3600
    bars_per_bucket = max(1, DAY_MINUTES // base_minutes)
    gap_tolerance_bars = max(1, round(90 / base_minutes))
    min_required = max(1, bars_per_bucket - gap_tolerance_bars)
    buckets, order, counts = {}, [], {}
    for bar in bars:
        bucket_start = ((bar["time"] - rollover_offset) // bucket_seconds) * bucket_seconds + rollover_offset
        if bucket_start not in buckets:
            buckets[bucket_start] = {"time": bucket_start, "open": bar["open"], "high": bar["high"],
                                      "low": bar["low"], "close": bar["close"]}
            order.append(bucket_start)
            counts[bucket_start] = 1
        else:
            slot = buckets[bucket_start]
            slot["high"] = max(slot["high"], bar["high"])
            slot["low"] = min(slot["low"], bar["low"])
            slot["close"] = bar["close"]
            counts[bucket_start] += 1
    return [buckets[t] for t in order if counts[t] >= min_required]


def compute_state(rates, tf="", cfg=None):
    """เทียบแท่ง Daily ล่าสุดที่ปิดสมบูรณ์แล้ว กับแท่งก่อนหน้า — คืน (state, None)
    หรือ (None, เหตุผล). state = {"event","buying","delta","percentage",
    "yesterday_close","today_close"}

    ⚠️ เคยลองเปลี่ยนเป็น "เทียบ close ปัจจุบัน (แท่ง TF ที่ใช้อยู่) กับ close
    Daily ที่ปิดล่าสุด" (ตีความว่า Pine's security() แบบไม่ตั้ง lookahead=off
    หมายถึง repaint ต่อเนื่องทุกแท่ง) แต่ยืนยันด้วยข้อมูลจริงจาก TradingView
    (2026-08-13, เทียบ trade frequency ของ 5 ช่วง M1-H1) ว่า**ผิด** — ความถี่
    ไม้ของ TV คงที่ ~0.4-0.5 ไม้/วัน "ไม่ว่า TF ไหนก็ตาม" (M1:0.5, M5:0.5,
    M15:0.42, M30:0.38, H1:0.40) ซึ่งตรงกับสูตร "เทียบ 2 แท่ง Daily ที่ปิดแล้ว"
    นี้เป๊ะ (ได้ ~0.37/วัน) ไม่ใช่สูตร repaint-ต่อเนื่อง (ทดสอบแล้วได้ 159 ไม้ใน
    10 วันบน M1 เพราะราคา whipsaw ข้ามเส้น yesterday's close บ่อยมาก ซึ่งควร
    จะสเกลตาม TF ถ้าเป็น repaint จริง แต่ TV ไม่สเกลแบบนั้น) — win-rate ที่ต่าง
    กันมาก (TV ~90% เทียบ ~35% ของเรา) จึงน่าจะมาจากสาเหตุอื่น (ตลาดทองเทรนด์
    ขึ้นแรงต่อเนื่องช่วงที่ทดสอบ ทำให้กลยุทธ์ตามเทรนด์ชนะง่าย) ไม่ใช่สูตรผิด"""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)
    base_minutes = TF_MINUTES.get(str(tf).upper())
    if base_minutes is None:
        return None, f"Unsupported tf {tf}"
    try:
        threshold = float(c["THRESHOLD"])
    except (KeyError, TypeError, ValueError) as exc:
        return None, f"Invalid cfg: {exc}"

    if rates is None or len(rates) < 30:
        return None, "Not enough data"
    try:
        bars = _bars(rates)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return None, f"Invalid rates: {exc}"

    daily = _aggregate_daily(bars, base_minutes)
    if len(daily) < 2:
        return None, "Not enough complete daily bars (need 2)"

    event = bars[-1]
    yesterday_close = daily[-2]["close"]
    today_close = daily[-1]["close"]
    if yesterday_close == 0.0:
        return None, "yesterday close is zero"
    delta = today_close - yesterday_close
    percentage = delta / yesterday_close

    if percentage > threshold:
        buying = True
    elif percentage < -threshold:
        buying = False
    else:
        return None, (f"Inside threshold dead-zone (percentage={percentage:.5f} "
                       f"threshold={threshold:.5f}) — no state-carry in stateless detect")

    return {
        "event": event, "buying": buying, "delta": delta, "percentage": percentage,
        "yesterday_close": yesterday_close, "today_close": today_close,
    }, None


def detect_s424(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """S424 Daily Close Comparison — Long ถ้าปิด Daily ล่าสุดสูงกว่าเมื่อวาน,
    Short ถ้าต่ำกว่า (ดู docstring บนสุดของไฟล์นี้สำหรับรายละเอียดที่ปรับให้เข้า
    กับ engine ของโปรเจกต์)."""
    del dt_bkk, kwargs
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    state, err = compute_state(rates, tf, c)
    if state is None:
        return _wait(err)

    signal = "BUY" if state["buying"] else "SELL"
    if signal == "BUY" and not bool(c["ALLOW_BUY"]):
        return _wait("BUY disabled")
    if signal == "SELL" and not bool(c["ALLOW_SELL"]):
        return _wait("SELL disabled")

    try:
        bars = _bars(rates)
        atr_period = int(c["ATR_PERIOD"])
        sl_mult = float(c["SL_ATR_MULT"])
        tp_rr = max(1.5, float(c["TP_RR"]))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _wait(f"Invalid cfg/rates: {exc}")

    atr = _atr(bars, atr_period)
    if atr <= 0.0:
        return _wait("ATR is zero")

    entry = round(state["event"]["close"], 2)
    risk = atr * sl_mult
    sl = round(entry - risk, 2) if signal == "BUY" else round(entry + risk, 2)
    tp = round(entry + risk * tp_rr, 2) if signal == "BUY" else round(entry - risk * tp_rr, 2)

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "order_type": "market",
        "pattern": f"S424 {signal} Daily Close Comparison",
        "reason": (f"today={state['today_close']:.2f} yesterday={state['yesterday_close']:.2f} "
                   f"delta%={state['percentage'] * 100:.3f}% ATR={atr:.2f}"),
        "be_rr": c["BE_RR"],
        "cancel_bars": c["CANCEL_BARS"],
    }
