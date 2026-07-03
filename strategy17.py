"""
strategy17.py — S17 Sweep Sniper (Triple-Confluence Mean Reversion)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
เป้าหมาย: win rate สูง (engineered) — TP สั้นมาก + filter ซ้อน 4 ชั้น
⚠️ win rate สูงมาจาก TP สั้น/SL กว้าง (RR ต่ำ) — 1 SL กิน TP หลายไม้
   ต้องคุม risk ด้วย SL Guard + lot เล็ก ห้ามเข้าใจว่าการันตีกำไร

แนวคิด (4 ชั้น confluence):
  1. Liquidity Sweep: แท่ง signal ไส้ทะลุ low/high ของกรอบ lookback
       แต่ "เปิดในกรอบ + ปิดกลับเข้ากรอบ" (stop hunt แล้วราคาปฏิเสธ)
       — เช็ค open ด้วยเสมอ (บทเรียน sweep_filter bugfix 05/06/2026)
  2. Rejection Wick: ไส้ฝั่ง sweep ≥ S17_WICK_MIN_PCT ของ range แท่ง
  3. RSI Extreme: RSI ที่แท่ง signal ≤ S17_RSI_BUY_MAX (BUY)
       หรือ ≥ S17_RSI_SELL_MIN (SELL)
  4. PD Fibo Zone: close ของแท่ง signal อยู่ Discount (<38.2%) สำหรับ BUY
       / Premium (>61.8%) สำหรับ SELL ของกรอบ lookback
       (filter แบบเดียวกับที่พิสูจน์แล้ว +$534 ใน PD Fibo Plus)
  + Session Filter: เทรดเฉพาะ Killzones London/NY (S17_SESSIONS)

Entry/Exit (default จาก backtest 30+60 วัน 03-06/2026 — sim_s17_backtest.py):
  - Entry: LIMIT รอ retrace 61.8% ของแท่ง sweep (S17_ENTRY_MODE="limit_618")
           ไม่ fill ใน S17_LIMIT_CANCEL_BARS แท่ง → cancel (กลไก cancel_bars กลาง)
  - TP   : entry ± 0.3 × ATR  (สั้นมาก — โอกาสโดนสูง)
  - SL   : ใต้/เหนือไส้ sweep ∓ 1.0 × ATR (S17_SL_ATR_BUFFER ของตัวเอง
            — ไม่ใช้ SL_BUFFER กลาง 2×ATR เพราะ backtest แสดงว่ากว้างเกิน)
  - guard: risk ต้องไม่เกิน S17_MAX_RISK_ATR_MULT × ATR
  - **เฉพาะ M1** (S17_ALLOWED_TFS) — backtest ชัดเจนว่า M5/M15 ขาดทุน

ผล backtest (M1, KZ London/NY, spread $0.20/ไม้, lot 0.01):
  - 30 วัน: n=146, WR 92.5%, P/L +$42.96, แพ้ติดกันสูงสุด 1 ไม้
  - 60 วัน: n=248, WR 91.1%, P/L +$78.90, แพ้ติดกันสูงสุด 2 ไม้
  - stress spread $0.35: ยังกำไร +$21.06 (WR 89.0%)

Standalone — bypass trend filter / recheck กลางทั้งหมด (เหมือน S14/S15/S16)
comment: <TF>_S17_SNB / <TF>_S17_SNS
"""

from datetime import time

import config
from mt5_utils import calc_atr

# ── dedup state (in-memory — ไม่ persist ข้าม restart) ──────────────
# (tf, side) → sweep bar time ที่ fire ล่าสุด: กัน re-fire ระหว่างรอบ scan 5s
_s17_last_fire: dict = {}
# (tf, side, level ปัด 1 ตำแหน่ง) → sweep bar time: กันยิงซ้ำ level เดิม
_s17_level_fired: dict = {}

_TF_SECS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}


def _calc_rsi(rates, period=14):
    """RSI แบบ Wilder's smoothing (เหมือน strategy15) — ใช้ close ของ rates ที่ส่งมา"""
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


def _in_session(dt_bkk) -> bool:
    """เช็คว่าเวลา BKK อยู่ใน S17_SESSIONS หรือไม่"""
    if not getattr(config, "S17_SESSION_FILTER", True):
        return True
    cur = dt_bkk.time()
    for start_str, end_str in getattr(
        config, "S17_SESSIONS", [("14:00", "18:00"), ("19:00", "23:00")]
    ):
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        if time(sh, sm) <= cur < time(eh, em):
            return True
    return False


