"""
strategy28.py — S28 Asian Range Liquidity Sweep + Session Breakout (RESEARCH / BACKTEST-ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py / trailing.py / main.py
   ไม่มี config.active_strategies[28], ไม่มี wiring เข้า live trading ใดๆ
   ใช้คู่กับ sim_s28_backtest.py / optimize_s28.py เพื่อ backtest เท่านั้น

แนวคิด: Asian Session (02:00-09:00 BKK = 01:00-08:00 chart) สร้าง liquidity pool
(retail stops สะสมเหนือ High / ใต้ Low ของ range) — เมื่อ London/NY session เปิด
institutional players มักจะ "sweep" liquidity เหล่านี้ก่อน (fakeout ทะลุ range แล้ว
กลับตัว) แล้วจึงวิ่งทิศจริง → เราเข้า reversal หลัง sweep

ท่าหลักที่ Lock (กฎข้อ 1 — entry mechanism เดียวตลอดทั้งกริด):
  "Asian Range Liquidity Sweep Reversal" — ตรวจจับ sweep ที่:
  1. ราคา wick เกิน Asian H/L อย่างน้อย SWEEP_MIN_ATR × ATR
  2. Body ปิดกลับข้ามเข้า range (หรืออย่างน้อย > BODY_REVERSAL_PCT ของ candle range)
  3. Optional confirmations: RSI divergence, Volume spike, momentum filter

Entry/Exit:
  - Entry: MARKET ที่ open ของแท่งถัดจากแท่ง sweep (กัน look-ahead)
  - SL: จุดสุดของ sweep wick + ATR buffer
  - TP: entry ∓ RR × risk distance

Session timing (BKK UTC+7):
  - Asian range build: ASIAN_START - ASIAN_END (default 02:00-09:00)
  - Trade window: TRADE_START - TRADE_END (default 14:00-23:00)
"""

S28_DEFAULTS = {
    # ── Asian Range Definition ──
    "ASIAN_START_H": 2,   # BKK hour start for Asian range
    "ASIAN_START_M": 0,
    "ASIAN_END_H": 9,     # BKK hour end for Asian range
    "ASIAN_END_M": 0,

    # ── Trade Window ──
    "TRADE_START_H": 11,  # BKK hour start trading (London open = 14:00, pre-London = 11:00)
    "TRADE_START_M": 0,
    "TRADE_END_H": 23,    # BKK hour end trading
    "TRADE_END_M": 0,

    # ── Sweep Detection ──
    "SWEEP_MIN_ATR": 0.02,        # min wick เกิน range ที่ = sweep (× ATR) — เปิดกว้างมาก
    "SWEEP_MAX_ATR": 5.0,         # max wick เกิน range (> นี้ = breakout จริง ไม่ใช่ sweep)
    "BODY_REVERSAL_PCT": 0.3,     # body ต้องกลับมา >= N% ของ candle range
    "MIN_RANGE_ATR": 0.3,         # Asian range ต้อง >= N × ATR (กันวันที่ range เล็กเกิน)
    "MAX_RANGE_ATR": 20.0,        # Asian range ต้อง <= N × ATR (เปิดกว้างมาก)

    # ── Entry/Exit ──
    "SL_ATR_MULT": 0.3,           # SL buffer เพิ่มเติมจาก sweep extreme (× ATR)
    "TP_RR": 2.0,                 # TP = entry ± RR × risk_distance
    "MAX_RISK_ATR_MULT": 8.0,     # risk distance max ที่ยอมรับ (เปิดกว้าง)

    # ── Risk ──
    "RISK_PCT": 2.0,              # % ของ equity ต่อไม้

    # ── Optional Filters ──
    "RSI_FILTER": False,          # ใช้ RSI confirmation
    "RSI_PERIOD": 14,
    "RSI_OB": 70,                 # overbought (sweep high → SELL ต้อง RSI >= RSI_OB)
    "RSI_OS": 30,                 # oversold (sweep low → BUY ต้อง RSI <= RSI_OS)

    "MOMENTUM_FILTER": False,     # ใช้ momentum filter (candle body vs ATR)
    "MOM_BODY_ATR": 0.5,          # sweep candle body ต้อง >= N × ATR

    "VOLUME_FILTER": False,       # ใช้ volume filter
    "VOL_MULT": 1.5,              # sweep bar volume ต้อง >= N × avg volume

    "ATR_REGIME_FILTER": False,   # ใช้ ATR regime filter
    "ATR_REGIME_MIN": 0.5,        # ATR period ≥ N (กัน low vol)

    "EMA_TREND_FILTER": False,    # Edge Improvement #1: EMA trend filter
    "EMA_TREND_PERIOD": 200,      # EMA period สำหรับ trend filter

    "SL_COOLDOWN": False,         # Edge Improvement #2: หยุดเทรดฝั่งเดียวกันหลัง SL hit
    "SL_COOLDOWN_COUNT": 2,       # หยุดหลัง N ครั้ง SL hit ติดต่อกัน
    "SL_COOLDOWN_BARS": 30,       # cooldown N bars ก่อนเปิดฝั่งเดิมอีกครั้ง

    # ── Multi-entry ──
    "MAX_TRADES_PER_DAY": 10,     # max trades ต่อวัน
    "MIN_GAP_BARS": 2,            # ขั้นต่ำระหว่าง entry (bars)

    # ── ATR ──
    "ATR_PERIOD": 14,
}


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S28_DEFAULTS[key]


