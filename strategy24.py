"""
strategy24.py — S24 Asian-Range London-Breakout (RESEARCH / BACKTEST-ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py / trailing.py / main.py
   ไม่มี config.active_strategies[24], ไม่มี wiring เข้า live trading ใดๆ
   ใช้คู่กับ sim_s24_backtest.py เพื่อ backtest เท่านั้น จนกว่าจะมีคำสั่งแยกให้ wire เข้าระบบจริง

แนวคิด (สังเคราะห์จากกลยุทธ์ XAUUSD ที่นิยมทั่วโลก — เป็นแนว "session-based volatility"
คนละขั้วกับ S21 (breakout-retest), S22 (mean-reversion), S23 (trend-follow):
  1. Asian range (price action): วัด high/low ของช่วง Asian session ที่นิ่ง/แคบ
     (BKK 05:00-12:00) เป็นกรอบอ้างอิง — concept คลาสสิกของ "London breakout"
  2. Breakout: แท่งแรกของ London session (BKK 14:00-15:00 entry window) ที่ปิด
     ทะลุ high/low ของกรอบ Asian -> เข้าทันที (momentum เริ่ม session ใหม่)
  3. Range-quality filter: เทรดเฉพาะวันที่กรอบ Asian "แคบพอ" (range <=
     MAX_ASIAN_RANGE_ATR_MULT * ATR) — กันวันที่ Asian session ผันผวนมาก่อนแล้ว
     ซึ่ง breakout มักเป็น false signal
  4. Momentum filter (RSI): กรอง breakout ที่ extreme เกินไปแล้วออก (เลี่ยง
     ไล่ซื้อ/ขายตอน exhaustion เหมือน S21)
  5. Session-based: entry window แคบมาก (เฉพาะ 1 ชม. แรกของ London ต่อวัน) —
     ทดสอบแนวคิด "1 โอกาส/วัน คุณภาพสูง" แทน high-frequency
  6. News filter: ออกแบบ hook ไว้ (S24_NEWS_FILTER) แต่ **backtest ไม่มีข้อมูล
     ปฏิทินข่าวย้อนหลังในระบบ** จึงไม่ replay จริง — เป็นข้อจำกัดที่ต้องรายงาน

Entry/Exit:
  - Entry: MARKET ทันทีที่แท่งใน entry window ปิดทะลุกรอบ Asian
  - SL   : อีกฝั่งของกรอบ Asian ∓ S24_SL_ATR_MULT × ATR
  - TP   : entry ± S24_TP_RR × risk (RR กำหนดได้)
  - Position sizing: risk-based ตาม % equity ต่อไม้ (S24_RISK_PCT) ดู
    sim_s24_backtest.py สำหรับการคำนวณ lot และ compounding equity
  - 1 trade ต่อ "วัน" ต่อทิศทาง (ใครมาก่อนใน entry window ได้ก่อน — ไม่ปิดแล้วเปิดใหม่
    วันเดียวกัน)

ไม่มีผลกำไร/ขาดทุนใดๆ ในไฟล์นี้ที่เป็นการอ้างลอย — ทุกตัวเลขต้องมาจาก
sim_s24_backtest.py รันจริงกับข้อมูล MT5 เท่านั้น (ดู s24_backtest_summary.csv)
"""

from datetime import time

from mt5_utils import calc_atr

# ── ค่าเริ่มต้นของ S24 (เก็บในไฟล์นี้เอง — ไม่แตะ config.py) ─────────
S24_DEFAULTS = {
    "ASIAN_START": "05:00",         # BKK
    "ASIAN_END":   "12:00",         # BKK
    "ENTRY_WINDOW_START": "14:00",  # BKK (London open)
    "ENTRY_WINDOW_END":   "15:00",  # BKK (เปิดโอกาสเข้าได้แค่ 1 ชม.แรก)
    "MAX_ASIAN_RANGE_ATR_MULT": 3.0,   # กรอง Asian range ที่กว้างเกินไป (ผันผวนมาก่อนแล้ว)
    "MIN_ASIAN_RANGE_ATR_MULT": 0.5,   # กรอง Asian range ที่แบนเกินไป (breakout level ใกล้เกิน)
    "RSI_PERIOD": 14,
    "RSI_MAX_FOR_BUY": 75.0,
    "RSI_MIN_FOR_SELL": 25.0,
    "SL_ATR_MULT": 0.5,
    "TP_RR": 1.5,
    "NEWS_FILTER": False,            # hook only — ไม่มีข้อมูลปฏิทินใน backtest
    "RISK_PCT": 1.5,                 # % ของ equity ต่อไม้
    "MAX_RISK_ATR_MULT": 3.0,        # guard ป้องกัน risk ห่างผิดปกติ
}

