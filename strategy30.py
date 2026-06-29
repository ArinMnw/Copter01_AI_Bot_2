"""
strategy30.py — S30 Frequency-optimized engulfing family + multi-TF (RESEARCH / BACKTEST-ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py / trailing.py / main.py
   ไม่มี config.active_strategies[30], ไม่มี wiring เข้า live trading ใดๆ
   ใช้คู่กับ sim_s30_backtest.py / optimize_s30.py เพื่อ backtest เท่านั้น

ต่อยอดตรงจาก S29 (ดู create_s29.md): S29 พบว่า engulfing entry + htf_trend(M15/EMA50) +
circuit_breaker ให้ edge ดีที่สุด (WR 60%, avgR +0.231, PF 1.23-1.29, maxDD 16.7% ปลอดภัย)
แต่ติด "คอขวดเดียว": ความถี่ต่ำเกินไป (3.4 ไม้/วัน) เพราะ engulfing candle เกิดยาก

S30 โจมตีคอขวดความถี่โดยตรง โดย "lock คุณภาพ" (htf_trend M15/EMA50 + SL/RR + circuit_breaker
ของ S29) ไว้ แล้วเพิ่มความถี่ผ่าน 3 lever:

1. ENTRY_PATTERN ตระกูล engulfing ที่ผ่อน/ขยายให้เกิดถี่ขึ้น:
   - "engulfing"      : engulfing เดิมของ S29 (baseline เทียบในกริดเดียวกัน)
   - "strong_close"   : momentum bar ที่ปิดใน STRONG_CLOSE_PCT บน/ล่างของ range แท่ง + body
                        >= STRONG_BODY_ATR x ATR ใกล้ EMA (เกิดถี่กว่า engulfing มากเพราะไม่ต้อง
                        "กลืน" แท่งก่อน แค่ปิดแรงทิศเดียว)
   - "family"         : ยิงเมื่อเข้าเงื่อนไข engulfing OR strong_close (เพิ่ม signal count รวม
                        โดยคุมคุณภาพด้วย htf_trend + SL/RR เดิม)
2. ENTRY_TF เลือก M5 (เดิม) หรือ M1 (ความถี่สูงขึ้น) — htf_trend confirmation จาก M15 คงเดิม
3. MIN_GAP_BARS / SESSIONS ปรับได้ (S29 hardcode min_gap=2, session 14:00-23:00)

Entry/Exit/HTF-lookahead-guard/DD-control เหมือน S29 ทุกประการ
"""

S30_DEFAULTS = {
    "ENTRY_TF": "M5",                  # "M5" | "M1"
    "ENTRY_PATTERN": "family",         # "engulfing" | "strong_close" | "family"
    "EMA_FAST": 8,
    "PULLBACK_TOUCH_ATR": 0.15,
    "ENGULF_MIN_RATIO": 1.3,           # ผ่อนลงได้จาก 1.6 ของ S29 เพื่อความถี่
    "STRONG_CLOSE_PCT": 0.70,          # close อยู่ใน 30% บนสุด(BUY)/ล่างสุด(SELL) ของ range
    "STRONG_BODY_ATR": 0.5,            # body แท่ง >= ratio x ATR (กัน noise bar เล็ก)
    "MIN_GAP_BARS": 1,                 # S29 = 2; ผ่อนเป็น 1 เพิ่มความถี่
    "SL_ATR_MULT": 0.5,                # locked จาก S29 grid winner
    "TP_RR": 0.8,                      # locked จาก S29 grid winner
    "MAX_RISK_ATR_MULT": 4.0,
    "SESSION_FILTER": True,
    "SESSIONS": [("14:00", "23:00")],

    "RISK_PCT": 0.5,                   # locked จาก S29 (safe DD)
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.4,
    "COOLDOWN_TRADES": 10,

    "CONFIRMATION_TYPE": "htf_trend",  # locked จาก S27/S29
    "HTF_TF": "M15",
    "HTF_EMA_PERIOD": 50,
    "HTF_SLOPE_BARS": 5,
    "ADX_PERIOD": 14,
    "ADX_MIN_THRESHOLD": 0.0,
}

_TF_SECS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S30_DEFAULTS[key]


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


def _ema_now(rates, cfg):
    ema_fast_p = int(_cfg(cfg, "EMA_FAST"))
    closes = [float(r["close"]) for r in rates[:-1]]
    if len(closes) < ema_fast_p + 2:
        return None
    ef = _ema_series(closes, ema_fast_p)
    if len(ef) < 2:
        return None
    return ef[-1]