def calc_atr(rates, period=14):
    """ATR ของ rates (ใช้แท่ง 0..n-1 ไม่ lookahead)"""
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


def _rsi_at(closes, period=14):
    """RSI ของ closes ล่าสุด"""
    n = len(closes)
    if n < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, n):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def detect_sweep(asian_high, asian_low, bar, atr, cfg):
    """
    ตรวจจับ sweep ของ Asian range บนแท่งเดียว
    Returns: ("BUY"|"SELL", sweep_extreme) or None
    """
    bo = float(bar["open"]); bh = float(bar["high"])
    bl = float(bar["low"]); bc = float(bar["close"])
    body = abs(bc - bo)
    candle_range = bh - bl
    if candle_range <= 0 or atr <= 0:
        return None

    sweep_min = float(_cfg(cfg, "SWEEP_MIN_ATR")) * atr
    sweep_max = float(_cfg(cfg, "SWEEP_MAX_ATR")) * atr
    body_rev_pct = float(_cfg(cfg, "BODY_REVERSAL_PCT"))

    # ── Sweep HIGH (wick above Asian High) → potential SELL ──
    wick_above = bh - asian_high
    if wick_above >= sweep_min and wick_above <= sweep_max:
        # Body ต้องปิดกลับมาต่ำกว่า Asian High (bearish reversal)
        if bc < asian_high and bc < bo:  # bearish candle ปิดใต้ Asian High
            body_ratio = body / candle_range if candle_range > 0 else 0
            if body_ratio >= body_rev_pct:
                return ("SELL", bh)

    # ── Sweep LOW (wick below Asian Low) → potential BUY ──
    wick_below = asian_low - bl
    if wick_below >= sweep_min and wick_below <= sweep_max:
        # Body ต้องปิดกลับมาสูงกว่า Asian Low (bullish reversal)
        if bc > asian_low and bc > bo:  # bullish candle ปิดเหนือ Asian Low
            body_ratio = body / candle_range if candle_range > 0 else 0
            if body_ratio >= body_rev_pct:
                return ("BUY", bl)

    return None