_TF_SECS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}

# ── dedup state (in-memory เท่านั้น — ไฟล์นี้ไม่ถูกเรียกจาก runtime จริง) ──
_s24_last_fire_day: dict = {}


def _cfg(cfg: dict | None, key: str):
    if cfg and key in cfg:
        return cfg[key]
    return S24_DEFAULTS[key]


def _calc_rsi(rates, period=14):
    """RSI Wilder's smoothing — เหมือน strategy15/21/22/23"""
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


def _time_in(cur, start_str, end_str):
    sh, sm = map(int, start_str.split(":"))
    eh, em = map(int, end_str.split(":"))
    return time(sh, sm) <= cur < time(eh, em)


def _asian_range(rates_closed, dt_bkk_list, cfg):
    """หา high/low ของกรอบ Asian session ของ 'วันนี้เดียวกับแท่งล่าสุด' ย้อนหา
    ในแท่งที่ปิดแล้วเท่านั้น คืน (range_high, range_low) หรือ (None, None)"""
    if not rates_closed:
        return None, None
    last_dt = dt_bkk_list[-1]
    target_date = last_dt.date()
    a_start = _cfg(cfg, "ASIAN_START")
    a_end = _cfg(cfg, "ASIAN_END")
    highs, lows = [], []
    for r, dt in zip(rates_closed, dt_bkk_list):
        if dt.date() != target_date:
            continue
        if _time_in(dt.time(), a_start, a_end):
            highs.append(float(r["high"]))
            lows.append(float(r["low"]))
    if not highs or not lows:
        return None, None
    return max(highs), min(lows)


