"""
strategy22.py — S22 Session-VWAP Mean-Reversion Scalp (RESEARCH / BACKTEST-ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py / trailing.py / main.py
   ไม่มี config.active_strategies[22], ไม่มี wiring เข้า live trading ใดๆ
   ใช้คู่กับ sim_s22_backtest.py เพื่อ backtest เท่านั้น จนกว่าจะมีคำสั่งแยกให้ wire เข้าระบบจริง

แนวคิด (สังเคราะห์จากกลยุทธ์ XAUUSD ที่นิยมทั่วโลก — ต่างจาก S21 ที่เป็น
breakout-retest ความถี่ต่ำ/RR ต่ำ/risk สูง):
  1. Mean-reversion (price action): ใช้ session VWAP (รีเซ็ตทุกวันที่เริ่ม session
     แรก) เป็นแกนกลาง — ราคาเบี่ยงจาก VWAP เกิน N*stdev (คล้าย Bollinger-on-VWAP)
     ถือเป็น overextension ที่มีโอกาส revert
  2. Momentum exhaustion filter (RSI): เข้าเฉพาะตอน RSI อยู่ในโซน
     overbought/oversold จริง (กัน "เบี่ยงแต่ยังไม่หมดแรง" ที่มักวิ่งต่อ)
  3. Range filter: เทรดเฉพาะเมื่อ ATR ของ session ไม่ expand ผิดปกติ (กัน
     ชนข่าว/breakout volatility ที่ mean-reversion เจ๊งง่าย)
  4. Session-based: เทรดเฉพาะ London/NY overlap (BKK 19:00-23:00) ที่ liquidity
     สูง ทำให้ mean-reversion กลับเข้า VWAP ได้เร็ว ไม่ต้องรอนาน
  5. High-frequency scalp (M1/M5): RR ต่ำ (TP ใกล้กว่า S21) แต่จำนวนไม้/วันสูงกว่า
     มาก — ทดสอบแนวทาง "ชนะบ่อย ไม้เล็ก เก็บทุกวัน" แทน "ไม้น้อย risk สูง"
  6. News filter: ออกแบบ hook ไว้ (S22_NEWS_FILTER) แต่ **backtest ไม่มีข้อมูล
     ปฏิทินข่าวย้อนหลังในระบบ** จึงไม่ replay จริง — เป็นข้อจำกัดที่ต้องรายงาน

Entry/Exit:
  - Entry: MARKET ทันทีที่เบี่ยงเกิน threshold + RSI exhaustion ครบเงื่อนไข
           (ไม่ใช้ limit/retest แบบ S21 — เก็บความถี่สูงสุด)
  - SL   : อีกฝั่งของ VWAP band (กัน trend จริงที่ไม่ revert) + buffer ATR
  - TP   : กลับไปที่ VWAP (เป้าหมาย mean-reversion) จำกัดด้วย S22_TP_RR ขั้นต่ำ
  - Position sizing: risk-based ตาม % equity ต่อไม้ (S22_RISK_PCT) ดู
    sim_s22_backtest.py สำหรับการคำนวณ lot และ compounding equity

ไม่มีผลกำไร/ขาดทุนใดๆ ในไฟล์นี้ที่เป็นการอ้างลอย — ทุกตัวเลขต้องมาจาก
sim_s22_backtest.py รันจริงกับข้อมูล MT5 เท่านั้น (ดู s22_backtest_summary.csv)
"""

from datetime import time

from mt5_utils import calc_atr

