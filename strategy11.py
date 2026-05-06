"""
ท่าที่ 11: Fibo S1
- Trigger: S1 pattern (กลืนกิน / ตำหนิ / ย้อนโครงสร้าง) BUY/SELL
- Anchor: แท่งสีตรงกับ direction ตัวล่าสุด (BUY=green, SELL=red)
  ตี Fibo: BUY → 1=high, 0=low | SELL → 1=low, 0=high
- Watch: รอราคาแตะระดับ trigger (1.617 / 3.097 / 5.165)
- Triggers:
  Pattern 1: แตะ 1.617 → LIMIT @ 0.5,   TP=7.044, SL=-0.31
  Pattern 2: แตะ 3.097 → LIMIT @ 0.5,   TP=7.044, SL=-0.31
  Pattern 3: แตะ 5.165 → LIMIT @ 1.617, TP=7.044, SL=-0.31
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

# Fibo levels per spec (subset ของ FIBO_LEVELS ที่ใช้ trigger/entry/SL/TP จริง)
FIBO_TRIGGER_LEVELS = (
    (1.617, 0.5),     # touch KRH1 → entry at 50%
    (3.097, 0.5),     # touch KRH2 → entry at 50%
    (5.165, 1.617),   # touch KRH3 → entry at KRH1
)
FIBO_TP = 7.044         # Run Engulfing
FIBO_SL = -0.31         # XXL
FIBO_RECOVERY = -0.95   # Liquidity m5 (ใช้ตอน SL hit phase 2)

# ── State per TF ──────────────────────────────────────────────────
# {tf_name: {
#   "direction": "BUY"|"SELL",
#   "anchor_high": float, "anchor_low": float, "anchor_time": int,
#   "phase": "armed"|"triggered",
#   "triggered_level": float,  # ระดับ trigger ที่แตะแล้ว (ถ้ามี)
# }}
_s11_state: dict = {}


def _level_to_price(level: float, anchor_high: float, anchor_low: float, direction: str) -> float:
    """แปลง Fibo level → ราคา"""
    rng = anchor_high - anchor_low
    if direction == "BUY":
        # BUY: 1=high, 0=low → price = low + level × range
        return anchor_low + level * rng
    # SELL: 1=low, 0=high → price = high - level × range
    return anchor_high - level * rng


def record_s1_pattern(tf_name: str, signal: str, candles, last_close_time: int):
    """
    เรียกตอน scanner เห็น S1 BUY/SELL signal
    หา anchor candle สีตรงกับ direction (BUY=green, SELL=red)
    candles = list ของ {open, high, low, close} เรียงตามเวลา (เก่า→ใหม่)
    """
    if not candles or signal not in ("BUY", "SELL"):
        return
    # หาแท่งสีตรงกับ direction (แท่งแรก = chronological first ใน pattern)
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

    # ถ้ามี state เดิมที่ phase=triggered → คงไว้ (รอเทรดจบก่อน reset)
    existing = _s11_state.get(tf_name)
    if existing and existing.get("phase") == "triggered":
        return

    _s11_state[tf_name] = {
        "direction": signal,
        "anchor_high": anchor_high,
        "anchor_low": anchor_low,
        "anchor_time": int(last_close_time),
        "phase": "armed",
        "triggered_level": None,
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
    ถ้าแตะ → return order signal (LIMIT)
    """
    state = _s11_state.get(tf_name)
    if not state:
        return {"signal": "WAIT", "reason": f"S11 ยังไม่มี anchor (รอ S1 pattern ที่ {tf_name})"}
    if state.get("phase") != "armed":
        return {"signal": "WAIT", "reason": f"S11 phase={state.get('phase')} (รอเทรดจบ)"}

    if rates is None or len(rates) == 0:
        return {"signal": "WAIT", "reason": "S11 ไม่มี rates"}

    direction = state["direction"]
    anchor_high = state["anchor_high"]
    anchor_low = state["anchor_low"]

    # เช็กแท่งล่าสุด (ปิดแล้ว) ว่า wick แตะ trigger level ไหม
    last_bar = rates[-1]
    last_high = float(last_bar["high"])
    last_low = float(last_bar["low"])

    for pattern_idx, (trigger_level, entry_level) in enumerate(FIBO_TRIGGER_LEVELS, start=1):
        trigger_price = _level_to_price(trigger_level, anchor_high, anchor_low, direction)

        # BUY: trigger อยู่เหนือ anchor → wick high แตะ
        # SELL: trigger อยู่ใต้ anchor → wick low แตะ
        if direction == "BUY":
            touched = last_high >= trigger_price
        else:
            touched = last_low <= trigger_price
        if not touched:
            continue

        entry_price = _level_to_price(entry_level, anchor_high, anchor_low, direction)
        sl_price = _level_to_price(FIBO_SL, anchor_high, anchor_low, direction)
        tp_price = _level_to_price(FIBO_TP, anchor_high, anchor_low, direction)

        # Validate ราคา
        if direction == "BUY" and not (sl_price < entry_price < tp_price):
            continue
        if direction == "SELL" and not (tp_price < entry_price < sl_price):
            continue

        # Update state → triggered
        state["phase"] = "triggered"
        state["triggered_level"] = trigger_level

        sig_e = "🟢" if direction == "BUY" else "🔴"
        trigger_label = FIBO_LEVELS.get(trigger_level, str(trigger_level))
        entry_label = FIBO_LEVELS.get(entry_level, str(entry_level))
        sl_label = FIBO_LEVELS.get(FIBO_SL, str(FIBO_SL))
        tp_label = FIBO_LEVELS.get(FIBO_TP, str(FIBO_TP))
        return {
            "signal": direction,
            "entry": round(entry_price, 2),
            "sl": round(sl_price, 2),
            "tp": round(tp_price, 2),
            "pattern": f"ท่าที่ 11 Fibo S1 {sig_e} {direction} — Pattern {pattern_idx} ({trigger_label})",
            "reason": (
                f"Pattern {pattern_idx}: แตะ {trigger_label} → LIMIT @ {entry_label}\n"
                f"Anchor [H:{anchor_high:.2f} L:{anchor_low:.2f}]\n"
                f"แตะ Fibo {trigger_level} ({trigger_label}) @ {trigger_price:.2f}\n"
                f"LIMIT @ Fibo {entry_level} ({entry_label}) = {entry_price:.2f}\n"
                f"SL: Fibo {FIBO_SL} ({sl_label}) = {sl_price:.2f} | "
                f"TP: Fibo {FIBO_TP} ({tp_label}) = {tp_price:.2f}"
            ),
            "order_mode": "limit",
            "candles": [
                {"open": anchor_low, "high": anchor_high, "low": anchor_low, "close": anchor_high},
                {"open": float(last_bar["open"]), "high": last_high, "low": last_low, "close": float(last_bar["close"])},
            ],
        }

    return {"signal": "WAIT", "reason": f"S11 armed [{direction}] รอแตะ 1.617/3.097/5.165"}
