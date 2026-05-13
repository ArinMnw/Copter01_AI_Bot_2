"""
ท่าที่ 10 — CRT TBS (Candle Range Theory + Three Bar Sweep)

แนวคิด: liquidity sweep + close กลับเข้าในกรอบ = false break = สัญญาณกลับ

Mode (config.CRT_BAR_MODE) — รูปแบบ pattern:
  "2bar" (default — classic CRT) — parent + sweep-and-close-inside (single candle)
  "3bar" (TBS variant)            — parent + sweep + confirm (3 แท่งแยก)

Entry Mode (config.CRT_ENTRY_MODE) — จุดเข้า order:
  "htf" (default) — เข้า market ทันทีตอน HTF detect (M15+) — SL ใหญ่
  "mtf"           — HTF detect → arm state → drop ลง LTF รอ color shift confirm
                    → entry ที่ LTF (SL เล็กลงเยอะ)

LTF mapping (HTF → LTF):
  D1, H12 → M15
  H4 → M5
  H1, M30, M15 → M1

Filter:
  - Parent range ≥ CRT_MIN_RANGE_POINTS
  - Sweep depth ≥ CRT_SWEEP_DEPTH_PCT × parent_range
"""

from config import (
    crt_min_range_price,
    crt_sl_buffer_price,
    CRT_BAR_MODE,
    CRT_SWEEP_DEPTH_PCT,
    fmt_mt5_bkk_ts,
)
import config as _config

# ── LTF mapping for MTF mode ──────────────────────────────────────
_HTF_TO_LTF = {
    "D1":  "M15",
    "H12": "M15",
    "H4":  "M5",
    "H1":  "M1",
    "M30": "M1",
    "M15": "M1",
}
_LTF_TO_HTFS = {}
for _h, _l in _HTF_TO_LTF.items():
    _LTF_TO_HTFS.setdefault(_l, []).append(_h)

_TF_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}

# ── Armed states for MTF mode ─────────────────────────────────────
# {htf_tf: {direction, sl_target, tp_target, armed_at, htf_tf, ltf_tf, candles, pattern_base}}
_armed_states: dict = {}
# track armed_at ที่เคย fire order แล้ว — ป้องกัน re-arm ด้วย HTF bar เดิม
_last_fired_armed_at: dict = {}  # {htf_tf: armed_at}


def _candle_dict(c):
    d = {
        "open":  float(c["open"]),
        "high":  float(c["high"]),
        "low":   float(c["low"]),
        "close": float(c["close"]),
    }
    try:
        d["time"] = int(c["time"])
    except (KeyError, ValueError, IndexError, TypeError):
        pass
    return d


def _arm_target_hit_reason(state, rates, htf_tf: str = "") -> str:
    """
    ถ้า arm ถูก invalidate เพราะราคาวิ่งไปแตะ HTF target ก่อน LTF trigger
    จะคืน reason กลับมา ไม่งั้นคืนค่าว่าง
    """
    if not state or rates is None or len(rates) == 0:
        return ""

    direction = str(state.get("direction", "") or "").upper()
    armed_at = int(state.get("armed_at", 0) or 0)
    tp_target = float(state.get("tp_target", 0.0) or 0.0)
    if direction not in ("BUY", "SELL") or armed_at <= 0 or tp_target <= 0:
        return ""

    # 1) invalidate ทันทีถ้า HTF sweep candle แตะ target แล้ว
    htf_candles = state.get("candles") or []
    if len(htf_candles) >= 2:
        sweep = htf_candles[1]
        s_high = float(_s10_bar_value(sweep, "high", 0.0) or 0.0)
        s_low = float(_s10_bar_value(sweep, "low", 0.0) or 0.0)
        sweep_time = _s10_bar_int(sweep, "time", 0)
        if direction == "BUY" and s_high >= tp_target:
            return (
                f"S10 MTF: invalidate {htf_tf or state.get('htf_tf', '')} BUY arm "
                f"(HTF sweep แตะ TP {tp_target:.2f} แล้ว @ "
                f"{fmt_mt5_bkk_ts(sweep_time, '%H:%M %d-%b-%Y')})"
            )
        if direction == "SELL" and s_low <= tp_target:
            return (
                f"S10 MTF: invalidate {htf_tf or state.get('htf_tf', '')} SELL arm "
                f"(HTF sweep แตะ TP {tp_target:.2f} แล้ว @ "
                f"{fmt_mt5_bkk_ts(sweep_time, '%H:%M %d-%b-%Y')})"
            )

    # 2) invalidate ถ้ามี LTF bar หลัง armed_at แตะ target ไปก่อน trigger
    for i in range(len(rates)):
        bar = rates[i]
        bar_time = _s10_bar_int(bar, "time", 0)
        if bar_time <= armed_at:
            continue
        bar_high = float(_s10_bar_value(bar, "high", 0.0) or 0.0)
        bar_low = float(_s10_bar_value(bar, "low", 0.0) or 0.0)
        if direction == "BUY" and bar_high >= tp_target:
            return (
                f"S10 MTF: invalidate {htf_tf or state.get('htf_tf', '')} BUY arm "
                f"(LTF แตะ TP {tp_target:.2f} ก่อน trigger @ "
                f"{fmt_mt5_bkk_ts(bar_time, '%H:%M %d-%b-%Y')})"
            )
        if direction == "SELL" and bar_low <= tp_target:
            return (
                f"S10 MTF: invalidate {htf_tf or state.get('htf_tf', '')} SELL arm "
                f"(LTF แตะ TP {tp_target:.2f} ก่อน trigger @ "
                f"{fmt_mt5_bkk_ts(bar_time, '%H:%M %d-%b-%Y')})"
            )
    return ""


