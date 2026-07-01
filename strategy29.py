"""
strategy29.py — S29 Entry-quality upgrade + DD control บนฐาน S27 locked config (RESEARCH / BACKTEST-ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py / trailing.py / main.py
   ไม่มี config.active_strategies[29], ไม่มี wiring เข้า live trading ใดๆ
   ใช้คู่กับ sim_s29_backtest.py / optimize_s29.py เพื่อ backtest เท่านั้น

ต่อยอดตรงจาก S27 (ดู create_s27.md): S27 พบ edge บวกที่ robust จริง (PF~1.02-1.03,
avgR~+0.025 ถึง +0.030) ด้วย locked config: M5 entry + htf_trend confirmation (M15/EMA50),
SL=0.8xATR, RR=1.0 — แต่ entry mechanism ("EMA-fast pullback bounce") ตั้งใจทำหยาบเพื่อแยกผล
ของ HTF confirmation ล้วนๆ และ maxDD สูงผิดปกติ (75-79% ที่ risk แค่ 1%)

S29 แก้ 2 ปัญหานี้พร้อมกันโดย **lock htf_trend confirmation (M15/EMA50) ไว้เป็นฐานเดิม**:

1. ยกระดับ entry mechanism (lever ใหม่ `ENTRY_PATTERN`) จาก EMA-bounce หยาบ เป็น:
   - "ema_bounce"  : ท่าเดิมของ S27 (baseline เทียบ)
   - "engulfing"   : engulfing candle (body แท่งปัจจุบันกลืนแท่งก่อน) ใกล้ EMA
   - "pinbar"      : pin bar (wick ยาว/body เล็ก) ปฏิเสธราคาใกล้ EMA
   - "confluence"  : multi-bar confluence (N แท่งทิศทางเดียวกันต่อเนื่องหลัง touch EMA)

2. ลด maxDD ด้วย lever ใหม่ `DD_CONTROL` (ทำงานบนลำดับเวลาจริงของ trade stream ใน
   sim_s29_backtest.simulate_equity_v2):
   - "none"           : risk% คงที่ (baseline เทียบ, ปรับ RISK_PCT พื้นฐานลงได้)
   - "dynamic_risk"    : ลด risk% ลงเป็น REDUCED_RISK_PCT เมื่อแพ้ติดกัน >= CONSEC_LOSS_TRIGGER
                         ไม้ แล้วคืนกลับเป็น RISK_PCT เดิมทันทีที่ชนะ 1 ไม้
   - "circuit_breaker" : พักการเทรด (ข้าม) COOLDOWN_TRADES ไม้ถัดไป เมื่อแพ้ติดกัน
                         >= CONSEC_LOSS_TRIGGER ไม้ (จำลอง "หยุดเทรดชั่วคราวหลังแพ้ติดกัน N ไม้")

Entry/Exit อื่นเหมือน S27 ทุกประการ (entry MARKET ที่ open แท่งถัดจาก signal, SL ผ่าน buffer
ATR, TP = entry +- TP_RR*risk, HTF lookup กัน look-ahead ข้าม timeframe ด้วย bisect บนเวลาปิดแท่ง)
"""

S29_DEFAULTS = {
    "ENTRY_TF": "M5",                 # locked จาก S27 (M5 ดีกว่า M1 ในกลุ่ม htf_trend)
    "ENTRY_PATTERN": "ema_bounce",    # "ema_bounce" | "engulfing" | "pinbar" | "confluence"
    "EMA_FAST": 8,
    "PULLBACK_TOUCH_ATR": 0.15,
    "ENGULF_MIN_RATIO": 1.3,          # body แท่งปัจจุบัน >= ratio x body แท่งก่อน
    "PINBAR_WICK_RATIO": 2.5,         # wick ยาว >= ratio x body
    "CONFLUENCE_BARS": 2,             # จำนวนแท่งทิศทางเดียวกันต่อเนื่องหลัง touch EMA
    "SL_ATR_MULT": 0.8,               # locked จาก S27
    "TP_RR": 1.0,                     # locked จาก S27 (เปิดกริดทดสอบรอบ entry quality ด้วย)
    "MAX_RISK_ATR_MULT": 4.0,
    "SESSION_FILTER": True,
    "SESSIONS": [("14:00", "23:00")],  # locked จาก S27

    "RISK_PCT": 1.0,                  # base risk% (DD_CONTROL ปรับลดจากค่านี้ตามเงื่อนไข)
    "DD_CONTROL": "none",             # "none" | "dynamic_risk" | "circuit_breaker"
    "CONSEC_LOSS_TRIGGER": 4,
    "REDUCED_RISK_PCT": 0.4,
    "COOLDOWN_TRADES": 6,

    "CONFIRMATION_TYPE": "htf_trend",  # locked จาก S27 — ไม่ grid type อื่นซ้ำ (S27 พิสูจน์แล้ว)
    "HTF_TF": "M15",                   # locked จาก S27
    "HTF_EMA_PERIOD": 50,              # locked จาก S27
    "HTF_SLOPE_BARS": 5,
    "ADX_PERIOD": 14,
    "ADX_MIN_THRESHOLD": 0.0,
}

