"""
strategy20.py — S20 All in 4s (Hardcore Mode + VIP Enhancements)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sub-patterns (ท่าย่อยตามฉบับ All in 4s):
  S20.1: Classic 2-Bar — เขียว 2 แท่ง ปิดคลุมไส้ (กลับตัวสมบูรณ์)
  S20.2: Wick Fill & Reject — ลงไปกินไส้เก่าแล้วปิดเหนือปลายไส้ (แท่งตำหนิ/ท่าไม้ตาย)
  S20.3: Solid Momentum — แท่งตัน (Solid) ไม่มีไส้ บอกทิศทางแรง
  S20.4: Small 2L-2H (Butterfly) — เทรนด์ขึ้น ย่อแดงสั้นๆ 1 แท่ง แล้วเขียวกลืนกิน (พักตัวสั้น)
  S20.5: LQ Sweep (Candlestick Divergence) — ทะลุหลอกกวาด Liquidity แล้วถูกตบกลับเข้า FVG
  S20.6: FVG Retest & Reject 
  S20.7: Doji at Structure Break
  S20.8: Candlestick Divergence
  S20.9: Trap Engulfing Return

VIP Enhancements Added:
- Psychological Numbers (หลบ 0 และ 5)
- Fibo Targets: RUN (7.044) & KRH2 (3.097)
- Strict No-Touch SL
"""

from datetime import time
import config
import hhll_swing
from mt5_utils import calc_atr

def _in_session(dt_bkk) -> bool:
    """เช็ค Killzones (London/NY)"""
    if not getattr(config, "S20_SESSION_FILTER", False):
        return True
    if dt_bkk is None:
        return True
    cur = dt_bkk.time() if hasattr(dt_bkk, 'time') else dt_bkk
    sessions = getattr(config, "S20_SESSIONS", [("14:00", "18:00"), ("19:00", "23:00")])
    for start_str, end_str in sessions:
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        if time(sh, sm) <= cur < time(eh, em):
            return True
    return False

def _trend_allows(signal: str, tf: str) -> bool:
    """ห้ามเข้าสวน Strong Trend"""
    if not getattr(config, "S20_TREND_FILTER", False):
        return True
    trend_info = hhll_swing.get_trend_from_structure(tf)
    if not trend_info:
        return True
    trend = trend_info.get("trend", "UNKNOWN")
    strength = trend_info.get("strength", "")
    if signal == "BUY" and trend == "BEAR" and strength == "strong":
        return False
    if signal == "SELL" and trend == "BULL" and strength == "strong":
        return False
    return True

def _has_fvg(rates, signal: str, start_idx: int) -> bool:
    """ตรวจว่ามี FVG รองรับทิศทางนั้นหรือไม่"""
    if start_idx < 2:
        return False
    c1, c2, c3 = rates[start_idx-2], rates[start_idx-1], rates[start_idx]
    if signal == "BUY" and c3['low'] > c1['high']:
        return True
    if signal == "SELL" and c3['high'] < c1['low']:
        return True
    return False