# ══════════════════════════════════════════════════════════════════
# Public entry point
# ══════════════════════════════════════════════════════════════════

def strategy_10(rates, tf_name: str = ""):
    """
    Public entry point — branch ตาม CRT_ENTRY_MODE
    - htf: detect บน HTF + entry ทันที (logic เดิม)
    - mtf: detect บน HTF → arm; LTF เช็ก color shift → entry
    """
    if len(rates) < 4:
        return {"signal": "WAIT", "reason": "ข้อมูลไม่พอ (ต้องการอย่างน้อย 4 แท่ง)"}

    entry_mode = getattr(_config, "CRT_ENTRY_MODE", "htf")
    if entry_mode == "mtf":
        return _strategy_10_mtf(rates, tf_name)
    return _strategy_10_htf(rates)


# ══════════════════════════════════════════════════════════════════
# HTF mode (original — entry บน HTF ทันที)
# ══════════════════════════════════════════════════════════════════

def _strategy_10_htf(rates):
    mode = CRT_BAR_MODE if CRT_BAR_MODE in ("2bar", "3bar") else "2bar"
    if mode == "2bar":
        return _strategy_10_2bar(rates)
    return _strategy_10_3bar(rates)


def _strategy_10_2bar(rates):
    if rates is None or len(rates) < 3:
        return {"signal": "WAIT", "reason": "[2bar] ไม่มีข้อมูลเพียงพอ"}

    min_range = crt_min_range_price()
    buffer    = crt_sl_buffer_price()
    lookback  = 10  # สแกนย้อนหลังสูงสุด 10 แท่ง HTF
    start_pi  = max(0, len(rates) - lookback)
    last_reason = "[2bar] ไม่พบ CRT TBS Setup"

    # สแกนหา (parent, sweep) pair — sweep เป็นแท่งที่ >= 2 หลัง parent
    # คืนค่า sweep ล่าสุดที่ valid ที่สุด (sweep index สูงสุด)
    best_si     = -1
    best_result = None

    for pi in range(start_pi, len(rates) - 1):
        parent  = rates[pi]
        p_high  = float(parent["high"])
        p_low   = float(parent["low"])
        p_range = p_high - p_low
        if p_range < min_range:
            last_reason = (
                f"[2bar] Parent range เล็กไป "
                f"(H:{p_high:.2f} L:{p_low:.2f} range:{p_range:.2f} < {min_range:.2f})"
            )
            continue
        min_depth = p_range * float(CRT_SWEEP_DEPTH_PCT)
        parent_time = _s10_bar_int(parent, "time", 0)
        parent_ts = fmt_mt5_bkk_ts(parent_time, "%H:%M %d-%b-%Y") if parent_time else "?"

        inter_high_broken = False  # แท่งระหว่าง parent-sweep ทะลุ p_high ไปแล้ว
        inter_low_broken  = False  # แท่งระหว่าง parent-sweep ทะลุ p_low ไปแล้ว

        for si in range(pi + 1, len(rates)):
            if si <= best_si:
                # อัปเดต intermediate break สำหรับแท่งที่ข้ามไป
                if si > pi + 1:
                    prev = rates[si - 1]
                    if float(prev["high"]) > p_high:
                        inter_high_broken = True
                    if float(prev["low"]) < p_low:
                        inter_low_broken = True
                continue

            # อัปเดต intermediate break ก่อนเช็ค si
            if si > pi + 1:
                prev = rates[si - 1]
                if float(prev["high"]) > p_high:
                    inter_high_broken = True
                if float(prev["low"]) < p_low:
                    inter_low_broken = True

            # ถ้าทั้ง high และ low ถูกทะลุแล้ว parent นี้ใช้ไม่ได้อีก
            if inter_high_broken and inter_low_broken:
                last_reason = (
                    f"[2bar] Parent {parent_ts} ถูกทะลุทั้งสองด้านก่อน sweep "
                    f"(high>{p_high:.2f} และ low<{p_low:.2f})"
                )
                break

            sweep   = rates[si]
            s_open  = float(sweep["open"])
            s_high  = float(sweep["high"])
            s_low   = float(sweep["low"])
            s_close = float(sweep["close"])
            candles = [_candle_dict(parent), _candle_dict(sweep)]
            sweep_time = _s10_bar_int(sweep, "time", 0)
            sweep_ts = fmt_mt5_bkk_ts(sweep_time, "%H:%M %d-%b-%Y") if sweep_time else "?"

            # BUY: sweep low, ปิดกลับเข้า range (ยอมรับ doji)
            if not inter_low_broken and s_low < p_low and s_close > p_low and s_close >= s_open:
                sweep_depth = p_low - s_low
                if sweep_depth < min_depth:
                    last_reason = (
                        f"[2bar BUY] Sweep {sweep_ts} ตื้นไป "
                        f"(depth:{sweep_depth:.2f} < {min_depth:.2f} = {CRT_SWEEP_DEPTH_PCT*100:.0f}% ของ range)"
                    )
                    continue
                entry = round(s_close, 2)
                sl    = round(s_low - buffer, 2)
                tp    = round(p_high, 2)
                if not (sl < entry < tp):
                    last_reason = (
                        f"[2bar BUY] Sweep {sweep_ts} SL/TP ไม่ valid "
                        f"(SL:{sl:.2f} Entry:{entry:.2f} TP:{tp:.2f})"
                    )
                    continue
                risk = entry - sl
                rr   = round((tp - entry) / risk, 2) if risk > 0 else 0
                best_si     = si
                best_result = {
                    "signal": "BUY",
                    "pattern": "ท่าที่ 10 CRT TBS 🟢 BUY — Sweep Low (2bar)",
                    "entry": entry, "sl": sl, "tp": tp,
                    "order_mode": "market",
                    "reason": (
                        f"[2bar] Parent[H:{p_high:.2f} L:{p_low:.2f} range:{p_range:.2f}] "
                        f"SweepClose🟢[L:{s_low:.2f} depth:{sweep_depth:.2f} C:{s_close:.2f}>{p_low:.2f}]\n"
                        f"Entry:{entry} SL:{sl} TP:{tp} RR1:{rr}"
                    ),
                    "candles": candles,
                }

            # SELL: sweep high, ปิดต่ำกว่า high ของ parent (ยอมรับ doji)
            elif not inter_high_broken and s_high > p_high and s_close < p_high and s_close <= s_open:
                sweep_depth = s_high - p_high
                if sweep_depth < min_depth:
                    last_reason = (
                        f"[2bar SELL] Sweep {sweep_ts} ตื้นไป "
                        f"(depth:{sweep_depth:.2f} < {min_depth:.2f} = {CRT_SWEEP_DEPTH_PCT*100:.0f}% ของ range)"
                    )
                    continue
                entry = round(s_close, 2)
                sl    = round(s_high + buffer, 2)
                tp    = round(p_low, 2)
                if not (tp < entry < sl):
                    last_reason = (
                        f"[2bar SELL] Sweep {sweep_ts} SL/TP ไม่ valid "
                        f"(TP:{tp:.2f} Entry:{entry:.2f} SL:{sl:.2f})"
                    )
                    continue
                risk = sl - entry
                rr   = round((entry - tp) / risk, 2) if risk > 0 else 0
                best_si     = si
                best_result = {
                    "signal": "SELL",
                    "pattern": "ท่าที่ 10 CRT TBS 🔴 SELL — Sweep High (2bar)",
                    "entry": entry, "sl": sl, "tp": tp,
                    "order_mode": "market",
                    "reason": (
                        f"[2bar] Parent[H:{p_high:.2f} L:{p_low:.2f} range:{p_range:.2f}] "
                        f"SweepClose🔴[H:{s_high:.2f} depth:{sweep_depth:.2f} C:{s_close:.2f}<{p_high:.2f}]\n"
                        f"Entry:{entry} SL:{sl} TP:{tp} RR1:{rr}"
                    ),
                    "candles": candles,
                }
            else:
                side_hints = []
                if s_low < p_low:
                    if not (s_close > p_low):
                        side_hints.append(f"BUY close:{s_close:.2f} ยังไม่กลับเหนือ parent low:{p_low:.2f}")
                    elif not (s_close >= s_open):
                        side_hints.append(f"BUY candle ไม่เขียว/dojiพอ (O:{s_open:.2f} C:{s_close:.2f})")
                if s_high > p_high:
                    if not (s_close < p_high):
                        side_hints.append(f"SELL close:{s_close:.2f} ยังไม่กลับต่ำกว่า parent high:{p_high:.2f}")
                    elif not (s_close <= s_open):
                        side_hints.append(f"SELL candle ไม่แดง/dojiพอ (O:{s_open:.2f} C:{s_close:.2f})")
                if not side_hints:
                    side_hints.append(
                        f"ยังไม่ sweep parent (parent H:{p_high:.2f} L:{p_low:.2f} | sweep H:{s_high:.2f} L:{s_low:.2f})"
                    )
                last_reason = f"[2bar] Parent {parent_ts} / Sweep {sweep_ts}: " + " | ".join(side_hints)

    if best_result:
        return best_result
    return {"signal": "WAIT", "reason": last_reason}