def detect_s17(rates, tf: str = "", dt_bkk=None):
    """
    Pure detection — ไม่แตะ dedup state (backtest เรียกตรงได้)
    rates: แท่งสุดท้าย = แท่งกำลังวิ่ง, rates[-2] = แท่ง signal (ปิดแล้ว)
    dt_bkk: เวลา BKK สำหรับ session filter (backtest ส่งเวลาแท่งมาได้)
    คืน dict {signal: BUY/SELL/WAIT, ...} แบบเดียวกับ strategy อื่น
    """
    lookback = int(getattr(config, "S17_LOOKBACK", 60))
    if rates is None or len(rates) < lookback + 3:
        return {"signal": "WAIT", "reason": f"S17: ข้อมูลไม่พอ (ต้องการ ≥ {lookback + 3} แท่ง)"}

    if dt_bkk is not None and not _in_session(dt_bkk):
        return {"signal": "WAIT", "reason": "S17: อยู่นอกช่วง Killzones London/NY"}

    b = rates[-2]                      # แท่ง signal (ปิดแล้ว)
    window = rates[-(lookback + 2):-2]  # กรอบอ้างอิงก่อนแท่ง signal
    win_low = min(float(r["low"]) for r in window)
    win_high = max(float(r["high"]) for r in window)
    rng = win_high - win_low
    if rng <= 0:
        return {"signal": "WAIT", "reason": "S17: กรอบ lookback แบนผิดปกติ"}

    bo, bh, bl, bc = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
    bar_range = bh - bl
    if bar_range <= 0:
        return {"signal": "WAIT", "reason": "S17: แท่ง signal ไม่มี range"}

    atr = calc_atr(rates[:-1], 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S17: คำนวณ ATR ไม่ได้"}

    rsi = _calc_rsi(rates[:-1], int(getattr(config, "S17_RSI_PERIOD", 14)))
    if rsi is None:
        return {"signal": "WAIT", "reason": "S17: คำนวณ RSI ไม่ได้"}

    wick_min = float(getattr(config, "S17_WICK_MIN_PCT", 0.50))
    tp_mult = float(getattr(config, "S17_TP_ATR_MULT", 0.5))
    max_risk_mult = float(getattr(config, "S17_MAX_RISK_ATR_MULT", 4.0))
    pd_filter = bool(getattr(config, "S17_PD_FILTER", True))
    rsi_buy_max = float(getattr(config, "S17_RSI_BUY_MAX", 32))
    rsi_sell_min = float(getattr(config, "S17_RSI_SELL_MIN", 68))

    fib_382 = win_low + rng * 0.382
    fib_618 = win_low + rng * 0.618
    cur_price = float(rates[-1]["close"])
    sl_buf = atr * float(getattr(config, "S17_SL_ATR_BUFFER", 0.5))
    candles = list(rates[-4:-1])

    # ── Trend filter (EMA slope): ช้อนเฉพาะ dip ตามเทรนด์ใหญ่ ─────────
    # BUY เฉพาะ EMA กำลังขึ้น / SELL เฉพาะ EMA กำลังลง (slope ย้อน N แท่ง)
    trend_buy_ok = trend_sell_ok = True
    if bool(getattr(config, "S17_TREND_FILTER", False)):
        ema_period = int(getattr(config, "S17_TREND_EMA", 50))
        slope_bars = int(getattr(config, "S17_TREND_SLOPE_BARS", 10))
        closes = [float(r["close"]) for r in rates[:-1]]
        if len(closes) >= ema_period + slope_bars:
            k = 2.0 / (ema_period + 1.0)
            ema = closes[0]
            ema_hist = []
            for c in closes:
                ema = c * k + ema * (1.0 - k)
                ema_hist.append(ema)
            ema_now = ema_hist[-1]
            ema_prev = ema_hist[-1 - slope_bars]
            trend_buy_ok = ema_now > ema_prev
            trend_sell_ok = ema_now < ema_prev

    entry_mode = str(getattr(config, "S17_ENTRY_MODE", "limit_50"))

    # ── BUY: sweep ใต้กรอบ + ปฏิเสธกลับขึ้น ─────────────────────────
    lower_wick = min(bo, bc) - bl
    if (
        bl < win_low                       # ไส้ทะลุ low กรอบ
        and bo > win_low and bc > win_low  # เปิดในกรอบ + ปิดกลับเข้ากรอบ
        and lower_wick / bar_range >= wick_min
        and rsi <= rsi_buy_max
        and (not pd_filter or bc <= fib_382)
        and trend_buy_ok
    ):
        if entry_mode == "limit_786":
            entry = round(bl + bar_range * 0.214, 2)  # LIMIT รอ retrace 78.6% (ลึกสุด)
            order_mode, entry_label = "limit", "BUY LIMIT (Sweep Sniper 78.6%)"
        elif entry_mode == "limit_618":
            entry = round(bl + bar_range * 0.382, 2)  # LIMIT รอ retrace 61.8% (ลึก)
            order_mode, entry_label = "limit", "BUY LIMIT (Sweep Sniper 61.8%)"
        elif entry_mode == "limit_50":
            entry = round((bh + bl) / 2.0, 2)   # LIMIT รอ retrace 50% ของแท่ง sweep
            order_mode, entry_label = "limit", "BUY LIMIT (Sweep Sniper 50%)"
        else:
            entry = round(cur_price, 2)
            order_mode, entry_label = "market", "BUY MARKET (Sweep Sniper)"
        sl = round(bl - sl_buf, 2)
        tp = round(entry + tp_mult * atr, 2)
        risk = entry - sl
        if (
            0 < risk <= max_risk_mult * atr and tp > entry
            and (order_mode != "limit" or cur_price > entry)
        ):
            return {
                "signal":      "BUY",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 17 Sweep Sniper 🟢 BUY",
                "reason": (
                    f"Sweep Low กรอบ {lookback} แท่ง: L=`{bl:.2f}` < ref=`{win_low:.2f}` "
                    f"(เปิด/ปิดกลับในกรอบ)\n"
                    f"Wick: `{lower_wick / bar_range * 100:.0f}%` ≥ {wick_min * 100:.0f}% | "
                    f"RSI: `{rsi:.1f}` ≤ {rsi_buy_max:.0f}\n"
                    f"PD: close `{bc:.2f}` ใน Discount (<38.2%=`{fib_382:.2f}`)\n"
                    f"TP สั้น `{tp_mult}`×ATR(`{atr:.2f}`) | SL ใต้ไส้ sweep"
                ),
                "order_mode":  order_mode,
                "entry_label": entry_label,
                "candles":     candles,
                "cancel_bars": int(getattr(config, "S17_LIMIT_CANCEL_BARS", 5)) if order_mode == "limit" else 0,
                "sweep_level": round(win_low, 2),
                "sweep_bar_time": int(b["time"]),
                "rsi_at_signal": rsi,
            }

    # ── SELL: sweep เหนือกรอบ + ปฏิเสธกลับลง ────────────────────────
    upper_wick = bh - max(bo, bc)
    if (
        bh > win_high
        and bo < win_high and bc < win_high
        and upper_wick / bar_range >= wick_min
        and rsi >= rsi_sell_min
        and (not pd_filter or bc >= fib_618)
        and trend_sell_ok
    ):
        if entry_mode == "limit_786":
            entry = round(bh - bar_range * 0.214, 2)  # LIMIT รอ retrace 78.6% (ลึกสุด)
            order_mode, entry_label = "limit", "SELL LIMIT (Sweep Sniper 78.6%)"
        elif entry_mode == "limit_618":
            entry = round(bh - bar_range * 0.382, 2)  # LIMIT รอ retrace 61.8% (ลึก)
            order_mode, entry_label = "limit", "SELL LIMIT (Sweep Sniper 61.8%)"
        elif entry_mode == "limit_50":
            entry = round((bh + bl) / 2.0, 2)   # LIMIT รอ retrace 50% ของแท่ง sweep
            order_mode, entry_label = "limit", "SELL LIMIT (Sweep Sniper 50%)"
        else:
            entry = round(cur_price, 2)
            order_mode, entry_label = "market", "SELL MARKET (Sweep Sniper)"
        sl = round(bh + sl_buf, 2)
        tp = round(entry - tp_mult * atr, 2)
        risk = sl - entry
        if (
            0 < risk <= max_risk_mult * atr and tp < entry
            and (order_mode != "limit" or cur_price < entry)
        ):
            return {
                "signal":      "SELL",
                "entry":       entry,
                "sl":          sl,
                "tp":          tp,
                "pattern":     "ท่าที่ 17 Sweep Sniper 🔴 SELL",
                "reason": (
                    f"Sweep High กรอบ {lookback} แท่ง: H=`{bh:.2f}` > ref=`{win_high:.2f}` "
                    f"(เปิด/ปิดกลับในกรอบ)\n"
                    f"Wick: `{upper_wick / bar_range * 100:.0f}%` ≥ {wick_min * 100:.0f}% | "
                    f"RSI: `{rsi:.1f}` ≥ {rsi_sell_min:.0f}\n"
                    f"PD: close `{bc:.2f}` ใน Premium (>61.8%=`{fib_618:.2f}`)\n"
                    f"TP สั้น `{tp_mult}`×ATR(`{atr:.2f}`) | SL เหนือไส้ sweep"
                ),
                "order_mode":  order_mode,
                "entry_label": entry_label,
                "candles":     candles,
                "cancel_bars": int(getattr(config, "S17_LIMIT_CANCEL_BARS", 5)) if order_mode == "limit" else 0,
                "sweep_level": round(win_high, 2),
                "sweep_bar_time": int(b["time"]),
                "rsi_at_signal": rsi,
            }

    return {"signal": "WAIT", "reason": "S17: ยังไม่พบ sweep + wick + RSI extreme ครบเงื่อนไข"}


def _s17_compound_multiplier(entry: float, sl: float) -> float:
    """คำนวณ quant_lot_multiplier แบบ S20.12: lot = balance × risk% / (ระยะ SL × contract)
    คืน multiplier เทียบ base lot (get_volume) — 1.0 เมื่อปิด compounding หรือข้อมูลไม่พอ
    เรียกเฉพาะ runtime (ไม่อยู่ใน detect_s17 → backtest จำลอง compounding เองใน sim)
    """
    if not getattr(config, "S17_COMPOUNDING_ENABLED", False):
        return 1.0
    try:
        import MetaTrader5 as mt5
        acc = mt5.account_info()
        sym = mt5.symbol_info(config.SYMBOL)
        if acc is None or sym is None:
            return 1.0
        sl_dist = abs(round(float(entry), 2) - round(float(sl), 2))
        if sl_dist <= 0:
            return 1.0
        contract_size = float(getattr(sym, "trade_contract_size", 100.0) or 100.0)
        risk_usd = float(acc.balance) * (float(getattr(config, "S17_RISK_PCT", 2.0)) / 100.0)
        calculated_lot = risk_usd / (sl_dist * contract_size)
        max_lot = float(getattr(config, "S17_MAX_LOT", 50.0))
        target_lot = max(0.01, min(round(calculated_lot, 2), max_lot))
        base_lot = config.get_volume()
        if base_lot > 0:
            return target_lot / base_lot
    except Exception:
        pass
    return 1.0


def strategy_17(rates, tf: str = ""):
    """
    S17: Sweep Sniper — wrapper runtime (TF gate + dedup + session ด้วยเวลาปัจจุบัน)
    """
    allowed_tfs = getattr(config, "S17_ALLOWED_TFS", ["M1"])
    if allowed_tfs and tf not in allowed_tfs:
        return {"signal": "WAIT", "reason": f"S17: ใช้เฉพาะ TF {','.join(allowed_tfs)} (backtest: TF อื่นขาดทุน)"}

    result = detect_s17(rates, tf=tf, dt_bkk=config.now_bkk())
    sig = result.get("signal")
    if sig not in ("BUY", "SELL"):
        return result

    bar_time = int(result.get("sweep_bar_time", 0))
    level = float(result.get("sweep_level", 0.0))

    # กัน re-fire แท่งเดิมระหว่างรอบ scan (scanner วนทุก 5 วินาที)
    if _s17_last_fire.get((tf, sig)) == bar_time:
        return {"signal": "WAIT", "reason": "S17: fire แท่งนี้ไปแล้ว (dedup)"}

    # กันยิงซ้ำ level เดิมภายใน S17_LEVEL_COOLDOWN_BARS แท่ง
    cooldown_bars = int(getattr(config, "S17_LEVEL_COOLDOWN_BARS", 20))
    tf_secs = _TF_SECS.get(tf, 60)
    lv_key = (tf, sig, round(level, 1))
    last_lv_time = _s17_level_fired.get(lv_key, 0)
    if last_lv_time and (bar_time - last_lv_time) < cooldown_bars * tf_secs:
        return {"signal": "WAIT", "reason": f"S17: level `{level:.1f}` อยู่ใน cooldown {cooldown_bars} แท่ง"}

    _s17_last_fire[(tf, sig)] = bar_time
    _s17_level_fired[lv_key] = bar_time
    # Compounding (แบบ S20.12): scanner คูณ base lot ด้วย quant_lot_multiplier ตอน place order
    result["quant_lot_multiplier"] = _s17_compound_multiplier(result["entry"], result["sl"])
    return result
