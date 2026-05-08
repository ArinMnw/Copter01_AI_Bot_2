"""
ท่าที่ 11: Fibo S1
- Trigger: S1 pattern (กลืนกิน / ตำหนิ / ย้อนโครงสร้าง) BUY/SELL
- Anchor: แท่งสีตรงกับ direction ตัวล่าสุด (BUY=green, SELL=red)
  ตี Fibo: BUY → 1=high, 0=low | SELL → 1=low, 0=high
- Watch: รอราคาแตะระดับ trigger (1.617 / 3.097 / 5.165)
- Triggers (cascade — P1→P2→P3 ยิงต่อกันได้):
  Pattern 1: แตะ KRH1  → LIMIT @ 50%,   TP=7.044, SL=-0.31
  Pattern 2: แตะ KRH2  → LIMIT @ 50%   (ถ้ามี BUY reversal ใน Frame1 → KRH1), TP=7.044, SL=-0.31
  Pattern 3: แตะ KRH3  → LIMIT @ KRH1  (ถ้ามี BUY reversal ใน Frame2 → KRH2), TP=7.044, SL=-0.31
  Pattern 4: แตะ 7.044 → LIMIT reverse @ 7.044, TP=KRH1, SL=X Divergence (terminal)
- Frame check: BUY reversal (green candle) ใน frame → ใช้ entry ที่ bottom ของ frame นั้น
- Touch detection: wick (high สำหรับ BUY, low สำหรับ SELL)
"""

# ── Fibo grid เต็มชุด (level → label) ───────────────────────────────
FIBO_LEVELS = {
    -1.31:  "Liquidity day",
    -0.95:  "Liquidity m5",
    -0.31:  "XXL",
    -0.17:  "XL",
    0.0:    "0",
    0.242:  "KRL",
    0.382:  "0.382",
    0.5:    "50%",
    0.57:   "60%",
    1.0:    "1",
    1.617:  "KRH1",
    3.097:  "KRH2",
    5.165:  "KRH3",
    7.044:  "Run Engulfing",
    7.467:  "RUN",
    8.237:  "X Divergence",
}

# Fibo levels per spec (trigger_level, default_entry_level)
FIBO_TRIGGER_LEVELS = (
    (1.617, 0.5),     # P1: touch KRH1  → entry at 50%
    (3.097, 0.5),     # P2: touch KRH2  → entry at 50% (frame check → KRH1)
    (5.165, 1.617),   # P3: touch KRH3  → entry at KRH1 (frame check → KRH2)
)
FIBO_TP_ENGULF = 7.044  # Run Engulfing (ใช้เมื่อ S1 เป็น pattern กลืนกิน)
FIBO_TP_OTHER  = 7.467  # RUN (ใช้เมื่อ S1 เป็น pattern อื่น)
FIBO_TP = FIBO_TP_ENGULF  # backward-compat alias
FIBO_SL = -0.31         # XXL
FIBO_RECOVERY = -0.95   # Liquidity m5 (ใช้ตอน SL hit phase 2)

# Pattern 4: reverse trade เมื่อราคาแตะ 7.044 (Run Engulfing) — terminal
FIBO_P4_TRIGGER = 7.044
FIBO_P4_ENTRY   = 7.044
FIBO_P4_TP      = 1.617   # KRH1
FIBO_P4_SL      = 8.237   # X Divergence

# Frame check: pattern_idx → (frame_low_level, frame_high_level, alt_entry_level)
# BUY reversal (green candle) ในกรอบ → ใช้ alt_entry แทน default
FIBO_FRAME_CHECK = {
    2: (1.617, 3.097, 1.617),  # Frame 1 (KRH1–KRH2) → alt entry = KRH1
    3: (3.097, 5.165, 3.097),  # Frame 2 (KRH2–KRH3) → alt entry = KRH2
}

# ── State per TF ──────────────────────────────────────────────────
# {tf_name: {
#   "direction": "BUY"|"SELL",
#   "anchor_high": float, "anchor_low": float, "anchor_time": int,
#   "phase": "armed"|"triggered",
#   "triggered_level": float|None,  # highest level fired so far (P1-P3 cascade)
# }}
_s11_state: dict = {}


def _level_to_price(level: float, anchor_high: float, anchor_low: float, direction: str) -> float:
    """แปลง Fibo level → ราคา"""
    rng = anchor_high - anchor_low
    if direction == "BUY":
        return anchor_low + level * rng
    return anchor_high - level * rng