def _strategy_10_3bar(rates):
    parent  = rates[-3]
    sweep   = rates[-2]
    confirm = rates[-1]

    p_high = float(parent["high"])
    p_low  = float(parent["low"])
    p_range = p_high - p_low
    min_range = crt_min_range_price()
    if p_range < min_range:
        return {
            "signal": "WAIT",
            "reason": f"[3bar] Parent range เล็กไป ({p_range:.2f} < {min_range:.2f})",
        }

    s_high = float(sweep["high"])
    s_low  = float(sweep["low"])
    c_open  = float(confirm["open"])
    c_close = float(confirm["close"])
    buffer  = crt_sl_buffer_price()
    min_depth = p_range * float(CRT_SWEEP_DEPTH_PCT)

    candles = [_candle_dict(parent), _candle_dict(sweep), _candle_dict(confirm)]

    if s_low < p_low and c_close > p_low and c_close > c_open:
        sweep_depth = p_low - s_low
        if sweep_depth < min_depth:
            return {
                "signal": "WAIT",
                "reason": f"[3bar BUY] Sweep ตื้นไป ({sweep_depth:.2f} < {min_depth:.2f} = {CRT_SWEEP_DEPTH_PCT*100:.0f}% ของ range)",
            }
        entry = round(c_close, 2)
        sl    = round(s_low - buffer, 2)
        tp    = round(p_high, 2)
        if not (sl < entry < tp):
            return {"signal": "WAIT", "reason": "[3bar BUY] SL/TP ไม่ valid"}
        risk = entry - sl
        rr = round((tp - entry) / risk, 2) if risk > 0 else 0
        return {
            "signal": "BUY",
            "pattern": "ท่าที่ 10 CRT TBS 🟢 BUY — Sweep Low (3bar)",
            "entry": entry, "sl": sl, "tp": tp,
            "order_mode": "market",
            "reason": (
                f"[3bar] Parent[H:{p_high:.2f} L:{p_low:.2f} range:{p_range:.2f}] "
                f"Sweep[L:{s_low:.2f} depth:{sweep_depth:.2f}] "
                f"Confirm🟢[O:{c_open:.2f} C:{c_close:.2f}>{p_low:.2f}]\n"
                f"Entry:{entry} SL:{sl} TP:{tp} RR1:{rr}"
            ),
            "candles": candles,
        }

    if s_high > p_high and c_close < p_high and c_close < c_open:
        sweep_depth = s_high - p_high
        if sweep_depth < min_depth:
            return {
                "signal": "WAIT",
                "reason": f"[3bar SELL] Sweep ตื้นไป ({sweep_depth:.2f} < {min_depth:.2f} = {CRT_SWEEP_DEPTH_PCT*100:.0f}% ของ range)",
            }
        entry = round(c_close, 2)
        sl    = round(s_high + buffer, 2)
        tp    = round(p_low, 2)
        if not (tp < entry < sl):
            return {"signal": "WAIT", "reason": "[3bar SELL] SL/TP ไม่ valid"}
        risk = sl - entry
        rr = round((entry - tp) / risk, 2) if risk > 0 else 0
        return {
            "signal": "SELL",
            "pattern": "ท่าที่ 10 CRT TBS 🔴 SELL — Sweep High (3bar)",
            "entry": entry, "sl": sl, "tp": tp,
            "order_mode": "market",
            "reason": (
                f"[3bar] Parent[H:{p_high:.2f} L:{p_low:.2f} range:{p_range:.2f}] "
                f"Sweep[H:{s_high:.2f} depth:{sweep_depth:.2f}] "
                f"Confirm🔴[O:{c_open:.2f} C:{c_close:.2f}<{p_high:.2f}]\n"
                f"Entry:{entry} SL:{sl} TP:{tp} RR1:{rr}"
            ),
            "candles": candles,
        }

    return {"signal": "WAIT", "reason": "[3bar] ไม่พบ CRT TBS Setup"}