# ── ค่าเริ่มต้นของ S22 (เก็บในไฟล์นี้เอง — ไม่แตะ config.py) ─────────
S22_DEFAULTS = {
    "VWAP_LOOKBACK_BARS": 240,      # bars ย้อนกลับสำหรับคำนวณ session VWAP (M5≈20h)
    "DEV_STDEV_MULT": 2.0,          # ราคาเบี่ยงจาก VWAP >= N * stdev ของ deviation
    "RSI_PERIOD": 14,
    "RSI_OVERBOUGHT": 70.0,         # RSI >= นี้ -> มองหา SELL (revert ลง)
    "RSI_OVERSOLD": 30.0,           # RSI <= นี้ -> มองหา BUY (revert ขึ้น)
    "ATR_PERIOD": 14,
    "MAX_ATR_EXPANSION_MULT": 1.8,  # ATR ปัจจุบัน <= N * ATR เฉลี่ยย้อนหลัง (กัน breakout vol)
    "SL_ATR_MULT": 1.2,             # SL อีกฝั่ง VWAP band + buffer นี้ * ATR
    "TP_RR": 0.8,                   # TP = entry -> VWAP, จำกัดขั้นต่ำที่ RR นี้
    "SESSION_FILTER": True,
    "SESSIONS": [("19:00", "23:00")],   # London/NY overlap BKK — liquidity สูงสุด
    "NEWS_FILTER": False,           # hook only — ไม่มีข้อมูลปฏิทินใน backtest
    "RISK_PCT": 1.0,                # % ของ equity ต่อไม้
    "MAX_RISK_ATR_MULT": 3.0,       # guard ป้องกัน risk ห่างผิดปกติ
    "COOLDOWN_BARS": 6,             # กันยิงรัวที่ระดับเดิมซ้ำในช่วงสั้น
}

_TF_SECS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}

# ── dedup state (in-memory เท่านั้น — ไฟล์นี้ไม่ถูกเรียกจาก runtime จริง) ──
_s22_last_fire: dict = {}


def _cfg(cfg: dict | None, key: str):
    if cfg and key in cfg:
        return cfg[key]
    return S22_DEFAULTS[key]


def _calc_rsi(rates, period=14):
    """RSI Wilder's smoothing — เหมือน strategy15/strategy17/strategy21"""
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


def _session_vwap_and_band(rates, lookback, dev_mult):
    """คำนวณ VWAP แบบถ่วงด้วย range (proxy volume เพราะ MT5 tick volume ไม่นิ่งพอ
    สำหรับ retail feed) ย้อนกลับ `lookback` แท่งล่าสุด (ไม่รวมแท่งกำลังวิ่ง)
    คืน (vwap, stdev_dev) หรือ (None, None) ถ้าข้อมูลไม่พอ"""
    if len(rates) < lookback + 1:
        return None, None
    window = rates[-(lookback + 1):-1]
    num, den = 0.0, 0.0
    typicals = []
    for r in window:
        h, l, c = float(r["high"]), float(r["low"]), float(r["close"])
        rng = max(h - l, 1e-6)
        tp = (h + l + c) / 3.0
        num += tp * rng
        den += rng
        typicals.append(tp)
    if den <= 0:
        return None, None
    vwap = num / den
    mean_tp = sum(typicals) / len(typicals)
    var = sum((tp - mean_tp) ** 2 for tp in typicals) / len(typicals)
    stdev = var ** 0.5
    return vwap, stdev


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


