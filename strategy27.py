"""
strategy27.py — S27 High-Frequency entry (M1/M5) + HTF confirmation (M15/H1/H4) (RESEARCH / BACKTEST-ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py / trailing.py / main.py
   ไม่มี config.active_strategies[27], ไม่มี wiring เข้า live trading ใดๆ
   ใช้คู่กับ sim_s27_backtest.py / optimize_s27.py เพื่อ backtest เท่านั้น

สมมติฐานที่ทดสอบ: S26 พิสูจน์แล้วว่า entry ดิบบน M1 ที่ไม่มี filter ยืนยันเลย ให้ WR ระดับ
noise (~52-53%) ไม่พอเป็น edge แม้ความถี่จะสูงมาก (140 ไม้/วัน) — S27 ทดสอบว่าถ้าบังคับให้
entry ความถี่สูงบน M1/M5 ทุกไม้ต้องผ่าน **confirmation จาก timeframe ใหญ่กว่า (M15/H1/H4)**
อย่างน้อย 1 ชั้นก่อนเข้าเสมอ จะยก WR ขึ้นได้มากพอเทียบกับความถี่ที่เสียไปหรือไม่ (sweet spot
ระหว่าง WR×frequency×RR ไม่ใช่ไล่ WR สูงสุดหรือความถี่สูงสุดอย่างเดียว)

ท่าหลักที่ Lock (กฎข้อ 1 — entry mechanism เดียวตลอดทั้งกริด):
  "EMA-fast pullback bounce" บน entry timeframe (M1 หรือ M5) — ราคาแตะ/ทะลุ EMA_FAST เบาๆ
  แล้วปิดแท่งเด้งกลับสวนแท่งก่อน (bounce candle) โดย**ไม่มี own-TF trend filter ในตัว**
  (ตัดสิ่งนี้ออกตั้งใจ เพื่อให้ HTF confirmation เป็นตัวกรองทิศทางเดียวที่ทดสอบผลกระทบได้ชัด
  ต่างจาก S26 ที่ trend filter มาจาก M1 เอง) ทิศทางของ signal มาจาก bounce candle เท่านั้น
  (close > open + กลับขึ้นเหนือ EMA = BUY candidate, ตรงข้าม = SELL candidate)

ชั้น confirmation จาก HTF ที่ทดสอบในกริดเดียวกัน (เลือกด้วย `CONFIRMATION_TYPE`):
  1. "none"      : baseline ไม่มี confirmation เลย (วัด WR ดิบเทียบ S26)
  2. "htf_trend" : ทิศทาง bounce ต้องตรงกับ slope ของ EMA(HTF_EMA_PERIOD) บน HTF_TF
                   (เทรดตามทิศทาง trend ของ M15/H1 เท่านั้น) — ปรับ ADX_MIN_THRESHOLD ได้
                   (>0 = ต้องผ่าน ADX(HTF) >= threshold ด้วย ยืนยัน trend strength)
  3. "htf_rsi"   : RSI(RSI_PERIOD) บน HTF_TF ต้องไม่อยู่ใน "zone สวนทาง" กับทิศทาง bounce
                   (BUY ต้องการ RSI >= 50-RSI_THRESHOLD, SELL ต้องการ RSI <= 50+RSI_THRESHOLD)
  4. "htf_level" : ราคาปัจจุบันต้องอยู่ในโซน key level จาก HTF_TF (rolling high/low ของ
                   LEVEL_LOOKBACK แท่ง HTF) — BUY เฉพาะใกล้ขอบล่าง(support), SELL เฉพาะใกล้
                   ขอบบน(resistance) ตาม LEVEL_ZONE_PCT

Entry/Exit:
  - Entry: MARKET ที่ open ของแท่ง entry-TF ถัดจากแท่ง signal (กัน look-ahead)
  - SL: จุดเกิด signal (high/low ของ bounce candle ฝั่งตรงข้าม) + ATR(entry-TF) buffer
  - TP: entry ∓ TP_RR × risk (TP_RR ไม่ fix — กริดหาค่าที่เหมาะสม 0.8-2.0)
  - HTF lookup ใช้เฉพาะ "แท่ง HTF ที่ปิดแล้วล่าสุดก่อนเวลา entry-bar" เท่านั้น (กัน look-ahead
    ข้าม timeframe ด้วย — ดู _htf_lookup ใน sim_s27_backtest.py)
"""

S27_DEFAULTS = {
    "ENTRY_TF": "M1",                 # "M1" | "M5"
    "EMA_FAST": 8,
    "PULLBACK_TOUCH_ATR": 0.15,
    "SL_ATR_MULT": 0.5,
    "TP_RR": 1.0,                     # ไม่ fix รอบนี้ — กริดหาค่า 0.8-2.0
    "MAX_RISK_ATR_MULT": 4.0,
    "SESSION_FILTER": True,
    "SESSIONS": [("14:00", "23:00")],
    "RISK_PCT": 1.0,

    "CONFIRMATION_TYPE": "none",      # "none" | "htf_trend" | "htf_rsi" | "htf_level"
    "HTF_TF": "M15",                  # "M15" | "H1" | "H4"
    "HTF_EMA_PERIOD": 50,
    "HTF_SLOPE_BARS": 5,
    "ADX_PERIOD": 14,
    "ADX_MIN_THRESHOLD": 0.0,         # 0 = ไม่ใช้ ADX confirmation เพิ่ม
    "RSI_PERIOD": 14,
    "RSI_THRESHOLD": 10.0,            # zone สวนทาง = midline(50) ∓ threshold
    "LEVEL_LOOKBACK": 20,
    "LEVEL_ZONE_PCT": 0.20,
}