def _s10_bar_value(bar, key: str, default=0.0):
    """Read from dict-like bars and numpy.void rows returned by MT5 copy_rates_*."""
    if bar is None:
        return default
    try:
        if hasattr(bar, "get"):
            return bar.get(key, default)
    except Exception:
        pass
    try:
        return bar[key]
    except Exception:
        return default


def _s10_bar_int(bar, key: str, default=0) -> int:
    try:
        return int(_s10_bar_value(bar, key, default) or default)
    except Exception:
        return int(default)


def is_s10_htf_sweep_valid(parent, sweep, signal: str, mode: str = "") -> bool:
    """Validate ว่า parent/sweep pair ยังเป็น CRT sweep จริงหรือไม่เมื่อแท่ง HTF ปิดแล้ว"""
    if parent is None or sweep is None or signal not in ("BUY", "SELL"):
        return False

    use_mode = mode or CRT_BAR_MODE
    if use_mode not in ("2bar", "3bar"):
        use_mode = "2bar"
    if use_mode != "2bar":
        return False

    p_high = float(_s10_bar_value(parent, "high", 0) or 0)
    p_low = float(_s10_bar_value(parent, "low", 0) or 0)
    s_open = float(_s10_bar_value(sweep, "open", 0) or 0)
    s_high = float(_s10_bar_value(sweep, "high", 0) or 0)
    s_low = float(_s10_bar_value(sweep, "low", 0) or 0)
    s_close = float(_s10_bar_value(sweep, "close", 0) or 0)
    p_range = p_high - p_low
    if p_range < crt_min_range_price():
        return False
    min_depth = p_range * float(CRT_SWEEP_DEPTH_PCT)
    if signal == "BUY":
        sweep_depth = p_low - s_low
        return (
            s_low < p_low
            and s_close > p_low
            and s_close >= s_open
            and sweep_depth >= min_depth
        )

    sweep_depth = s_high - p_high
    return (
        s_high > p_high
        and s_close < p_high
        and s_close <= s_open
        and sweep_depth >= min_depth
    )


