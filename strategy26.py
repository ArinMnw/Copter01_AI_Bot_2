"""
strategy26.py — S26 High-Frequency M1 Scalping, ท่าเดียวซ้ำๆ, RR1:1 (RESEARCH / BACKTEST-ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py / trailing.py / main.py
   ไม่มี config.active_strategies[26], ไม่มี wiring เข้า live trading ใดๆ
   ใช้คู่กับ sim_s26_backtest.py / optimize_s26.py เพื่อ backtest เท่านั้น

สมมติฐานที่ทดสอบ: S21-S25 ทุกตัวความถี่ต่ำ (2-6 ไม้/วัน) แม้ avgR เป็นบวกก็ไปไม่ถึง
$1000/วันที่ risk ปลอดภัย เพราะไม้น้อยเกินไป — S26 ทดสอบว่าถ้าลง M1 (timeframe ละเอียดสุด)
ด้วย "ท่าเดียวที่เทรดซ้ำได้บ่อยมาก" + RR1:1 fixed (ง่ายต่อการ hit แต่ต้องการ WR>50%+spread
เพื่อ breakeven) จะปิดช่องว่างไปเป้าได้ด้วยความถี่สูงหรือไม่

cfg["SETUP_TYPE"] เลือกได้ 3 ท่า (ทดสอบในกริดเดียวกันเพื่อหาท่าที่ดีที่สุด แล้ว LOCK เหลือ
ท่าเดียวตามกฎข้อ 1 — ไม่ใช่ ensemble):
  1. "ema_pullback"     : ราคาแตะ EMA fast บน M1 แล้วเด้งตามเทรนด์ EMA_TREND (M1)
  2. "momentum_pullback": แท่ง momentum แรง ตามด้วยแท่ง pullback เล็ก แล้วเข้าตามทิศ momentum
  3. "range_scalp"       : fade ที่ขอบกรอบ range ช่วง session ผันผวนสูง (London/NY overlap)

Entry/Exit (ทุกท่าเหมือนกัน):
  - Entry: MARKET ที่ open ของแท่งถัดจากแท่ง signal (กัน look-ahead)
  - SL   : ตาม logic เฉพาะท่า (ดูจุดเกิด signal + ATR buffer)
  - TP   : entry ∓ TP_RR × risk, TP_RR fixed = 1.0 (ตามที่ผู้ใช้สั่ง — ไม่ปรับในกริดนี้)
  - Position sizing: risk-based ตาม % equity ต่อไม้ (S26_RISK_PCT) — ดู sim_s26_backtest.py
"""

S26_DEFAULTS = {
    "SETUP_TYPE": "ema_pullback",   # "ema_pullback" | "momentum_pullback" | "range_scalp"
    # ema_pullback params
    "EMA_FAST": 8,
    "EMA_TREND": 50,
    "EMA_SLOPE_BARS": 10,
    "PULLBACK_TOUCH_ATR": 0.15,     # close ต้องอยู่ใกล้ ema_fast ไม่เกินเท่านี้ ATR ถึงนับว่า "แตะ"
    # momentum_pullback params
    "MOMENTUM_BODY_ATR": 0.8,       # แท่ง momentum body >= เท่านี้ ATR
    "PULLBACK_MAX_ATR": 0.35,       # แท่ง pullback body <= เท่านี้ ATR (ต้องเล็ก)
    # range_scalp params
    "RANGE_LOOKBACK": 20,
    "RANGE_EDGE_PCT": 0.15,         # close ต้องอยู่ใน 15% ขอบบน/ล่างของกรอบ range
    "RANGE_MIN_SIZE_ATR": 1.5,      # กรอง range แคบเกินไป (ต้องกว้าง >= เท่านี้ ATR)
    # common
    "RSI_PERIOD": 14,
    "SL_ATR_MULT": 0.5,
    "TP_RR": 1.0,                   # FIXED ตามที่ผู้ใช้สั่ง — ห้ามปรับในกริดนี้
    "MAX_RISK_ATR_MULT": 4.0,
    "SESSION_FILTER": True,
    "SESSIONS": [("14:00", "23:00")],  # London+NY กว้างๆ เพื่อให้ signal เกิดบ่อยพอ
    "RISK_PCT": 1.0,
    # edge-improvement attempt A (ดู create_s26.md) — ATR volatility-regime confirmation
    "ATR_REGIME_FILTER": False,
    "ATR_REGIME_PERIOD_LONG": 50,
    "ATR_REGIME_MULT": 1.0,
}

