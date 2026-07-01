"""
strategy25.py — S25 Liquidity Sweep Reversal (RESEARCH / BACKTEST-ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py / trailing.py / main.py
   ไม่มี config.active_strategies[25], ไม่มี wiring เข้า live trading ใดๆ
   ใช้คู่กับ sim_s25_backtest.py เพื่อ backtest เท่านั้น จนกว่าจะมีคำสั่งแยกให้ wire เข้าระบบจริง

แนวคิด (สังเคราะห์จากกลยุทธ์ XAUUSD ที่นิยมทั่วโลก — สาย Smart-Money-Concept / ICT):
  "Liquidity Sweep / Stop-Hunt Reversal" — กลไกตรงข้ามกับ S21 (breakout-following):
  1. หา swing high/low ของกรอบ lookback ที่ผ่านมา (จุดที่มี stop-loss ของฝั่งตรงข้ามสะสมอยู่)
  2. แท่ง "sweep" ต้องแทงทะลุ swing level ไปด้วย wick (เก็บ liquidity ของฝั่งตรงข้าม)
     แต่ปิด "กลับเข้ามาใน" กรอบเดิม (ปิด < swing_high สำหรับ sell, ปิด > swing_low สำหรับ buy)
     → นี่คือสัญญาณว่าราคาไม่สามารถยืนนอกกรอบได้ = false breakout / stop-hunt จริง
  3. ต้องมี rejection wick ชัดเจน (wick ratio ของแท่ง sweep >= REJECTION_WICK_PCT ของ range)
  4. RSI exhaustion confirm: sweep ฝั่ง high ต้อง RSI overbought, sweep ฝั่ง low ต้อง RSI oversold
     (ยืนยันว่าราคาวิ่งสุดทางจริงก่อน reversal ไม่ใช่แค่ noise)
  5. Session filter: เทรดเฉพาะ London/NY killzone (เหมือน S21) — sweep/stop-hunt เกิดบ่อย
     และมีนัยสำคัญที่สุดช่วง volatility/liquidity สูง

ข้อแตกต่างสำคัญจาก S21-S24 (ตามกฎข้อ 1 — "เพิ่มความลึก" ไม่ใช่ "กลยุทธ์เดียวกันคนละชื่อ"):
  - S21 breakout-retest: เทรด "ตาม" ทิศทาง breakout (เชื่อว่า breakout จริง)
  - S22 VWAP mean-reversion: เทรดกลับเข้า "ค่าเฉลี่ย" ไม่สนใจ structure/swing
  - S23 trend ADX/EMA: เทรดตาม trend ที่มีอยู่ ถือยาว
  - S24 Asian-range breakout: เทรดตาม breakout ของกรอบ session คงที่
  - S25 (ใหม่): เทรด "กลับทิศ" หลัง false-breakout ของ swing structure ที่ผันแปรตามราคาจริง
    (ไม่ใช่ mean-reversion ทางสถิติ และไม่ใช่ breakout-following — เป็นกลไกที่ 3 ที่ต่างออกไป)

Entry/Exit:
  - Entry: MARKET ที่ open ของแท่งถัดจากแท่ง sweep (กัน look-ahead — แท่ง sweep ต้องปิดก่อน)
  - SL   : เลยปลาย wick ของแท่ง sweep ไป S25_SL_ATR_MULT × ATR (กัน wick ใหม่ stop-out ทันที)
  - TP   : entry ∓ S25_TP_RR × risk
  - Position sizing: risk-based ตาม % equity ต่อไม้ (S25_RISK_PCT) — ดู sim_s25_backtest.py
"""

from datetime import time

from mt5_utils import calc_atr