# ══════════════════════════════════════════════════════════════════
# MTF mode (HTF detect → arm; LTF color-shift → entry)
# ══════════════════════════════════════════════════════════════════

def _strategy_10_mtf(rates, tf_name: str):
    if not tf_name:
        return {"signal": "WAIT", "reason": "S10 MTF: ไม่ทราบ TF"}

    # Step 1: ถ้า TF นี้เป็น LTF ของ armed HTF → เช็ก trigger
    htfs_for_this_ltf = _LTF_TO_HTFS.get(tf_name, [])
    for htf in htfs_for_this_ltf:
        state = _armed_states.get(htf)
        if not state:
            continue
        invalid_reason = _arm_target_hit_reason(state, rates, htf)
        if invalid_reason:
            _armed_states.pop(htf, None)
            return {"signal": "WAIT", "reason": invalid_reason}
        if _is_armed_expired(state, rates, htf):
            _armed_states.pop(htf, None)
            continue
        trigger = _check_ltf_trigger(rates, state, tf_name, htf)
        if trigger:
            _last_fired_armed_at[htf] = state["armed_at"]  # กัน re-arm ด้วย bar เดิม
            _armed_states.pop(htf, None)   # consumed
            return trigger

    # Step 2: ถ้า TF นี้เป็น HTF ใน mapping → run detection + arm
    if tf_name in _HTF_TO_LTF:
        htf_result = _strategy_10_htf(rates)
        sig = htf_result.get("signal")
        if sig in ("BUY", "SELL"):
            _arm_htf_state(htf_result, tf_name, rates)
            return {
                "signal": "WAIT",
                "reason": f"S10 MTF: armed {sig} on {tf_name} → รอ color shift บน {_HTF_TO_LTF[tf_name]}",
            }
        return {"signal": "WAIT", "reason": f"S10 MTF: HTF {tf_name} {htf_result.get('reason', '')}"}

    return {"signal": "WAIT", "reason": f"S10 MTF: TF {tf_name} ไม่อยู่ใน HTF/LTF mapping"}


def _arm_htf_state(htf_result, htf_tf: str, rates):
    if rates is None or len(rates) == 0:
        return
    last_bar = rates[-1]
    new_armed_at = int(last_bar["time"])
    if new_armed_at == _last_fired_armed_at.get(htf_tf):
        return  # HTF bar นี้เคย fire order ไปแล้ว — ไม่ re-arm
    new_state = {
        "direction":    htf_result["signal"],
        "sl_target":    float(htf_result["sl"]),
        "tp_target":    float(htf_result["tp"]),
        "armed_at":     int(last_bar["time"]),
        "htf_tf":       htf_tf,
        "ltf_tf":       _HTF_TO_LTF[htf_tf],
        "candles":      htf_result.get("candles", []),
        "pattern_base": htf_result.get("pattern", ""),
    }
    # ถ้าแท่ง HTF ที่เป็น sweep แตะ target ไปแล้ว setup ถือว่าหมดความสด ไม่ต้อง arm
    if _arm_target_hit_reason(new_state, rates, htf_tf):
        return
    _armed_states[htf_tf] = new_state