_TF_SECS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S26_DEFAULTS[key]


def _calc_atr(rates, period=14):
    n = len(rates)
    if n == 0:
        return 0.0
    trs = []
    for i in range(n):
        h = float(rates[i]["high"]); l = float(rates[i]["low"])
        if i == 0:
            trs.append(h - l)
        else:
            pc = float(rates[i - 1]["close"])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0.0
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr


def _ema_series(closes, period):
    if len(closes) < period:
        return []
    k = 2.0 / (period + 1.0)
    ema = closes[0]
    out = []
    for c in closes:
        ema = c * k + ema * (1.0 - k)
        out.append(ema)
    return out


def _in_session(dt_bkk, cfg):
    if not _cfg(cfg, "SESSION_FILTER"):
        return True
    if dt_bkk is None:
        return True
    from datetime import time
    cur = dt_bkk.time()
    for start_str, end_str in _cfg(cfg, "SESSIONS"):
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        if time(sh, sm) <= cur < time(eh, em):
            return True
    return False


def _detect_ema_pullback(rates, atr, cfg):
    ema_fast_p = int(_cfg(cfg, "EMA_FAST"))
    ema_trend_p = int(_cfg(cfg, "EMA_TREND"))
    slope_bars = int(_cfg(cfg, "EMA_SLOPE_BARS"))
    closes = [float(r["close"]) for r in rates[:-1]]
    need = max(ema_fast_p, ema_trend_p) + slope_bars + 2
    if len(closes) < need:
        return None
    ef = _ema_series(closes, ema_fast_p)
    et = _ema_series(closes, ema_trend_p)
    if len(ef) < 2 or len(et) < slope_bars + 1:
        return None
    ema_fast_now = ef[-1]
    ema_trend_now = et[-1]
    ema_trend_prev = et[-1 - slope_bars]
    trend_up = ema_trend_now > ema_trend_prev
    trend_down = ema_trend_now < ema_trend_prev

    b = rates[-2]
    bo, bh, bl, bc = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
    touch_buf = float(_cfg(cfg, "PULLBACK_TOUCH_ATR")) * atr

    if trend_up and bl <= ema_fast_now + touch_buf and bc > bo and bc > ema_fast_now:
        entry = round(bc, 2)
        sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
        sl = round(min(bl, ema_fast_now) - sl_buf, 2)
        return ("BUY", entry, sl, "EMA pullback BUY: low touched EMA{} ({:.2f}) ตามเทรนด์ขึ้น".format(ema_fast_p, ema_fast_now))

    if trend_down and bh >= ema_fast_now - touch_buf and bc < bo and bc < ema_fast_now:
        entry = round(bc, 2)
        sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
        sl = round(max(bh, ema_fast_now) + sl_buf, 2)
        return ("SELL", entry, sl, "EMA pullback SELL: high touched EMA{} ({:.2f}) ตามเทรนด์ลง".format(ema_fast_p, ema_fast_now))

    return None


def _detect_momentum_pullback(rates, atr, cfg):
    if len(rates) < 4:
        return None
    mom = rates[-3]   # แท่ง momentum
    pb = rates[-2]    # แท่ง pullback (ปิดแล้ว ใช้เป็น signal bar)
    mo, mc = float(mom["open"]), float(mom["close"])
    po, ph, pl, pc = float(pb["open"]), float(pb["high"]), float(pb["low"]), float(pb["close"])

    mom_body = abs(mc - mo)
    pb_body = abs(pc - po)
    mom_min = float(_cfg(cfg, "MOMENTUM_BODY_ATR")) * atr
    pb_max = float(_cfg(cfg, "PULLBACK_MAX_ATR")) * atr
    if mom_body < mom_min or pb_body > pb_max:
        return None

    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    if mc > mo:  # momentum candle ขึ้น
        if pc <= mo:  # pullback ลงเลยจุดเปิดแท่ง momentum -> momentum ตาย ไม่เข้า
            return None
        entry = round(pc, 2)
        sl = round(min(pl, mo) - sl_buf, 2)
        return ("BUY", entry, sl, "Momentum+pullback BUY: momentum body {:.2f} ตามด้วย pullback เล็ก".format(mom_body))
    elif mc < mo:  # momentum candle ลง
        if pc >= mo:
            return None
        entry = round(pc, 2)
        sl = round(max(ph, mo) + sl_buf, 2)
        return ("SELL", entry, sl, "Momentum+pullback SELL: momentum body {:.2f} ตามด้วย pullback เล็ก".format(mom_body))

    return None