def _apply_psychological_number(price: float, is_buy: bool, is_tp: bool) -> float:
    """
    VIP Rule: Adjusts the price to end in 3 or 7. Avoids 0 and 5.
    Front-runs the retail stops.
    """
    if not getattr(config, "S20_USE_PSYCHO_NUMBERS", True):
        return price
        
    int_price = int(price)
    remainder = int_price % 10
    
    if remainder == 7:
        target_int = int_price
    elif remainder < 7:
        if is_tp and is_buy:
            target_int = int_price - remainder + 7
            if target_int > price: target_int -= 10
        else:
            target_int = int_price - remainder + 7 - 10
    else: 
        if is_tp and is_buy:
            target_int = int_price - remainder + 17
            if target_int > price: target_int -= 1
    
    # ── อ่านตั้งค่า Pipeline ──
    s_defect = getattr(config, "S20_TRIGGER_DEFECT", True)
    s_2l2h = getattr(config, "S20_TRIGGER_2L2H", True)
    s_solid = getattr(config, "S20_TRIGGER_SOLID_CLEAR", True)
    s_fvg = getattr(config, "S20_TRIGGER_FVG_OB", True)

    m_magic = getattr(config, "S20_MODIFIER_MAGIC_NUM", True)
    m_no_body = getattr(config, "S20_MODIFIER_NO_BODY_BRK", True)
    m_fibo = getattr(config, "S20_MODIFIER_FIBO_CONF", True)

    c_prev3 = rates[-4] if len(rates) >= 4 else None
    c_prev2 = rates[-3] if len(rates) >= 3 else None
    c_prev1 = rates[-2] if len(rates) >= 2 else None
    c_curr  = rates[-1] if len(rates) >= 1 else None

    # helper properties
    def is_green(c): return c and c['close'] > c['open']
    def is_red(c): return c and c['close'] < c['open']
    def body_size(c): return abs(c['close'] - c['open']) if c else 0
    def wick_top(c): return c['high'] - max(c['open'], c['close']) if c else 0
    def wick_bot(c): return min(c['open'], c['close']) - c['low'] if c else 0
    
    atr = calc_atr(rates[:-1], 14) or 1.0

    signal = None
    sub_pattern = None
    ref_bar = c_curr

    # ── STAGE 1: Base Triggers ──────────────────────────────────────────
    # 1. Defect Pullback (การดูดกลับรอยแหว่ง)
    if not signal and s_defect and len(rates) >= 4:
        if is_red(c_prev1) and wick_bot(c_prev1) > body_size(c_prev1) and is_green(c_curr) and c_curr['low'] <= c_prev1['low']:
            signal, sub_pattern, ref_bar = "BUY", "S20.Base.Defect", c_curr
        elif is_green(c_prev1) and wick_top(c_prev1) > body_size(c_prev1) and is_red(c_curr) and c_curr['high'] >= c_prev1['high']:
            signal, sub_pattern, ref_bar = "SELL", "S20.Base.Defect", c_curr

    # 2. 2L/2H Structure (โครงสร้างเบรคหลอก)
    if not signal and s_2l2h and len(rates) >= 4:
        if is_green(c_curr) and c_curr['low'] < c_prev1['low'] and c_curr['close'] > c_prev1['low']:
            signal, sub_pattern, ref_bar = "BUY", "S20.Base.2L2H", c_curr
        elif is_red(c_curr) and c_curr['high'] > c_prev1['high'] and c_curr['close'] < c_prev1['high']:
            signal, sub_pattern, ref_bar = "SELL", "S20.Base.2L2H", c_curr

    # 3. Solid / Clear Candle (แท่งตัน/แท่งเคลียร์)
    if not signal and s_solid and len(rates) >= 3:
        if is_green(c_prev1) and wick_top(c_prev1) < (atr*0.05) and is_red(c_curr) and c_curr['close'] < c_prev1['low']:
            signal, sub_pattern, ref_bar = "SELL", "S20.Base.Solid", c_curr
        elif is_red(c_prev1) and wick_bot(c_prev1) < (atr*0.05) and is_green(c_curr) and c_curr['close'] > c_prev1['high']:
            signal, sub_pattern, ref_bar = "BUY", "S20.Base.Solid", c_curr

    # 4. FVG / OB Retrace (ย่อตัว 50% หรือเทส FVG)
    if not signal and s_fvg and len(rates) >= 4:
        if is_green(c_prev2) and is_red(c_prev1) and is_green(c_curr) and c_curr['low'] <= (c_prev2['open'] + c_prev2['close']) / 2:
            signal, sub_pattern, ref_bar = "BUY", "S20.Base.FVG", c_curr
        elif is_red(c_prev2) and is_green(c_prev1) and is_red(c_curr) and c_curr['high'] >= (c_prev2['open'] + c_prev2['close']) / 2:
            signal, sub_pattern, ref_bar = "SELL", "S20.Base.FVG", c_curr

    # ── STAGE 2: Modifiers & Filters ────────────────────────────────────
    if signal:
        # Modifier 1: Magic Number 7 Filter
        if m_magic:
            last_digit = int(c_curr['close']) % 10
            if last_digit == 7:
                sub_pattern += "+Magic7"
                
        # Modifier 2: No Body Close on Support Rule
        if m_no_body:
            if signal == "BUY" and c_curr['close'] < c_prev1['low']:
                signal = None # Failed test, cancel buy
            elif signal == "SELL" and c_curr['close'] > c_prev1['high']:
                signal = None # Failed test, cancel sell
        
        # Modifier 3: Fibo Confluence (Pseudo-check via wicks)
        if m_fibo and signal:
            if wick_top(c_curr) > body_size(c_curr) * 2 or wick_bot(c_curr) > body_size(c_curr) * 2:
                sub_pattern += "+Fibo"

    if not signal:
        return res
    # ── Trend Filter ──
    if tf and not _trend_allows(signal, tf):
        res["reason"] = f"S20: Blocked by Counter-Trend [{tf}]"
        return res

    # ── Body Size Filter ──
    min_body_pct = getattr(config, "S20_MIN_BODY_ATR_PCT", 0.3)
    if min_body_pct > 0 and sub_pattern != "S20.2":
        body_size = abs(ref_bar['close'] - ref_bar['open'])
        if body_size < min_body_pct * atr:
            res["reason"] = f"S20: Body ({body_size:.2f}) < {min_body_pct}xATR"
            return res

    # ── Calculate Entry, SL, TP ──
    tf_max_wick = {"M1": 50.0, "M5": 310.0, "M15": 363.0, "M30": 621.0, "H1": 1200.0, "H4": 2100.0, "H12": 3500.0, "D1": 3390.0}
    base_wick = 310.0
    tf_scale = tf_max_wick.get(tf, base_wick) / base_wick
    
    entry_buffer = getattr(config, "S20_ENTRY_BUFFER", 0.0) * tf_scale
    sl_2l2h = getattr(config, "S20_SL_2L2H", 100.0) * tf_scale
    
    # 1. Entry
    if sub_pattern == "S20.Base.Defect":
        entry = ref_bar['low'] if signal == "BUY" else ref_bar['high']
    elif sub_pattern == "S20.Base.2L2H":
        entry = c_curr['close']
        if signal == "BUY": entry -= entry_buffer
        else: entry += entry_buffer
    else:
        if entry_buffer > 0:
            if signal == "BUY": entry = c_curr['close'] - entry_buffer
            else: entry = c_curr['close'] + entry_buffer
        else:
            entry = (c_curr['open'] + c_curr['close']) / 2.0

    # 2. SL (Stop Loss)
    sl_buf = config.SL_BUFFER(atr) * getattr(config, "S20_SL_BUFFER", 1.0)
    setup_bars = rates[-3:]
    
    if sub_pattern == "S20.Base.2L2H":
        if signal == "BUY": sl = entry - sl_2l2h
        else: sl = entry + sl_2l2h
    else:
        if signal == "BUY": sl = min(b['low'] for b in setup_bars) - sl_buf
        else: sl = max(b['high'] for b in setup_bars) + sl_buf

    # 3. TP (Take Profit) - Stage 3 Dynamic Exits
    fibo_run = getattr(config, "S20_FIBO_RUN", 7.044)
    defect_run = getattr(config, "S20_DEFECT_FIBO_RUN", 7.467)
    fibo_krh2 = getattr(config, "S20_FIBO_KRH2", 3.097)
    
    if sub_pattern == "S20.Base.Defect":
        # Defect plays use special 7.467 extension
        if signal == "BUY":
            sl_raw = min(b['low'] for b in setup_bars)
            high_pt = max(b['high'] for b in setup_bars)
            tp_raw = sl_raw + ((high_pt - sl_raw) * defect_run)
        else:
            sl_raw = max(b['high'] for b in setup_bars)
            low_pt = min(b['low'] for b in setup_bars)
            tp_raw = sl_raw - ((sl_raw - low_pt) * defect_run)
    elif sub_pattern == "S20.Base.2L2H":
        # Massive Fibo run for Traps
        if signal == "BUY":
            sl_raw = min(b['low'] for b in setup_bars)
            high_pt = max(b['high'] for b in setup_bars)
            tp_raw = sl_raw + ((high_pt - sl_raw) * fibo_run)
        else:
            sl_raw = max(b['high'] for b in setup_bars)
            low_pt = min(b['low'] for b in setup_bars)
            tp_raw = sl_raw - ((sl_raw - low_pt) * fibo_run)
    else:
        # Default KRH2 Fibo for Solid and FVG Retrace
        if signal == "BUY":
            sl_raw = min(b['low'] for b in setup_bars)
            high_pt = max(b['high'] for b in setup_bars)
            tp_raw = sl_raw + ((high_pt - sl_raw) * fibo_krh2)
        else:
            sl_raw = max(b['high'] for b in setup_bars)
            low_pt = min(b['low'] for b in setup_bars)
            tp_raw = sl_raw - ((sl_raw - low_pt) * fibo_krh2)

    # 4. Apply Stage 2 Modifiers (Psychological Numbers VIP Rule)
    if getattr(config, "S20_USE_PSYCHO_NUMBERS", True):
        entry = _apply_psychological_number(entry, is_buy=(signal=="BUY"), is_tp=False)
        tp_raw = _apply_psychological_number(tp_raw, is_buy=(signal=="BUY"), is_tp=True)

    if signal == "BUY":
        tp_raw = max(tp_raw, entry + atr)
        sl = min(sl, entry - (atr*0.2))
    else:
        tp_raw = min(tp_raw, entry - atr)
        sl = max(sl, entry + (atr*0.2))

    return {
        "signal": signal,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp": round(tp_raw, 2),
        "reason": f"S20 - {sub_pattern}",
        "pattern": sub_pattern,
        "sid": 20
    }
