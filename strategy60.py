"""
strategy60.py — S60 Asian Range Sweep Reversal, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด: high/low ของ Asian session เป็น liquidity pool ระยะสั้น ก่อน London/NY มักมี sweep เหนือ/ใต้
กรอบเพื่อกิน stop แล้วกลับเข้ากรอบ (Judas swing / liquidity grab) ท่านี้เข้า reversal หลังแท่ง sweep
ปิดกลับเข้ากรอบและมี displacement ออกจาก extreme
"""

from datetime import time


S60_DEFAULTS = {
    "ENTRY_TF": "M5",
    "ASIA_START": "02:00",
    "ASIA_END": "13:55",
    "TRADE_SESSIONS": [("14:00", "23:00")],
    "SWEEP_ATR_MULT": 0.20,
    "REJECT_ATR_MULT": 0.10,
    "MIN_RANGE_ATR": 2.0,
    "MAX_RANGE_ATR": 12.0,
    "BODY_ATR_MULT": 0.10,
    "MODE": "reversal",            # reversal | breakout
    "SL_ATR_MULT": 0.8,
    "TP_RR": 1.2,
    "MAX_RISK_ATR_MULT": 5.0,
    "MIN_GAP_BARS": 1,
    "ONE_TRADE_PER_DAY_SIDE": True,

    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.4,
    "COOLDOWN_TRADES": 10,

    "CONFIRMATION_TYPE": "none",
    "HTF_TF": "M15",
    "HTF_EMA_PERIOD": 50,
    "HTF_SLOPE_BARS": 5,
    "ADX_PERIOD": 14,
    "ADX_MIN_THRESHOLD": 0.0,
}


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S60_DEFAULTS[key]


def _parse_time(s):
    h, m = map(int, s.split(":"))
    return time(h, m)


def _calc_atr(rates, period=14):
    trs = []
    for i, b in enumerate(rates):
        h = float(b["high"]); l = float(b["low"])
        if i == 0:
            trs.append(h - l)
        else:
            pc = float(rates[i - 1]["close"])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return 0.0
    if len(trs) < period:
        return sum(trs) / len(trs)
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr


def _in_trade_session(dt_bkk, cfg):
    if dt_bkk is None:
        return True
    cur = dt_bkk.time()
    for start_str, end_str in _cfg(cfg, "TRADE_SESSIONS"):
        if _parse_time(start_str) <= cur < _parse_time(end_str):
            return True
    return False


def _asian_range(closed_rates, bar_dt_list, cfg):
    if not bar_dt_list or len(bar_dt_list) != len(closed_rates):
        return None
    cur_day = bar_dt_list[-1].date()
    start_t = _parse_time(_cfg(cfg, "ASIA_START"))
    end_t = _parse_time(_cfg(cfg, "ASIA_END"))
    bars = []
    for b, dt in zip(closed_rates, bar_dt_list):
        if dt.date() == cur_day and start_t <= dt.time() <= end_t:
            bars.append(b)
    if len(bars) < 12:
        return None
    hi = max(float(b["high"]) for b in bars)
    lo = min(float(b["low"]) for b in bars)
    return hi, lo, cur_day


def detect_s60(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None,
               bar_dt_list=None):
    if rates is None or len(rates) < 80:
        return {"signal": "WAIT", "reason": "S60: ข้อมูลไม่พอ"}
    if not _in_trade_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S60: นอก London/NY window"}

    closed = rates[:-1]
    closed_dt = bar_dt_list[:-1] if bar_dt_list else None
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S60: ATR ไม่ได้"}

    ar = _asian_range(closed, closed_dt, cfg)
    if ar is None:
        return {"signal": "WAIT", "reason": "S60: ไม่มี Asian range วันนี้"}
    asia_high, asia_low, asia_day = ar
    range_size = asia_high - asia_low
    if range_size < float(_cfg(cfg, "MIN_RANGE_ATR")) * atr:
        return {"signal": "WAIT", "reason": "S60: Asian range แคบเกินไป"}
    if range_size > float(_cfg(cfg, "MAX_RANGE_ATR")) * atr:
        return {"signal": "WAIT", "reason": "S60: Asian range กว้างเกินไป"}

    cur = closed[-1]
    co = float(cur["open"]); ch = float(cur["high"]); cl = float(cur["low"]); cc = float(cur["close"])
    sweep_buf = float(_cfg(cfg, "SWEEP_ATR_MULT")) * atr
    reject_buf = float(_cfg(cfg, "REJECT_ATR_MULT")) * atr
    body_min = float(_cfg(cfg, "BODY_ATR_MULT")) * atr

    mode = _cfg(cfg, "MODE")
    direction = None
    sweep_extreme = None
    if mode == "breakout":
        if cc >= asia_high + reject_buf and (cc - co) >= body_min:
            direction = "BUY"; sweep_extreme = cl
        elif cc <= asia_low - reject_buf and (co - cc) >= body_min:
            direction = "SELL"; sweep_extreme = ch
    elif ch >= asia_high + sweep_buf and cc <= asia_high - reject_buf and (co - cc) >= body_min:
        direction = "SELL"; sweep_extreme = ch
    elif cl <= asia_low - sweep_buf and cc >= asia_low + reject_buf and (cc - co) >= body_min:
        direction = "BUY"; sweep_extreme = cl
    if direction is None:
        return {"signal": "WAIT", "reason": "S60: ยังไม่มี sweep+reject"}

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S60: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S60: ADX(HTF) ไม่ผ่าน"}
            # reversal หลัง sweep จะ allow แบบสวน HTF เท่านั้นใน mode นี้
            if direction == "BUY" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S60: HTF ไม่ลงก่อน BUY sweep"}
            if direction == "SELL" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S60: HTF ไม่ขึ้นก่อน SELL sweep"}

    entry = round(cc, 2)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr
    if direction == "BUY":
        sl = round(sweep_extreme - sl_buf, 2)
    else:
        sl = round(sweep_extreme + sl_buf, 2)

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S60: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S60: risk ผิดปกติ"}

    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 60 AsiaSweep {'BUY' if direction == 'BUY' else 'SELL'}",
        "reason": f"Asia range {asia_day} [{asia_low:.2f},{asia_high:.2f}] sweep@{sweep_extreme:.2f}",
        "order_mode": "market", "signal_bar_time": int(cur["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_60(rates, tf: str = "", cfg: dict | None = None):
    return detect_s60(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None, bar_dt_list=None)