def _detect_engulfing(rates, atr, ema_now, cfg):
    """Engulfing candle ใกล้ EMA (เหมือน S29) — คืน (dir, entry, sl, reason) หรือ None"""
    if len(rates) < 4:
        return None
    prev, cur = rates[-3], rates[-2]
    po, pc = float(prev["open"]), float(prev["close"])
    co, ch, cl, cc = float(cur["open"]), float(cur["high"]), float(cur["low"]), float(cur["close"])
    touch_buf = float(_cfg(cfg, "PULLBACK_TOUCH_ATR")) * atr
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    ratio = float(_cfg(cfg, "ENGULF_MIN_RATIO"))
    body_prev = abs(pc - po)
    body_cur = abs(cc - co)
    body_floor = max(body_prev, atr * 0.02)

    if pc < po and cc > co and co <= pc and cc >= po and body_cur >= ratio * body_floor:
        if cl <= ema_now + touch_buf:
            entry = round(cc, 2)
            sl = round(min(cl, float(prev["low"]), ema_now) - sl_buf, 2)
            return ("BUY", entry, sl, f"Bullish engulfing near EMA @ {ema_now:.2f}")
    if pc > po and cc < co and co >= pc and cc <= po and body_cur >= ratio * body_floor:
        if ch >= ema_now - touch_buf:
            entry = round(cc, 2)
            sl = round(max(ch, float(prev["high"]), ema_now) + sl_buf, 2)
            return ("SELL", entry, sl, f"Bearish engulfing near EMA @ {ema_now:.2f}")
    return None


def _detect_strong_close(rates, atr, ema_now, cfg):
    """Momentum bar: ปิดแรงทิศเดียว (close ใน X% บน/ล่างของ range) + body พอ ใกล้ EMA
    เกิดถี่กว่า engulfing มากเพราะไม่ต้อง 'กลืน' แท่งก่อน"""
    b = rates[-2]
    bo, bh, bl, bc = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
    rng = bh - bl
    if rng <= 0:
        return None
    body = abs(bc - bo)
    if body < float(_cfg(cfg, "STRONG_BODY_ATR")) * atr:
        return None
    touch_buf = float(_cfg(cfg, "PULLBACK_TOUCH_ATR")) * atr
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    close_pos = (bc - bl) / rng  # 1.0 = ปิดที่ high สุด, 0.0 = ปิดที่ low สุด
    strong = float(_cfg(cfg, "STRONG_CLOSE_PCT"))

    # BUY: ปิดแรงขึ้น (close ใกล้ high) + bullish + แตะ EMA จากบน
    if close_pos >= strong and bc > bo and bl <= ema_now + touch_buf:
        entry = round(bc, 2)
        sl = round(min(bl, ema_now) - sl_buf, 2)
        return ("BUY", entry, sl, f"Strong bullish close near EMA @ {ema_now:.2f}")
    # SELL: ปิดแรงลง (close ใกล้ low) + bearish + แตะ EMA จากล่าง
    if close_pos <= (1.0 - strong) and bc < bo and bh >= ema_now - touch_buf:
        entry = round(bc, 2)
        sl = round(max(bh, ema_now) + sl_buf, 2)
        return ("SELL", entry, sl, f"Strong bearish close near EMA @ {ema_now:.2f}")
    return None


def _detect_family(rates, atr, ema_now, cfg):
    """ยิงเมื่อเข้า engulfing หรือ strong_close (engulfing มาก่อน เพราะคุณภาพสูงกว่า)"""
    sig = _detect_engulfing(rates, atr, ema_now, cfg)
    if sig is not None:
        return sig
    return _detect_strong_close(rates, atr, ema_now, cfg)


_PATTERN_DETECTORS = {
    "engulfing": _detect_engulfing,
    "strong_close": _detect_strong_close,
    "family": _detect_family,
}


def detect_s30(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    ema_fast_p = int(_cfg(cfg, "EMA_FAST"))
    need = ema_fast_p + 12
    if rates is None or len(rates) < need:
        return {"signal": "WAIT", "reason": f"S30: ข้อมูลไม่พอ (>= {need})"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S30: นอก session"}
    atr = _calc_atr(rates[:-1], 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S30: ATR ไม่ได้"}
    ema_now = _ema_now(rates, cfg)
    if ema_now is None:
        return {"signal": "WAIT", "reason": "S30: EMA ไม่ได้"}

    pattern = _cfg(cfg, "ENTRY_PATTERN")
    detector = _PATTERN_DETECTORS.get(pattern)
    if detector is None:
        return {"signal": "WAIT", "reason": f"S30: pattern ไม่รู้จัก ({pattern})"}
    sig = detector(rates, atr, ema_now, cfg)
    if sig is None:
        return {"signal": "WAIT", "reason": f"S30: ยังไม่พบสัญญาณ ({pattern})"}

    direction, entry, sl, reason = sig

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S30: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S30: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S30: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S30: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S30: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S30: risk ผิดปกติ"}

    b = rates[-2]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 30 {pattern}+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"{reason}\nentry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market",
        "signal_bar_time": int(b["time"]),
        "atr_at_signal": atr,
        "entry_pattern": pattern,
        "confirmation_type": conf_type,
    }


def strategy_30(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s30(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