S25_DEFAULTS = {
    # ค่า validated ผ่าน grid search 242 combinations (sim_s25_backtest.py / optimize_s25.py /
    # edge_test_s25.py / be_sweep_s25.py / leverage_test_s25.py — ดูสรุปใน create_s25.md):
    # best risk-adjusted ที่ risk=2.0-2.5%: avgR~0.16, PF~1.55, maxDD~12-14%, $9-12/วัน (60d/M5+M15)
    "SWING_LOOKBACK": 15,           # bars หา swing high/low (ก่อนแท่ง sweep)
    "SWEEP_MIN_PIERCE_ATR": 0.05,   # wick ต้องแทงทะลุ swing level >= เท่านี้ ATR
    "REJECTION_WICK_PCT": 0.55,     # wick (ฝั่ง sweep) >= % ของ range แท่งนั้น — สำคัญสุดในกลุ่ม
                                     # param ทั้งหมด (กรอง false sweep ออก) validated
    "RSI_PERIOD": 14,
    "RSI_OVERBOUGHT": 62.0,         # sweep swing_high ต้องมี RSI >= ค่านี้ (exhaustion ก่อนกลับ)
    "RSI_OVERSOLD": 38.0,           # sweep swing_low ต้องมี RSI <= ค่านี้
    "SL_ATR_MULT": 0.6,             # SL = เลย wick ไปอีก mult*ATR
    "TP_RR": 2.0,                   # validated: RR<2.0 ให้ avgR ติดลบ/ใกล้ 0 ในกลุ่มนี้
    "SESSION_FILTER": True,
    "SESSIONS": [("14:00", "18:00"), ("19:00", "23:00")],  # London/NY BKK (เหมือน S21)
    "RISK_PCT": 2.0,                # validated: maxDD 11.6% ที่ risk 2% (safe), avgR คงที่
                                     # ไม่ขึ้นกับ risk% (ดู leverage-vs-edge analysis ใน create_s25.md)
    "MAX_RISK_ATR_MULT": 4.0,       # guard กัน risk distance ห่างผิดปกติ
    "TREND_FILTER": "against",      # validated: against ดีกว่า none เล็กน้อยในทุก RR/wick ที่ดี
    "EMA_TREND": 50,
    "EMA_SLOPE_BARS": 10,
    "ATR_REGIME_FILTER": False,     # edge-improvement attempt A — ทดสอบแล้วไม่ช่วย (ดู create_s25.md)
    "ATR_REGIME_PERIOD_LONG": 50,
    "ATR_REGIME_MULT": 1.0,
    "BREAKEVEN_AFTER_R": 0.3,       # edge-improvement attempt B — validated ดีที่สุด (PF 1.34, maxDD 11%)
}
# หมายเหตุ ATR_REGIME_FILTER (edge-improvement แนวทาง A ตาม Exhaustion Checklist ข้อ 2):
#   sweep/stop-hunt ที่มีนัยสำคัญจริงควรเกิดในช่วง volatility expansion (ATR สั้นยกตัวเหนือ
#   ATR ยาว) ไม่ใช่ตลาดนิ่ง — กรองด้วย ATR(14) >= ATR_REGIME_MULT * ATR(ATR_REGIME_PERIOD_LONG)
#   เป็นแนวทางที่ต่างจากการขยับ threshold เดิม (wick/pierce/RSI) โดยสิ้นเชิง — เพิ่ม "regime"
#   confirmation ใหม่ทั้งหมด ไม่ใช่แค่ขยับตัวเลขพารามิเตอร์เดิม
# หมายเหตุ TREND_FILTER (ใช้ทดสอบ edge-improvement แนวทาง B ตาม Exhaustion Checklist ข้อ 2):
#   "none"    = ไม่กรอง trend (sweep reversal ล้วน — ตามแนวคิดดั้งเดิม)
#   "against" = เทรดเฉพาะ sweep ที่ "สวนเทรนด์หลัก" เท่านั้น (เชื่อว่า sweep ของฝั่งที่อ่อนแอ
#               กว่าจะกลับตัวง่ายกว่า เพราะไม่มีแรงซื้อ/ขายจริงรองรับ)
#   "with"    = เทรดเฉพาะ sweep ที่ "ตามเทรนด์หลัก" (เชื่อว่า pullback สวนเทรนด์ระยะสั้นที่ถูก
#               sweep แล้วกลับตัว คือจังหวะกลับเข้าเทรนด์หลักที่ดี)

