"""
strategy42.py — S42 CRT (Candle Range Theory) — sweep+reversal of a range block, RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live
(แยกจาก strategy10.py เดิมที่ใช้ CRT อยู่แล้วใน live bot S1-S20 — ไฟล์นี้คือ research ใหม่ใน
เฟรมเวิร์ก S30+)

แนวคิด CRT (Candle Range Theory / Power-of-3 accumulation-manipulation-distribution):
1) "range block" = high/low ของกลุ่มแท่ง RANGE_BARS แท่ง (โซน accumulation)
2) "manipulation" = แท่งถัดมา sweep ทะลุ high หรือ low ของ range >= SWEEP_ATR_MULT x ATR (ล่าstop/
   liquidity grab) แล้ว **ปิดกลับเข้ามาในโซน range** (false breakout)
3) "distribution" = เข้า reversal ทิศตรงข้าม sweep (sweep high -> SELL, sweep low -> BUY)
   ตั้ง SL เลยจุด sweep, TP ตาม RR — ต่างจาก S25 (sweep ของ swing pivot จุดเดียว) ตรงที่ใช้
   "โซน range block + ปิดกลับเข้าโซน" เป็นเงื่อนไขยืนยัน false-breakout
"""

S42_DEFAULTS = {
    "ENTRY_TF": "M5",
    "RANGE_BARS": 6,               # จำนวนแท่งที่ใช้นิยาม range block (โซน accumulation)
    "SWEEP_ATR_MULT": 0.25,        # แท่ง manipulation ต้อง sweep เลยขอบ range >= mult x ATR
    "MIN_RANGE_ATR": 1.0,          # range block ต้องกว้าง >= mult x ATR (กัน range เล็กเกินไป/noise)
    "MAX_SETUP_AGE_BARS": 3,       # ต้องเข้าภายใน N แท่งหลัง manipulation
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
    return S42_DEFAULTS[key]


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


def _find_crt_setup(closed_rates, atr, cfg):
    """
    หา sweep+reversal ล่าสุด: range block = [i-range_bars .. i-1], แท่ง manipulation ที่ index >= i
    sweep ทะลุขอบ range แล้วปิดกลับเข้าโซน — สแกนถอยหลังจากท้ายสุด
    คืน (direction, range_high, range_low, sweep_extreme, setup_idx) หรือ None
    """
    range_bars = int(_cfg(cfg, "RANGE_BARS"))
    sweep_buf = float(_cfg(cfg, "SWEEP_ATR_MULT")) * atr
    min_range = float(_cfg(cfg, "MIN_RANGE_ATR")) * atr
    max_age = int(_cfg(cfg, "MAX_SETUP_AGE_BARS"))
    n = len(closed_rates)
    # manipulation bar m ต้องอยู่ใน [n-1-max_age .. n-1]
    earliest_m = max(range_bars, n - 1 - max_age)

    for m in range(n - 1, earliest_m - 1, -1):
        block = closed_rates[m - range_bars:m]
        if len(block) < range_bars:
            continue
        range_high = max(float(b["high"]) for b in block)
        range_low = min(float(b["low"]) for b in block)
        if (range_high - range_low) < min_range:
            continue

        mb = closed_rates[m]
        mh = float(mb["high"]); ml = float(mb["low"]); mc = float(mb["close"])

        # sweep high แล้วปิดกลับเข้าโซน -> bearish reversal (SELL)
        if mh >= range_high + sweep_buf and mc < range_high and mc > range_low:
            return ("SELL", range_high, range_low, mh, m)
        # sweep low แล้วปิดกลับเข้าโซน -> bullish reversal (BUY)
        if ml <= range_low - sweep_buf and mc > range_low and mc < range_high:
            return ("BUY", range_high, range_low, ml, m)
    return None


def detect_s42(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    range_bars = int(_cfg(cfg, "RANGE_BARS"))
    need = range_bars + 30
    if rates is None or len(rates) < min(need, 50):
        return {"signal": "WAIT", "reason": "S42: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S42: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S42: ATR ไม่ได้"}

    setup = _find_crt_setup(closed, atr, cfg)
    if setup is None:
        return {"signal": "WAIT", "reason": "S42: ไม่พบ CRT sweep+reversal"}
    direction, range_high, range_low, sweep_extreme, _ = setup

    cur = closed[-1]
    cc = float(cur["close"])
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr

    # ราคาแท่งล่าสุดต้องยังอยู่ในโซน range (ยังไม่ฝ่าทะลุไปแล้ว)
    if direction == "SELL":
        if not (range_low < cc < range_high):
            return {"signal": "WAIT", "reason": "S42: ราคาออกนอกโซนแล้ว (SELL)"}
        entry = round(cc, 2)
        sl = round(sweep_extreme + sl_buf, 2)
    else:
        if not (range_low < cc < range_high):
            return {"signal": "WAIT", "reason": "S42: ราคาออกนอกโซนแล้ว (BUY)"}
        entry = round(cc, 2)
        sl = round(sweep_extreme - sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S42: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S42: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S42: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S42: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S42: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S42: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 42 CRT_sweep+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"CRT range=[{range_low:.2f},{range_high:.2f}] sweep@{sweep_extreme:.2f}\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_42(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s42(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
