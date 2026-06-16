"""
strategy20.py — S20 All in 4s (Reversal & Retracement)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sub-patterns:
  S20.1: Classic — กลับตัวสมบูรณ์ เนื้อคลุมเนื้อ (body engulf body, 2 แท่ง)
  S20.2: Tainted — กลับตัวแบบมีตำหนิ แท่ง 1 คลุมไม่มิด ต้องใช้แท่ง 3 คอนเฟิร์ม
  S20.3: HTF Fibo — อิงสวิงของ H1 (ราคาอยู่ใน Fibo 50-78.6%)
  S20.4: FVG Bounce — เด้งจากโซน FVG เก่า
  S20.5: Sideway Trap — กวาด High/Low (Liquidity Sweep) แล้วกลับตัว

Entry: ย่อ 50% ของ body แท่ง confirm (Limit Order)
TP:    Fibo 161.8% ของสวิงชุดกลับตัว
SL:    ไส้ extreme + ATR buffer

Filters (WR improvement):
  - Body Size Filter: engulf bar body ≥ S20_MIN_BODY_ATR_PCT × ATR
  - Session Filter: เทรดเฉพาะ Killzones (London/NY)
  - Trend Filter: HHLL structure alignment (ไม่เข้าสวน strong trend)
"""

from datetime import time

import config
import hhll_swing
from mt5_utils import calc_atr


# ──────────────────────────────────────────────────────────────────────
# Helper: FVG detection (for S20.4)
# ──────────────────────────────────────────────────────────────────────

def _get_recent_fvg(rates, signal: str):
    """
    Find the most recent FVG that hasn't been completely filled.
    BUY signal needs Bullish FVG (Demand): L3 > H1.
    SELL signal needs Bearish FVG (Supply): H3 < L1.
    """
    # Check last 20 candles
    n = len(rates)
    for i in range(n - 4, max(-1, n - 20), -1):
        c1, c2, c3 = rates[i], rates[i+1], rates[i+2]
        if signal == "BUY":
            if c3['low'] > c1['high']:  # Bullish FVG
                # Check if it was filled by subsequent candles
                filled = False
                for j in range(i+3, n):
                    if rates[j]['low'] <= c1['high']:
                        filled = True
                        break
                if not filled:
                    return (c1['high'], c3['low']) # FVG Top, FVG Bot
        else:
            if c3['high'] < c1['low']:  # Bearish FVG
                filled = False
                for j in range(i+3, n):
                    if rates[j]['high'] >= c1['low']:
                        filled = True
                        break
                if not filled:
                    return (c3['high'], c1['low']) # FVG Top, FVG Bot
    return None


# ──────────────────────────────────────────────────────────────────────
# Helper: Sideway Trap detection (for S20.5)
# ──────────────────────────────────────────────────────────────────────

def _is_sideway_trap(rates, signal: str):
    """
    Detect if the recent price action swept a local High/Low and reversed.
    For BUY: Swept a local Low, then reversed up (ปิดกลับเหนือ local low).
    For SELL: Swept a local High, then reversed down (ปิดกลับใต้ local high).
    """
    n = len(rates)
    lookback = max(10, min(n - 3, 15))  # ขยาย lookback สำหรับ M1 ที่ต้องการ context กว้างขึ้น
    if n < lookback + 3:
        return False

    sweep_bar = rates[-2]  # แท่งที่เกิด sweep (ปิดแล้ว)
    confirm_bar = rates[-1]  # แท่งยืนยัน

    if signal == "BUY":
        # หา local low จาก lookback window (ไม่รวม 2 แท่งสุดท้าย)
        local_lows = [rates[i]['low'] for i in range(n - lookback, n - 3)]
        if not local_lows:
            return False
        min_local_low = min(local_lows)

        # Sweep: ไส้ทะลุต่ำกว่า local low
        swept = min(sweep_bar['low'], confirm_bar['low']) < min_local_low
        # Close back: ปิดกลับเหนือ local low (genuine trap, ไม่ใช่ breakdown)
        closed_back = confirm_bar['close'] > min_local_low

        return swept and closed_back
    else:
        local_highs = [rates[i]['high'] for i in range(n - lookback, n - 3)]
        if not local_highs:
            return False
        max_local_high = max(local_highs)

        swept = max(sweep_bar['high'], confirm_bar['high']) > max_local_high
        closed_back = confirm_bar['close'] < max_local_high

        return swept and closed_back


