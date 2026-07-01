"""
strategy36.py — S36 FVG (Fair Value Gap) Retracement — ICT/SMC mechanism, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live
(แยกจาก strategy2.py/strategy4.py เดิมที่ใช้ FVG อยู่แล้วใน live bot — ไฟล์นี้คือ research ใหม่
ในเฟรมเวิร์ก S30+ ที่มี htf_trend confirmation + circuit_breaker + robustness rigor)

แนวคิด ICT/SMC: **Fair Value Gap** เกิดเมื่อ 3 แท่งต่อกัน high ของแท่งที่ 1 ไม่ทับ low ของแท่งที่ 3
(bullish FVG) หรือ low ของแท่งที่ 1 ไม่ทับ high ของแท่งที่ 3 (bearish FVG) — เป็น "ช่องว่างราคา"
ที่ตลาดมักย้อนกลับมาเติมก่อนวิ่งต่อทิศเดิม (continuation, ไม่ใช่ reversal) เข้าตอนราคาย้อนกลับเข้า
ไปในช่องว่าง (retracement) ยืนยันด้วย htf_trend (M15/EMA50) เหมือน A/B เดิม
"""

S36_DEFAULTS = {
    "ENTRY_TF": "M5",
    "MIN_GAP_ATR": 0.15,          # ขนาดช่องว่าง FVG ขั้นต่ำ >= mult x ATR (กัน FVG เล็กเกินไป/noise)
    "MAX_GAP_AGE_BARS": 20,       # FVG ต้องยังไม่ถูกเติมเต็มภายใน N แท่งหลังเกิด (ไม่งั้นถือว่าหมดอายุ)
    "RETRACE_ENTRY_PCT": 0.5,     # เข้าตอนราคาย้อนเข้าไปในช่องว่าง >= 50% ของช่องว่าง (มากกว่านี้ = ลึกกว่า)
    "SL_ATR_MULT": 1.0,
    "TP_RR": 1.0,
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
    return S36_DEFAULTS[key]


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


def _find_unfilled_fvg(closed_rates, atr, cfg):
    """
    หา FVG ล่าสุดที่ยังไม่ถูกเติมเต็ม (จากท้ายสุดของ closed_rates ถอยหลัง) — 3-candle pattern
    ที่ index i-2,i-1,i: bullish FVG ถ้า low[i] > high[i-2] (ช่องว่างระหว่าง high ของแท่ง1 กับ
    low ของแท่ง3), bearish FVG ถ้า high[i] < low[i-2]
    คืน (direction, gap_top, gap_bottom, gap_created_idx) หรือ None
    """
    n = len(closed_rates)
    min_gap = float(_cfg(cfg, "MIN_GAP_ATR")) * atr
    max_age = int(_cfg(cfg, "MAX_GAP_AGE_BARS"))
    lookback_start = max(2, n - max_age - 1)

    for i in range(n - 1, lookback_start, -1):
        if i < 2:
            break
        b1 = closed_rates[i - 2]; b3 = closed_rates[i]
        h1 = float(b1["high"]); l1 = float(b1["low"])
        h3 = float(b3["high"]); l3 = float(b3["low"])

        # bullish FVG: low ของแท่ง3 อยู่เหนือ high ของแท่ง1
        if l3 > h1 and (l3 - h1) >= min_gap:
            gap_bottom, gap_top = h1, l3
            filled = any(float(closed_rates[k]["low"]) <= gap_bottom
                         for k in range(i + 1, n))
            if not filled:
                return ("BUY", gap_top, gap_bottom, i)
        # bearish FVG: high ของแท่ง3 อยู่ใต้ low ของแท่ง1
        if h3 < l1 and (l1 - h3) >= min_gap:
            gap_top, gap_bottom = l1, h3
            filled = any(float(closed_rates[k]["high"]) >= gap_top
                         for k in range(i + 1, n))
            if not filled:
                return ("SELL", gap_top, gap_bottom, i)
    return None


def detect_s36(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    need = 40
    if rates is None or len(rates) < need:
        return {"signal": "WAIT", "reason": f"S36: ข้อมูลไม่พอ (>= {need})"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S36: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S36: ATR ไม่ได้"}

    fvg = _find_unfilled_fvg(closed, atr, cfg)
    if fvg is None:
        return {"signal": "WAIT", "reason": "S36: ไม่พบ FVG ที่ยังไม่เติม"}
    direction, gap_top, gap_bottom, _ = fvg

    cur = closed[-1]
    cc = float(cur["close"])
    gap_size = gap_top - gap_bottom
    retrace_pct = float(_cfg(cfg, "RETRACE_ENTRY_PCT"))
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))

    # ราคาต้องย้อนกลับเข้าไปในช่องว่าง >= retrace_pct ของช่องว่าง (นับจากขอบที่ใกล้ทิศ continuation)
    if direction == "BUY":
        # bullish FVG: ต้องการราคาย้อนลงมาแตะโซนล่างของช่องว่าง (ใกล้ gap_bottom) แล้วปิดเหนือ gap_bottom
        retrace_level = gap_top - retrace_pct * gap_size
        if not (cc <= retrace_level and cc > gap_bottom):
            return {"signal": "WAIT", "reason": "S36: ยังไม่ retrace เข้า FVG พอ (BUY)"}
        entry = round(cc, 2)
        sl = round(gap_bottom - sl_buf, 2)
    else:
        retrace_level = gap_bottom + retrace_pct * gap_size
        if not (cc >= retrace_level and cc < gap_top):
            return {"signal": "WAIT", "reason": "S36: ยังไม่ retrace เข้า FVG พอ (SELL)"}
        entry = round(cc, 2)
        sl = round(gap_top + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S36: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S36: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S36: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S36: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S36: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S36: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 36 FVG_retrace+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"FVG retrace gap=[{gap_bottom:.2f},{gap_top:.2f}]\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_36(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s36(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
