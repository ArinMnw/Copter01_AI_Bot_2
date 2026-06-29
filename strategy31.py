"""
strategy31.py — S31 Consistency-focused: wider-SL grid + portfolio blend (RESEARCH / BACKTEST-ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

ต่อยอดจาก S30 (ดู create_s30.md): champion เดิม (engulfing r1.0/SL0.8/RR1.0) ถูกแทนที่ด้วย
"wider_sl" (SL_ATR_MULT=1.2) ที่ขอผู้ใช้ทดสอบรอบล่าสุด — สม่ำเสมอกว่าจริง (max losing-day-streak
3-4 วัน vs 10 วันเดิม, sharpe-like 0.15-0.21 robust ทุก window) โดยเป้าหมายเปลี่ยนจาก "DD ต่ำสุด/
WR สูงสุด" เป็น **"กำไรต่อเนื่องสม่ำเสมอ"** (เมตริก: %วันบวก, max losing-day-streak, sharpe-like)

S31 ทดสอบ 2 lever ใหม่เพื่อความสม่ำเสมอ:
1. SL_ATR_MULT grid ที่กว้างกว่า S30 เดิม (1.0-2.5) — ดูว่าขยาย SL ต่อยังช่วยไหม หรือถึงจุดอิ่มตัว
2. PORTFOLIO_BLEND — รวม 2 sub-config ที่ไม่ relate กัน (SL/RR ต่างกัน) แบ่ง risk ครึ่งต่อครึ่ง
   ต่อวัน เพื่อให้ losing streak ของตัวหนึ่งไม่ตรงกับอีกตัว (ลด correlated drawdown / streak)

Entry mechanism เดียวกับ S30 (engulfing + htf_trend M15/EMA50 + circuit_breaker) — ไม่เปลี่ยน
pattern family เพราะ S30 พิสูจน์แล้วว่า family ความถี่สูงเจือจาง edge มากกว่าคุ้ม
"""

from strategy30 import (  # noqa: F401  (reuse S30 detectors — engulfing pattern เดียวกัน)
    S30_DEFAULTS, _calc_atr, _ema_series, _in_session, _ema_now,
    _detect_engulfing, _detect_strong_close, _detect_family, _PATTERN_DETECTORS,
)

S31_DEFAULTS = dict(S30_DEFAULTS)
S31_DEFAULTS.update({
    "ENTRY_PATTERN": "engulfing",
    "ENGULF_MIN_RATIO": 1.0,
    "SL_ATR_MULT": 1.2,        # locked จากผลทดสอบ "wider_sl" ของผู้ใช้รอบก่อน
    "TP_RR": 1.0,
    "MIN_GAP_BARS": 1,
    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "COOLDOWN_TRADES": 10,
    "CONFIRMATION_TYPE": "htf_trend",
    "HTF_TF": "M15",
    "HTF_EMA_PERIOD": 50,
})


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S31_DEFAULTS[key]


def detect_s31(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    """Pure detection เหมือน S30 detect_s30 — ใช้ S31_DEFAULTS เป็น fallback"""
    ema_fast_p = int(_cfg(cfg, "EMA_FAST"))
    need = ema_fast_p + 12
    if rates is None or len(rates) < need:
        return {"signal": "WAIT", "reason": f"S31: ข้อมูลไม่พอ (>= {need})"}
    if not _in_session(dt_bkk, cfg or S31_DEFAULTS):
        return {"signal": "WAIT", "reason": "S31: นอก session"}
    atr = _calc_atr(rates[:-1], 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S31: ATR ไม่ได้"}
    ema_now = _ema_now(rates, cfg or S31_DEFAULTS)
    if ema_now is None:
        return {"signal": "WAIT", "reason": "S31: EMA ไม่ได้"}

    pattern = _cfg(cfg, "ENTRY_PATTERN")
    detector = _PATTERN_DETECTORS.get(pattern)
    if detector is None:
        return {"signal": "WAIT", "reason": f"S31: pattern ไม่รู้จัก ({pattern})"}
    eff_cfg = cfg if cfg else S31_DEFAULTS
    sig = detector(rates, atr, ema_now, eff_cfg)
    if sig is None:
        return {"signal": "WAIT", "reason": f"S31: ยังไม่พบสัญญาณ ({pattern})"}

    direction, entry, sl, reason = sig

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S31: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S31: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S31: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S31: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S31: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S31: risk ผิดปกติ"}

    b = rates[-2]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 31 {pattern}+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"{reason}\nentry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "entry_pattern": pattern, "confirmation_type": conf_type,
    }


def strategy_31(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s31(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
