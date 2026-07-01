"""
strategy23.py — S23 Trend-Following ADX/EMA Pullback (RESEARCH / BACKTEST-ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py / trailing.py / main.py
   ไม่มี config.active_strategies[23], ไม่มี wiring เข้า live trading ใดๆ
   ใช้คู่กับ sim_s23_backtest.py เพื่อ backtest เท่านั้น จนกว่าจะมีคำสั่งแยกให้ wire เข้าระบบจริง

แนวคิด (สังเคราะห์จากกลยุทธ์ XAUUSD ที่นิยมทั่วโลก — ต่างขั้วจาก S21 breakout-retest
และ S22 mean-reversion: S23 เป็น trend-following ล้วนๆ ถือยาวกว่า ใช้ RR สูงกว่ามาก
เพื่อทดสอบว่าการเพิ่ม RR (ไม่ใช่เพิ่ม risk%) ช่วยให้ $/วันสูงขึ้นโดย DD ไม่บวมเท่า S21/S22):
  1. Trend-following (ADX): ADX(period) >= threshold ยืนยันว่าตลาดอยู่ในเทรนด์จริง
     (กรอง choppy market ที่ trend-following เจ๊งง่าย)
  2. Trend direction: EMA fast > EMA slow = uptrend (กลับกัน = downtrend)
  3. Pullback entry (price action): รอราคาย่อกลับมาแถว EMA fast (ภายใน
     PULLBACK_ATR_MULT * ATR) แล้ว "ปฏิเสธ" กลับไปทิศทางเทรนด์ (แท่งปิดยืนยัน)
     — ป้องกันการไล่ราคาที่จุด breakout, เข้าที่ความเสี่ยงต่ำกว่า
  4. Momentum filter (RSI): ต้องไม่ extreme เกินไปในทิศตรงข้าม (กัน reversal จริง)
  5. Session-based: เทรดเฉพาะ London/NY (BKK 14:00-23:00) ที่ trend มักเกิดจริง
  6. Exit: SL ใต้/บน swing pullback + ATR buffer, TP ใช้ RR สูง (2.0-3.0) เพราะ
     ถือเทรนด์ยาวกว่า S21/S22 — ทดสอบสมมติฐานว่า "ไม้น้อย แต่ RR สูง" ให้ EV/วัน
     ดีกว่าที่ risk ปลอดภัยเมื่อเทียบกับ high-frequency/low-RR แบบ S21/S22
  7. News filter: ออกแบบ hook ไว้ (S23_NEWS_FILTER) แต่ **backtest ไม่มีข้อมูล
     ปฏิทินข่าวย้อนหลังในระบบ** จึงไม่ replay จริง — เป็นข้อจำกัดที่ต้องรายงาน

Entry/Exit:
  - Entry: MARKET ทันทีที่แท่ง pullback-rejection ปิด (ไม่ใช้ limit — ลดความซับซ้อน)
  - SL   : swing low/high ของ pullback ∓ S23_SL_ATR_MULT × ATR
  - TP   : entry ± S23_TP_RR × risk
  - Position sizing: risk-based ตาม % equity ต่อไม้ (S23_RISK_PCT) ดู
    sim_s23_backtest.py สำหรับการคำนวณ lot และ compounding equity

ไม่มีผลกำไร/ขาดทุนใดๆ ในไฟล์นี้ที่เป็นการอ้างลอย — ทุกตัวเลขต้องมาจาก
sim_s23_backtest.py รันจริงกับข้อมูล MT5 เท่านั้น (ดู s23_backtest_summary.csv)
"""

from datetime import time

from mt5_utils import calc_atr

# ── ค่าเริ่มต้นของ S23 (เก็บในไฟล์นี้เอง — ไม่แตะ config.py) ─────────
S23_DEFAULTS = {
    "EMA_FAST": 20,
    "EMA_SLOW": 50,
    "ADX_PERIOD": 14,
    "ADX_MIN": 22.0,                # ตลาดต้องมี trend strength พอ (กัน choppy)
    "PULLBACK_ATR_MULT": 0.6,       # ราคาต้องย่อกลับมาใกล้ EMA fast ภายในระยะนี้ * ATR
    "RSI_PERIOD": 14,
    "RSI_MAX_FOR_BUY": 65.0,        # กัน buy ตอน RSI สูงเกินไปแล้ว (ไล่ราคา)
    "RSI_MIN_FOR_BUY": 35.0,
    "RSI_MAX_FOR_SELL": 65.0,
    "RSI_MIN_FOR_SELL": 35.0,
    "SWING_LOOKBACK": 6,            # bars ย้อนหา swing low/high ของ pullback
    "SL_ATR_MULT": 0.8,
    "TP_RR": 2.0,                   # RR สูงกว่า S21/S22 มาก — ทดสอบ "ไม้น้อย RR สูง"
    "SESSION_FILTER": True,
    "SESSIONS": [("14:00", "23:00")],   # London + NY BKK
    "NEWS_FILTER": False,           # hook only — ไม่มีข้อมูลปฏิทินใน backtest
    "RISK_PCT": 1.0,                # % ของ equity ต่อไม้
    "MAX_RISK_ATR_MULT": 3.0,       # guard ป้องกัน risk ห่างผิดปกติ
    "COOLDOWN_BARS": 10,
}