def _is_armed_expired(state, rates, htf_tf: str) -> bool:
    if rates is None or len(rates) == 0:
        return False
    htf_secs = _TF_SECONDS.get(htf_tf, 3600)
    # armed_at = HTF bar open time → HTF close = armed_at + htf_secs
    # expire 1 HTF bar หลัง HTF close (รวม 2 HTF bars หลัง armed)
    expiry = state["armed_at"] + 2 * htf_secs
    last_time = int(rates[-1]["time"])
    return last_time > expiry


# Model 1/3 search range = LTF bars จาก armed_at+1 ถึง engulf_idx-1
# ไม่ใช้ lookback คงที่ — boundary คือ HTF sweep candle open


def _find_phase1_failed_push(rates, direction: str, armed_at: int,
                              parent_high: float, parent_low: float):
    """
    Phase 1: failed-push บน LTF (ยืนยันว่า CRT TBS pattern complete)
    BUY:  RED bar + close < HTF parent.low - 50 points
    SELL: GREEN bar + close > HTF parent.high + 50 points
    เริ่มค้นจาก bar.time > armed_at
    """
    buy_extra_break = float(crt_sl_buffer_price())
    sell_extra_break = float(crt_sl_buffer_price())
    for i in range(1, len(rates)):
        if int(rates[i]["time"]) <= armed_at:
            continue
        bo = float(rates[i]["open"])
        bc = float(rates[i]["close"])
        if direction == "BUY" and bc < bo and bc < (parent_low - buy_extra_break):
            return i
        if direction == "SELL" and bc > bo and bc > (parent_high + sell_extra_break):
            return i
    return None


def _find_phase2_engulfing(rates, direction: str, start_idx: int):
    """
    Phase 2: body-engulf 2-bar pattern (concept จาก S1 — ไม่เรียก S1 จริง)
    BUY engulf:  prev RED + curr GREEN + curr.close > prev.open
    SELL engulf: prev GREEN + curr RED + curr.close < prev.open
    ค้นต่อจาก start_idx + 1
    """
    for i in range(max(1, start_idx + 1), len(rates)):
        prev = rates[i - 1]
        curr = rates[i]
        po = float(prev["open"])
        pc = float(prev["close"])
        co = float(curr["open"])
        cc = float(curr["close"])
        if direction == "BUY":
            if pc < po and cc > co and cc > po:
                return i
        else:
            if pc > po and cc < co and cc < po:
                return i
    return None


def _calc_model1_ob(rates, engulf_idx: int, direction: str, armed_at: int):
    """
    Model 1 — Order Block entry
    SELL:
      1) เขียว -> แดงกลืนกิน
      2) เขียว -> แดง -> แดงกลืนกิน
      ใช้ราคาเปิดของแท่งเขียวเป็น entry
    BUY:
      1) แดง -> เขียวกลืนกิน
      2) แดง -> เขียว -> เขียวกลืนกิน
      ใช้ราคาปิดของแท่งแดงเป็น entry
    """
    if engulf_idx <= 0 or engulf_idx >= len(rates):
        return None

    cur = rates[engulf_idx]
    cur_o = float(cur["open"])
    cur_c = float(cur["close"])

    if direction == "SELL" and cur_c < cur_o:
        prev = rates[engulf_idx - 1]
        prev_o = float(prev["open"])
        prev_c = float(prev["close"])
        if int(prev["time"]) > armed_at and prev_c > prev_o and cur_c < prev_o:
            return prev_o

        if engulf_idx >= 2:
            src = rates[engulf_idx - 2]
            mid = rates[engulf_idx - 1]
            src_o = float(src["open"])
            src_c = float(src["close"])
            mid_o = float(mid["open"])
            mid_c = float(mid["close"])
            if (
                int(src["time"]) > armed_at
                and src_c > src_o
                and mid_c < mid_o
                and cur_c < src_o
            ):
                return src_o

    if direction == "BUY" and cur_c > cur_o:
        prev = rates[engulf_idx - 1]
        prev_o = float(prev["open"])
        prev_c = float(prev["close"])
        if int(prev["time"]) > armed_at and prev_c < prev_o and cur_c > prev_o:
            return prev_c

        if engulf_idx >= 2:
            src = rates[engulf_idx - 2]
            mid = rates[engulf_idx - 1]
            src_o = float(src["open"])
            src_c = float(src["close"])
            mid_o = float(mid["open"])
            mid_c = float(mid["close"])
            if (
                int(src["time"]) > armed_at
                and src_c < src_o
                and mid_c > mid_o
                and cur_c > src_o
            ):
                return src_c
    return None


