# -*- coding: utf-8 -*-
"""
S103: Sideways Mean-Reversion Expert (มือปราบไซด์เวย์ — จิ๊กซอว์ตัวสุดท้ายของตระกูล)

ช่องว่างทางสถิติที่ S103 อุด:
  S99/S100/S101 มี ATR_REGIME_PCTL — "ห้ามเทรดตอน volatility ต่ำ"
  S102 ต้องรอ breakout จาก compression — ตอนตลาดนิ่งมันคือช่วง "รอ"
  = ช่วงตลาดไซด์เวย์เงียบๆ ไม่มีใครในตระกูลทำเงินเลย
  S103 เทรด "เฉพาะ" ช่วงนั้น → correlation กับพี่น้องต่ำสุดโดยโครงสร้าง

ตรรกะ (The Alpha):
  1. Low-Vol Regime Gate — ATR ปัจจุบันต้อง "ต่ำกว่า" percentile ที่กำหนด
     (กลับด้านกับ S99-S101) = เทรดเฉพาะตอนตลาดหลับ
  2. Range Box — กรอบ N แท่งต้องกว้างพอตีปิงปอง (>= MIN) แต่ไม่ใช่เทรนด์ (<= MAX)
     และราคา "อยู่ในกรอบ" มาแล้วอย่างน้อย M แท่ง (กรอบนิ่งจริง ไม่ใช่เพิ่งวิ่งมา)
  3. Edge Rejection — แตะขอบกรอบ + แท่ง reject (close กลับเข้ากรอบ):
     ขอบบน → SELL / ขอบล่าง → BUY
  4. Fast RSI Extreme — RSI(7) ต้องสุดขั้ว (>=70 / <=30) ยืนยัน overextension
  5. Z-Score Filter — close ห่างจาก SMA20 เกิน Z เท่าของ std → ยิ่งห่างยิ่งดีดกลับ
  6. TP ที่ "กลางกรอบ" (mean) — เป้าธรรมชาติของ mean reversion, SL หลังขอบนิดเดียว
     ไม่ใช้ trailing (สวนตรรกะ mean reversion ที่เป้าคือค่าเฉลี่ย ไม่ใช่ let-run)
  7. Session Guard — บล็อกชั่วโมงเปิด London/NY (ที่ S102 ชอบ) เพราะ box มักแตกตอนนั้น
"""

DEFAULT_CFG = {
    # mode: "box" = range ping-pong / "vwap" = VWAP + SD band mean reversion
    "MODE": "box",
    # --- vwap mode ---
    "VWAP_SD_MULT": 2.0,        # fade เมื่อราคาห่าง VWAP >= k×SD
    "VWAP_MIN_BARS": 30,        # ต้องมีแท่งในวันนั้นอย่างน้อยเท่านี้ก่อนเชื่อ VWAP
    "VWAP_TP_AT": "vwap",       # "vwap" = TP ที่เส้น VWAP / "half" = ครึ่งทาง
    "VWAP_SL_SD": 1.0,          # SL ห่างจาก entry ออกไปอีก k×SD
    # regime gate (กลับด้านกับ S99-S101)
    "ATR_REGIME_PCTL_MAX": 45.0,   # ATR ต้อง < percentile นี้ของ ATR ย้อนหลัง
    # range box
    "RANGE_BARS": 30,              # sweep: 30 >> 50 (n 83 vs 4 — กรอบสั้นจับ box จริงได้ไวกว่า)
    "RANGE_MIN_ATR": 1.5,          # กรอบต้องกว้าง >= k×ATR (มีที่ให้ตีปิงปอง)
    "RANGE_MAX_ATR": 5.0,          # และ <= k×ATR (ไม่ใช่เทรนด์)
    "INSIDE_BARS_MIN": 10,         # แท่งล่าสุด M แท่งต้องอยู่ในกรอบทั้งหมด (box นิ่งจริง)
    "EDGE_ZONE_PCT": 0.20,         # โซนขอบ = 20% บน/ล่างของกรอบ
    # confirmation
    "RSI_PERIOD": 7,
    "RSI_SELL_MIN": 68.0,          # SELL ที่ขอบบน: RSI >= ค่านี้
    "RSI_BUY_MAX": 32.0,           # BUY ที่ขอบล่าง: RSI <= ค่านี้
    "ZSCORE_ENABLED": True,
    "ZSCORE_SMA": 20,
    "ZSCORE_MIN": 1.5,             # |z| ของ close เทียบ SMA ต้อง >= ค่านี้
    "REJECT_CLOSE_INSIDE": True,   # แท่งล่าสุดต้อง close กลับเข้ากรอบ (wick reject)
    # entry / risk
    "ENTRY_AT": "close",           # "close" = market ที่ close / "edge" = limit ที่ขอบ
    "SL_BUF_ATR": 0.3,             # SL หลังขอบกรอบ k×ATR (sweep: 0.3 > 0.5)
    "TP_TARGET": "mid",            # "mid" = กลางกรอบ / "opposite" = ขอบตรงข้าม / "rr" = RR คงที่จาก SL
    "TP_RR": 1.0,                  # ใช้เมื่อ TP_TARGET = "rr"
    # session guard — บล็อกชั่วโมงที่ box มักแตก (ช่วงโปรดของ S102)
    "TIME_FILTER_ENABLED": True,
    "BLOCK_HOURS": (14, 15, 20, 21),
    "ML_FILTER_ENABLED": False,
    "ML_SCORE_THRESHOLD": 0.55,
}


