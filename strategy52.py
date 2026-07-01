"""
strategy52.py — S52 Quantified Pin Bar Reversal, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด: pin bar (long wick + small body) ที่นิยามด้วยกฎเชิงปริมาณล้วน (ไม่ใช่การมองภาพ) —
body = |close-open|, wick ด้านที่ยาว (rejection wick) ต้อง >= MIN_WICK_BODY_RATIO x body, wick
ฝั่งตรงข้าม (opposite wick) ต้องเล็ก <= MAX_OPPOSITE_WICK_RATIO x rejection wick, และ candle range
รวมต้อง >= MIN_RANGE_ATR x ATR (กัน noise candle เล็กเกินไป) — ต่างจาก S37/S44/S49/S51 (ที่หา
"ระดับ" ก่อนแล้วเช็ค rejection ที่ระดับ) เพราะ S52 ไม่สนใจระดับราคาเลย เป็น pure price-action
candlestick pattern: bullish pin bar (wick ล่างยาว) -> BUY, bearish pin bar (wick บนยาว) -> SELL
ยืนยันด้วย htf_trend
"""

S52_DEFAULTS = {
    "ENTRY_TF": "M5",
    "MIN_WICK_BODY_RATIO": 2.0,     # wick ด้าน rejection ต้อง >= mult x body
    "MAX_OPPOSITE_WICK_RATIO": 0.3, # wick ฝั่งตรงข้ามต้อง <= mult x rejection wick
    "MIN_RANGE_ATR": 0.5,           # candle range รวมต้อง >= mult x ATR
    "SL_ATR_MULT": 1.0,
    "TP_RR": 1.5,
    "MAX_RISK_ATR_MULT": 4.0,
    "MIN_GAP_BARS": 1,
    "SESSION_FILTER": True,
    "SESSIONS": [("14:00", "23:00")],

    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.4,
    "COOLDOWN_TRADES": 10,

    "CONFIRMATION_TYPE": "htf_trend",
    "HTF_TF": "M15",
    "HTF_EMA_PERIOD": 50,
    "HTF_SLOPE_BARS": 5,
    "ADX_PERIOD": 14,
    "ADX_MIN_THRESHOLD": 0.0,
}


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S52_DEFAULTS[key]


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


def detect_s52(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    if rates is None or len(rates) < 30:
        return {"signal": "WAIT", "reason": "S52: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S52: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S52: ATR ไม่ได้"}

    cur = closed[-1]
    co = float(cur["open"]); ch = float(cur["high"]); cl = float(cur["low"]); cc = float(cur["close"])
    rng = ch - cl
    min_range = float(_cfg(cfg, "MIN_RANGE_ATR")) * atr
    if rng < min_range or rng <= 0:
        return {"signal": "WAIT", "reason": "S52: candle range เล็กเกินไป"}

    body = abs(cc - co)
    body_top = max(co, cc)
    body_bot = min(co, cc)
    upper_wick = ch - body_top
    lower_wick = body_bot - cl

    min_ratio = float(_cfg(cfg, "MIN_WICK_BODY_RATIO"))
    max_opp_ratio = float(_cfg(cfg, "MAX_OPPOSITE_WICK_RATIO"))
    body_floor = max(body, 1e-9)

    direction = None
    # bullish pin bar: wick ล่างยาว, wick บนเล็ก -> คาดเด้งขึ้น (BUY)
    if lower_wick >= min_ratio * body_floor and upper_wick <= max_opp_ratio * lower_wick:
        direction = "BUY"
    # bearish pin bar: wick บนยาว, wick ล่างเล็ก -> คาดเด้งลง (SELL)
    elif upper_wick >= min_ratio * body_floor and lower_wick <= max_opp_ratio * upper_wick:
        direction = "SELL"
    if direction is None:
        return {"signal": "WAIT", "reason": "S52: ไม่ใช่ pin bar"}

    entry = round(cc, 2)
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    if direction == "BUY":
        sl = round(cl - sl_buf, 2)
    else:
        sl = round(ch + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S52: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S52: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S52: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S52: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S52: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S52: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 52 PinBar+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"PinBar body={body:.3f} upperW={upper_wick:.3f} lowerW={lower_wick:.3f}\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_52(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s52(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