def _calc_model2_fvg(rates, engulf_idx: int, direction: str):
    """
    Model 2 — FVG 98% (concept จาก S2 — ไม่เรียก S2 จริง)
    3-bar imbalance: B1=engulf_idx-2, B2=engulf_idx-1, B3=engulf_idx
    Bullish FVG: B1.high < B3.low → entry @ 98% (ลึกใน gap, ใกล้ B1.high)
    Bearish FVG: B1.low > B3.high → entry @ 98% (ลึกใน gap, ใกล้ B1.low)
    """
    if engulf_idx < 2:
        return None
    b1 = rates[engulf_idx - 2]
    b3 = rates[engulf_idx]
    b1_high = float(b1["high"])
    b1_low  = float(b1["low"])
    b3_high = float(b3["high"])
    b3_low  = float(b3["low"])
    if direction == "BUY":
        # Bullish FVG: gap ระหว่าง [b1.high, b3.low]
        if b3_low > b1_high:
            # 98% deep = ใกล้ b1.high (ราคา retrace ลงลึก)
            return b3_low - 0.98 * (b3_low - b1_high)
    else:
        # Bearish FVG: gap ระหว่าง [b3.high, b1.low]
        if b1_low > b3_high:
            # 98% deep = ใกล้ b1.low (ราคา retrace ขึ้นลึก)
            return b3_high + 0.98 * (b1_low - b3_high)
    return None


def _calc_model3_mss(rates, engulf_idx: int, direction: str, armed_at: int):
    """
    Model 3 — MSS swing point (confirmation only, ไม่ใช้เป็น entry)
    SELL: lowest low ภายใน LTF range (armed_at, engulf_idx)
    BUY:  highest high ภายใน LTF range (armed_at, engulf_idx)
    """
    lows = []
    highs = []
    for j in range(engulf_idx - 1, -1, -1):
        if int(rates[j]["time"]) <= armed_at:
            break
        lows.append(float(rates[j]["low"]))
        highs.append(float(rates[j]["high"]))
    if not lows:
        return None
    if direction == "SELL":
        return min(lows)
    return max(highs)