# ──────────────────────────────────────────────────────────────────────
# Helper: Session filter (for WR improvement)
# ──────────────────────────────────────────────────────────────────────

def _in_session(dt_bkk) -> bool:
    """เช็คว่าเวลา BKK อยู่ใน S20_SESSIONS หรือไม่"""
    if not getattr(config, "S20_SESSION_FILTER", False):
        return True
    if dt_bkk is None:
        return True
    cur = dt_bkk.time() if hasattr(dt_bkk, 'time') else dt_bkk
    for start_str, end_str in getattr(
        config, "S20_SESSIONS", [("14:00", "18:00"), ("19:00", "23:00")]
    ):
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        if time(sh, sm) <= cur < time(eh, em):
            return True
    return False


# ──────────────────────────────────────────────────────────────────────
# Helper: Trend filter via HHLL structure
# ──────────────────────────────────────────────────────────────────────

def _trend_allows(signal: str, tf: str) -> bool:
    """เช็คว่า HHLL trend ของ TF นี้ไม่สวนทาง signal
    - BUY ห้ามเข้าเมื่อ BEAR strong
    - SELL ห้ามเข้าเมื่อ BULL strong
    - SIDEWAY / UNKNOWN / weak = อนุญาต
    """
    if not getattr(config, "S20_TREND_FILTER", False):
        return True
    trend_info = hhll_swing.get_trend_from_structure(tf)
    if not trend_info:
        return True  # ไม่มีข้อมูล → อนุญาต
    trend = trend_info.get("trend", "UNKNOWN")
    strength = trend_info.get("strength", "")
    if signal == "BUY" and trend == "BEAR" and strength == "strong":
        return False
    if signal == "SELL" and trend == "BULL" and strength == "strong":
        return False
    return True


# ──────────────────────────────────────────────────────────────────────
# Main strategy function
# ──────────────────────────────────────────────────────────────────────

