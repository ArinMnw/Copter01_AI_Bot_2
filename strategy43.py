"""
strategy43.py — S43 Turtle Trading (Donchian channel breakout, trend-following), RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

แนวคิด Turtle Trading (Dennis/Eckhardt classic): เข้า breakout ของ Donchian channel —
BUY เมื่อราคาทะลุ highest-high ของ DONCHIAN_ENTRY_BARS แท่งก่อนหน้า, SELL เมื่อทะลุ lowest-low
เป็น pure trend-following breakout (ตรงข้ามกับ S37/S38 ที่ fade เข้าหา level) ต่างจาก S34
(volume-breakout) ตรงที่ไม่ต้องการ volume surge และใช้ lookback ยาวกว่า (Donchian 20-60 แท่ง)

หมายเหตุการ adapt: Turtle ดั้งเดิม exit ด้วย Donchian channel ฝั่งตรงข้าม (trailing) + pyramiding
+ position sizing แบบ N-unit — แต่ engine backtest ของชุดนี้ใช้ SL/TP คงที่ จึง adapt เป็น
ATR-stop (2N) + RR-based TP ที่ตั้งให้ RR ใหญ่ขึ้น (let winners run) แทน trailing — บันทึกไว้
ใน create_s43.md ว่าเป็นการ adapt เพื่อเข้ากับ framework
"""

S43_DEFAULTS = {
    "ENTRY_TF": "M5",
    "DONCHIAN_ENTRY_BARS": 40,     # lookback ของ Donchian channel (จำนวนแท่งก่อนหน้า)
    "MIN_BREAK_ATR": 0.05,         # ต้อง break เลยขอบ channel >= mult x ATR (กัน marginal break)
    "SL_ATR_MULT": 2.0,            # Turtle ดั้งเดิมใช้ 2N = 2 x ATR
    "TP_RR": 2.0,                  # RR ใหญ่ขึ้นเพื่อ let winners run (adapt จาก trailing exit)
    "MAX_RISK_ATR_MULT": 6.0,
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
    return S43_DEFAULTS[key]


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


def detect_s43(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    n_entry = int(_cfg(cfg, "DONCHIAN_ENTRY_BARS"))
    need = n_entry + 20
    if rates is None or len(rates) < min(need, 60):
        return {"signal": "WAIT", "reason": "S43: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S43: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S43: ATR ไม่ได้"}

    sig_bar = closed[-1]
    sc = float(sig_bar["close"])
    # Donchian channel ของ n_entry แท่งก่อนหน้าแท่ง signal (ไม่รวมแท่ง signal)
    channel = closed[-(n_entry + 1):-1]
    if len(channel) < n_entry:
        return {"signal": "WAIT", "reason": "S43: channel ไม่ครบ"}
    ch_high = max(float(b["high"]) for b in channel)
    ch_low = min(float(b["low"]) for b in channel)
    break_buf = float(_cfg(cfg, "MIN_BREAK_ATR")) * atr

    direction = None
    if sc >= ch_high + break_buf:
        direction = "BUY"
    elif sc <= ch_low - break_buf:
        direction = "SELL"
    if direction is None:
        return {"signal": "WAIT", "reason": "S43: ไม่มี Donchian breakout"}

    entry = round(sc, 2)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr
    if direction == "BUY":
        sl = round(entry - sl_buf, 2)
    else:
        sl = round(entry + sl_buf, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S43: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S43: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S43: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S43: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S43: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S43: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 43 Turtle_Donchian+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"Donchian({n_entry}) breakout ch=[{ch_low:.2f},{ch_high:.2f}]\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_43(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s43(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