_TF_SECS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S29_DEFAULTS[key]


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


def _detect_ema_bounce(rates, atr, cfg):
    """ท่าเดิมของ S27 (baseline เทียบ): แตะ/ทะลุ EMA เบาๆ แล้วปิดแท่งเด้งกลับ"""
    ema_now = _ema_now(rates, cfg)
    if ema_now is None:
        return None
    b = rates[-2]
    bo, bh, bl, bc = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
    touch_buf = float(_cfg(cfg, "PULLBACK_TOUCH_ATR")) * atr
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))

    if bl <= ema_now + touch_buf and bc > bo and bc > ema_now:
        entry = round(bc, 2)
        sl = round(min(bl, ema_now) - sl_buf, 2)
        return ("BUY", entry, sl, f"EMA pullback bounce BUY @ {ema_now:.2f}")
    if bh >= ema_now - touch_buf and bc < bo and bc < ema_now:
        entry = round(bc, 2)
        sl = round(max(bh, ema_now) + sl_buf, 2)
        return ("SELL", entry, sl, f"EMA pullback bounce SELL @ {ema_now:.2f}")
    return None


def _detect_engulfing(rates, atr, cfg):
    """Engulfing candle ใกล้ EMA — แท่งปัจจุบัน body กลืนแท่งก่อนหน้า + ทิศทางพลิกกลับ"""
    ema_now = _ema_now(rates, cfg)
    if ema_now is None or len(rates) < 4:
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


def _detect_pinbar(rates, atr, cfg):
    """Pin bar (wick ยาว/body เล็ก) ปฏิเสธราคาใกล้ EMA"""
    ema_now = _ema_now(rates, cfg)
    if ema_now is None:
        return None
    b = rates[-2]
    bo, bh, bl, bc = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
    body = abs(bc - bo)
    body_floor = max(body, atr * 0.02)
    upper_wick = bh - max(bo, bc)
    lower_wick = min(bo, bc) - bl
    wick_ratio = float(_cfg(cfg, "PINBAR_WICK_RATIO"))
    touch_buf = float(_cfg(cfg, "PULLBACK_TOUCH_ATR")) * atr
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))

    if lower_wick >= wick_ratio * body_floor and bc >= bo and bl <= ema_now + touch_buf:
        entry = round(bc, 2)
        sl = round(min(bl, ema_now) - sl_buf, 2)
        return ("BUY", entry, sl, f"Bullish pin bar near EMA @ {ema_now:.2f}")

    if upper_wick >= wick_ratio * body_floor and bc <= bo and bh >= ema_now - touch_buf:
        entry = round(bc, 2)
        sl = round(max(bh, ema_now) + sl_buf, 2)
        return ("SELL", entry, sl, f"Bearish pin bar near EMA @ {ema_now:.2f}")

    return None