_TF_SECS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S27_DEFAULTS[key]


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


def _detect_ema_pullback_bounce(rates, atr, cfg):
    """
    ท่าหลัก (locked): ราคาแตะ/ทะลุ EMA_FAST เบาๆ แล้วปิดแท่งเด้งกลับ — ไม่มี own-TF trend
    filter ในตัว ทิศทางมาจาก bounce candle ล้วนๆ (ตัดสินใจทิศทางที่ HTF confirmation
    ในชั้นถัดไปเท่านั้น)
    """
    ema_fast_p = int(_cfg(cfg, "EMA_FAST"))
    closes = [float(r["close"]) for r in rates[:-1]]
    if len(closes) < ema_fast_p + 2:
        return None
    ef = _ema_series(closes, ema_fast_p)
    if len(ef) < 2:
        return None
    ema_now = ef[-1]

    b = rates[-2]
    bo, bh, bl, bc = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
    touch_buf = float(_cfg(cfg, "PULLBACK_TOUCH_ATR")) * atr
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))

    if bl <= ema_now + touch_buf and bc > bo and bc > ema_now:
        entry = round(bc, 2)
        sl = round(min(bl, ema_now) - sl_buf, 2)
        return ("BUY", entry, sl, "EMA{} pullback bounce BUY @ {:.2f}".format(ema_fast_p, ema_now))

    if bh >= ema_now - touch_buf and bc < bo and bc < ema_now:
        entry = round(bc, 2)
        sl = round(max(bh, ema_now) + sl_buf, 2)
        return ("SELL", entry, sl, "EMA{} pullback bounce SELL @ {:.2f}".format(ema_fast_p, ema_now))

    return None


def detect_s27(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    """
    Pure detection (backtest เรียกตรง)
    rates: แท่งสุดท้าย = แท่งกำลังวิ่ง (รู้แค่ open), rates[-2] = แท่ง signal candidate (ปิดแล้ว)
    htf_ctx: dict ของค่า HTF ที่คำนวณไว้ล่วงหน้าแล้ว (จาก sim_s27_backtest._htf_lookup) เพื่อกัน
             look-ahead ข้าม timeframe และเลี่ยงคำนวณ indicator ซ้ำทุกแท่ง:
             {"trend_up":bool,"trend_down":bool,"adx":float,"rsi":float,
              "level_high":float,"level_low":float,"price":float}
    คืน dict {signal: BUY/SELL/WAIT, ...}
    """
    ema_fast_p = int(_cfg(cfg, "EMA_FAST"))
    need = ema_fast_p + 10
    if rates is None or len(rates) < need:
        return {"signal": "WAIT", "reason": f"S27: ข้อมูลไม่พอ (ต้องการ >= {need} แท่ง)"}

    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S27: อยู่นอกช่วง session filter"}

    atr = _calc_atr(rates[:-1], 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S27: คำนวณ ATR ไม่ได้"}

    sig = _detect_ema_pullback_bounce(rates, atr, cfg)
    if sig is None:
        return {"signal": "WAIT", "reason": "S27: ยังไม่พบสัญญาณ bounce"}

    direction, entry, sl, reason = sig

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S27: ไม่มี HTF context สำหรับ confirmation"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S27: ADX(HTF) ไม่ผ่าน threshold"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S27: HTF trend ไม่ขึ้น (BUY ถูกบล็อก)"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S27: HTF trend ไม่ลง (SELL ถูกบล็อก)"}
        elif conf_type == "htf_rsi":
            rsi = htf_ctx.get("rsi")
            if rsi is None:
                return {"signal": "WAIT", "reason": "S27: ไม่มี RSI(HTF)"}
            thr = float(_cfg(cfg, "RSI_THRESHOLD"))
            if direction == "BUY" and rsi < (50.0 - thr):
                return {"signal": "WAIT", "reason": "S27: RSI(HTF) อยู่ใน zone สวนทาง BUY"}
            if direction == "SELL" and rsi > (50.0 + thr):
                return {"signal": "WAIT", "reason": "S27: RSI(HTF) อยู่ใน zone สวนทาง SELL"}
        elif conf_type == "htf_level":
            lo, hi = htf_ctx.get("level_low"), htf_ctx.get("level_high")
            if lo is None or hi is None or hi <= lo:
                return {"signal": "WAIT", "reason": "S27: ไม่มี HTF level"}
            size = hi - lo
            zone_pct = float(_cfg(cfg, "LEVEL_ZONE_PCT"))
            price = htf_ctx.get("price", entry)
            lower_zone = lo + zone_pct * size
            upper_zone = hi - zone_pct * size
            if direction == "BUY" and price > lower_zone:
                return {"signal": "WAIT", "reason": "S27: ราคาไม่อยู่ในโซน support (HTF level)"}
            if direction == "SELL" and price < upper_zone:
                return {"signal": "WAIT", "reason": "S27: ราคาไม่อยู่ในโซน resistance (HTF level)"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    b = rates[-2]

    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S27: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S27: risk ผิดปกติ"}

    return {
        "signal": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "pattern": f"ท่าที่ 27 HF-{_cfg(cfg,'ENTRY_TF')}-EMAbounce+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"{reason}\nentry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market",
        "entry_label": f"{direction} MARKET (S27 {conf_type})",
        "signal_bar_time": int(b["time"]),
        "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_27(rates, tf: str = "", cfg: dict | None = None):
    """
    Wrapper runtime-style เก็บไว้เผื่ออนาคต
    ⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียกฟังก์ชันนี้ — standalone จริง
    """
    return detect_s27(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