def detect_s28(rates, asian_high, asian_low, asian_range_atr, atr, dt_bkk=None, cfg=None,
               rsi_closes=None, volumes=None, avg_volume=None, ema_value=None):
    """
    Pure detection สำหรับ backtest
    rates: window ล่าสุด, rates[-2] = signal candidate (ปิดแล้ว), rates[-1] = แท่งกำลังวิ่ง
    asian_high/low: H/L ของ Asian range วันนี้
    atr: ATR ปัจจุบัน
    ema_value: EMA ปัจจุบันสำหรับ trend filter (optional)
    Returns: dict {signal, entry, sl, tp, ...}
    """
    if rates is None or len(rates) < 3:
        return {"signal": "WAIT", "reason": "S28: ข้อมูลไม่พอ"}

    if asian_high is None or asian_low is None:
        return {"signal": "WAIT", "reason": "S28: ยังไม่มี Asian range"}

    asian_range = asian_high - asian_low
    if asian_range <= 0:
        return {"signal": "WAIT", "reason": "S28: Asian range <= 0"}

    # Check Asian range size
    min_range = float(_cfg(cfg, "MIN_RANGE_ATR")) * atr
    max_range = float(_cfg(cfg, "MAX_RANGE_ATR")) * atr
    if asian_range < min_range:
        return {"signal": "WAIT", "reason": f"S28: Asian range ({asian_range:.2f}) < min ({min_range:.2f})"}
    if asian_range > max_range:
        return {"signal": "WAIT", "reason": f"S28: Asian range ({asian_range:.2f}) > max ({max_range:.2f})"}

    # Check trade window
    if dt_bkk is not None:
        h, m = dt_bkk.hour, dt_bkk.minute
        cur_min = h * 60 + m
        trade_start = int(_cfg(cfg, "TRADE_START_H")) * 60 + int(_cfg(cfg, "TRADE_START_M"))
        trade_end = int(_cfg(cfg, "TRADE_END_H")) * 60 + int(_cfg(cfg, "TRADE_END_M"))
        if not (trade_start <= cur_min < trade_end):
            return {"signal": "WAIT", "reason": "S28: นอก trade window"}

    # Signal candle = rates[-2] (ปิดแล้ว)
    sig_bar = rates[-2]
    sweep = detect_sweep(asian_high, asian_low, sig_bar, atr, cfg)
    if sweep is None:
        return {"signal": "WAIT", "reason": "S28: ไม่พบ sweep pattern"}

    direction, sweep_extreme = sweep

    # ── Optional Filters ──
    if bool(_cfg(cfg, "RSI_FILTER")) and rsi_closes is not None:
        rsi = _rsi_at(rsi_closes, int(_cfg(cfg, "RSI_PERIOD")))
        if direction == "SELL" and rsi < float(_cfg(cfg, "RSI_OB")):
            return {"signal": "WAIT", "reason": f"S28: RSI ({rsi:.1f}) < OB ({_cfg(cfg, 'RSI_OB')})"}
        if direction == "BUY" and rsi > float(_cfg(cfg, "RSI_OS")):
            return {"signal": "WAIT", "reason": f"S28: RSI ({rsi:.1f}) > OS ({_cfg(cfg, 'RSI_OS')})"}

    if bool(_cfg(cfg, "MOMENTUM_FILTER")):
        body = abs(float(sig_bar["close"]) - float(sig_bar["open"]))
        if body < float(_cfg(cfg, "MOM_BODY_ATR")) * atr:
            return {"signal": "WAIT", "reason": "S28: momentum body ไม่พอ"}

    if bool(_cfg(cfg, "VOLUME_FILTER")) and volumes is not None and avg_volume is not None and avg_volume > 0:
        sig_vol = volumes[-2] if len(volumes) >= 2 else 0
        if sig_vol < float(_cfg(cfg, "VOL_MULT")) * avg_volume:
            return {"signal": "WAIT", "reason": "S28: volume ไม่พอ"}

    if bool(_cfg(cfg, "ATR_REGIME_FILTER")):
        if atr < float(_cfg(cfg, "ATR_REGIME_MIN")):
            return {"signal": "WAIT", "reason": "S28: ATR regime ต่ำเกินไป"}

    # ── Edge Improvement #1: EMA Trend Filter ──
    if bool(_cfg(cfg, "EMA_TREND_FILTER")) and ema_value is not None:
        price_now = float(rates[-2]["close"])
        if direction == "BUY" and price_now < ema_value:
            return {"signal": "WAIT", "reason": f"S28: EMA trend filter — price ({price_now:.2f}) < EMA ({ema_value:.2f}), BUY blocked"}
        if direction == "SELL" and price_now > ema_value:
            return {"signal": "WAIT", "reason": f"S28: EMA trend filter — price ({price_now:.2f}) > EMA ({ema_value:.2f}), SELL blocked"}

    # ── Compute entry, SL, TP ──
    entry = float(rates[-1]["open"])  # entry ที่ open แท่งถัดไป (กัน look-ahead)
    sl_buf = float(_cfg(cfg, "SL_ATR_MULT")) * atr
    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))

    if direction == "BUY":
        sl = round(sweep_extreme - sl_buf, 2)
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S28: risk ผิดปกติ (BUY)"}
    else:  # SELL
        sl = round(sweep_extreme + sl_buf, 2)
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S28: risk ผิดปกติ (SELL)"}

    return {
        "signal": direction,
        "entry": round(entry, 2),
        "sl": sl,
        "tp": tp,
        "pattern": f"S28 AsianSweep {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": (f"Asian range H={asian_high:.2f} L={asian_low:.2f} "
                   f"sweep_extreme={sweep_extreme:.2f}\n"
                   f"entry {entry:.2f} SL {sl:.2f} TP {tp:.2f} (RR {rr})"),
        "order_mode": "market",
        "entry_label": f"{direction} MARKET (S28 AsianSweep)",
        "signal_bar_time": int(sig_bar["time"]),
        "atr_at_signal": atr,
        "asian_high": asian_high,
        "asian_low": asian_low,
        "sweep_extreme": sweep_extreme,
    }