def detect_s24(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, dt_bkk_fn=None):
    """
    Pure detection (backtest เรียกตรง) — ไม่แตะ dedup state
    rates: แท่งสุดท้าย = แท่งกำลังวิ่ง (รู้แค่ open)
    dt_bkk_fn: callable(timestamp)->datetime BKK สำหรับแปลงเวลาทุกแท่ง (ฉีดจาก caller
               เพื่อเลี่ยง import config ตรงในไฟล์ strategy — เก็บ standalone)
    คืน dict {signal: BUY/SELL/WAIT, ...}
    """
    if rates is None or len(rates) < 60 or dt_bkk_fn is None:
        return {"signal": "WAIT", "reason": "S24: ข้อมูลไม่พอ หรือไม่มี dt_bkk_fn"}

    if dt_bkk is None:
        return {"signal": "WAIT", "reason": "S24: ไม่มี dt_bkk"}

    cur_time = dt_bkk.time()
    if not _time_in(cur_time, _cfg(cfg, "ENTRY_WINDOW_START"), _cfg(cfg, "ENTRY_WINDOW_END")):
        return {"signal": "WAIT", "reason": "S24: อยู่นอก entry window (London open ชม.แรก)"}

    closed = rates[:-1]
    dt_list = [dt_bkk_fn(int(r["time"])) for r in closed[-200:]]
    closed_recent = closed[-200:]

    range_high, range_low = _asian_range(closed_recent, dt_list, cfg)
    if range_high is None or range_low is None:
        return {"signal": "WAIT", "reason": "S24: หากรอบ Asian session ไม่ได้"}
    asian_range = range_high - range_low

    atr = calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S24: คำนวณ ATR ไม่ได้"}

    max_mult = float(_cfg(cfg, "MAX_ASIAN_RANGE_ATR_MULT"))
    min_mult = float(_cfg(cfg, "MIN_ASIAN_RANGE_ATR_MULT"))
    if not (min_mult * atr <= asian_range <= max_mult * atr):
        return {"signal": "WAIT", "reason": "S24: กรอบ Asian range ไม่อยู่ในเกณฑ์คุณภาพ"}

    rsi = _calc_rsi(closed, int(_cfg(cfg, "RSI_PERIOD")))
    if rsi is None:
        return {"signal": "WAIT", "reason": "S24: คำนวณ RSI ไม่ได้"}

    b = closed[-1]
    bo, bc = float(b["open"]), float(b["close"])
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    entry = round(float(rates[-1]["open"]), 2)
    candles = list(rates[-4:-1])
    bar_time = int(b["time"])
    day_key = dt_bkk.date().isoformat()

    if bc > range_high and bc > bo and rsi <= float(_cfg(cfg, "RSI_MAX_FOR_BUY")):
        sl = round(range_high - sl_buf, 2)   # SL ใต้ระดับที่ breakout (broken level กลายเป็นแนวรับใหม่)
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if 0 < risk <= max_risk_mult * atr and tp > entry:
            return {
                "signal":      "BUY",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 24 Asian-Range London-Breakout 🟢 BUY",
                "reason": (
                    f"London open breakout: close `{bc:.2f}` > Asian high `{range_high:.2f}` "
                    f"(Asian range `{asian_range:.2f}`)\n"
                    f"RSI `{rsi:.1f}` | SL `{sl:.2f}` | TP `{tp:.2f}` (RR {rr})"
                ),
                "order_mode":  "market",
                "entry_label": "BUY MARKET (Asian-Range London-Breakout)",
                "candles":     candles,
                "asian_high": round(range_high, 2),
                "asian_low": round(range_low, 2),
                "signal_bar_time": bar_time,
                "signal_day": day_key,
                "rsi_at_signal": rsi,
                "atr_at_signal": atr,
            }

    if bc < range_low and bc < bo and rsi >= float(_cfg(cfg, "RSI_MIN_FOR_SELL")):
        sl = round(range_low + sl_buf, 2)   # SL เหนือระดับที่ breakout (broken level กลายเป็นแนวต้านใหม่)
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if 0 < risk <= max_risk_mult * atr and tp < entry:
            return {
                "signal":      "SELL",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 24 Asian-Range London-Breakout 🔴 SELL",
                "reason": (
                    f"London open breakout: close `{bc:.2f}` < Asian low `{range_low:.2f}` "
                    f"(Asian range `{asian_range:.2f}`)\n"
                    f"RSI `{rsi:.1f}` | SL `{sl:.2f}` | TP `{tp:.2f}` (RR {rr})"
                ),
                "order_mode":  "market",
                "entry_label": "SELL MARKET (Asian-Range London-Breakout)",
                "candles":     candles,
                "asian_high": round(range_high, 2),
                "asian_low": round(range_low, 2),
                "signal_bar_time": bar_time,
                "signal_day": day_key,
                "rsi_at_signal": rsi,
                "atr_at_signal": atr,
            }

    return {"signal": "WAIT", "reason": "S24: ยังไม่ทะลุกรอบ Asian ครบเงื่อนไข"}


def strategy_24(rates, tf: str = "", cfg: dict | None = None, dt_bkk=None, dt_bkk_fn=None):
    """
    Wrapper runtime-style (TF gate + dedup 1 ไม้/วัน/ทิศทาง) — เก็บไว้เผื่ออนาคต
    ⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียกฟังก์ชันนี้ — standalone จริง
    """
    result = detect_s24(rates, tf=tf, dt_bkk=dt_bkk, cfg=cfg, dt_bkk_fn=dt_bkk_fn)
    sig = result.get("signal")
    if sig not in ("BUY", "SELL"):
        return result

    day_key = result.get("signal_day", "")
    fire_key = (tf, day_key)
    if _s24_last_fire_day.get(fire_key):
        return {"signal": "WAIT", "reason": "S24: ยิงไปแล้ววันนี้ (1 ไม้/วัน)"}

    _s24_last_fire_day[fire_key] = True
    return result
