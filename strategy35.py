"""
strategy35.py — S35 Mean-Reversion (deviation + RSI exhaustion) — 3rd diversification leg
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

เป้า: หากลไกที่ 3 มาเสริม blend (A=engulfing trend-follow จาก S30/S31, B=volume-breakout
momentum-follow จาก S34) — mean-reversion ทำกำไรตอนตลาด sideways/choppy ซึ่งเป็นจุดที่ A และ B
(ทั้งคู่เป็น "ตามทิศทาง") มักแพ้ คาดว่าจะ decorrelate กับทั้ง A และ B ได้ดี (ต้องเช็คด้วยโค้ดก่อนเชื่อ
ตามบทเรียนจาก S31 ที่ fake-blend เคย fool ได้)

Logic: ราคาเบี่ยงจาก SMA(period) เกิน N x stdev (แทน VWAP ของ S22 เดิม — SMA+stdev คำนวณง่ายกว่า
และไม่ต้อง reset รายวันแบบ VWAP) + RSI exhaustion (overbought สำหรับ fade-sell, oversold สำหรับ
fade-buy) เข้า MARKET กลับเข้าเส้นกลาง — **ไม่ใช้ htf_trend confirmation** (mean-reversion เป็น
contrarian โดยธรรมชาติ บังคับตาม trend จะขัดกับ idea หลัก) ใช้ regime filter อื่นแทน: ADX(entry-TF)
ต่ำ (ตลาด sideways) เป็นตัวกรองว่า "ควร fade" หรือไม่
"""

S35_DEFAULTS = {
    "ENTRY_TF": "M5",
    "SMA_PERIOD": 20,
    "DEV_STDEV_MULT": 2.0,
    "RSI_PERIOD": 14,
    "RSI_OVERBOUGHT": 70,
    "RSI_OVERSOLD": 30,
    "ADX_MAX_THRESHOLD": 25.0,   # fade เฉพาะตอน ADX ต่ำ (sideways) — 0 = ปิด filter นี้
    "SL_ATR_MULT": 1.0,
    "TP_RR": 1.0,
    "MAX_RISK_ATR_MULT": 4.0,
    "MIN_GAP_BARS": 2,
    "SESSION_FILTER": True,
    "SESSIONS": [("14:00", "23:00")],

    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.4,
    "COOLDOWN_TRADES": 10,
    "CONFIRMATION_TYPE": "none",  # ไม่ใช้ htf_trend (contrarian by design)
}


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S35_DEFAULTS[key]


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


def _adx_now(rates, period=14):
    """ADX ของแท่งสุดท้ายที่ปิดแล้ว (rates[:-1]) — ใช้กรอง regime sideways/trending"""
    closes_rates = rates[:-1]
    n = len(closes_rates)
    if n < period * 2 + 1:
        return 0.0
    highs = [float(r["high"]) for r in closes_rates]
    lows = [float(r["low"]) for r in closes_rates]
    closes = [float(r["close"]) for r in closes_rates]
    plus_dm = [0.0] * n; minus_dm = [0.0] * n; tr = [0.0] * n
    for i in range(1, n):
        up = highs[i] - highs[i - 1]; down = lows[i - 1] - lows[i]
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))

    def _ws(vals):
        sm = [0.0] * n
        sm[period] = sum(vals[1:period + 1])
        for i in range(period + 1, n):
            sm[i] = sm[i - 1] - sm[i - 1] / period + vals[i]
        return sm

    tr_sm = _ws(tr); pdm_sm = _ws(plus_dm); mdm_sm = _ws(minus_dm)
    dx = [0.0] * n
    for i in range(period, n):
        if tr_sm[i] <= 0:
            continue
        pdi = 100.0 * pdm_sm[i] / tr_sm[i]; mdi = 100.0 * mdm_sm[i] / tr_sm[i]
        denom = pdi + mdi
        dx[i] = 100.0 * abs(pdi - mdi) / denom if denom > 0 else 0.0
    start = period * 2
    if start >= n:
        return 0.0
    adx = sum(dx[period:start]) / period
    for i in range(start + 1, n):
        adx = (adx * (period - 1) + dx[i]) / period
    return adx


def _rsi_now(closes_list, period=14):
    if len(closes_list) < period + 1:
        return 50.0
    gains = []; losses = []
    for i in range(1, len(closes_list)):
        diff = closes_list[i] - closes_list[i - 1]
        gains.append(max(diff, 0.0)); losses.append(max(-diff, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


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


def detect_s35(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx=None):
    sma_p = int(_cfg(cfg, "SMA_PERIOD"))
    rsi_p = int(_cfg(cfg, "RSI_PERIOD"))
    need = max(sma_p, rsi_p) + 15
    if rates is None or len(rates) < need:
        return {"signal": "WAIT", "reason": f"S35: ข้อมูลไม่พอ (>= {need})"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S35: นอก session"}

    closed = rates[:-1]
    closes = [float(r["close"]) for r in closed]
    sma_window = closes[-sma_p:]
    sma = sum(sma_window) / len(sma_window)
    variance = sum((c - sma) ** 2 for c in sma_window) / len(sma_window)
    stdev = variance ** 0.5
    if stdev <= 0:
        return {"signal": "WAIT", "reason": "S35: stdev=0"}

    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S35: ATR ไม่ได้"}

    adx_max = float(_cfg(cfg, "ADX_MAX_THRESHOLD"))
    if adx_max > 0:
        adx = _adx_now(rates, 14)
        if adx > adx_max:
            return {"signal": "WAIT", "reason": f"S35: ADX={adx:.1f} เกิน {adx_max} (trending, ไม่ fade)"}

    b = closed[-1]
    bc = float(b["close"])
    dev_mult = float(_cfg(cfg, "DEV_STDEV_MULT"))
    upper = sma + dev_mult * stdev
    lower = sma - dev_mult * stdev

    rsi = _rsi_now(closes[-(rsi_p + 30):], rsi_p)
    rsi_ob = float(_cfg(cfg, "RSI_OVERBOUGHT"))
    rsi_os = float(_cfg(cfg, "RSI_OVERSOLD"))
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))

    direction = None; entry = None; sl = None; reason = None
    if bc >= upper and rsi >= rsi_ob:
        direction = "SELL"; entry = round(bc, 2)
        sl = round(max(float(b["high"]), upper) + sl_buf, 2)
        reason = f"Fade upper dev (sma={sma:.2f}, dev={dev_mult}xstd, RSI={rsi:.1f})"
    elif bc <= lower and rsi <= rsi_os:
        direction = "BUY"; entry = round(bc, 2)
        sl = round(min(float(b["low"]), lower) - sl_buf, 2)
        reason = f"Fade lower dev (sma={sma:.2f}, dev={dev_mult}xstd, RSI={rsi:.1f})"
    if direction is None:
        return {"signal": "WAIT", "reason": "S35: ยังไม่เบี่ยงพอ/RSI ไม่ exhaustion"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S35: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S35: risk ผิดปกติ"}

    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 35 mean_reversion {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"{reason}\nentry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
    }


def strategy_35(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s35(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
