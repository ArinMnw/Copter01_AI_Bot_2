"""
strategy44.py — S44 Volume Profile (POC/VAH/VAL bounce), RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด Volume Profile: สร้าง histogram ของ volume ตามระดับราคา (ใช้ tick_volume เพราะ XAUUSD CFD
ไม่มี real_volume เหมือน S34) ย้อนหลัง LOOKBACK_BARS แท่ง แบ่งราคาเป็น bucket ขนาด BUCKET_ATR_MULT
x ATR หา **POC** (Point of Control = bucket ที่มี volume สูงสุด) แล้วขยายออกจาก POC จนได้
**Value Area** (VAH/VAL) ที่ครอบคลุม VALUE_AREA_PCT ของ volume ทั้งหมด (มาตรฐาน 70%)

เข้า BUY เมื่อราคาย้อนกลับมาแตะ VAL หรือ POC จากด้านบนแล้ว reject กลับขึ้น (high-volume node =
แนวรับ/ต้านที่แข็งแรงเพราะมีคนเทรดเยอะ) เข้า SELL ที่ VAH/POC จากด้านล่าง — continuation ตามทิศ
htf_trend (คล้าย S37 แต่ระดับมาจาก volume profile ไม่ใช่ fractal pivot)
"""

S44_DEFAULTS = {
    "ENTRY_TF": "M5",
    "LOOKBACK_BARS": 80,           # สร้าง volume profile ย้อนหลัง N แท่ง
    "BUCKET_ATR_MULT": 0.2,        # ขนาด bucket ราคา = mult x ATR
    "VALUE_AREA_PCT": 0.70,        # ครอบคลุม 70% ของ volume รอบ POC (มาตรฐาน)
    "TOUCH_ATR_MULT": 0.3,         # ราคาต้องแตะใกล้ระดับภายใน mult x ATR
    "REJECT_ATR_MULT": 0.15,       # ต้องปิดถอยห่างจากระดับ >= mult x ATR
    "SL_ATR_MULT": 1.0,
    "TP_RR": 1.5,
    "MAX_RISK_ATR_MULT": 5.0,
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
    return S44_DEFAULTS[key]


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


def _build_volume_profile(rates, atr, cfg):
    """
    สร้าง volume histogram ตาม price bucket แล้วหา POC/VAH/VAL
    คืน (poc_price, vah, val) หรือ None
    """
    bucket_size = float(_cfg(cfg, "BUCKET_ATR_MULT")) * atr
    if bucket_size <= 0:
        return None
    hist = {}
    for r in rates:
        vol = float(r["tick_volume"])
        if vol <= 0:
            continue
        lo_b = int(float(r["low"]) / bucket_size)
        hi_b = int(float(r["high"]) / bucket_size)
        span = max(1, hi_b - lo_b + 1)
        per_bucket_vol = vol / span
        for b in range(lo_b, hi_b + 1):
            hist[b] = hist.get(b, 0.0) + per_bucket_vol
    if not hist:
        return None

    total_vol = sum(hist.values())
    poc_bucket = max(hist, key=hist.get)
    poc_price = (poc_bucket + 0.5) * bucket_size

    target = total_vol * float(_cfg(cfg, "VALUE_AREA_PCT"))
    covered = hist[poc_bucket]
    lo_b = hi_b = poc_bucket
    while covered < target:
        lo_cand = lo_b - 1
        hi_cand = hi_b + 1
        vol_lo = hist.get(lo_cand, 0.0)
        vol_hi = hist.get(hi_cand, 0.0)
        if vol_lo == 0.0 and vol_hi == 0.0:
            break
        if vol_lo >= vol_hi:
            lo_b = lo_cand
            covered += vol_lo
        else:
            hi_b = hi_cand
            covered += vol_hi
    val_price = lo_b * bucket_size
    vah_price = (hi_b + 1) * bucket_size
    return (poc_price, vah_price, val_price)


def detect_s44(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    lb = int(_cfg(cfg, "LOOKBACK_BARS"))
    need = lb + 20
    if rates is None or len(rates) < min(need, 60):
        return {"signal": "WAIT", "reason": "S44: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S44: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S44: ATR ไม่ได้"}

    profile_window = closed[-lb:]
    vp = _build_volume_profile(profile_window, atr, cfg)
    if vp is None:
        return {"signal": "WAIT", "reason": "S44: สร้าง volume profile ไม่ได้"}
    poc, vah, val = vp

    cur = closed[-1]
    cc = float(cur["close"]); ch = float(cur["high"]); cl = float(cur["low"])
    touch_buf = atr * float(_cfg(cfg, "TOUCH_ATR_MULT"))
    reject_buf = atr * float(_cfg(cfg, "REJECT_ATR_MULT"))

    direction = None
    level_hit = None
    for lvl in (val, poc):
        if cl <= lvl + touch_buf and cc >= lvl + reject_buf and cc > cl:
            direction = "BUY"; level_hit = lvl
            break
    if direction is None:
        for lvl in (vah, poc):
            if ch >= lvl - touch_buf and cc <= lvl - reject_buf and cc < ch:
                direction = "SELL"; level_hit = lvl
                break
    if direction is None:
        return {"signal": "WAIT", "reason": "S44: ไม่มี rejection ที่ระดับ volume profile"}

    entry = round(cc, 2)
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    if direction == "BUY":
        sl = round(min(level_hit, cl) - sl_buf, 2)
    else:
        sl = round(max(level_hit, ch) + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S44: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S44: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S44: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S44: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S44: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S44: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 44 VolProfile+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"VolProfile POC={poc:.2f} VAH={vah:.2f} VAL={val:.2f}\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_44(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s44(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