_TF_SECS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}

# ── dedup state (in-memory เท่านั้น — ไฟล์นี้ไม่ถูกเรียกจาก runtime จริง) ──
_s23_last_fire: dict = {}


def _cfg(cfg: dict | None, key: str):
    if cfg and key in cfg:
        return cfg[key]
    return S23_DEFAULTS[key]


def _calc_rsi(rates, period=14):
    """RSI Wilder's smoothing — เหมือน strategy15/strategy21/strategy22"""
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


def _ema_series(closes, period):
    if len(closes) < period:
        return None
    k = 2.0 / (period + 1.0)
    ema = closes[0]
    hist = []
    for c in closes:
        ema = c * k + ema * (1.0 - k)
        hist.append(ema)
    return hist


def _calc_adx(rates, period=14):
    """ADX แบบ Wilder's smoothing มาตรฐาน"""
    if len(rates) < period * 2 + 1:
        return None
    highs = [float(r["high"]) for r in rates]
    lows = [float(r["low"]) for r in rates]
    closes = [float(r["close"]) for r in rates]

    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(rates)):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm.append(up_move if (up_move > down_move and up_move > 0) else 0.0)
        minus_dm.append(down_move if (down_move > up_move and down_move > 0) else 0.0)
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)

    if len(trs) < period:
        return None

    def _wilder_smooth(vals, period):
        sm = [sum(vals[:period])]
        for v in vals[period:]:
            sm.append(sm[-1] - sm[-1] / period + v)
        return sm

    tr_sm = _wilder_smooth(trs, period)
    plus_sm = _wilder_smooth(plus_dm, period)
    minus_sm = _wilder_smooth(minus_dm, period)

    dxs = []
    for i in range(len(tr_sm)):
        if tr_sm[i] <= 0:
            continue
        plus_di = 100.0 * plus_sm[i] / tr_sm[i]
        minus_di = 100.0 * minus_sm[i] / tr_sm[i]
        di_sum = plus_di + minus_di
        dx = 100.0 * abs(plus_di - minus_di) / di_sum if di_sum > 0 else 0.0
        dxs.append(dx)

    if len(dxs) < period:
        return None
    adx = sum(dxs[:period]) / period
    for dx in dxs[period:]:
        adx = (adx * (period - 1) + dx) / period
    return round(adx, 2)


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