def _has_buy_reversal_in_zone(rates, zone_bot: float, zone_top: float) -> bool:
    """ตรวจว่ามีแท่งเขียว (BUY reversal) ที่ overlap กับ zone_bot–zone_top"""
    for bar in rates[-20:]:
        h = float(bar["high"]); l = float(bar["low"])
        o = float(bar["open"]); c = float(bar["close"])
        if h < zone_bot or l > zone_top:
            continue
        if c > o:
            return True
    return False


def _has_sell_reversal_in_zone(rates, zone_bot: float, zone_top: float) -> bool:
    """ตรวจว่ามีแท่งแดง (SELL reversal) ที่ overlap กับ zone_bot–zone_top"""
    for bar in rates[-20:]:
        h = float(bar["high"]); l = float(bar["low"])
        o = float(bar["open"]); c = float(bar["close"])
        if h < zone_bot or l > zone_top:
            continue
        if c < o:
            return True
    return False


def _has_consecutive_candles_in_zone(rates, zone_bot: float, zone_top: float,
                                      color: str, count: int = 2) -> bool:
    """
    ตรวจว่ามี `count` แท่งติดต่อกันล่าสุดที่ overlap กับ zone มีสี color
    color: "red" (close < open) | "green" (close > open)
    """
    zone_bars = []
    for bar in rates[-20:]:
        h = float(bar["high"]); l = float(bar["low"])
        if h < zone_bot or l > zone_top:
            continue
        zone_bars.append(bar)
    if len(zone_bars) < count:
        return False
    for bar in zone_bars[-count:]:
        o = float(bar["open"]); c = float(bar["close"])
        if color == "red"   and c >= o:
            return False
        if color == "green" and c <= o:
            return False
    return True


def record_s1_pattern(tf_name: str, signal: str, candles, last_close_time: int, s1_pattern: str = ""):
    """
    เรียกตอน scanner เห็น S1 BUY/SELL signal
    หา anchor candle สีตรงกับ direction (BUY=green, SELL=red)
    candles = list ของ {open, high, low, close} เรียงตามเวลา (เก่า→ใหม่)
    """
    if not candles or signal not in ("BUY", "SELL"):
        return
    target_color = "green" if signal == "BUY" else "red"
    anchor = None
    for c in candles:
        try:
            o = float(c["open"])
            cl = float(c["close"])
        except Exception:
            continue
        is_green = cl > o
        is_red = cl < o
        if (target_color == "green" and is_green) or (target_color == "red" and is_red):
            anchor = c
            break
    if not anchor:
        return
    anchor_high = float(anchor["high"])
    anchor_low = float(anchor["low"])
    if anchor_high <= anchor_low:
        return

    existing = _s11_state.get(tf_name)
    if existing and existing.get("phase") == "triggered":
        return

    is_engulf = "กลืนกิน" in (s1_pattern or "")
    _s11_state[tf_name] = {
        "direction": signal,
        "anchor_high": anchor_high,
        "anchor_low": anchor_low,
        "anchor_time": int(last_close_time),
        "phase": "armed",
        "triggered_level": None,
        "fibo_tp": FIBO_TP_ENGULF if is_engulf else FIBO_TP_OTHER,
    }


def reset_state(tf_name: str = ""):
    """Reset state — ใช้ตอน position closed (TODO phase 2)"""
    if tf_name:
        _s11_state.pop(tf_name, None)
    else:
        _s11_state.clear()