def detect_s22(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    """
    Pure detection (backtest เรียกตรง) — ไม่แตะ dedup state
    rates: แท่งสุดท้าย = แท่งกำลังวิ่ง (รู้แค่ open)
    คืน dict {signal: BUY/SELL/WAIT, ...}
    """
    lookback = int(_cfg(cfg, "VWAP_LOOKBACK_BARS"))
    atr_period = int(_cfg(cfg, "ATR_PERIOD"))
    need = lookback + atr_period + 30
    if rates is None or len(rates) < need:
        return {"signal": "WAIT", "reason": f"S22: ข้อมูลไม่พอ (ต้องการ >= {need} แท่ง)"}

    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S22: อยู่นอกช่วง London/NY overlap"}

    closed = rates[:-1]
    vwap, stdev = _session_vwap_and_band(closed, lookback, float(_cfg(cfg, "DEV_STDEV_MULT")))
    if vwap is None or stdev is None or stdev <= 0:
        return {"signal": "WAIT", "reason": "S22: คำนวณ VWAP/stdev ไม่ได้"}

    rsi = _calc_rsi(closed, int(_cfg(cfg, "RSI_PERIOD")))
    if rsi is None:
        return {"signal": "WAIT", "reason": "S22: คำนวณ RSI ไม่ได้"}

    atr = calc_atr(closed, atr_period)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S22: คำนวณ ATR ไม่ได้"}

    recent_atrs = []
    for k in range(1, 11):
        a = calc_atr(closed[:-k] if k else closed, atr_period)
        if a and a > 0:
            recent_atrs.append(a)
    avg_atr = (sum(recent_atrs) / len(recent_atrs)) if recent_atrs else atr
    max_atr_mult = float(_cfg(cfg, "MAX_ATR_EXPANSION_MULT"))
    if avg_atr > 0 and atr > max_atr_mult * avg_atr:
        return {"signal": "WAIT", "reason": "S22: ATR expand ผิดปกติ (เลี่ยง breakout vol)"}

    cur_price = float(rates[-1]["open"])
    dev_mult = float(_cfg(cfg, "DEV_STDEV_MULT"))
    upper = vwap + dev_mult * stdev
    lower = vwap - dev_mult * stdev

    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    min_rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    candles = list(rates[-4:-1])
    bar_time = int(closed[-1]["time"])

    # ── BUY: ราคาต่ำกว่า lower band + RSI oversold -> revert ขึ้นไป VWAP ──
    if cur_price <= lower and rsi <= float(_cfg(cfg, "RSI_OVERSOLD")):
        entry = round(cur_price, 2)
        sl = round(lower - sl_buf, 2)
        risk = entry - sl
        tp_to_vwap = vwap - entry
        tp = round(entry + max(tp_to_vwap, min_rr * risk), 2)
        if 0 < risk <= max_risk_mult * atr and tp > entry:
            return {
                "signal":      "BUY",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 22 Session-VWAP Mean-Reversion 🟢 BUY",
                "reason": (
                    f"ราคา `{cur_price:.2f}` <= lower band `{lower:.2f}` "
                    f"(VWAP `{vwap:.2f}`, stdev `{stdev:.2f}`)\n"
                    f"RSI `{rsi:.1f}` oversold | SL `{sl:.2f}` | TP `{tp:.2f}` (-> VWAP)"
                ),
                "order_mode":  "market",
                "entry_label": "BUY MARKET (Session-VWAP Mean-Reversion)",
                "candles":     candles,
                "vwap": round(vwap, 2),
                "band_level": round(lower, 2),
                "signal_bar_time": bar_time,
                "rsi_at_signal": rsi,
                "atr_at_signal": atr,
            }

    # ── SELL: ราคาสูงกว่า upper band + RSI overbought -> revert ลงไป VWAP ──
    if cur_price >= upper and rsi >= float(_cfg(cfg, "RSI_OVERBOUGHT")):
        entry = round(cur_price, 2)
        sl = round(upper + sl_buf, 2)
        risk = sl - entry
        tp_to_vwap = entry - vwap
        tp = round(entry - max(tp_to_vwap, min_rr * risk), 2)
        if 0 < risk <= max_risk_mult * atr and tp < entry:
            return {
                "signal":      "SELL",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 22 Session-VWAP Mean-Reversion 🔴 SELL",
                "reason": (
                    f"ราคา `{cur_price:.2f}` >= upper band `{upper:.2f}` "
                    f"(VWAP `{vwap:.2f}`, stdev `{stdev:.2f}`)\n"
                    f"RSI `{rsi:.1f}` overbought | SL `{sl:.2f}` | TP `{tp:.2f}` (-> VWAP)"
                ),
                "order_mode":  "market",
                "entry_label": "SELL MARKET (Session-VWAP Mean-Reversion)",
                "candles":     candles,
                "vwap": round(vwap, 2),
                "band_level": round(upper, 2),
                "signal_bar_time": bar_time,
                "rsi_at_signal": rsi,
                "atr_at_signal": atr,
            }

    return {"signal": "WAIT", "reason": "S22: ยังไม่เบี่ยงเกิน band + RSI exhaustion ครบเงื่อนไข"}


def strategy_22(rates, tf: str = "", cfg: dict | None = None):
    """
    Wrapper runtime-style (TF gate + dedup) — เก็บไว้เผื่ออนาคต
    ⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียกฟังก์ชันนี้ — standalone จริง
    """
    result = detect_s22(rates, tf=tf, dt_bkk=None, cfg=cfg)
    sig = result.get("signal")
    if sig not in ("BUY", "SELL"):
        return result

    bar_time = int(result.get("signal_bar_time", 0))
    cooldown_bars = int(_cfg(cfg, "COOLDOWN_BARS"))
    tf_secs = _TF_SECS.get(tf, 60)
    key = (tf, sig)
    last_t = _s22_last_fire.get(key, 0)
    if last_t and (bar_time - last_t) < cooldown_bars * tf_secs:
        return {"signal": "WAIT", "reason": "S22: cooldown หลังยิงล่าสุด"}

    _s22_last_fire[key] = bar_time
    return result