def strategy_20(rates, tf=None, dt_bkk=None):
    """
    Strategy 20: All in 4s Variants
    S20.1: Classic (2 bars body engulfing)
    S20.2: Tainted (3 bars delayed body engulfing)
    S20.3: HTF Fibo Alignment
    S20.4: FVG / OB Bounce
    S20.5: Sideway Trap (Liquidity Sweep)
    """
    res = {"signal": "WAIT", "reason": ""}

    if len(rates) < 4:
        res["reason"] = "Not enough data"
        return res

    if tf and tf not in config.S20_ALLOWED_TFS:
        res["reason"] = f"TF {tf} not allowed for S20"
        return res

    # ── Session Filter ─────────────────────────────────────────────
    if dt_bkk is not None and not _in_session(dt_bkk):
        res["reason"] = "S20: อยู่นอกช่วง Killzones"
        return res

    bar_prev2 = rates[-3]
    bar_prev1 = rates[-2]
    bar_curr  = rates[-1]

    # ── Bar color detection ───────────────────────────────────────
    is_red1 = bar_prev1['close'] < bar_prev1['open']      # prev1 = แดง
    is_green2 = bar_curr['close'] > bar_curr['open']        # curr = เขียว

    # --- S20.1 Classic: "เนื้อคลุมเนื้อ" (body engulf body) ---
    # BUY: แท่งแดง (มีไส้ล่าง = rejection) → แท่งเขียว body คลุม body แดง
    #   Red body: top=open, bot=close   Green body: top=close, bot=open
    classic_buy = (is_red1 and is_green2 and
                   bar_prev1['low'] < bar_prev1['close'] and       # มีไส้ล่าง (rejection wick)
                   bar_curr['open'] <= bar_prev1['close'] and      # green body_bot ≤ red body_bot
                   bar_curr['close'] >= bar_prev1['open'])          # green body_top ≥ red body_top

    # SELL: แท่งเขียว (มีไส้บน = rejection) → แท่งแดง body คลุม body เขียว
    #   Green body: top=close, bot=open   Red body: top=open, bot=close
    classic_sell = (not is_red1 and not is_green2 and
                    bar_prev1['high'] > bar_prev1['close'] and     # มีไส้บน (rejection wick)
                    bar_curr['open'] >= bar_prev1['close'] and     # red body_top ≥ green body_top
                    bar_curr['close'] <= bar_prev1['open'])         # red body_bot ≤ green body_bot

    # --- S20.2 Tainted: แท่ง 1 คลุมไม่มิด → แท่ง 2 คลุมสำเร็จ ---
    is_red_prev2 = bar_prev2['close'] < bar_prev2['open']
    is_green_prev1 = bar_prev1['close'] > bar_prev1['open']
    is_green_curr = bar_curr['close'] > bar_curr['open']

    # BUY tainted: prev2=แดง(rejection), prev1=เขียว(ยังคลุมไม่มิด), curr=เขียว(คลุมสำเร็จ)
    #   Red prev2: body_top=open, body_bot=close
    tainted_buy = (is_red_prev2 and is_green_prev1 and is_green_curr and
                   bar_prev2['low'] < bar_prev2['close'] and          # prev2 มีไส้ล่าง
                   bar_prev1['close'] <= bar_prev2['open'] and        # prev1 body ยังไม่คลุม prev2 body_top
                   bar_curr['close'] > bar_prev2['open'])              # curr body คลุม prev2 body_top สำเร็จ

    # SELL tainted: prev2=เขียว(rejection), prev1=แดง(ยังคลุมไม่มิด), curr=แดง(คลุมสำเร็จ)
    #   Green prev2: body_top=close, body_bot=open
    tainted_sell = (not is_red_prev2 and not is_green_prev1 and not is_green_curr and
                    bar_prev2['high'] > bar_prev2['close'] and        # prev2 มีไส้บน
                    bar_prev1['close'] >= bar_prev2['open'] and       # prev1 body ยังไม่คลุม prev2 body_bot
                    bar_curr['close'] < bar_prev2['open'])             # curr body คลุม prev2 body_bot สำเร็จ

    signal = None
    sub_pattern = None
    entry_bar = None
    ref_bar = None  # แท่งตั้งต้นที่ใช้อ้างอิง High/Low สำหรับ Fibo

    if classic_buy:
        signal = "BUY"
        sub_pattern = "S20.1"
        entry_bar = bar_curr
        ref_bar = bar_prev1
    elif classic_sell:
        signal = "SELL"
        sub_pattern = "S20.1"
        entry_bar = bar_curr
        ref_bar = bar_prev1
    elif tainted_buy:
        signal = "BUY"
        sub_pattern = "S20.2"
        entry_bar = bar_curr
        ref_bar = bar_prev2
    elif tainted_sell:
        signal = "SELL"
        sub_pattern = "S20.2"
        entry_bar = bar_curr
        ref_bar = bar_prev2

    if not signal:
        return res

    # ── Body Size Filter: กรอง engulf ที่เล็กเกินไป (noise) ─────────
    min_body_pct = float(getattr(config, "S20_MIN_BODY_ATR_PCT", 0.3))
    if min_body_pct > 0 and len(rates) >= 16:
        atr = calc_atr(rates[:-1], 14)
        if atr and atr > 0:
            body_size = abs(entry_bar['close'] - entry_bar['open'])
            if body_size < min_body_pct * atr:
                res["reason"] = f"S20: body ({body_size:.2f}) < {min_body_pct}×ATR ({min_body_pct * atr:.2f})"
                return res

    # ── Trend Filter: ห้ามเข้าสวน strong trend ──────────────────────
    if tf and not _trend_allows(signal, tf):
        res["reason"] = f"S20: {signal} blocked by strong counter-trend [{tf}]"
        return res

    # ── Check for S20.3, S20.4, S20.5 enhancements ────────────────
    # ถ้า classic/tainted pattern match → เช็คว่ามี confluence เพิ่มเติมไหม

    # 1. Check Sideway Trap (S20.5)
    if _is_sideway_trap(rates, signal):
        sub_pattern = "S20.5"

    # 2. Check FVG Bounce (S20.4)
    fvg_zone = _get_recent_fvg(rates, signal)
    if fvg_zone:
        # FVG Zone (Top, Bot)
        # If the entry_bar low/high touched the FVG, it's a bounce
        if signal == "BUY" and entry_bar['low'] <= fvg_zone[0] and entry_bar['low'] >= fvg_zone[1]:
            sub_pattern = "S20.4"
        elif signal == "SELL" and entry_bar['high'] >= fvg_zone[1] and entry_bar['high'] <= fvg_zone[0]:
            sub_pattern = "S20.4"

    # 3. Check HTF Alignment (S20.3)
    # If we have H1 swing data
    h1_swing = hhll_swing.get_swing_hl_pts("H1")
    if h1_swing and h1_swing[0] is not None and h1_swing[1] is not None:
        htf_high, htf_low = h1_swing[0], h1_swing[1]
        fibo_range = htf_high - htf_low
        if fibo_range > 0:
            ret_50  = htf_low + (fibo_range * 0.5)      # 50% retracement level
            ret_786 = htf_low + (fibo_range * 0.214)     # 78.6% retracement level

            if signal == "BUY":
                # Retracement down → BUY ใน discount zone (50-78.6%)
                if ret_786 <= entry_bar['low'] <= ret_50:
                    sub_pattern = "S20.3"
            else:
                # Retracement up → SELL ใน premium zone (50-78.6% from top)
                ret_50_up  = htf_high - (fibo_range * 0.5)
                ret_786_up = htf_high - (fibo_range * 0.214)
                if ret_50_up <= entry_bar['high'] <= ret_786_up:
                    sub_pattern = "S20.3"

    # ── Calculate Entry, SL, TP ────────────────────────────────────
    entry = (entry_bar['open'] + entry_bar['close']) / 2.0

    # คำนวณ ATR สำหรับ SL buffer (consistent กับท่าอื่นในระบบ)
    atr_val = None
    if len(rates) >= 16:
        atr_val = calc_atr(rates[:-1], 14)

    # Fibo for TP: 161.8% extension ของ swing กลับตัว
    if signal == "BUY":
        sl_raw = min(ref_bar['low'], entry_bar['low'])
        high_pt = max(ref_bar['high'], entry_bar['high'])
        fibo_range = high_pt - sl_raw
        tp_raw = sl_raw + (fibo_range * getattr(config, 'S20_FIBO_TP_LEVEL', 1.618))
        sl_buffer = config.SL_BUFFER(atr_val) * getattr(config, 'S20_SL_BUFFER', 1.0)
        sl = sl_raw - sl_buffer
    else:
        sl_raw = max(ref_bar['high'], entry_bar['high'])
        low_pt = min(ref_bar['low'], entry_bar['low'])
        fibo_range = sl_raw - low_pt
        tp_raw = sl_raw - (fibo_range * getattr(config, 'S20_FIBO_TP_LEVEL', 1.618))
        sl_buffer = config.SL_BUFFER(atr_val) * getattr(config, 'S20_SL_BUFFER', 1.0)
        sl = sl_raw + sl_buffer

    # Formatting reason based on sub_pattern
    reason_map = {
        "S20.1": "Classic Allin4s",
        "S20.2": "Tainted Allin4s (ตำหนิ)",
        "S20.3": "HTF Fibo Align Allin4s",
        "S20.4": "FVG Bounce Allin4s",
        "S20.5": "Sideway Trap Allin4s"
    }

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp_raw,
        "reason": f"{sub_pattern} {reason_map[sub_pattern]}",
        "pattern": sub_pattern,
        "sid": 20
    }
