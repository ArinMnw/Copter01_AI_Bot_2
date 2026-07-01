"""
strategy50.py — S50 Asian Range Liquidity Sweep (ICT Judas Swing), RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด ICT Judas Swing: นิยาม "Asian range" = high/low ของแท่งในช่วง ASIAN_RANGE_START-
ASIAN_RANGE_END (BKK) ของวันนั้น (ค่าเริ่มต้น 08:00-12:00 BKK ≈ 20:00-00:00 EST ตามนิยาม ICT) รอ
"London Judas Swing" คือราคาทะลุขอบ Asian range (sweep liquidity) ภายในช่วง SWEEP window หลัง
London เปิด (14:00 BKK) แล้ว **ปิดกลับเข้ามาในโซน Asian range** (false breakout/manipulation) —
เข้า reversal ทิศตรงข้าม sweep (sweep high -> SELL, sweep low -> BUY) — ต่างจาก S42 (CRT ทั่วไปที่
range block = rolling N-bar ใดก็ได้) เพราะ S50 ยึด range กับ session เฉพาะ (Asian) และจุด
sweep ต้องเกิดที่ session เฉพาะ (London open) เท่านั้น — ผสม session-anchored (เหมือน S46) +
sweep-reversal (เหมือน S42) ทั้ง 2 หมวดที่ชนะ
"""

S50_DEFAULTS = {
    "ENTRY_TF": "M5",
    "ASIAN_RANGE_START": "08:00",   # BKK ≈ 20:00 EST (เริ่มสร้าง Asian range)
    "ASIAN_RANGE_END": "12:00",     # BKK ≈ 00:00 EST (ปิด Asian range)
    "SWEEP_SESSION_START": "14:00", # London open BKK (เริ่มมองหา Judas Swing)
    "MAX_SWEEP_AGE_MIN": 180,       # sweep ต้องเกิดภายใน N นาทีหลัง London เปิด
    "SWEEP_ATR_MULT": 0.25,         # ต้อง sweep เลยขอบ Asian range >= mult x ATR
    "MIN_RANGE_ATR": 0.8,           # Asian range ต้องกว้าง >= mult x ATR (กัน range เล็กเกินไป)
    "SL_ATR_MULT": 1.0,
    "TP_RR": 1.5,
    "MAX_RISK_ATR_MULT": 5.0,
    "MIN_GAP_BARS": 1,

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
    return S50_DEFAULTS[key]


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


def detect_s50(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None,
               bar_dt_list=None):
    """
    bar_dt_list: list ของ datetime (BKK) คู่กับ closed_rates แต่ละแท่ง (ต้องส่งมาจาก replay เพราะ
    การคำนวณ dt_bkk ทีละแท่งจาก timestamp ต้องใช้ config.mt5_ts_to_bkk ซึ่งอยู่นอกไฟล์นี้)
    """
    if rates is None or len(rates) < 40 or bar_dt_list is None or len(bar_dt_list) != len(rates) - 1:
        return {"signal": "WAIT", "reason": "S50: ข้อมูลไม่พอ"}
    if dt_bkk is None:
        return {"signal": "WAIT", "reason": "S50: ไม่มีเวลา"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S50: ATR ไม่ได้"}

    from datetime import datetime, time as dtime, timedelta
    ash, asm = map(int, _cfg(cfg, "ASIAN_RANGE_START").split(":"))
    aeh, aem = map(int, _cfg(cfg, "ASIAN_RANGE_END").split(":"))
    swh, swm = map(int, _cfg(cfg, "SWEEP_SESSION_START").split(":"))
    max_age_min = int(_cfg(cfg, "MAX_SWEEP_AGE_MIN"))

    today = dt_bkk.date()
    asian_start_dt = datetime.combine(today, dtime(ash, asm), tzinfo=dt_bkk.tzinfo)
    asian_end_dt = datetime.combine(today, dtime(aeh, aem), tzinfo=dt_bkk.tzinfo)
    sweep_start_dt = datetime.combine(today, dtime(swh, swm), tzinfo=dt_bkk.tzinfo)
    sweep_deadline = sweep_start_dt + timedelta(minutes=max_age_min)

    if dt_bkk < sweep_start_dt or dt_bkk > sweep_deadline:
        return {"signal": "WAIT", "reason": "S50: นอกช่วง Judas Swing window ของวันนี้"}

    asian_highs, asian_lows = [], []
    for i, bdt in enumerate(bar_dt_list):
        if bdt is None:
            continue
        if bdt.date() == today and asian_start_dt <= bdt < asian_end_dt:
            asian_highs.append(float(closed[i]["high"]))
            asian_lows.append(float(closed[i]["low"]))
    if not asian_highs:
        return {"signal": "WAIT", "reason": "S50: ไม่มีแท่งใน Asian range ของวันนี้"}

    asian_high = max(asian_highs)
    asian_low = min(asian_lows)
    min_range = float(_cfg(cfg, "MIN_RANGE_ATR")) * atr
    if (asian_high - asian_low) < min_range:
        return {"signal": "WAIT", "reason": "S50: Asian range แคบเกินไป"}

    sig_bar = closed[-1]
    sh = float(sig_bar["high"]); sl_ = float(sig_bar["low"]); sc = float(sig_bar["close"])
    sweep_buf = float(_cfg(cfg, "SWEEP_ATR_MULT")) * atr

    direction = None
    sweep_extreme = None
    # sweep high แล้วปิดกลับเข้า Asian range -> bearish reversal (SELL)
    if sh >= asian_high + sweep_buf and asian_low < sc < asian_high:
        direction = "SELL"; sweep_extreme = sh
    # sweep low แล้วปิดกลับเข้า Asian range -> bullish reversal (BUY)
    elif sl_ <= asian_low - sweep_buf and asian_low < sc < asian_high:
        direction = "BUY"; sweep_extreme = sl_
    if direction is None:
        return {"signal": "WAIT", "reason": "S50: ไม่มี Judas Swing sweep+reversal"}

    entry = round(sc, 2)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr
    if direction == "BUY":
        sl = round(sweep_extreme - sl_buf, 2)
    else:
        sl = round(sweep_extreme + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S50: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S50: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S50: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S50: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S50: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S50: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 50 JudasSwing+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"Asian range=[{asian_low:.2f},{asian_high:.2f}] sweep={sweep_extreme:.2f}\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }
