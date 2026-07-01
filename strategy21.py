"""
strategy21.py — S21 Confluence Breakout-Retest (RESEARCH / BACKTEST-ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py / trailing.py / main.py
   ไม่มี config.active_strategies[21], ไม่มี wiring เข้า live trading ใดๆ
   ใช้คู่กับ sim_s21_backtest.py เพื่อ backtest เท่านั้น จนกว่าจะมีคำสั่งแยกให้ wire เข้าระบบจริง

แนวคิด (สังเคราะห์จากกลยุทธ์ XAUUSD ที่นิยมทั่วโลก):
  1. Trend-following: EMA(S21_EMA_TREND) slope เป็น HTF bias (กรองทิศทาง)
  2. Breakout (price action): แท่งปิดทะลุ high/low ของกรอบ lookback ด้วย body
     แข็งแรง (>= S21_BREAKOUT_MIN_BODY_PCT ของ range แท่ง) — ยืนยัน momentum จริง
     ไม่ใช่ wick ปลอม
  3. Retest entry: รอราคาย่อกลับมาทดสอบระดับที่ breakout (เดิมเป็นแนวต้าน/รับ
     กลายเป็นแนวรับ/ต้านใหม่) ก่อนเข้า — ลด risk จากการไล่ราคาที่จุด breakout ตรง
  4. Momentum filter (RSI): กรอง breakout ที่ extreme เกินไปแล้ว (RSI ใกล้ 100/0)
     ออก เพื่อเลี่ยงไล่ซื้อ/ขายตอน exhaustion
  5. Session filter: เทรดเฉพาะ London/NY killzone (BKK 14-18, 19-23) ตาม
     concept session-based ที่ volatility/liquidity สูงสุดของ XAUUSD
  6. News filter: ออกแบบ hook ไว้ (S21_NEWS_FILTER) แต่ **backtest ไม่มีข้อมูล
     ปฏิทินข่าวย้อนหลังในระบบ** จึงไม่ replay จริง — เป็นข้อจำกัดที่ต้องรายงาน

Entry/Exit:
  - Entry: LIMIT รอ retrace กลับมาที่ระดับ breakout (+ buffer เล็กน้อย)
           ไม่ fill ใน S21_LIMIT_CANCEL_BARS แท่ง → cancel
  - SL   : อีกฝั่งของระดับ breakout ∓ S21_SL_ATR_MULT × ATR (กัน structure invalidate)
  - TP   : entry ± S21_TP_RR × risk (RR กำหนดได้ผ่าน S21_TP_RR)
  - Position sizing: risk-based ตาม % equity ต่อไม้ (S21_RISK_PCT) ไม่ fix lot
    ดู sim_s21_backtest.py สำหรับการคำนวณ lot และ compounding equity

ไม่มีผลกำไร/ขาดทุนใดๆ ในไฟล์นี้ที่เป็นการอ้างลอย — ทุกตัวเลขต้องมาจาก
sim_s21_backtest.py รันจริงกับข้อมูล MT5 เท่านั้น (ดู s21_backtest_summary.csv)
"""

from datetime import time

from mt5_utils import calc_atr

# ── ค่าเริ่มต้นของ S21 (เก็บในไฟล์นี้เอง — ไม่แตะ config.py) ─────────
S21_DEFAULTS = {
    "LOOKBACK": 40,                 # bars ของกรอบหา breakout level
    "EMA_TREND": 50,                # EMA period สำหรับ HTF bias
    "EMA_SLOPE_BARS": 10,           # ย้อนกี่แท่งเพื่อวัด slope
    "RSI_PERIOD": 14,
    "RSI_MIN_FOR_BUY": 45.0,        # momentum confirm (ไม่ใช่ dip อ่อนแรง)
    "RSI_MAX_FOR_BUY": 80.0,        # กัน exhaustion (RSI สูงเกินไปแล้ว)
    "RSI_MAX_FOR_SELL": 55.0,
    "RSI_MIN_FOR_SELL": 20.0,
    "BREAKOUT_MIN_BODY_PCT": 0.55,  # body ของแท่ง breakout >= % ของ range
    "RETEST_ATR_BUFFER": 0.15,      # entry = breakout level +/- buffer*ATR
    "SL_ATR_MULT": 1.0,
    "TP_RR": 0.3,                   # validated via sim_s21_backtest.py 60d/90d: WR~86% RR=0.3
    "LIMIT_CANCEL_BARS": 6,
    "SESSION_FILTER": True,
    "SESSIONS": [("14:00", "18:00"), ("19:00", "23:00")],  # London/NY BKK
    "NEWS_FILTER": False,           # hook only — ไม่มีข้อมูลปฏิทินใน backtest
    "RISK_PCT": 1.5,                # % ของ equity ต่อไม้ (ใช้ใน backtest sizing) — สมดุล
                                     # ระหว่าง return ($/day) กับ max drawdown ที่ยอมรับได้
    "MAX_RISK_ATR_MULT": 3.0,       # guard ป้องกัน risk ห่างผิดปกติ
}

_TF_SECS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}

# ── dedup state (in-memory เท่านั้น — ไฟล์นี้ไม่ถูกเรียกจาก runtime จริง) ──
_s21_last_fire: dict = {}
_s21_level_fired: dict = {}


def _cfg(cfg: dict | None, key: str):
    if cfg and key in cfg:
        return cfg[key]
    return S21_DEFAULTS[key]


def _calc_rsi(rates, period=14):
    """RSI Wilder's smoothing — เหมือน strategy15/strategy17"""
    if len(rates) < period + 1:
        return None
    closes = [float(r["close"]) for r in rates[-(period * 3):]]
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    if len(gains) < period:
        return None
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def _ema_slope(closes, period, slope_bars):
    """คืน (ema_now, ema_now>ema_prev, ema_now<ema_prev) — ใช้วัด trend bias"""
    if len(closes) < period + slope_bars:
        return None, True, True
    k = 2.0 / (period + 1.0)
    ema = closes[0]
    hist = []
    for c in closes:
        ema = c * k + ema * (1.0 - k)
        hist.append(ema)
    ema_now = hist[-1]
    ema_prev = hist[-1 - slope_bars]
    return ema_now, ema_now > ema_prev, ema_now < ema_prev


def _in_session(dt_bkk, cfg):
    if not _cfg(cfg, "SESSION_FILTER"):
        return True
    if dt_bkk is None:
        return True
    cur = dt_bkk.time()
    for start_str, end_str in _cfg(cfg, "SESSIONS"):
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        if time(sh, sm) <= cur < time(eh, em):
            return True
    return False


def detect_s21(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    """
    Pure detection (backtest เรียกตรง) — ไม่แตะ dedup state
    rates: แท่งสุดท้าย = แท่งกำลังวิ่ง (รู้แค่ open), rates[-2] = แท่ง breakout (ปิดแล้ว)
    คืน dict {signal: BUY/SELL/WAIT, ...}
    """
    lookback = int(_cfg(cfg, "LOOKBACK"))
    ema_period = int(_cfg(cfg, "EMA_TREND"))
    slope_bars = int(_cfg(cfg, "EMA_SLOPE_BARS"))
    need = lookback + max(ema_period + slope_bars, 30) + 3
    if rates is None or len(rates) < need:
        return {"signal": "WAIT", "reason": f"S21: ข้อมูลไม่พอ (ต้องการ >= {need} แท่ง)"}

    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S21: อยู่นอกช่วง Killzones London/NY"}

    b = rates[-2]                       # แท่ง breakout (ปิดแล้ว)
    window = rates[-(lookback + 2):-2]  # กรอบก่อนแท่ง breakout
    range_high = max(float(r["high"]) for r in window)
    range_low = min(float(r["low"]) for r in window)
    rng = range_high - range_low
    if rng <= 0:
        return {"signal": "WAIT", "reason": "S21: กรอบ lookback แบนผิดปกติ"}

    bo, bh, bl, bc = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
    bar_range = bh - bl
    if bar_range <= 0:
        return {"signal": "WAIT", "reason": "S21: แท่ง breakout ไม่มี range"}

    body_pct = abs(bc - bo) / bar_range
    min_body = float(_cfg(cfg, "BREAKOUT_MIN_BODY_PCT"))

    atr = calc_atr(rates[:-1], 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S21: คำนวณ ATR ไม่ได้"}

    rsi = _calc_rsi(rates[:-1], int(_cfg(cfg, "RSI_PERIOD")))
    if rsi is None:
        return {"signal": "WAIT", "reason": "S21: คำนวณ RSI ไม่ได้"}

    closes = [float(r["close"]) for r in rates[:-1]]
    _, trend_up, trend_down = _ema_slope(closes, ema_period, slope_bars)

    retest_buf = atr * float(_cfg(cfg, "RETEST_ATR_BUFFER"))
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    cur_price = float(rates[-1]["close"])
    candles = list(rates[-4:-1])

    # ── BUY: ทะลุ range_high ขึ้น + body แข็งแรง + trend ขึ้น + RSI momentum ──
    if (
        bc > range_high
        and body_pct >= min_body
        and bc > bo                       # แท่งเขียว (ปิดสูงกว่าเปิด)
        and trend_up
        and float(_cfg(cfg, "RSI_MIN_FOR_BUY")) <= rsi <= float(_cfg(cfg, "RSI_MAX_FOR_BUY"))
    ):
        entry = round(range_high + retest_buf, 2)   # LIMIT รอ retest แนวต้านเดิม
        sl = round(range_high - sl_buf, 2)
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if (
            0 < risk <= max_risk_mult * atr
            and tp > entry
            and cur_price > entry  # ยังไม่ retrace ลงมาแตะ entry (รอ limit fill)
        ):
            return {
                "signal":      "BUY",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 21 Confluence Breakout-Retest 🟢 BUY",
                "reason": (
                    f"Breakout: close `{bc:.2f}` > range_high `{range_high:.2f}` "
                    f"(body {body_pct*100:.0f}% >= {min_body*100:.0f}%)\n"
                    f"Trend EMA{ema_period} ขึ้น | RSI `{rsi:.1f}` momentum confirm\n"
                    f"Retest entry `{entry:.2f}` | SL `{sl:.2f}` | TP `{tp:.2f}` (RR {rr})"
                ),
                "order_mode":  "limit",
                "entry_label": "BUY LIMIT (Confluence Breakout-Retest)",
                "candles":     candles,
                "cancel_bars": int(_cfg(cfg, "LIMIT_CANCEL_BARS")),
                "breakout_level": round(range_high, 2),
                "breakout_bar_time": int(b["time"]),
                "rsi_at_signal": rsi,
                "atr_at_signal": atr,
            }

    # ── SELL: ทะลุ range_low ลง + body แข็งแรง + trend ลง + RSI momentum ──
    if (
        bc < range_low
        and body_pct >= min_body
        and bc < bo
        and trend_down
        and float(_cfg(cfg, "RSI_MIN_FOR_SELL")) <= rsi <= float(_cfg(cfg, "RSI_MAX_FOR_SELL"))
    ):
        entry = round(range_low - retest_buf, 2)
        sl = round(range_low + sl_buf, 2)
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if (
            0 < risk <= max_risk_mult * atr
            and tp < entry
            and cur_price < entry
        ):
            return {
                "signal":      "SELL",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 21 Confluence Breakout-Retest 🔴 SELL",
                "reason": (
                    f"Breakout: close `{bc:.2f}` < range_low `{range_low:.2f}` "
                    f"(body {body_pct*100:.0f}% >= {min_body*100:.0f}%)\n"
                    f"Trend EMA{ema_period} ลง | RSI `{rsi:.1f}` momentum confirm\n"
                    f"Retest entry `{entry:.2f}` | SL `{sl:.2f}` | TP `{tp:.2f}` (RR {rr})"
                ),
                "order_mode":  "limit",
                "entry_label": "SELL LIMIT (Confluence Breakout-Retest)",
                "candles":     candles,
                "cancel_bars": int(_cfg(cfg, "LIMIT_CANCEL_BARS")),
                "breakout_level": round(range_low, 2),
                "breakout_bar_time": int(b["time"]),
                "rsi_at_signal": rsi,
                "atr_at_signal": atr,
            }

    return {"signal": "WAIT", "reason": "S21: ยังไม่พบ breakout + retest ครบเงื่อนไข"}


def strategy_21(rates, tf: str = "", cfg: dict | None = None):
    """
    Wrapper runtime-style (TF gate + dedup) — เก็บไว้เผื่ออนาคต
    ⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียกฟังก์ชันนี้ — standalone จริง
    """
    result = detect_s21(rates, tf=tf, dt_bkk=None, cfg=cfg)
    sig = result.get("signal")
    if sig not in ("BUY", "SELL"):
        return result

    bar_time = int(result.get("breakout_bar_time", 0))
    level = float(result.get("breakout_level", 0.0))

    if _s21_last_fire.get((tf, sig)) == bar_time:
        return {"signal": "WAIT", "reason": "S21: fire แท่งนี้ไปแล้ว (dedup)"}

    cooldown_bars = 20
    tf_secs = _TF_SECS.get(tf, 60)
    lv_key = (tf, sig, round(level, 1))
    last_lv_time = _s21_level_fired.get(lv_key, 0)
    if last_lv_time and (bar_time - last_lv_time) < cooldown_bars * tf_secs:
        return {"signal": "WAIT", "reason": "S21: level อยู่ใน cooldown"}

    _s21_last_fire[(tf, sig)] = bar_time
    _s21_level_fired[lv_key] = bar_time
    return result