def _detect_range_scalp(rates, atr, cfg):
    lookback = int(_cfg(cfg, "RANGE_LOOKBACK"))
    if len(rates) < lookback + 3:
        return None
    window = rates[-(lookback + 2):-2]
    range_high = max(float(r["high"]) for r in window)
    range_low = min(float(r["low"]) for r in window)
    range_size = range_high - range_low
    if range_size <= 0 or range_size < float(_cfg(cfg, "RANGE_MIN_SIZE_ATR")) * atr:
        return None

    b = rates[-2]
    bo, bh, bl, bc = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
    edge_pct = float(_cfg(cfg, "RANGE_EDGE_PCT"))
    upper_zone = range_high - edge_pct * range_size
    lower_zone = range_low + edge_pct * range_size
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))

    if bh >= upper_zone and bc < bo:  # แตะขอบบน + ปิดแดง -> fade ลง
        entry = round(bc, 2)
        sl = round(max(bh, range_high) + sl_buf, 2)
        return ("SELL", entry, sl, "Range fade SELL: แตะขอบบนกรอบ {:.2f} (range {:.2f}-{:.2f})".format(bh, range_low, range_high))

    if bl <= lower_zone and bc > bo:  # แตะขอบล่าง + ปิดเขียว -> fade ขึ้น
        entry = round(bc, 2)
        sl = round(min(bl, range_low) - sl_buf, 2)
        return ("BUY", entry, sl, "Range fade BUY: แตะขอบล่างกรอบ {:.2f} (range {:.2f}-{:.2f})".format(bl, range_low, range_high))

    return None


def detect_s26(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    """
    Pure detection (backtest เรียกตรง)
    rates: แท่งสุดท้าย = แท่งกำลังวิ่ง (รู้แค่ open), rates[-2] = แท่ง signal candidate (ปิดแล้ว)
    คืน dict {signal: BUY/SELL/WAIT, ...}
    """
    setup = _cfg(cfg, "SETUP_TYPE")
    need = max(int(_cfg(cfg, "EMA_TREND")), int(_cfg(cfg, "RANGE_LOOKBACK"))) + 40
    if rates is None or len(rates) < need:
        return {"signal": "WAIT", "reason": f"S26: ข้อมูลไม่พอ (ต้องการ >= {need} แท่ง)"}

    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S26: อยู่นอกช่วง session filter"}

    atr = _calc_atr(rates[:-1], 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S26: คำนวณ ATR ไม่ได้"}

    if bool(_cfg(cfg, "ATR_REGIME_FILTER")):
        atr_long = _calc_atr(rates[:-1], int(_cfg(cfg, "ATR_REGIME_PERIOD_LONG")))
        if not atr_long or atr_long <= 0 or atr < float(_cfg(cfg, "ATR_REGIME_MULT")) * atr_long:
            return {"signal": "WAIT", "reason": "S26: ATR ไม่อยู่ใน volatility-expansion regime"}

    if setup == "ema_pullback":
        sig = _detect_ema_pullback(rates, atr, cfg)
    elif setup == "momentum_pullback":
        sig = _detect_momentum_pullback(rates, atr, cfg)
    elif setup == "range_scalp":
        sig = _detect_range_scalp(rates, atr, cfg)
    else:
        return {"signal": "WAIT", "reason": f"S26: setup_type ไม่รู้จัก '{setup}'"}

    if sig is None:
        return {"signal": "WAIT", "reason": f"S26({setup}): ยังไม่พบสัญญาณ"}

    direction, entry, sl, reason = sig
    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    b = rates[-2]

    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": f"S26({setup}): risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": f"S26({setup}): risk ผิดปกติ"}

    return {
        "signal": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 26 HF-M1-Scalp ({setup}) {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"{reason}\nentry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market",
        "entry_label": f"{direction} MARKET (S26 {setup})",
        "signal_bar_time": int(b["time"]),
        "atr_at_signal": atr,
        "setup_type": setup,
    }


def strategy_26(rates, tf: str = "", cfg: dict | None = None):
    """
    Wrapper runtime-style เก็บไว้เผื่ออนาคต
    ⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียกฟังก์ชันนี้ — standalone จริง
    """
    return detect_s26(rates, tf=tf, dt_bkk=None, cfg=cfg)
