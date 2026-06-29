"""
strategy34.py — S34 Volume-confirmed breakout (NEW entry mechanism, RESEARCH / BACKTEST-ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

ผู้ใช้ขอให้เปลี่ยน entry mechanism จาก price-action ล้วน (engulfing+EMA touch ของ S30/S31) ไปลอง
แกนใหม่: **volume/order-flow** เพราะ engulfing-family ขุดจนหมดแล้ว (S31-S33 ลอง 5 lever ไม่มีตัว
ไหนดีกว่า champion เดิม)

กลไกใหม่: **Volume-Confirmed Breakout** — ใช้ MT5 `tick_volume` (จำนวนการเปลี่ยนแปลงราคาต่อแท่ง,
proxy ของ order-flow/activity เพราะโบรกเกอร์ส่วนใหญ่ไม่มี real_volume สำหรับ CFD gold) เป็นตัวยืนยัน
breakout ของกรอบ N แท่งล่าสุด — ต่างจาก engulfing โดยสิ้นเชิง: engulfing คือ price-pattern ใกล้ EMA,
breakout+volume คือ structure-break ที่มี "แรงซื้อขาย" (volume spike) ยืนยัน ไม่สนใจ EMA เลย

ยัง lock confirmation = htf_trend(M15/EMA50) ไว้ (พิสูจน์แล้วว่ามี efficiency เป็นบวกตั้งแต่ S27)
และ DD_CONTROL = circuit_breaker (พิสูจน์แล้วว่าช่วย consistency ตั้งแต่ S29)
"""

S34_DEFAULTS = {
    "ENTRY_TF": "M5",
    "BREAKOUT_LOOKBACK": 12,       # N แท่งย้อนหลัง (ไม่รวมแท่ง signal) สำหรับหา recent high/low
    "VOLUME_SURGE_MULT": 1.5,      # tick_volume(แท่ง signal) >= mult x SMA(tick_volume, lookback)
    "VOLUME_SMA_PERIOD": 20,
    "MIN_BREAKOUT_ATR": 0.1,       # ระยะ breakout เกินกรอบเดิม >= mult x ATR (กัน noise breakout เล็กๆ)
    "SL_ATR_MULT": 1.2,            # locked จาก champion S30/S31 (ใช้ฐานเดียวกันก่อนค่อย grid)
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
    return S34_DEFAULTS[key]


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


def _detect_volume_breakout(rates, atr, cfg):
    """
    แท่งสุดท้าย (rates[-2], ปิดแล้ว) ต้อง:
      1. ปิดทะลุ high/low ของ N แท่งก่อนหน้า (ไม่รวมตัวเอง) เกิน MIN_BREAKOUT_ATR x ATR
      2. tick_volume >= VOLUME_SURGE_MULT x SMA(tick_volume, VOLUME_SMA_PERIOD) ของแท่งก่อนๆ
    """
    lookback = int(_cfg(cfg, "BREAKOUT_LOOKBACK"))
    vol_period = int(_cfg(cfg, "VOLUME_SMA_PERIOD"))
    need = max(lookback, vol_period) + 3
    if len(rates) < need + 1:
        return None

    sig = rates[-2]  # แท่งปิดแล้วล่าสุด = แท่ง breakout
    sig_close = float(sig["close"])
    sig_open = float(sig["open"])
    sig_vol = float(sig["tick_volume"])

    # กรอบ N แท่งก่อนแท่ง signal (ไม่รวม sig เอง)
    window = rates[-(lookback + 2):-2]
    if len(window) < lookback:
        return None
    recent_high = max(float(b["high"]) for b in window)
    recent_low = min(float(b["low"]) for b in window)

    # volume baseline จากแท่งก่อนแท่ง signal (ไม่รวม sig เอง กัน look-ahead/self-reference)
    vol_window = rates[-(vol_period + 2):-2]
    if len(vol_window) < vol_period:
        return None
    vol_sma = sum(float(b["tick_volume"]) for b in vol_window) / len(vol_window)
    if vol_sma <= 0:
        return None

    surge_mult = float(_cfg(cfg, "VOLUME_SURGE_MULT"))
    min_breakout = float(_cfg(cfg, "MIN_BREAKOUT_ATR")) * atr
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))

    volume_ok = sig_vol >= surge_mult * vol_sma
    if not volume_ok:
        return None

    if sig_close > recent_high + min_breakout and sig_close > sig_open:
        entry = round(sig_close, 2)
        sl = round(recent_high - sl_buf, 2)  # SL ใต้ระดับที่ breakout (กลายเป็นแนวรับใหม่)
        if sl >= entry:
            return None
        return ("BUY", entry, sl, f"Volume-confirmed breakout UP (vol={sig_vol:.0f} vs sma={vol_sma:.0f})")

    if sig_close < recent_low - min_breakout and sig_close < sig_open:
        entry = round(sig_close, 2)
        sl = round(recent_low + sl_buf, 2)
        if sl <= entry:
            return None
        return ("SELL", entry, sl, f"Volume-confirmed breakout DOWN (vol={sig_vol:.0f} vs sma={vol_sma:.0f})")

    return None


def detect_s34(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    lookback = int(_cfg(cfg, "BREAKOUT_LOOKBACK"))
    vol_period = int(_cfg(cfg, "VOLUME_SMA_PERIOD"))
    need = max(lookback, vol_period) + 12
    if rates is None or len(rates) < need:
        return {"signal": "WAIT", "reason": f"S34: ข้อมูลไม่พอ (>= {need})"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S34: นอก session"}
    atr = _calc_atr(rates[:-1], 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S34: ATR ไม่ได้"}

    sig = _detect_volume_breakout(rates, atr, cfg)
    if sig is None:
        return {"signal": "WAIT", "reason": "S34: ยังไม่พบ volume breakout"}
    direction, entry, sl, reason = sig

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S34: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S34: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S34: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S34: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S34: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S34: risk ผิดปกติ"}

    b = rates[-2]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 34 volume_breakout+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"{reason}\nentry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_34(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s34(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