def _check_ltf_trigger(rates, state, ltf_tf: str, htf_tf: str):
    """
    CRT TBS Classic MTF — 2 phase + 3 model entry
    Phase 1: failed-push บน LTF เพื่อ confirm pattern
    Phase 2: engulfing บน LTF เพื่อหา entry
    Models:
      #1 Order Block (recommended) — entry @ OB.open
      #2 FVG 98%                   — entry ลึกใน FVG
      #3 MSS swing point           — confirmation only (log)
    เลือก Model 1 ก่อน, fallback Model 2
    """
    if rates is None or len(rates) < 3:
        return None
    direction = state["direction"]
    armed_at = int(state["armed_at"])

    htf_candles = state.get("candles") or []
    if not htf_candles:
        return None
    parent = htf_candles[0]
    parent_high = float(_s10_bar_value(parent, "high", 0) or 0)
    parent_low = float(_s10_bar_value(parent, "low", 0) or 0)
    if parent_high <= 0 or parent_low <= 0:
        return None

    # Phase 1: failed-push (pattern confirmation)
    phase1_idx = _find_phase1_failed_push(rates, direction, armed_at, parent_high, parent_low)
    if phase1_idx is None:
        return None

    # Phase 2: engulfing (entry trigger search)
    trigger_idx = phase1_idx

    # คำนวณ 3 models (Model 1/3 ใช้ armed_at เป็นขอบ, Model 2 ใช้ 3-bar window รอบ engulf)
    m1_entry = None
    m2_entry = None
    m3_level = None
    m1_idx = None
    m2_idx = None
    m3_idx = None
    for idx in range(trigger_idx, len(rates)):
        if m1_entry is None:
            v = _calc_model1_ob(rates, idx, direction, armed_at)
            if v is not None:
                m1_entry = v
                m1_idx = idx
        if m2_entry is None:
            v = _calc_model2_fvg(rates, idx, direction)
            if v is not None:
                m2_entry = v
                m2_idx = idx
        if m3_level is None:
            v = _calc_model3_mss(rates, idx, direction, armed_at)
            if v is not None:
                m3_level = v
                m3_idx = idx
        if m1_entry is not None and m2_entry is not None and m3_level is not None:
            break

    # Entry priority: Model 1 -> fallback Model 2
    # Model 3 ใช้เป็น log/confirmation เท่านั้น ไม่บังคับเป็น entry
    if m1_entry is None and m2_entry is None:
        return None

    sl = round(float(state["sl_target"]), 2)
    tp = round(float(state["tp_target"]), 2)

    m1_str = f"{m1_entry:.2f}" if m1_entry is not None else "n/a"
    m2_str = f"{m2_entry:.2f}" if m2_entry is not None else "n/a"
    m3_str = f"{m3_level:.2f}" if m3_level is not None else "n/a"
    m1_time = fmt_mt5_bkk_ts(int(rates[m1_idx]["time"]), "%H:%M %d-%b-%Y") if m1_idx is not None else "n/a"
    m2_time = fmt_mt5_bkk_ts(int(rates[m2_idx]["time"]), "%H:%M %d-%b-%Y") if m2_idx is not None else "n/a"
    m3_time = fmt_mt5_bkk_ts(int(rates[m3_idx]["time"]), "%H:%M %d-%b-%Y") if m3_idx is not None else "n/a"
    sig_e = "🟢" if direction == "BUY" else "🔴"

    phase1_bar = rates[phase1_idx]
    p1_close = float(phase1_bar["close"])

    def _is_valid_entry(v) -> bool:
        if v is None:
            return False
        vv = round(float(v), 2)
        if direction == "BUY":
            return sl < vv < tp
        return tp < vv < sl

    model_orders = []
    if _is_valid_entry(m1_entry):
        model_orders.append({
            "model": 1,
            "entry": round(float(m1_entry), 2),
            "pattern": f"ท่าที่ 10 CRT TBS {sig_e} {direction} — MTF TBS [{htf_tf}→{ltf_tf}] Model1",
            "entry_label": "BUY LIMIT ที่" if direction == "BUY" else "SELL LIMIT ที่",
        })
    if _is_valid_entry(m2_entry):
        model2_entry = round(float(m2_entry), 2)
        if not model_orders or abs(float(model_orders[0]["entry"]) - model2_entry) > 0.01:
            model_orders.append({
                "model": 2,
                "entry": model2_entry,
                "pattern": f"ท่าที่ 10 CRT TBS {sig_e} {direction} — MTF TBS [{htf_tf}→{ltf_tf}] Model2",
                "entry_label": "BUY LIMIT ที่" if direction == "BUY" else "SELL LIMIT ที่",
            })

    if not model_orders:
        return None

    trigger_idx = max(i for i in (m1_idx, m2_idx, m3_idx) if i is not None)
    entry = round(float(model_orders[0]["entry"]), 2)
    model_used = int(model_orders[0]["model"])
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr = round(reward / risk, 2) if risk > 0 else 0

    return {
        "signal":     direction,
        "entry":      entry,
        "sl":         sl,
        "tp":         tp,
        "order_mode": "limit",
        "entry_label": "BUY LIMIT ที่" if direction == "BUY" else "SELL LIMIT ที่",
        "pattern":    f"ท่าที่ 10 CRT TBS {sig_e} {direction} — MTF TBS [{htf_tf}→{ltf_tf}] Model{model_used}",
        "reason": (
            f"[MTF {htf_tf}→{ltf_tf}] HTF armed at bar={armed_at}\n"
            f"Parent[H:{parent_high:.2f} L:{parent_low:.2f}]\n"
            f"Phase 1 (failed-push): bar={phase1_idx} close={p1_close:.2f}\n"
            f"Phase 2: disabled (use Phase 1 as trigger)\n"
            f"Model 1 (OB.open):  {m1_str} @ {m1_time}\n"
            f"Model 2 (FVG 98%):  {m2_str} @ {m2_time}\n"
            f"Model 3 (MSS):      {m3_str} @ {m3_time}\n"
            f"USING Model {model_used} = {entry} | SL:{sl} | TP:{tp} | RR1:{rr}"
        ),
        "candles": [_candle_dict(r) for r in rates[max(0, trigger_idx - 2):trigger_idx + 1]],
        "htf_candles": list(htf_candles),
        "htf_tf": htf_tf,
        "armed_at": armed_at,
        "s10_parent_high": round(float(parent_high), 2),
        "s10_parent_low": round(float(parent_low), 2),
        "s10_parent_time": _s10_bar_int(parent, "time", 0),
        "s10_sweep_time": _s10_bar_int(htf_candles[1], "time", 0) if len(htf_candles) > 1 else 0,
        "s10_bar_mode": CRT_BAR_MODE,
        "s10_model_orders": model_orders,
    }


def reset_mtf_state(htf_tf: str = ""):
    """Reset armed state — เรียกตอน position close หรือ user สั่ง"""
    if htf_tf:
        _armed_states.pop(htf_tf, None)
        _last_fired_armed_at.pop(htf_tf, None)
    else:
        _armed_states.clear()
        _last_fired_armed_at.clear()