def detect_s23(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    """
    Pure detection (backtest เรียกตรง) — ไม่แตะ dedup state
    rates: แท่งสุดท้าย = แท่งกำลังวิ่ง (รู้แค่ open), rates[-2] = แท่ง pullback-rejection (ปิดแล้ว)
    คืน dict {signal: BUY/SELL/WAIT, ...}
    """
    ema_slow = int(_cfg(cfg, "EMA_SLOW"))
    adx_period = int(_cfg(cfg, "ADX_PERIOD"))
    swing_lb = int(_cfg(cfg, "SWING_LOOKBACK"))
    need = max(ema_slow, adx_period * 2) + swing_lb + 10
    if rates is None or len(rates) < need:
        return {"signal": "WAIT", "reason": f"S23: ข้อมูลไม่พอ (ต้องการ >= {need} แท่ง)"}

    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S23: อยู่นอกช่วง London/NY"}

    closed = rates[:-1]
    b = closed[-1]                      # แท่ง pullback-rejection (ปิดแล้ว)
    closes = [float(r["close"]) for r in closed]

    ema_fast_hist = _ema_series(closes, int(_cfg(cfg, "EMA_FAST")))
    ema_slow_hist = _ema_series(closes, ema_slow)
    if ema_fast_hist is None or ema_slow_hist is None:
        return {"signal": "WAIT", "reason": "S23: คำนวณ EMA ไม่ได้"}
    ema_fast_now = ema_fast_hist[-1]
    ema_slow_now = ema_slow_hist[-1]

    adx = _calc_adx(closed, adx_period)
    if adx is None:
        return {"signal": "WAIT", "reason": "S23: คำนวณ ADX ไม่ได้"}
    if adx < float(_cfg(cfg, "ADX_MIN")):
        return {"signal": "WAIT", "reason": f"S23: ADX `{adx:.1f}` ต่ำกว่า threshold (choppy)"}

    atr = calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S23: คำนวณ ATR ไม่ได้"}

    rsi = _calc_rsi(closed, int(_cfg(cfg, "RSI_PERIOD")))
    if rsi is None:
        return {"signal": "WAIT", "reason": "S23: คำนวณ RSI ไม่ได้"}

    bo, bh, bl, bc = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
    pullback_buf = atr * float(_cfg(cfg, "PULLBACK_ATR_MULT"))
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    swing_window = closed[-(swing_lb + 1):-1]
    candles = list(rates[-4:-1])
    bar_time = int(b["time"])

    uptrend = ema_fast_now > ema_slow_now
    downtrend = ema_fast_now < ema_slow_now

    # ── BUY: uptrend + ราคาย่อมาแถว EMA fast + แท่งปิดเขียวยืนยันกลับขึ้น ──
    if (
        uptrend
        and bc > bo
        and abs(bl - ema_fast_now) <= pullback_buf
        and bc > ema_fast_now
        and float(_cfg(cfg, "RSI_MIN_FOR_BUY")) <= rsi <= float(_cfg(cfg, "RSI_MAX_FOR_BUY"))
    ):
        swing_low = min(float(r["low"]) for r in swing_window) if swing_window else bl
        sl = round(min(swing_low, bl) - sl_buf, 2)
        entry = round(float(rates[-1]["open"]), 2)
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if 0 < risk <= max_risk_mult * atr and tp > entry:
            return {
                "signal":      "BUY",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 23 Trend ADX/EMA Pullback 🟢 BUY",
                "reason": (
                    f"Uptrend EMA{_cfg(cfg,'EMA_FAST')}>EMA{ema_slow} | ADX `{adx:.1f}` >= "
                    f"{_cfg(cfg,'ADX_MIN')} | pullback แตะ EMA fast แล้วปิดเขียวยืนยัน\n"
                    f"RSI `{rsi:.1f}` | SL `{sl:.2f}` | TP `{tp:.2f}` (RR {rr})"
                ),
                "order_mode":  "market",
                "entry_label": "BUY MARKET (Trend ADX/EMA Pullback)",
                "candles":     candles,
                "ema_fast": round(ema_fast_now, 2),
                "ema_slow": round(ema_slow_now, 2),
                "adx_at_signal": adx,
                "signal_bar_time": bar_time,
                "rsi_at_signal": rsi,
                "atr_at_signal": atr,
            }

    # ── SELL: downtrend + ราคาเด้งมาแถว EMA fast + แท่งปิดแดงยืนยันกลับลง ──
    if (
        downtrend
        and bc < bo
        and abs(bh - ema_fast_now) <= pullback_buf
        and bc < ema_fast_now
        and float(_cfg(cfg, "RSI_MIN_FOR_SELL")) <= rsi <= float(_cfg(cfg, "RSI_MAX_FOR_SELL"))
    ):
        swing_high = max(float(r["high"]) for r in swing_window) if swing_window else bh
        sl = round(max(swing_high, bh) + sl_buf, 2)
        entry = round(float(rates[-1]["open"]), 2)
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if 0 < risk <= max_risk_mult * atr and tp < entry:
            return {
                "signal":      "SELL",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 23 Trend ADX/EMA Pullback 🔴 SELL",
                "reason": (
                    f"Downtrend EMA{_cfg(cfg,'EMA_FAST')}<EMA{ema_slow} | ADX `{adx:.1f}` >= "
                    f"{_cfg(cfg,'ADX_MIN')} | pullback แตะ EMA fast แล้วปิดแดงยืนยัน\n"
                    f"RSI `{rsi:.1f}` | SL `{sl:.2f}` | TP `{tp:.2f}` (RR {rr})"
                ),
                "order_mode":  "market",
                "entry_label": "SELL MARKET (Trend ADX/EMA Pullback)",
                "candles":     candles,
                "ema_fast": round(ema_fast_now, 2),
                "ema_slow": round(ema_slow_now, 2),
                "adx_at_signal": adx,
                "signal_bar_time": bar_time,
                "rsi_at_signal": rsi,
                "atr_at_signal": atr,
            }

    return {"signal": "WAIT", "reason": "S23: ยังไม่พบ trend + pullback-rejection ครบเงื่อนไข"}


def strategy_23(rates, tf: str = "", cfg: dict | None = None):
    """
    Wrapper runtime-style (TF gate + dedup) — เก็บไว้เผื่ออนาคต
    ⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียกฟังก์ชันนี้ — standalone จริง
    """
    result = detect_s23(rates, tf=tf, dt_bkk=None, cfg=cfg)
    sig = result.get("signal")
    if sig not in ("BUY", "SELL"):
        return result

    bar_time = int(result.get("signal_bar_time", 0))
    cooldown_bars = int(_cfg(cfg, "COOLDOWN_BARS"))
    tf_secs = _TF_SECS.get(tf, 60)
    key = (tf, sig)
    last_t = _s23_last_fire.get(key, 0)
    if last_t and (bar_time - last_t) < cooldown_bars * tf_secs:
        return {"signal": "WAIT", "reason": "S23: cooldown หลังยิงล่าสุด"}

    _s23_last_fire[key] = bar_time
    return result
