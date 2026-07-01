"""
strategy20_12.py — S20.12 FutureKey (Candlestick Mechanics)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
อ้างอิงจาก เชิงแท่งเทียน_pdf.md
Sub-patterns:
  S20.12.SweepReversal (หน้า 7): กินไส้และตีกลับยืนเหนือ 35% ของ body เดิม
  S20.12.NoWickTrap (หน้า 8): แท่งไร้ไส้ (Solid) ตามด้วยแท่งสวนทางขนาดเล็กหลอกๆ เพื่อทุบ/ดึงกลับรุนแรง
"""

import math
from datetime import time
import config
from mt5_utils import calc_atr
import hhll_swing

def _in_session(dt_bkk) -> bool:
    if not getattr(config, "S20_12_SESSION_FILTER", False):
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

def _apply_psychological_number(price: float, is_buy: bool, is_tp: bool) -> float:
    if not getattr(config, "S20_10_USE_PSYCHOLOGICAL_NUMBERS", True): # Use global S20 psycho config
        return price
    int_price = int(price)
    last_digit = int_price % 10
    offset = 0
    if last_digit in (0, 1, 2):
        offset = - (last_digit + 2)
    elif last_digit in (3, 4, 5, 6):
        offset = (8 - last_digit)
    elif last_digit == 9:
        offset = -1
    if last_digit == 7:
        offset = 0
    return float(int_price + offset) + (price - int_price)

def strategy_20_12(rates, tf_name="M5", config=config) -> dict:
    res = {"signal": "WAIT", "reason": "", "pattern": "S20.12", "sid": 20.12}

    if not _in_session(None):
        res["reason"] = "S20.12 - นอกเวลาทำการ"
        return res
        
    if rates is None or len(rates) < 20:
        res["reason"] = "S20.12 - ข้อมูลไม่พอ (ตัองการ 20+ แท่ง)"
        return res

    atr = calc_atr(rates[:-1], 14) or 1.0
    c_curr  = rates[-2] # The one that just closed
    c_prev1 = rates[-3]
    c_prev2 = rates[-4]
    
    def is_green(c): return c and c['close'] > c['open']
    def is_red(c): return c and c['close'] < c['open']
    def body_size(c): return abs(c['close'] - c['open']) if c else 0
    def top_wick(c): return c['high'] - max(c['open'], c['close']) if c else 0
    def bot_wick(c): return min(c['open'], c['close']) - c['low'] if c else 0
    
    signal = None
    sub_pattern = None
    ref_bar = c_curr

    # ────────────────────────────────────────────────────────
    # Pattern 1: Sweep Reversal (หน้า 7)
    # ────────────────────────────────────────────────────────
    if not signal:
        # BUY: prev1 (Red) has bottom wick. curr (Green) sweeps prev1's low, and closes > 35% above prev1's body
        if is_red(c_prev1) and is_green(c_curr):
            if c_curr['low'] < c_prev1['low']: # Swept the wick
                # Check if closes >= 35% above prev1's body
                prev1_body_top = max(c_prev1['open'], c_prev1['close'])
                prev1_body_bot = min(c_prev1['open'], c_prev1['close'])
                prev1_body_size = prev1_body_top - prev1_body_bot
                
                target_close = prev1_body_bot + (prev1_body_size * 1.35)
                if c_curr['close'] >= target_close:
                    signal, sub_pattern, ref_bar = "BUY", "S20.12.SweepReversal", c_curr

        # SELL: prev1 (Green) has top wick. curr (Red) sweeps prev1's high, and closes > 35% below prev1's body
        if is_green(c_prev1) and is_red(c_curr):
            if c_curr['high'] > c_prev1['high']: # Swept the wick
                # Check if closes <= 35% below prev1's body
                prev1_body_top = max(c_prev1['open'], c_prev1['close'])
                prev1_body_bot = min(c_prev1['open'], c_prev1['close'])
                prev1_body_size = prev1_body_top - prev1_body_bot
                
                target_close = prev1_body_top - (prev1_body_size * 1.35)
                if c_curr['close'] <= target_close:
                    signal, sub_pattern, ref_bar = "SELL", "S20.12.SweepReversal", c_curr

    # ────────────────────────────────────────────────────────
    # Pattern 2: No-Wick Trap (หน้า 8)
    # ────────────────────────────────────────────────────────
    if not signal:
        # SELL: prev1 is Solid Red (no top wick, or < 0.1 ATR), curr is Small Green (body < 0.4 ATR)
        if is_red(c_prev1) and top_wick(c_prev1) < (atr * 0.1):
            if is_green(c_curr) and body_size(c_curr) < (atr * 0.4):
                if c_curr['high'] < c_prev1['high']: # Inside or small bounce
                    signal, sub_pattern, ref_bar = "SELL", "S20.12.NoWickTrap", c_curr

        # BUY: prev1 is Solid Green (no bot wick, or < 0.1 ATR), curr is Small Red (body < 0.4 ATR)
        if is_green(c_prev1) and bot_wick(c_prev1) < (atr * 0.1):
            if is_red(c_curr) and body_size(c_curr) < (atr * 0.4):
                if c_curr['low'] > c_prev1['low']:
                    signal, sub_pattern, ref_bar = "BUY", "S20.12.NoWickTrap", c_curr

    if not signal:
        return res

    # ── Calculate Entry, SL, TP ──
    # For SweepReversal, Entry = current close (market) or slight retrace. We use Limit at 38.2% of current candle
    # For NoWickTrap, Entry = current close (market) or slight retrace. We use Limit at 50% of current candle
    if "SweepReversal" in sub_pattern:
        retrace = 0.382
        fibo_run = 1.5
    else:
        retrace = 0.500
        fibo_run = 2.0

    anchor_high = ref_bar['high']
    anchor_low = ref_bar['low']
    anchor_size = anchor_high - anchor_low
    
    if signal == "BUY":
        entry = ref_bar['close'] - (anchor_size * retrace)
        sl_raw = anchor_low - (atr * 0.5) # Under the swept low
        tp_raw = entry + ((entry - sl_raw) * fibo_run)
    else:
        entry = ref_bar['close'] + (anchor_size * retrace)
        sl_raw = anchor_high + (atr * 0.5) # Above the swept high
        tp_raw = entry - ((sl_raw - entry) * fibo_run)

    # 3. Modifiers (Psychological Numbers)
    if getattr(config, "S20_10_USE_PSYCHOLOGICAL_NUMBERS", True):
        entry = _apply_psychological_number(entry, is_buy=(signal=="BUY"), is_tp=False)
        tp_raw = _apply_psychological_number(tp_raw, is_buy=(signal=="BUY"), is_tp=True)

    # 4. Limit minimum RR
    sl = sl_raw
    if signal == "BUY":
        tp_raw = max(tp_raw, entry + atr)
        sl = min(sl, entry - (atr*0.2))
    else:
        tp_raw = min(tp_raw, entry - atr)
        sl = max(sl, entry + (atr*0.2))

    res_out = {
        "signal": signal,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp": round(tp_raw, 2),
        "reason": f"S20.12 - {sub_pattern}",
        "pattern": sub_pattern,
        "sid": 20.12
    }
    
    return res_out