def _detect_confluence(rates, atr, cfg):
    """Multi-bar confluence: N แท่งทิศทางเดียวกันต่อเนื่อง โดยแท่งแรกของกลุ่ม touch EMA"""
    n_bars = int(_cfg(cfg, "CONFLUENCE_BARS"))
    ema_now = _ema_now(rates, cfg)
    if ema_now is None or len(rates) < n_bars + 3:
        return None
    group = rates[-(n_bars + 1):-1]  # n_bars แท่งปิดแล้วล่าสุด เรียงเก่า->ใหม่
    if len(group) < n_bars:
        return None
    touch_buf = float(_cfg(cfg, "PULLBACK_TOUCH_ATR")) * atr
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    first = group[0]
    last = group[-1]
    fo, fh, fl, fc = float(first["open"]), float(first["high"]), float(first["low"]), float(first["close"])
    lc = float(last["close"])

    all_bull = all(float(g["close"]) > float(g["open"]) for g in group)
    all_bear = all(float(g["close"]) < float(g["open"]) for g in group)

    if all_bull and fl <= ema_now + touch_buf and lc > ema_now:
        lows = [float(g["low"]) for g in group]
        entry = round(lc, 2)
        sl = round(min(min(lows), ema_now) - sl_buf, 2)
        return ("BUY", entry, sl, f"{n_bars}-bar bullish confluence after EMA touch @ {ema_now:.2f}")

    if all_bear and fh >= ema_now - touch_buf and lc < ema_now:
        highs = [float(g["high"]) for g in group]
        entry = round(lc, 2)
        sl = round(max(max(highs), ema_now) + sl_buf, 2)
        return ("SELL", entry, sl, f"{n_bars}-bar bearish confluence after EMA touch @ {ema_now:.2f}")

    return None


_PATTERN_DETECTORS = {
    "ema_bounce": _detect_ema_bounce,
    "engulfing": _detect_engulfing,
    "pinbar": _detect_pinbar,
    "confluence": _detect_confluence,
}


def detect_s29(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    """
    Pure detection (backtest เรียกตรง)
    rates: แท่งสุดท้าย = แท่งกำลังวิ่ง (รู้แค่ open), rates[-2] = แท่งปิดแล้วล่าสุด
    htf_ctx: dict ของค่า HTF ที่คำนวณไว้ล่วงหน้า (จาก sim_s29_backtest._htf_lookup) กัน look-ahead
    คืน dict {signal: BUY/SELL/WAIT, ...}
    """
    ema_fast_p = int(_cfg(cfg, "EMA_FAST"))
    confluence_bars = int(_cfg(cfg, "CONFLUENCE_BARS"))
    need = ema_fast_p + 10 + confluence_bars
    if rates is None or len(rates) < need:
        return {"signal": "WAIT", "reason": f"S29: ข้อมูลไม่พอ (ต้องการ >= {need} แท่ง)"}

    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S29: อยู่นอกช่วง session filter"}

    atr = _calc_atr(rates[:-1], 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S29: คำนวณ ATR ไม่ได้"}

    pattern = _cfg(cfg, "ENTRY_PATTERN")
    detector = _PATTERN_DETECTORS.get(pattern)
    if detector is None:
        return {"signal": "WAIT", "reason": f"S29: ENTRY_PATTERN ไม่รู้จัก ({pattern})"}

    sig = detector(rates, atr, cfg)
    if sig is None:
        return {"signal": "WAIT", "reason": f"S29: ยังไม่พบสัญญาณ ({pattern})"}

    direction, entry, sl, reason = sig

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S29: ไม่มี HTF context สำหรับ confirmation"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S29: ADX(HTF) ไม่ผ่าน threshold"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S29: HTF trend ไม่ขึ้น (BUY ถูกบล็อก)"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S29: HTF trend ไม่ลง (SELL ถูกบล็อก)"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))

    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S29: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S29: risk ผิดปกติ"}

    b = rates[-2]
    return {
        "signal": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 29 {pattern}+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"{reason}\nentry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market",
        "entry_label": f"{direction} MARKET (S29 {pattern}+{conf_type})",
        "signal_bar_time": int(b["time"]),
        "atr_at_signal": atr,
        "entry_pattern": pattern,
        "confirmation_type": conf_type,
    }


def strategy_29(rates, tf: str = "", cfg: dict | None = None):
    """
    Wrapper runtime-style เก็บไว้เผื่ออนาคต
    ⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียกฟังก์ชันนี้ — standalone จริง
    """
    return detect_s29(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