_TF_SECS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}

_s25_last_fire: dict = {}


def _cfg(cfg: dict | None, key: str):
    if cfg and key in cfg:
        return cfg[key]
    return S25_DEFAULTS[key]


def _calc_rsi(rates, period=14):
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


def detect_s25(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None):
    """
    Pure detection (backtest เรียกตรง)
    rates: แท่งสุดท้าย = แท่งกำลังวิ่ง (รู้แค่ open), rates[-2] = แท่ง sweep candidate (ปิดแล้ว)
    คืน dict {signal: BUY/SELL/WAIT, ...}
    """
    lookback = int(_cfg(cfg, "SWING_LOOKBACK"))
    ema_period = int(_cfg(cfg, "EMA_TREND"))
    slope_bars = int(_cfg(cfg, "EMA_SLOPE_BARS"))
    need = lookback + max(ema_period + slope_bars, 30) + 3
    if rates is None or len(rates) < need:
        return {"signal": "WAIT", "reason": f"S25: ข้อมูลไม่พอ (ต้องการ >= {need} แท่ง)"}

    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S25: อยู่นอกช่วง Killzones London/NY"}

    b = rates[-2]  # แท่ง sweep candidate (ปิดแล้ว)
    window = rates[-(lookback + 2):-2]  # กรอบก่อนแท่ง sweep (ไม่รวมแท่ง sweep เอง)
    swing_high = max(float(r["high"]) for r in window)
    swing_low = min(float(r["low"]) for r in window)
    if swing_high <= swing_low:
        return {"signal": "WAIT", "reason": "S25: กรอบ swing แบนผิดปกติ"}

    bo, bh, bl, bc = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
    bar_range = bh - bl
    if bar_range <= 0:
        return {"signal": "WAIT", "reason": "S25: แท่ง sweep ไม่มี range"}

    atr = calc_atr(rates[:-1], 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S25: คำนวณ ATR ไม่ได้"}

    rsi = _calc_rsi(rates[:-1], int(_cfg(cfg, "RSI_PERIOD")))
    if rsi is None:
        return {"signal": "WAIT", "reason": "S25: คำนวณ RSI ไม่ได้"}

    closes = [float(r["close"]) for r in rates[:-1]]
    _, trend_up, trend_down = _ema_slope(closes, ema_period, slope_bars)

    if bool(_cfg(cfg, "ATR_REGIME_FILTER")):
        atr_long = calc_atr(rates[:-1], int(_cfg(cfg, "ATR_REGIME_PERIOD_LONG")))
        if not atr_long or atr_long <= 0 or atr < float(_cfg(cfg, "ATR_REGIME_MULT")) * atr_long:
            return {"signal": "WAIT", "reason": "S25: ATR ไม่อยู่ใน volatility-expansion regime"}

    pierce_min = float(_cfg(cfg, "SWEEP_MIN_PIERCE_ATR")) * atr
    rej_min_pct = float(_cfg(cfg, "REJECTION_WICK_PCT"))
    sl_buf = atr * float(_cfg(cfg, "SL_ATR_MULT"))
    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    trend_filter = _cfg(cfg, "TREND_FILTER")
    candles = list(rates[-4:-1])

    # ── SELL: sweep swing_high (false breakout ขึ้น) แล้วปิดกลับเข้ากรอบ → reversal ลง ──
    upper_wick = bh - max(bo, bc)
    if (
        bh > swing_high + pierce_min
        and bc < swing_high
        and upper_wick / bar_range >= rej_min_pct
        and rsi >= float(_cfg(cfg, "RSI_OVERBOUGHT"))
    ):
        trend_ok = (
            trend_filter == "none"
            or (trend_filter == "against" and trend_up)   # sweep ขึ้นสวนเทรนด์ลงหลัก → SELL ตามเทรนด์หลัก
            or (trend_filter == "with" and trend_down)     # sweep ขึ้นเป็น pullback ในเทรนด์ลงหลัก
        )
        entry = round(bc, 2)
        sl = round(bh + sl_buf, 2)
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if trend_ok and 0 < risk <= max_risk_mult * atr and tp < entry:
            return {
                "signal":      "SELL",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 25 Liquidity Sweep Reversal 🔴 SELL",
                "reason": (
                    f"Sweep swing_high `{swing_high:.2f}` (high `{bh:.2f}`) แล้วปิดกลับ `{bc:.2f}` "
                    f"(wick {upper_wick/bar_range*100:.0f}% >= {rej_min_pct*100:.0f}%)\n"
                    f"RSI `{rsi:.1f}` overbought exhaustion | entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})"
                ),
                "order_mode":  "market",
                "entry_label": "SELL MARKET (Liquidity Sweep Reversal)",
                "candles":     candles,
                "sweep_bar_time": int(b["time"]),
                "swing_level": round(swing_high, 2),
                "rsi_at_signal": rsi,
                "atr_at_signal": atr,
            }

    # ── BUY: sweep swing_low (false breakout ลง) แล้วปิดกลับเข้ากรอบ → reversal ขึ้น ──
    lower_wick = min(bo, bc) - bl
    if (
        bl < swing_low - pierce_min
        and bc > swing_low
        and lower_wick / bar_range >= rej_min_pct
        and rsi <= float(_cfg(cfg, "RSI_OVERSOLD"))
    ):
        trend_ok = (
            trend_filter == "none"
            or (trend_filter == "against" and trend_down)  # sweep ลงสวนเทรนด์ขึ้นหลัก → BUY ตามเทรนด์หลัก
            or (trend_filter == "with" and trend_up)        # sweep ลงเป็น pullback ในเทรนด์ขึ้นหลัก
        )
        entry = round(bc, 2)
        sl = round(bl - sl_buf, 2)
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if trend_ok and 0 < risk <= max_risk_mult * atr and tp > entry:
            return {
                "signal":      "BUY",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 25 Liquidity Sweep Reversal 🟢 BUY",
                "reason": (
                    f"Sweep swing_low `{swing_low:.2f}` (low `{bl:.2f}`) แล้วปิดกลับ `{bc:.2f}` "
                    f"(wick {lower_wick/bar_range*100:.0f}% >= {rej_min_pct*100:.0f}%)\n"
                    f"RSI `{rsi:.1f}` oversold exhaustion | entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})"
                ),
                "order_mode":  "market",
                "entry_label": "BUY MARKET (Liquidity Sweep Reversal)",
                "candles":     candles,
                "sweep_bar_time": int(b["time"]),
                "swing_level": round(swing_low, 2),
                "rsi_at_signal": rsi,
                "atr_at_signal": atr,
            }

    return {"signal": "WAIT", "reason": "S25: ยังไม่พบ liquidity sweep + rejection ครบเงื่อนไข"}


def strategy_25(rates, tf: str = "", cfg: dict | None = None):
    """
    Wrapper runtime-style (dedup กันยิงรัว) — เก็บไว้เผื่ออนาคต
    ⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียกฟังก์ชันนี้ — standalone จริง
    """
    result = detect_s25(rates, tf=tf, dt_bkk=None, cfg=cfg)
    sig = result.get("signal")
    if sig not in ("BUY", "SELL"):
        return result

    bar_time = int(result.get("sweep_bar_time", 0))
    if _s25_last_fire.get((tf, sig)) == bar_time:
        return {"signal": "WAIT", "reason": "S25: fire แท่งนี้ไปแล้ว (dedup)"}
    _s25_last_fire[(tf, sig)] = bar_time
    return result