def strategy_11(rates, tf_name: str):
    """
    ตรวจว่าแท่งล่าสุดแตะ Fibo trigger level หรือไม่
    P1–P3 cascade: triggered_level track ระดับที่ยิงแล้ว ระดับสูงกว่ายังยิงได้
    P4 เป็น terminal: ตั้ง phase=triggered ปิดการยิงทั้งหมด
    """
    state = _s11_state.get(tf_name)
    if not state:
        return {"signal": "WAIT", "reason": f"S11 ยังไม่มี anchor (รอ S1 pattern ที่ {tf_name})"}
    if state.get("phase") == "triggered":
        return {"signal": "WAIT", "reason": f"S11 phase=triggered (รอเทรดจบ)"}

    if rates is None or len(rates) == 0:
        return {"signal": "WAIT", "reason": "S11 ไม่มี rates"}

    direction       = state["direction"]
    anchor_high     = state["anchor_high"]
    anchor_low      = state["anchor_low"]
    triggered_level = state.get("triggered_level")
    fibo_tp         = state.get("fibo_tp", FIBO_TP_ENGULF)

    last_bar = rates[-1]
    last_high = float(last_bar["high"])
    last_low  = float(last_bar["low"])

    for pattern_idx, (trigger_level, default_entry_level) in enumerate(FIBO_TRIGGER_LEVELS, start=1):
        # cascade: ข้ามระดับที่ยิงไปแล้ว อนุญาตเฉพาะระดับที่สูงกว่า
        if triggered_level is not None and trigger_level <= triggered_level:
            continue

        trigger_price = _level_to_price(trigger_level, anchor_high, anchor_low, direction)
        touched = last_high >= trigger_price if direction == "BUY" else last_low <= trigger_price
        if not touched:
            continue

        # ── P2 Frame 1: BUY counter-trade เมื่อ KRH2 เป็น support (SELL anchor) ──
        if pattern_idx == 2 and direction == "SELL":
            _krh1_p  = _level_to_price(1.617, anchor_high, anchor_low, direction)
            _f1_bot  = min(_krh1_p, trigger_price)
            _f1_top  = max(_krh1_p, trigger_price)
            _fibo0_p = _level_to_price(0.0, anchor_high, anchor_low, direction)
            if _has_consecutive_candles_in_zone(rates, _f1_bot, _f1_top, "green", 2):
                _buy_entry = trigger_price   # KRH2
                _buy_sl    = last_low
                _buy_tp    = _fibo0_p        # Fibo 0
                if _buy_sl < _buy_entry < _buy_tp:
                    state["triggered_level"] = trigger_level
                    return {
                        "signal": "BUY",
                        "entry": round(_buy_entry, 2),
                        "sl":    round(_buy_sl, 2),
                        "tp":    round(_buy_tp, 2),
                        "pattern": "ท่าที่ 11 Fibo S1 🟢 BUY — Frame1 KRH2 Support",
                        "reason": (
                            f"Frame1 BUY: เขียว 2 แท่งใน KRH1–KRH2 → BUY @ KRH2\n"
                            f"Anchor [H:{anchor_high:.2f} L:{anchor_low:.2f}]\n"
                            f"KRH2 = {_buy_entry:.2f} | SL = {_buy_sl:.2f} | TP (0) = {_buy_tp:.2f}"
                        ),
                        "order_mode": "limit",
                        "candles": [
                            {"open": anchor_low, "high": anchor_high, "low": anchor_low, "close": anchor_high},
                            {"open": float(last_bar["open"]), "high": last_high, "low": last_low, "close": float(last_bar["close"])},
                        ],
                    }

        # ── P2 Frame 1: SELL counter-trade เมื่อ KRH2 เป็น resistance ──
        if pattern_idx == 2 and direction == "BUY":
            _krh1_p  = _level_to_price(1.617, anchor_high, anchor_low, direction)
            _f1_bot  = min(_krh1_p, trigger_price)
            _f1_top  = max(_krh1_p, trigger_price)
            _fibo0_p = _level_to_price(0.0, anchor_high, anchor_low, direction)
            if _has_consecutive_candles_in_zone(rates, _f1_bot, _f1_top, "red", 2):
                _sell_entry = trigger_price   # KRH2
                _sell_sl    = last_high
                _sell_tp    = _fibo0_p        # Fibo 0
                if _sell_tp < _sell_entry < _sell_sl:
                    state["triggered_level"] = trigger_level
                    return {
                        "signal": "SELL",
                        "entry": round(_sell_entry, 2),
                        "sl":    round(_sell_sl, 2),
                        "tp":    round(_sell_tp, 2),
                        "pattern": "ท่าที่ 11 Fibo S1 🔴 SELL — Frame1 KRH2 Resistance",
                        "reason": (
                            f"Frame1 SELL: แดง 2 แท่งใน KRH1–KRH2 → SELL @ KRH2\n"
                            f"Anchor [H:{anchor_high:.2f} L:{anchor_low:.2f}]\n"
                            f"KRH2 = {_sell_entry:.2f} | SL = {_sell_sl:.2f} | TP (0) = {_sell_tp:.2f}"
                        ),
                        "order_mode": "limit",
                        "candles": [
                            {"open": anchor_low, "high": anchor_high, "low": anchor_low, "close": anchor_high},
                            {"open": float(last_bar["open"]), "high": last_high, "low": last_low, "close": float(last_bar["close"])},
                        ],
                    }

        # ── P3 Frame 2: BUY counter-trade เมื่อ KRH3 เป็น support (SELL anchor) ──
        if pattern_idx == 3 and direction == "SELL":
            _krh2_p  = _level_to_price(3.097, anchor_high, anchor_low, direction)
            _f2_bot  = min(_krh2_p, trigger_price)
            _f2_top  = max(_krh2_p, trigger_price)
            _fibo0_p = _level_to_price(0.0, anchor_high, anchor_low, direction)
            if _has_consecutive_candles_in_zone(rates, _f2_bot, _f2_top, "green", 2):
                _buy_entry = trigger_price   # KRH3
                _buy_sl    = last_low
                _buy_tp    = _fibo0_p        # Fibo 0
                if _buy_sl < _buy_entry < _buy_tp:
                    state["triggered_level"] = trigger_level
                    return {
                        "signal": "BUY",
                        "entry": round(_buy_entry, 2),
                        "sl":    round(_buy_sl, 2),
                        "tp":    round(_buy_tp, 2),
                        "pattern": "ท่าที่ 11 Fibo S1 🟢 BUY — Frame2 KRH3 Support",
                        "reason": (
                            f"Frame2 BUY: เขียว 2 แท่งใน KRH2–KRH3 → BUY @ KRH3\n"
                            f"Anchor [H:{anchor_high:.2f} L:{anchor_low:.2f}]\n"
                            f"KRH3 = {_buy_entry:.2f} | SL = {_buy_sl:.2f} | TP (0) = {_buy_tp:.2f}"
                        ),
                        "order_mode": "limit",
                        "candles": [
                            {"open": anchor_low, "high": anchor_high, "low": anchor_low, "close": anchor_high},
                            {"open": float(last_bar["open"]), "high": last_high, "low": last_low, "close": float(last_bar["close"])},
                        ],
                    }

        # ── P3 Frame 2: SELL counter-trade เมื่อ KRH3 เป็น resistance ──
        if pattern_idx == 3 and direction == "BUY":
            _krh2_p  = _level_to_price(3.097, anchor_high, anchor_low, direction)
            _f2_bot  = min(_krh2_p, trigger_price)
            _f2_top  = max(_krh2_p, trigger_price)
            _fibo0_p = _level_to_price(0.0, anchor_high, anchor_low, direction)
            if _has_consecutive_candles_in_zone(rates, _f2_bot, _f2_top, "red", 2):
                _sell_entry = trigger_price   # KRH3
                _sell_sl    = last_high       # high ของแท่งที่แตะ KRH3
                _sell_tp    = _fibo0_p        # Fibo 0
                if _sell_tp < _sell_entry < _sell_sl:
                    state["triggered_level"] = trigger_level
                    return {
                        "signal": "SELL",
                        "entry": round(_sell_entry, 2),
                        "sl":    round(_sell_sl, 2),
                        "tp":    round(_sell_tp, 2),
                        "pattern": f"ท่าที่ 11 Fibo S1 🔴 SELL — Frame2 KRH3 Resistance",
                        "reason": (
                            f"Frame2 SELL: แดง 2 แท่งใน KRH2–KRH3 → SELL @ KRH3\n"
                            f"Anchor [H:{anchor_high:.2f} L:{anchor_low:.2f}]\n"
                            f"KRH3 = {_sell_entry:.2f} | SL = {_sell_sl:.2f} | TP (0) = {_sell_tp:.2f}"
                        ),
                        "order_mode": "limit",
                        "candles": [
                            {"open": anchor_low, "high": anchor_high, "low": anchor_low, "close": anchor_high},
                            {"open": float(last_bar["open"]), "high": last_high, "low": last_low, "close": float(last_bar["close"])},
                        ],
                    }

        # ── Frame check: ดู reversal candle ในกรอบเพื่อเลือก entry ──
        entry_level = default_entry_level
        frame_info  = FIBO_FRAME_CHECK.get(pattern_idx)
        frame_note  = ""
        if frame_info:
            fl_lv, fh_lv, alt_lv = frame_info
            fl_price = _level_to_price(fl_lv, anchor_high, anchor_low, direction)
            fh_price = _level_to_price(fh_lv, anchor_high, anchor_low, direction)
            zone_bot = min(fl_price, fh_price)
            zone_top = max(fl_price, fh_price)
            alt_price = _level_to_price(alt_lv, anchor_high, anchor_low, direction)
            # ราคาต้องยังไม่ถึง alt entry (ไม่งั้น limit จะ fill ทันที)
            price_not_reached = last_low > alt_price if direction == "BUY" else last_high < alt_price
            has_reversal = (
                _has_buy_reversal_in_zone(rates, zone_bot, zone_top)
                if direction == "BUY"
                else _has_sell_reversal_in_zone(rates, zone_bot, zone_top)
            )
            if price_not_reached and has_reversal:
                entry_level = alt_lv
                frame_note  = f" [Frame→{FIBO_LEVELS.get(alt_lv, str(alt_lv))}]"

        entry_price = _level_to_price(entry_level, anchor_high, anchor_low, direction)
        sl_price    = _level_to_price(FIBO_SL,    anchor_high, anchor_low, direction)
        tp_price    = _level_to_price(fibo_tp,     anchor_high, anchor_low, direction)

        if direction == "BUY" and not (sl_price < entry_price < tp_price):
            continue
        if direction == "SELL" and not (tp_price < entry_price < sl_price):
            continue

        # อัปเดต triggered_level แต่ไม่ lock phase (cascade ต่อได้)
        state["triggered_level"] = trigger_level

        sig_e         = "🟢" if direction == "BUY" else "🔴"
        trigger_label = FIBO_LEVELS.get(trigger_level, str(trigger_level))
        entry_label   = FIBO_LEVELS.get(entry_level,   str(entry_level))
        sl_label      = FIBO_LEVELS.get(FIBO_SL,  str(FIBO_SL))
        tp_label      = FIBO_LEVELS.get(fibo_tp,   str(fibo_tp))
        return {
            "signal": direction,
            "entry": round(entry_price, 2),
            "sl":    round(sl_price, 2),
            "tp":    round(tp_price, 2),
            "pattern": f"ท่าที่ 11 Fibo S1 {sig_e} {direction} — Pattern {pattern_idx} ({trigger_label}){frame_note}",
            "reason": (
                f"Pattern {pattern_idx}: แตะ {trigger_label} → LIMIT @ {entry_label}{frame_note}\n"
                f"Anchor [H:{anchor_high:.2f} L:{anchor_low:.2f}]\n"
                f"แตะ Fibo {trigger_level} ({trigger_label}) @ {trigger_price:.2f}\n"
                f"LIMIT @ Fibo {entry_level} ({entry_label}) = {entry_price:.2f}\n"
                f"SL: Fibo {FIBO_SL} ({sl_label}) = {sl_price:.2f} | "
                f"TP: Fibo {fibo_tp} ({tp_label}) = {tp_price:.2f}"
            ),
            "order_mode": "limit",
            "candles": [
                {"open": anchor_low, "high": anchor_high, "low": anchor_low, "close": anchor_high},
                {"open": float(last_bar["open"]), "high": last_high, "low": last_low, "close": float(last_bar["close"])},
            ],
        }

    # ── Frame 1 Check B: KRH1 as support → BUY LIMIT (หลัง KRH2 แตะแล้ว) ──
    if direction == "BUY" and triggered_level is not None and triggered_level >= 3.097:
        _krh1_p = _level_to_price(1.617, anchor_high, anchor_low, "BUY")
        _krh2_p = _level_to_price(3.097, anchor_high, anchor_low, "BUY")
        _f1_bot = min(_krh1_p, _krh2_p)
        _f1_top = max(_krh1_p, _krh2_p)
        if last_low <= _krh1_p and _has_consecutive_candles_in_zone(rates, _f1_bot, _f1_top, "green", 2):
            _b_entry = _krh1_p
            _b_sl    = last_low
            _b_tp    = _level_to_price(7.467, anchor_high, anchor_low, "BUY")
            if _b_sl < _b_entry < _b_tp:
                return {
                    "signal": "BUY",
                    "entry": round(_b_entry, 2),
                    "sl":    round(_b_sl, 2),
                    "tp":    round(_b_tp, 2),
                    "pattern": "ท่าที่ 11 Fibo S1 🟢 BUY — Frame1 KRH1 Support",
                    "reason": (
                        f"Frame1 BUY: เขียว 2 แท่งใน KRH1–KRH2 → BUY @ KRH1\n"
                        f"Anchor [H:{anchor_high:.2f} L:{anchor_low:.2f}]\n"
                        f"KRH1 = {_b_entry:.2f} | SL = {_b_sl:.2f} | TP (RUN) = {_b_tp:.2f}"
                    ),
                    "order_mode": "limit",
                    "candles": [
                        {"open": anchor_low, "high": anchor_high, "low": anchor_low, "close": anchor_high},
                        {"open": float(last_bar["open"]), "high": last_high, "low": last_low, "close": float(last_bar["close"])},
                    ],
                }

    # ── Frame 1 Check B (SELL): KRH1 as resistance → SELL LIMIT (หลัง KRH2 แตะแล้ว) ──
    if direction == "SELL" and triggered_level is not None and triggered_level >= 3.097:
        _krh1_p = _level_to_price(1.617, anchor_high, anchor_low, "SELL")
        _krh2_p = _level_to_price(3.097, anchor_high, anchor_low, "SELL")
        _f1_bot = min(_krh1_p, _krh2_p)
        _f1_top = max(_krh1_p, _krh2_p)
        if last_high >= _krh1_p and _has_consecutive_candles_in_zone(rates, _f1_bot, _f1_top, "red", 2):
            _s_entry = _krh1_p
            _s_sl    = last_high
            _s_tp    = _level_to_price(7.467, anchor_high, anchor_low, "SELL")
            if _s_tp < _s_entry < _s_sl:
                return {
                    "signal": "SELL",
                    "entry": round(_s_entry, 2),
                    "sl":    round(_s_sl, 2),
                    "tp":    round(_s_tp, 2),
                    "pattern": "ท่าที่ 11 Fibo S1 🔴 SELL — Frame1 KRH1 Resistance",
                    "reason": (
                        f"Frame1 SELL: แดง 2 แท่งใน KRH1–KRH2 → SELL @ KRH1\n"
                        f"Anchor [H:{anchor_high:.2f} L:{anchor_low:.2f}]\n"
                        f"KRH1 = {_s_entry:.2f} | SL = {_s_sl:.2f} | TP (RUN) = {_s_tp:.2f}"
                    ),
                    "order_mode": "limit",
                    "candles": [
                        {"open": anchor_low, "high": anchor_high, "low": anchor_low, "close": anchor_high},
                        {"open": float(last_bar["open"]), "high": last_high, "low": last_low, "close": float(last_bar["close"])},
                    ],
                }

    # ── Frame 2 Check B: KRH2 as support → BUY LIMIT (หลัง KRH3 แตะแล้ว) ──
    if direction == "BUY" and triggered_level is not None and triggered_level >= 5.165:
        _krh2_p = _level_to_price(3.097, anchor_high, anchor_low, "BUY")
        _krh3_p = _level_to_price(5.165, anchor_high, anchor_low, "BUY")
        _f2_bot = min(_krh2_p, _krh3_p)
        _f2_top = max(_krh2_p, _krh3_p)
        if last_low <= _krh2_p and _has_consecutive_candles_in_zone(rates, _f2_bot, _f2_top, "green", 2):
            _b_entry = _krh2_p
            _b_sl    = last_low
            _b_tp    = _level_to_price(7.467, anchor_high, anchor_low, "BUY")
            if _b_sl < _b_entry < _b_tp:
                return {
                    "signal": "BUY",
                    "entry": round(_b_entry, 2),
                    "sl":    round(_b_sl, 2),
                    "tp":    round(_b_tp, 2),
                    "pattern": "ท่าที่ 11 Fibo S1 🟢 BUY — Frame2 KRH2 Support",
                    "reason": (
                        f"Frame2 BUY: เขียว 2 แท่งใน KRH2–KRH3 → BUY @ KRH2\n"
                        f"Anchor [H:{anchor_high:.2f} L:{anchor_low:.2f}]\n"
                        f"KRH2 = {_b_entry:.2f} | SL = {_b_sl:.2f} | TP (RUN) = {_b_tp:.2f}"
                    ),
                    "order_mode": "limit",
                    "candles": [
                        {"open": anchor_low, "high": anchor_high, "low": anchor_low, "close": anchor_high},
                        {"open": float(last_bar["open"]), "high": last_high, "low": last_low, "close": float(last_bar["close"])},
                    ],
                }

    # ── Frame 2 Check B (SELL): KRH2 as resistance → SELL LIMIT (หลัง KRH3 แตะแล้ว) ──
    if direction == "SELL" and triggered_level is not None and triggered_level >= 5.165:
        _krh2_p = _level_to_price(3.097, anchor_high, anchor_low, "SELL")
        _krh3_p = _level_to_price(5.165, anchor_high, anchor_low, "SELL")
        _f2_bot = min(_krh2_p, _krh3_p)
        _f2_top = max(_krh2_p, _krh3_p)
        if last_high >= _krh2_p and _has_consecutive_candles_in_zone(rates, _f2_bot, _f2_top, "red", 2):
            _s_entry = _krh2_p
            _s_sl    = last_high
            _s_tp    = _level_to_price(7.467, anchor_high, anchor_low, "SELL")
            if _s_tp < _s_entry < _s_sl:
                return {
                    "signal": "SELL",
                    "entry": round(_s_entry, 2),
                    "sl":    round(_s_sl, 2),
                    "tp":    round(_s_tp, 2),
                    "pattern": "ท่าที่ 11 Fibo S1 🔴 SELL — Frame2 KRH2 Resistance",
                    "reason": (
                        f"Frame2 SELL: แดง 2 แท่งใน KRH2–KRH3 → SELL @ KRH2\n"
                        f"Anchor [H:{anchor_high:.2f} L:{anchor_low:.2f}]\n"
                        f"KRH2 = {_s_entry:.2f} | SL = {_s_sl:.2f} | TP (RUN) = {_s_tp:.2f}"
                    ),
                    "order_mode": "limit",
                    "candles": [
                        {"open": anchor_low, "high": anchor_high, "low": anchor_low, "close": anchor_high},
                        {"open": float(last_bar["open"]), "high": last_high, "low": last_low, "close": float(last_bar["close"])},
                    ],
                }

    # ── Pattern 4: reverse trade แตะ 7.044 → LIMIT ทิศตรงข้าม (terminal) ──
    p4_trigger_price = _level_to_price(FIBO_P4_TRIGGER, anchor_high, anchor_low, direction)
    p4_touched = last_high >= p4_trigger_price if direction == "BUY" else last_low <= p4_trigger_price
    if p4_touched:
        rev_dir  = "SELL" if direction == "BUY" else "BUY"
        p4_entry = p4_trigger_price
        p4_tp    = _level_to_price(FIBO_P4_TP, anchor_high, anchor_low, direction)
        p4_sl    = _level_to_price(FIBO_P4_SL, anchor_high, anchor_low, direction)
        valid    = (p4_tp < p4_entry < p4_sl) if rev_dir == "SELL" else (p4_sl < p4_entry < p4_tp)
        if valid:
            state["phase"]           = "triggered"
            state["triggered_level"] = FIBO_P4_TRIGGER
            sig_e = "🟢" if rev_dir == "BUY" else "🔴"
            return {
                "signal": rev_dir,
                "entry": round(p4_entry, 2),
                "sl":    round(p4_sl, 2),
                "tp":    round(p4_tp, 2),
                "pattern": f"ท่าที่ 11 Fibo S1 {sig_e} {rev_dir} — Pattern 4 (Run Engulfing)",
                "reason": (
                    f"Pattern 4: แตะ Run Engulfing → LIMIT {rev_dir} @ {p4_entry:.2f}\n"
                    f"Anchor [H:{anchor_high:.2f} L:{anchor_low:.2f}]\n"
                    f"แตะ Fibo 7.044 (Run Engulfing) @ {p4_trigger_price:.2f}\n"
                    f"TP: KRH1 (1.617) = {p4_tp:.2f} | SL: X Divergence (8.237) = {p4_sl:.2f}"
                ),
                "order_mode": "limit",
                "candles": [
                    {"open": anchor_low, "high": anchor_high, "low": anchor_low, "close": anchor_high},
                    {"open": float(last_bar["open"]), "high": last_high, "low": last_low, "close": float(last_bar["close"])},
                ],
            }

    touched_levels = FIBO_LEVELS.get(triggered_level, str(triggered_level)) if triggered_level else "—"
    return {"signal": "WAIT", "reason": f"S11 armed [{direction}] triggered={touched_levels} รอแตะ 1.617/3.097/5.165/7.044"}