def _atr(rates, period=14):
    trs = []
    for i in range(len(rates) - period, len(rates)):
        h, l = float(rates[i]["high"]), float(rates[i]["low"])
        pc = float(rates[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)


def _atr_series(rates, period=14):
    out = [None] * len(rates)
    trs = []
    for i in range(1, len(rates)):
        h, l = float(rates[i]["high"]), float(rates[i]["low"])
        pc = float(rates[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        if len(trs) >= period:
            out[i] = sum(trs[-period:]) / period
    return out


def _rsi_fast(closes, period=7):
    if len(closes) < period + 2:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    rsi = None
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        rsi = 100.0 if avg_l == 0 else 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    return rsi


def _detect_vwap(rates, c, dt_bkk, tf):
    """โหมด VWAP: fade ราคาที่หลุด ±k×SD กลับหา VWAP (anchored รายวัน)"""
    from datetime import datetime as _dt
    if dt_bkk is None:
        return {"signal": "WAIT", "reason": "No time context"}
    cur_date = dt_bkk.date()
    day_bars = [r for r in rates
                if _dt.fromtimestamp(int(r["time"])).date() == cur_date]
    if len(day_bars) < int(c["VWAP_MIN_BARS"]):
        return {"signal": "WAIT", "reason": "Not enough bars today for VWAP"}

    # anchored VWAP + SD ของ deviation
    cum_pv, cum_v = 0.0, 0.0
    typicals, vols = [], []
    for r in day_bars:
        tp_price = (float(r["high"]) + float(r["low"]) + float(r["close"])) / 3.0
        v = max(float(r["tick_volume"]), 1.0)
        cum_pv += tp_price * v
        cum_v += v
        typicals.append(tp_price)
        vols.append(v)
    vwap = cum_pv / cum_v
    var = sum(v * (t - vwap) ** 2 for t, v in zip(typicals, vols)) / cum_v
    sd = var ** 0.5
    if sd <= 0:
        return {"signal": "WAIT", "reason": "Zero VWAP SD"}

    last = rates[-1]
    l_c = float(last["close"])
    l_o = float(last["open"])
    band = sd * float(c["VWAP_SD_MULT"])

    closes = [float(r["close"]) for r in rates]
    rsi = _rsi_fast(closes[-60:], int(c["RSI_PERIOD"]))
    if rsi is None:
        return {"signal": "WAIT", "reason": "RSI not ready"}

    def _res(direction, entry, sl, tp, why):
        return {
            "signal": direction, "entry": round(entry, 2), "sl": round(sl, 2),
            "tp": round(tp, 2), "order_type": "market",
            "pattern": f"S103 VWAP Fade {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
            "reason": why, "candles": [last],
        }

    # SELL: ราคาเหนือ VWAP เกิน band + แท่ง reject ลง + RSI สุดขั้วบน
    if l_c >= vwap + band and l_c < l_o and rsi >= float(c["RSI_SELL_MIN"]):
        entry = l_c
        sl = entry + sd * float(c["VWAP_SL_SD"])
        tp = vwap if c["VWAP_TP_AT"] == "vwap" else (entry + vwap) / 2.0
        if sl - entry <= 0 or entry - tp <= 0:
            return {"signal": "WAIT", "reason": "Invalid geometry"}
        return _res("SELL", entry, sl, tp,
                    f"Fade +{float(c['VWAP_SD_MULT']):.1f}SD above VWAP {vwap:.2f}, RSI7 {rsi:.0f}")

    # BUY: ราคาใต้ VWAP เกิน band + แท่ง reject ขึ้น + RSI สุดขั้วล่าง
    if l_c <= vwap - band and l_c > l_o and rsi <= float(c["RSI_BUY_MAX"]):
        entry = l_c
        sl = entry - sd * float(c["VWAP_SL_SD"])
        tp = vwap if c["VWAP_TP_AT"] == "vwap" else (entry + vwap) / 2.0
        if entry - sl <= 0 or tp - entry <= 0:
            return {"signal": "WAIT", "reason": "Invalid geometry"}
        return _res("BUY", entry, sl, tp,
                    f"Fade -{float(c['VWAP_SD_MULT']):.1f}SD below VWAP {vwap:.2f}, RSI7 {rsi:.0f}")

    return {"signal": "WAIT", "reason": "Price within VWAP bands"}


def detect_s103(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    if c.get("MODE") == "vwap":
        if len(rates) < 120:
            return {"signal": "WAIT", "reason": "Not enough data"}
        if c["TIME_FILTER_ENABLED"] and dt_bkk is not None:
            if dt_bkk.hour in c["BLOCK_HOURS"]:
                return {"signal": "WAIT", "reason": f"Blocked hour {dt_bkk.hour}"}
        return _detect_vwap(rates, c, dt_bkk, tf)

    rng_bars = int(c["RANGE_BARS"])
    if len(rates) < max(rng_bars + 20, 120):
        return {"signal": "WAIT", "reason": "Not enough data"}

    if c["TIME_FILTER_ENABLED"] and dt_bkk is not None:
        if dt_bkk.hour in c["BLOCK_HOURS"]:
            return {"signal": "WAIT", "reason": f"Blocked hour {dt_bkk.hour} (session open)"}

    atr = _atr(rates)
    if atr <= 0:
        return {"signal": "WAIT", "reason": "ATR zero"}

    # --- Low-vol regime gate (กลับด้านกับ S99-S101) ---
    series = [x for x in _atr_series(rates)[-100:] if x is not None]
    if series:
        s = sorted(series)
        k = min(max(int(len(s) * c["ATR_REGIME_PCTL_MAX"] / 100.0), 0), len(s) - 1)
        if atr > s[k]:
            return {"signal": "WAIT", "reason": "Volatility too high (not sideways)"}

    # --- Range box ---
    box = rates[-rng_bars:]
    box_h = max(float(r["high"]) for r in box)
    box_l = min(float(r["low"]) for r in box)
    box_w = box_h - box_l
    if box_w < atr * float(c["RANGE_MIN_ATR"]):
        return {"signal": "WAIT", "reason": "Range too narrow to ping-pong"}
    if box_w > atr * float(c["RANGE_MAX_ATR"]):
        return {"signal": "WAIT", "reason": "Range too wide (trending)"}
    box_mid = (box_h + box_l) / 2.0

    # box ต้องนิ่ง: M แท่งล่าสุดอยู่ในกรอบทั้งหมด (กรอบไม่ได้เพิ่งขยาย)
    m = int(c["INSIDE_BARS_MIN"])
    recent = rates[-m:]
    for r in recent:
        if float(r["high"]) > box_h + 1e-9 or float(r["low"]) < box_l - 1e-9:
            return {"signal": "WAIT", "reason": "Box not settled"}

    last = rates[-1]
    l_h, l_l, l_c = float(last["high"]), float(last["low"]), float(last["close"])
    edge_zone = box_w * float(c["EDGE_ZONE_PCT"])

    closes = [float(r["close"]) for r in rates]
    rsi = _rsi_fast(closes[-60:], int(c["RSI_PERIOD"]))
    if rsi is None:
        return {"signal": "WAIT", "reason": "RSI not ready"}

    zscore = None
    if c["ZSCORE_ENABLED"]:
        w = int(c["ZSCORE_SMA"])
        window = closes[-w:]
        sma = sum(window) / w
        var = sum((x - sma) ** 2 for x in window) / w
        std = var ** 0.5
        if std <= 0:
            return {"signal": "WAIT", "reason": "Zero std"}
        zscore = (l_c - sma) / std

    def _ml_ok(direction, entry):
        if not c["ML_FILTER_ENABLED"]:
            return True, 1.0
        import ml_scoring
        prob = ml_scoring.score_signal('XAUUSD.iux', tf, direction, entry,
                                       dt_bkk, historical_rates=rates)
        return prob >= float(c["ML_SCORE_THRESHOLD"]), prob

    def _result(direction, entry, sl, tp, why):
        return {
            "signal": direction,
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "order_type": "market" if c["ENTRY_AT"] == "close" else "limit",
            "pattern": f"S103 Range Ping-Pong {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
            "reason": why,
            "candles": [last],
        }

    # ---------- SELL ที่ขอบบน ----------
    if l_h >= box_h - edge_zone and rsi >= float(c["RSI_SELL_MIN"]):
        if zscore is not None and zscore < float(c["ZSCORE_MIN"]):
            return {"signal": "WAIT", "reason": f"Z-score too low ({zscore:.2f})"}
        if c["REJECT_CLOSE_INSIDE"] and l_c > box_h - edge_zone:
            return {"signal": "WAIT", "reason": "No rejection close back inside"}
        entry = l_c if c["ENTRY_AT"] == "close" else box_h - edge_zone
        sl = box_h + max(1.5, atr * float(c["SL_BUF_ATR"]))
        if c["TP_TARGET"] == "rr":
            tp = entry - (sl - entry) * float(c["TP_RR"])
        else:
            tp = box_mid if c["TP_TARGET"] == "mid" else box_l + edge_zone
        if sl - entry <= 0 or entry - tp <= 0:
            return {"signal": "WAIT", "reason": "Invalid geometry"}
        ok, prob = _ml_ok("SELL", entry)
        if not ok:
            return {"signal": "WAIT", "reason": f"S103 SELL blocked by ML ({prob:.2f})"}
        return _result("SELL", entry, sl, tp,
                       f"Upper edge reject, RSI7 {rsi:.0f}, z {zscore:.2f}" if zscore is not None
                       else f"Upper edge reject, RSI7 {rsi:.0f}")

    # ---------- BUY ที่ขอบล่าง ----------
    if l_l <= box_l + edge_zone and rsi <= float(c["RSI_BUY_MAX"]):
        if zscore is not None and zscore > -float(c["ZSCORE_MIN"]):
            return {"signal": "WAIT", "reason": f"Z-score too high ({zscore:.2f})"}
        if c["REJECT_CLOSE_INSIDE"] and l_c < box_l + edge_zone:
            return {"signal": "WAIT", "reason": "No rejection close back inside"}
        entry = l_c if c["ENTRY_AT"] == "close" else box_l + edge_zone
        sl = box_l - max(1.5, atr * float(c["SL_BUF_ATR"]))
        if c["TP_TARGET"] == "rr":
            tp = entry + (entry - sl) * float(c["TP_RR"])
        else:
            tp = box_mid if c["TP_TARGET"] == "mid" else box_h - edge_zone
        if entry - sl <= 0 or tp - entry <= 0:
            return {"signal": "WAIT", "reason": "Invalid geometry"}
        ok, prob = _ml_ok("BUY", entry)
        if not ok:
            return {"signal": "WAIT", "reason": f"S103 BUY blocked by ML ({prob:.2f})"}
        return _result("BUY", entry, sl, tp,
                       f"Lower edge reject, RSI7 {rsi:.0f}, z {zscore:.2f}" if zscore is not None
                       else f"Lower edge reject, RSI7 {rsi:.0f}")

    return {"signal": "WAIT", "reason": "No edge touch in settled sideways box"}
