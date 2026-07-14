from __future__ import annotations

import config
from mt5_utils import TF_SECONDS_MAP

try:
    from hhll_swing import _build_zz, _classify_pt
except Exception:  # pragma: no cover - defensive import for standalone tooling
    _build_zz = None
    _classify_pt = None

try:
    from strategy9 import _calc_rsi_values
except Exception:  # pragma: no cover - defensive import for standalone tooling
    _calc_rsi_values = None


PDFIBOPLUS_SKIP_SIDS = set(getattr(config, "PDFIBOPLUS_SKIP_SIDS", {1, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19}))
RSI_FILL_SKIP_SIDS = {1, 9, 11, 14, 15, 16, 17, 18, 19}


def pdfiboplus_applies(sid: int) -> bool:
    return bool(getattr(config, "PDFIBOPLUS_ENABLED", False)) and int(sid or 0) not in PDFIBOPLUS_SKIP_SIDS


def _latest_rsi_from_bars(bars: list[dict]) -> float | None:
    if _calc_rsi_values is None:
        return None
    period = int(getattr(config, "PENDING_RSI_PERIOD", 14) or 14)
    if len(bars) <= period:
        return None
    values = _calc_rsi_values(
        bars,
        period=period,
        applied_price=getattr(config, "PENDING_RSI_APPLIED_PRICE", "close"),
    )
    for value in reversed(values):
        if value is not None:
            return float(value)
    return None


def _rsi_mode2_state_from_bars(bars: list[dict]) -> tuple[str, float | None]:
    if _calc_rsi_values is None:
        return "ANY", None
    period = int(getattr(config, "PENDING_RSI_PERIOD", 14) or 14)
    values = _calc_rsi_values(
        bars,
        period=period,
        applied_price=getattr(config, "PENDING_RSI_APPLIED_PRICE", "close"),
    )
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return "ANY", None
    ob = float(getattr(config, "RSI_MODE2_OB", 70.0) or 70.0)
    os = float(getattr(config, "RSI_MODE2_OS", 30.0) or 30.0)
    mid = float(getattr(config, "RSI_MODE2_MID", 50.0) or 50.0)
    state = "ANY"
    prev = vals[0]
    for cur in vals[1:]:
        if prev >= ob and cur < ob:
            state = "SELL_ONLY"
        elif prev <= os and cur > os:
            state = "BUY_ONLY"
        elif prev <= mid and cur > mid:
            state = "BUY_ONLY"
        elif prev >= mid and cur < mid:
            state = "SELL_ONLY"
        prev = cur
    return state, vals[-1]


def fill_rsi_recheck(trade: dict, bars: list[dict]) -> dict:
    if not getattr(config, "PENDING_RSI_RECHECK_ENABLED", False):
        return {"status": "skip"}
    sid = int(trade.get("sid", 0) or 0)
    if sid in RSI_FILL_SKIP_SIDS:
        return {"status": "skip"}
    side = str(trade.get("signal") or trade.get("side") or "")
    if side not in ("BUY", "SELL"):
        return {"status": "skip"}

    mode = int(getattr(config, "PENDING_RSI_RECHECK_MODE", 1) or 1)
    fail_parts = []
    rsi_val = None

    if mode in (1, 3):
        rsi_val = _latest_rsi_from_bars(bars)
        if rsi_val is None:
            return {"status": "wait", "reason": "RSI unavailable"}
        if side == "BUY":
            threshold = float(getattr(config, "PENDING_RSI_BUY_MAX", 50.0) or 50.0)
            if not (rsi_val < threshold):
                fail_parts.append(f"Mode1 BUY RSI {rsi_val:.2f} >= {threshold:.2f}")
        else:
            threshold = float(getattr(config, "PENDING_RSI_SELL_MIN", 50.0) or 50.0)
            if not (rsi_val > threshold):
                fail_parts.append(f"Mode1 SELL RSI {rsi_val:.2f} <= {threshold:.2f}")

    if mode in (2, 3):
        state, latest = _rsi_mode2_state_from_bars(bars)
        rsi_val = rsi_val if rsi_val is not None else latest
        if latest is None:
            return {"status": "wait", "reason": "RSI mode2 unavailable"}
        if state == "BUY_ONLY" and side == "SELL":
            fail_parts.append("Mode2 BUY_ONLY blocks SELL")
        elif state == "SELL_ONLY" and side == "BUY":
            fail_parts.append("Mode2 SELL_ONLY blocks BUY")

    if fail_parts:
        return {"status": "fail", "reason": " | ".join(fail_parts), "rsi": rsi_val}
    return {"status": "pass", "reason": "RSI Fill Recheck pass", "rsi": rsi_val}


def _swing_pair(hh, lh):
    if hh and lh:
        return hh if hh["time"] >= lh["time"] else lh
    return hh or lh


def _prev_swing_pair(hh, lh):
    if hh and lh:
        return lh if hh["time"] >= lh["time"] else hh
    return None


def hhll_snapshot_from_bars(bars: list[dict]) -> dict:
    if _build_zz is None or _classify_pt is None:
        return {}

    lb = int(getattr(config, "HHLL_LEFT", 5) or 5)
    rb = int(getattr(config, "HHLL_RIGHT", 5) or 5)
    lookback = int(getattr(config, "HHLL_LOOKBACK", 500) or 500)
    need = lb + rb + 10
    if len(bars) < need:
        return {}

    window = bars[-(lookback + lb + rb + 5):]
    zz = _build_zz(window, lb, rb)
    if len(zz) < 5:
        return {}

    buckets = {"HH": None, "HL": None, "LH": None, "LL": None}
    prev_buckets = {"HH": None, "HL": None, "LH": None, "LL": None}
    structure = []
    for k in range(len(zz)):
        label = _classify_pt(zz, k)
        if not label:
            continue
        point = {"price": float(zz[k]["price"]), "time": int(zz[k]["time"]), "label": label}
        prev_buckets[label] = buckets[label]
        buckets[label] = point
        structure.append(label)

    sh = _swing_pair(buckets["HH"], buckets["LH"])
    sl = _swing_pair(buckets["HL"], buckets["LL"])
    prev_sh = _prev_swing_pair(buckets["HH"], buckets["LH"])
    prev_sl = _prev_swing_pair(buckets["HL"], buckets["LL"])
    if not sh or not sl:
        return {}
    return {
        "sh": sh,
        "sl": sl,
        "prev_sh": prev_sh,
        "prev_sl": prev_sl,
        "hh": buckets["HH"],
        "hl": buckets["HL"],
        "lh": buckets["LH"],
        "ll": buckets["LL"],
        "prev_hh": prev_buckets["HH"],
        "prev_hl": prev_buckets["HL"],
        "prev_lh": prev_buckets["LH"],
        "prev_ll": prev_buckets["LL"],
        "last_label": structure[-1] if structure else "",
        "structure": list(reversed(structure[-6:])),
    }


def _bar_by_time(bars: list[dict], ts: int) -> dict | None:
    for bar in reversed(bars):
        if int(bar.get("time", 0) or 0) == int(ts):
            return bar
    return None


def _valid_sweep_target(candidates: list[dict | None], close_price: float, side: str) -> dict | None:
    for point in candidates:
        if not point:
            continue
        price = float(point.get("price", 0.0) or 0.0)
        if price <= 0:
            continue
        if side == "BUY" and close_price > price:
            return point
        if side == "SELL" and close_price < price:
            return point
    return None


def _limit_sweep_in_range(order: dict, side: str, target_price: float, sh_price: float, sl_price: float) -> bool:
    if int(order.get("sid", 0) or 0) == 8:
        return True
    entry = float(order.get("entry", 0.0) or 0.0)
    if side == "BUY":
        return target_price <= entry <= sh_price
    return sl_price <= entry <= target_price


def limit_sweep_followup_s8(trade: dict, bars: list[dict], pending: list[dict], bar: dict, prev_bar: dict | None, tf_name: str) -> dict:
    if not getattr(config, "LIMIT_SWEEP", False):
        return {"status": "skip"}
    if not prev_bar:
        return {"status": "skip"}

    side = str(trade.get("signal") or trade.get("side") or "")
    close_price = float(bar.get("close", 0.0) or 0.0)
    open_price = float(bar.get("open", 0.0) or 0.0)
    prev_high = float(prev_bar.get("high", 0.0) or 0.0)
    prev_low = float(prev_bar.get("low", 0.0) or 0.0)

    buy_sweep = side == "BUY" and close_price < open_price and close_price < prev_low
    sell_sweep = side == "SELL" and close_price > open_price and close_price > prev_high
    if not buy_sweep and not sell_sweep:
        return {"status": "skip"}

    snap = hhll_snapshot_from_bars(bars)
    sh = snap.get("sh")
    sl = snap.get("sl")
    if not sh or not sl:
        return {"status": "close", "new_order": None, "reason": "Limit Sweep close; no swing target"}

    if side == "BUY":
        target = _valid_sweep_target([snap.get("ll"), snap.get("prev_ll")], close_price, side)
    else:
        target = _valid_sweep_target([snap.get("hh"), snap.get("prev_hh")], close_price, side)
    if not target:
        return {"status": "close", "new_order": None, "reason": "Limit Sweep close; no valid HH/LL target"}

    target_bar = _bar_by_time(bars, int(target.get("time", 0) or 0))
    if not target_bar:
        return {"status": "close", "new_order": None, "reason": "Limit Sweep close; target candle unavailable"}

    target_price = float(target.get("price", 0.0) or 0.0)
    sh_price = float(sh.get("price", 0.0) or 0.0)
    sl_price = float(sl.get("price", 0.0) or 0.0)
    same_side_pending = [
        order for order in pending
        if str(order.get("signal") or order.get("side") or "") == side
        and str(order.get("tf") or tf_name) == tf_name
        and _limit_sweep_in_range(order, side, target_price, sh_price, sl_price)
    ]
    if same_side_pending:
        nearest = min(
            same_side_pending,
            key=lambda order: abs(float(order.get("entry", 0.0) or 0.0) - close_price),
        )
        return {"status": "close", "new_order": None, "kept_order": nearest, "reason": "Limit Sweep close; kept existing pending"}

    c_high = float(target_bar.get("high", 0.0) or 0.0)
    c_low = float(target_bar.get("low", 0.0) or 0.0)
    c_range = c_high - c_low
    if c_range <= 0:
        return {"status": "close", "new_order": None, "reason": "Limit Sweep close; invalid target candle"}

    if side == "BUY":
        entry = c_low - (c_range * 0.17)
        sl = c_low - (c_range * 0.31)
        tp = sh_price if sh_price > 0 else c_high
    else:
        entry = c_high + (c_range * 0.17)
        sl = c_high + (c_range * 0.31)
        tp = sl_price if sl_price > 0 else c_low

    new_order = {
        "sid": 8,
        "tf": tf_name,
        "signal": side,
        "side": side,
        "pattern": f"S8 Limit Sweep {side}",
        "entry": round(float(entry), 2),
        "sl": round(float(sl), 2),
        "tp": round(float(tp), 2),
        "intended_sl": round(float(sl), 2),
        "sl_armed": False,
        "swing_price": target_price,
        "swing_bar_time": int(target.get("time", 0) or 0),
        "detect_time_raw": int(bar.get("time", 0) or 0),
        "source": "limit_sweep",
    }
    return {"status": "close", "new_order": new_order, "reason": "Limit Sweep close; placed S8 follow-up"}


def trend_from_hhll_snapshot(snap: dict) -> dict | None:
    struct = snap.get("structure") or []
    if not struct:
        return None
    h_labels = [s for s in struct if s in ("HH", "LH")]
    l_labels = [s for s in struct if s in ("HL", "LL")]
    if not h_labels or not l_labels:
        return {"trend": "UNKNOWN", "strength": "-", "label": "UNKNOWN"}

    h0 = h_labels[0]
    h1 = h_labels[1] if len(h_labels) > 1 else None
    l0 = l_labels[0]
    l1 = l_labels[1] if len(l_labels) > 1 else None

    if h0 == "HH" and l0 == "HL":
        strength = "strong" if h1 == "HH" and l1 == "HL" else "weak"
        return {"trend": "BULL", "strength": strength, "label": f"BULL ({strength})"}
    if h0 == "LH" and l0 == "LL":
        strength = "strong" if h1 == "LH" and l1 == "LL" else "weak"
        return {"trend": "BEAR", "strength": strength, "label": f"BEAR ({strength})"}
    return {"trend": "SIDEWAY", "strength": "-", "label": "SIDEWAY"}


def _sideway_label_blocks(snap: dict, signal: str) -> tuple[bool, str]:
    if not getattr(config, "TREND_FILTER_SIDEWAY_HHLL", False):
        return False, ""
    last = snap.get("last_label", "")
    if not last:
        return False, ""
    cur = snap.get(last.lower()) or {}
    prev = snap.get(f"prev_{last.lower()}") or {}
    cur_p = float(cur["price"]) if cur.get("price") is not None else None
    prev_p = float(prev["price"]) if prev.get("price") is not None else None
    effective = last
    if cur_p is not None and prev_p is not None:
        if last == "HH" and cur_p < prev_p:
            effective = "LH"
        elif last == "HL" and cur_p < prev_p:
            effective = "LL"
        elif last == "LH" and cur_p > prev_p:
            effective = "HH"
        elif last == "LL" and cur_p > prev_p:
            effective = "HL"
    label = last if effective == last else f"{last}->{effective}"
    if effective in ("LH", "LL") and signal == "BUY":
        return True, f"SIDEWAY/{label}"
    if effective in ("HH", "HL") and signal == "SELL":
        return True, f"SIDEWAY/{label}"
    return False, ""


def trend_allows_signal_from_bars(tf_name: str, signal: str, bars: list[dict]) -> tuple[bool, str]:
    per_tf_map = getattr(config, "TREND_FILTER_PER_TF", {}) or {}
    per_tf_on = bool(per_tf_map.get(tf_name, False))
    higher_on = bool(getattr(config, "TREND_FILTER_HIGHER_TF_ENABLED", False))
    if not per_tf_on and not higher_on:
        return True, ""
    if higher_on and not per_tf_on:
        return True, "higher_tf_not_replayed"

    snap = hhll_snapshot_from_bars(bars)
    if not snap:
        return True, "trend_no_hhll_data"
    trend = trend_from_hhll_snapshot(snap) or {}
    trend_name = trend.get("trend", "UNKNOWN")
    mode = getattr(config, "TREND_FILTER_MODE", "basic")

    if trend_name == "SIDEWAY":
        blocked, why = _sideway_label_blocks(snap, signal)
        if blocked:
            return False, why
        return True, ""
    if trend_name not in ("BULL", "BEAR"):
        return True, ""

    # Breakout mode can flip on runtime breakout context. Historical replay does
    # not model that context yet, so this first-pass overlay uses the base trend.
    if trend_name == "BULL" and signal == "SELL":
        return False, f"{tf_name} BULL"
    if trend_name == "BEAR" and signal == "BUY":
        return False, f"{tf_name} BEAR"
    return True, ""


def pdfiboplus_in_zone(order_price: float, signal: str, high: float, low: float,
                       sid: int = 0, gap_bot: float = 0.0, gap_top: float = 0.0) -> bool:
    if high <= low:
        return True
    price_range = high - low
    fib_382 = low + price_range * 0.382
    fib_618 = low + price_range * 0.618

    if sid == 2 and gap_bot > 0 and gap_top > 0 and gap_top > gap_bot:
        if signal == "BUY" and gap_bot < fib_382:
            return True
        if signal == "SELL" and gap_top > fib_618:
            return True
        if signal == "BUY" and gap_top > high and gap_bot >= fib_382:
            return True
        if signal == "SELL" and gap_bot < low and gap_top <= fib_618:
            return True

    if signal == "BUY":
        return order_price < fib_382
    if signal == "SELL":
        return order_price > fib_618
    return True


def pending_pdfiboplus_round1(order: dict, bars: list[dict], *, allow_entry_adjust: bool = True) -> dict:
    sid = int(order.get("sid", 0) or 0)
    signal = order.get("signal") or order.get("side")
    if not pdfiboplus_applies(sid) or signal not in ("BUY", "SELL"):
        return {"status": "skip"}

    snap = hhll_snapshot_from_bars(bars)
    if not snap:
        return {"status": "wait", "reason": "PD Fibo Plus no HHLL data"}

    order_price = float(order.get("entry", 0.0) or 0.0)
    sh = snap["sh"]
    sl = snap["sl"]
    high = float(sh["price"])
    low = float(sl["price"])
    if high <= low or order_price <= 0:
        return {"status": "wait", "reason": "PD Fibo Plus invalid range"}

    gap_bot = float(order.get("final_gap_bot", order.get("gap_bot", 0.0)) or 0.0)
    gap_top = float(order.get("final_gap_top", order.get("gap_top", 0.0)) or 0.0)
    eq = (high + low) / 2.0
    effective_high = high
    effective_low = low
    outside_pd = order_price < low or order_price > high
    fallback_used = False
    wait_round2 = False

    if outside_pd:
        prev_sh = snap.get("prev_sh")
        prev_sl = snap.get("prev_sl")
        if order_price < low and prev_sh is not None:
            try_high = float(prev_sh["price"])
            if try_high > effective_low:
                effective_high = try_high
                fallback_used = True
        elif order_price > high and prev_sl is not None:
            try_low = float(prev_sl["price"])
            if effective_high > try_low:
                effective_low = try_low
                fallback_used = True

    if fallback_used and (order_price < effective_low or order_price > effective_high):
        wait_round2 = True
        result = False
    else:
        result = pdfiboplus_in_zone(
            order_price, signal, effective_high, effective_low,
            sid=sid, gap_bot=gap_bot, gap_top=gap_top,
        )

    adjusted_entry = 0.0
    adjust_reason = ""
    if allow_entry_adjust and sid == 2 and gap_bot > 0 and gap_top > gap_bot and result:
        if signal == "BUY":
            if order_price > eq and gap_bot < eq:
                adjusted_entry = round(eq, 2)
                adjust_reason = "EQ"
            elif gap_top > high and gap_bot >= eq:
                adjusted_entry = round((gap_bot + gap_top) / 2.0, 2)
                adjust_reason = "50% gap"
        elif signal == "SELL":
            if order_price < eq and gap_top > eq:
                adjusted_entry = round(eq, 2)
                adjust_reason = "EQ"
            elif gap_bot < low and gap_top <= eq:
                adjusted_entry = round((gap_bot + gap_top) / 2.0, 2)
                adjust_reason = "50% gap"
    if adjusted_entry > 0:
        order["entry"] = adjusted_entry
        order["pd_adjusted_entry"] = adjusted_entry
        order["pd_adjust_reason"] = adjust_reason

    meta = {
        "pd_h": round(effective_high, 2),
        "pd_l": round(effective_low, 2),
        "pd_fib_382": round(effective_low + (effective_high - effective_low) * 0.382, 2),
        "pd_fib_618": round(effective_low + (effective_high - effective_low) * 0.618, 2),
        "pd_fallback_used": fallback_used,
        "pd_outside_range": outside_pd,
    }
    order.update(meta)
    if result or wait_round2:
        order["pd_pending_h"] = float(meta["pd_h"])
        order["pd_pending_l"] = float(meta["pd_l"])
        order["pd_gap_bot"] = gap_bot
        order["pd_gap_top"] = gap_top
        order["pd_pending_round2"] = True
    if wait_round2:
        return {"status": "wait", "reason": "PD Fibo Plus round1 waits for H/L change", **meta}
    if result:
        return {"status": "pass", "reason": "PD Fibo Plus round1 pass", **meta}
    return {"status": "fail", "reason": "PD Fibo Plus round1 fail", **meta}


def pending_pdfiboplus_round2(order: dict, bars: list[dict]) -> dict:
    sid = int(order.get("sid", 0) or 0)
    signal = order.get("signal") or order.get("side")
    if not pdfiboplus_applies(sid) or signal not in ("BUY", "SELL"):
        return {"status": "skip"}
    if not order.get("pd_pending_round2"):
        return {"status": "skip"}

    snap = hhll_snapshot_from_bars(bars)
    if not snap:
        return {"status": "wait", "reason": "PD Fibo Plus pending round2 no HHLL data"}
    high = float(snap["sh"]["price"])
    low = float(snap["sl"]["price"])
    if not (high > low > 0):
        return {"status": "wait", "reason": "PD Fibo Plus pending round2 invalid range"}

    prev_h = float(order.get("pd_pending_h", 0.0) or 0.0)
    prev_l = float(order.get("pd_pending_l", 0.0) or 0.0)
    h_changed = abs(high - prev_h) > 0.01
    l_changed = abs(low - prev_l) > 0.01
    if not (h_changed or l_changed):
        return {"status": "wait", "reason": "PD Fibo Plus pending round2 waiting H/L change"}

    order_price = float(order.get("entry", 0.0) or 0.0)
    result = pdfiboplus_in_zone(
        order_price, signal, high, low,
        sid=sid,
        gap_bot=float(order.get("pd_gap_bot", 0.0) or 0.0),
        gap_top=float(order.get("pd_gap_top", 0.0) or 0.0),
    )
    changed = "/".join(p for p in ("H" if h_changed else "", "L" if l_changed else "") if p)
    order["pd_pending_round2"] = False
    order["pd_pending_round2_h"] = round(high, 2)
    order["pd_pending_round2_l"] = round(low, 2)
    order["pd_pending_round2_changed"] = changed
    if result:
        return {"status": "pass", "reason": "PD Fibo Plus pending round2 pass", "changed": changed}
    return {"status": "fail", "reason": "PD Fibo Plus pending round2 fail", "changed": changed}


def pd_cancel_event(order: dict, close_time) -> dict:
    return {
        **order,
        "entry_time": order.get("detect_time"),
        "entry_time_raw": order.get("detect_time_raw"),
        "close_time": close_time,
        "close_price": None,
        "close_type": "PD_FAIL",
        "pnl": 0.0,
        "profit": 0.0,
        "reason": "PD Fibo Plus round1 fail",
        "cancel_reason": "PD Fibo Plus round1 fail",
    }


def fill_pdfiboplus_round1(trade: dict, bars: list[dict]) -> dict:
    result = pending_pdfiboplus_round1(trade, bars, allow_entry_adjust=False)
    if result.get("status") in ("pass", "wait") and result.get("pd_h") and result.get("pd_l"):
        trade["pd_fill_h"] = float(result["pd_h"])
        trade["pd_fill_l"] = float(result["pd_l"])
        trade["pd_gap_bot"] = float(trade.get("final_gap_bot", trade.get("gap_bot", 0.0)) or 0.0)
        trade["pd_gap_top"] = float(trade.get("final_gap_top", trade.get("gap_top", 0.0)) or 0.0)
        trade["pd_round2_pending"] = True
    return result


def fill_pdfiboplus_round2(trade: dict, bars: list[dict]) -> dict:
    sid = int(trade.get("sid", 0) or 0)
    signal = trade.get("signal") or trade.get("side")
    if not pdfiboplus_applies(sid) or signal not in ("BUY", "SELL"):
        return {"status": "skip"}
    if not trade.get("pd_round2_pending"):
        return {"status": "skip"}

    snap = hhll_snapshot_from_bars(bars)
    if not snap:
        return {"status": "wait", "reason": "PD Fibo Plus round2 no HHLL data"}
    high = float(snap["sh"]["price"])
    low = float(snap["sl"]["price"])
    if not (high > low > 0):
        return {"status": "wait", "reason": "PD Fibo Plus round2 invalid range"}

    prev_h = float(trade.get("pd_fill_h", 0.0) or 0.0)
    prev_l = float(trade.get("pd_fill_l", 0.0) or 0.0)
    h_changed = abs(high - prev_h) > 0.01
    l_changed = abs(low - prev_l) > 0.01
    if not (h_changed or l_changed):
        return {"status": "wait", "reason": "PD Fibo Plus round2 waiting H/L change"}

    order_price = float(trade.get("entry", 0.0) or 0.0)
    result = pdfiboplus_in_zone(
        order_price, signal, high, low,
        sid=sid,
        gap_bot=float(trade.get("pd_gap_bot", 0.0) or 0.0),
        gap_top=float(trade.get("pd_gap_top", 0.0) or 0.0),
    )
    changed = "/".join(p for p in ("H" if h_changed else "", "L" if l_changed else "") if p)
    trade["pd_round2_pending"] = False
    trade["pd_round2_h"] = round(high, 2)
    trade["pd_round2_l"] = round(low, 2)
    trade["pd_round2_changed"] = changed
    if result:
        return {"status": "pass", "reason": "PD Fibo Plus round2 pass", "changed": changed}
    return {"status": "fail", "reason": "PD Fibo Plus round2 fail", "changed": changed}


TREND_RECHECK_FILL_SKIP_SIDS = {1, 2, 3, 9, 10, 11, 14, 15, 16, 17, 18, 19}
TREND_RECHECK_PENDING_SKIP_SIDS = {1, 2, 3, 9, 10, 11, 14, 15, 17, 18, 19}


def fill_trend_recheck_round1(trade: dict, bars: list[dict]) -> dict:
    if not getattr(config, "LIMIT_TREND_RECHECK", False):
        return {"status": "skip"}
    sid = int(trade.get("sid", 0) or 0)
    if sid in TREND_RECHECK_FILL_SKIP_SIDS:
        return {"status": "skip"}
    tf_name = str(trade.get("tf", "") or "")
    signal = str(trade.get("signal") or trade.get("side") or "")
    if not tf_name or signal not in ("BUY", "SELL"):
        return {"status": "skip"}
    allowed, why = trend_allows_signal_from_bars(tf_name, signal, bars)
    if allowed:
        _mark_trend_round2_baseline(trade, bars, "trend_fill")
        return {"status": "pass", "reason": why or "Trend Recheck round1 pass"}
    return {"status": "fail", "reason": why or "Trend Recheck round1 fail"}


def pending_trend_check_round1(order: dict, bars: list[dict], bar: dict, point: float = 0.01) -> dict:
    if not getattr(config, "PENDING_TREND_CHECK_ENABLED", False):
        return {"status": "skip"}
    sid = int(order.get("sid", 0) or 0)
    if sid in TREND_RECHECK_PENDING_SKIP_SIDS:
        return {"status": "skip"}
    tf_name = str(order.get("tf", "") or "")
    signal = str(order.get("signal") or order.get("side") or "")
    if not tf_name or signal not in ("BUY", "SELL"):
        return {"status": "skip"}

    entry = float(order.get("entry", 0.0) or 0.0)
    if entry <= 0:
        return {"status": "skip"}
    pt = float(point or 0.01)
    approach_dist = float(getattr(config, "PENDING_TREND_CHECK_POINTS", 200) or 200) * pt * config.points_scale()
    high = float(bar["high"])
    low = float(bar["low"])
    approaching = low <= entry + approach_dist if signal == "BUY" else high >= entry - approach_dist
    if not approaching:
        return {"status": "wait"}

    allowed, why = trend_allows_signal_from_bars(tf_name, signal, bars)
    if allowed:
        _mark_trend_round2_baseline(order, bars, "trend_pending")
        return {"status": "pass", "reason": why or "Pending Trend Check round1 pass"}
    return {"status": "fail", "reason": why or "Pending Trend Check round1 fail"}


def _mark_trend_round2_baseline(row: dict, bars: list[dict], prefix: str) -> None:
    snap = hhll_snapshot_from_bars(bars)
    if not snap:
        return
    sh = snap.get("sh") or {}
    sl = snap.get("sl") or {}
    if sh.get("price") is None or sl.get("price") is None:
        return
    row[f"{prefix}_h"] = float(sh["price"])
    row[f"{prefix}_l"] = float(sl["price"])
    row[f"{prefix}_round2_pending"] = True


def _trend_round2_from_baseline(row: dict, bars: list[dict], prefix: str, *, rounds: int) -> dict:
    if int(rounds or 1) < 2:
        return {"status": "skip"}
    if not row.get(f"{prefix}_round2_pending"):
        return {"status": "skip"}

    tf_name = str(row.get("tf", "") or "")
    signal = str(row.get("signal") or row.get("side") or "")
    if not tf_name or signal not in ("BUY", "SELL"):
        return {"status": "skip"}

    snap = hhll_snapshot_from_bars(bars)
    if not snap:
        return {"status": "wait", "reason": "Trend Recheck round2 no HHLL data"}
    high = float(snap["sh"]["price"])
    low = float(snap["sl"]["price"])
    prev_h = float(row.get(f"{prefix}_h", 0.0) or 0.0)
    prev_l = float(row.get(f"{prefix}_l", 0.0) or 0.0)
    h_changed = prev_h > 0 and abs(high - prev_h) > 0.01
    l_changed = prev_l > 0 and abs(low - prev_l) > 0.01
    if not (h_changed or l_changed):
        return {"status": "wait", "reason": "Trend Recheck round2 waiting H/L change"}

    allowed, why = trend_allows_signal_from_bars(tf_name, signal, bars)
    if allowed:
        if signal == "BUY":
            if l_changed and low < prev_l:
                allowed = False
                why = f"LL ({low:.2f} < {prev_l:.2f})"
            elif h_changed and high < prev_h:
                allowed = False
                why = f"LH ({high:.2f} < {prev_h:.2f})"
        elif signal == "SELL":
            if h_changed and high > prev_h:
                allowed = False
                why = f"HH ({high:.2f} > {prev_h:.2f})"
            elif l_changed and low > prev_l:
                allowed = False
                why = f"HL ({low:.2f} > {prev_l:.2f})"

    row[f"{prefix}_round2_pending"] = False
    row[f"{prefix}_round2_h"] = round(high, 2)
    row[f"{prefix}_round2_l"] = round(low, 2)
    changed = "/".join(p for p in ("H" if h_changed else "", "L" if l_changed else "") if p)
    row[f"{prefix}_round2_changed"] = changed
    if allowed:
        return {"status": "pass", "reason": why or "Trend Recheck round2 pass", "changed": changed}
    return {"status": "fail", "reason": why or "Trend Recheck round2 fail", "changed": changed}


def pending_trend_check_round2(order: dict, bars: list[dict]) -> dict:
    return _trend_round2_from_baseline(
        order, bars, "trend_pending",
        rounds=int(getattr(config, "PENDING_TREND_CHECK_ROUNDS", 1) or 1),
    )


def fill_trend_recheck_round2(trade: dict, bars: list[dict]) -> dict:
    return _trend_round2_from_baseline(
        trade, bars, "trend_fill",
        rounds=int(getattr(config, "LIMIT_TREND_RECHECK_ROUNDS", 1) or 1),
    )


def trend_cancel_event(order: dict, close_time, reason: str = "Pending Trend Check round1 fail") -> dict:
    return {
        **order,
        "entry_time": order.get("detect_time"),
        "entry_time_raw": order.get("detect_time_raw"),
        "close_time": close_time,
        "close_price": None,
        "close_type": "CANCEL",
        "pnl": 0.0,
        "profit": 0.0,
        "reason": reason,
        "cancel_reason": reason,
    }


def s1_build_forward_meta(signal: str, detect_bar_time: int, forward_bars: int = 5) -> dict:
    return {
        "enabled": True,
        "signal": str(signal or "").upper(),
        "detect_bar_time": int(detect_bar_time or 0),
        "forward_bars": max(1, int(forward_bars or 5)),
        "confirmed": False,
        "confirmed_sid": 0,
        "confirmed_bar_time": 0,
    }


def s1_prepare_order(order: dict) -> dict:
    if int(order.get("sid", 0) or 0) != 1:
        return order
    if not order.get("s1_forward_meta"):
        order["s1_forward_meta"] = s1_build_forward_meta(
            str(order.get("signal") or order.get("side") or ""),
            int(order.get("detect_time_raw", 0) or 0),
            5,
        )
    return order


def s1_forward_confirm_state(row: dict, bars: list[dict]) -> dict:
    if int(row.get("sid", 0) or 0) != 1:
        return {"status": "skip"}
    meta = row.get("s1_forward_meta") or {}
    if not meta.get("enabled") or meta.get("confirmed"):
        return {"status": "skip"}

    signal = str(meta.get("signal") or row.get("signal") or row.get("side") or "").upper()
    detect_bar_time = int(meta.get("detect_bar_time", row.get("detect_time_raw", 0)) or 0)
    tf_secs = int(TF_SECONDS_MAP.get(str(row.get("tf") or ""), 0) or 0)
    forward_bars = max(1, int(meta.get("forward_bars", 5) or 5))
    if signal not in ("BUY", "SELL") or detect_bar_time <= 0 or tf_secs <= 0 or len(bars) < 4:
        return {"status": "skip"}

    deadline_time = detect_bar_time + tf_secs * forward_bars
    last_closed_time = int(bars[-1]["time"])
    matched_sid = 0
    matched_bar_time = 0

    from strategy2 import strategy_2
    from strategy3 import strategy_3

    for idx, bar in enumerate(bars):
        bar_time = int(bar["time"])
        if bar_time <= detect_bar_time:
            continue
        if bar_time > deadline_time:
            break
        if idx < 2:
            continue
        sliced_rates = bars[:idx + 1]
        try:
            s2 = strategy_2(sliced_rates)
        except Exception:
            s2 = {}
        if str(s2.get("signal", "")).upper() == "FVG_DETECTED":
            fvg = s2.get("fvg") or {}
            if str(fvg.get("signal", "")).upper() == signal:
                matched_sid = 2
                matched_bar_time = bar_time
                break
        try:
            s3 = strategy_3(sliced_rates)
        except Exception:
            s3 = {}
        if str(s3.get("signal", "")).upper() == signal:
            matched_sid = 3
            matched_bar_time = bar_time
            break

    if matched_sid:
        meta["confirmed"] = True
        meta["confirmed_sid"] = matched_sid
        meta["confirmed_bar_time"] = matched_bar_time
        row["s1_forward_meta"] = meta
        return {"status": "pass", "reason": f"S1 Forward Confirm S{matched_sid}", "matched_sid": matched_sid}
    if last_closed_time >= deadline_time:
        return {
            "status": "fail",
            "reason": f"S1 Forward: no S2/S3 same-side confirm in {forward_bars} bars",
        }
    return {"status": "wait"}


def _s1_swing_rule_state(row: dict, bars: list[dict], *, pending: bool) -> dict:
    signal = str(row.get("signal") or row.get("side") or "").upper()
    detect_bar_time = int(
        (row.get("s1_forward_meta") or {}).get("detect_bar_time", row.get("detect_time_raw", 0)) or 0
    )
    tf_secs = int(TF_SECONDS_MAP.get(str(row.get("tf") or ""), 0) or 0)
    if signal not in ("BUY", "SELL") or detect_bar_time <= 0 or tf_secs <= 0:
        return {"status": "skip"}

    snap = hhll_snapshot_from_bars(bars)
    if not snap:
        return {"status": "wait"}
    pts = []
    if signal == "BUY":
        pts = [p for p in (snap.get("hl"), snap.get("ll")) if p and p.get("time")]
    else:
        pts = [p for p in (snap.get("hh"), snap.get("lh")) if p and p.get("time")]

    hhll_right = int(getattr(config, "HHLL_RIGHT", 5) or 5)
    back_bars = 3 if pending else 2
    pattern_candle_times = {detect_bar_time - n * tf_secs for n in range(back_bars + 1)}
    for pt in pts:
        t_swing = int(pt["time"])
        if t_swing in pattern_candle_times:
            t_confirm = t_swing + hhll_right * tf_secs
            if detect_bar_time <= t_confirm <= detect_bar_time + 5 * tf_secs:
                return {"status": "pass", "reason": "S1 Swing confirmed"}

    last_closed_time = int(bars[-1]["time"])
    if last_closed_time > detect_bar_time + 4 * tf_secs:
        return {"status": "fail", "reason": f"S1 Swing: no {signal} swing confirmed in 4 bars"}
    return {"status": "wait"}


def s1_pending_rule_check(order: dict, bars: list[dict]) -> dict:
    if int(order.get("sid", 0) or 0) != 1:
        return {"status": "skip"}
    mode = str(getattr(config, "S1_ZONE_MODE", "") or "")
    zone_meta = order.get("s1_zone_meta") or {}
    if mode not in ("zone", "swing") or not zone_meta.get("enabled"):
        return s1_forward_confirm_state(order, bars)

    if mode == "swing":
        swing = _s1_swing_rule_state(order, bars, pending=True)
        if swing.get("status") == "fail":
            return swing
    else:
        detect_bar_time = int((order.get("s1_forward_meta") or {}).get("detect_bar_time", order.get("detect_time_raw", 0)) or 0)
        candles_passed = sum(1 for bar in bars if int(bar["time"]) > detect_bar_time)
        if candles_passed >= 7:
            from strategy1 import evaluate_s1_zone_status
            zone_state = evaluate_s1_zone_status(
                bars,
                str(zone_meta.get("signal") or order.get("signal") or ""),
                float(zone_meta.get("zone_price", 0.0) or 0.0),
                tf=str(order.get("tf") or ""),
            )
            if not zone_state.get("in_zone", True):
                return {
                    "status": "fail",
                    "reason": f"S1 Zone Cancel: pending still outside zone ({zone_state.get('boundary_price', 0.0):.2f})",
                }

    return s1_forward_confirm_state(order, bars)


def s1_fill_rule_check(trade: dict, bars: list[dict], current_price: float) -> dict:
    if int(trade.get("sid", 0) or 0) != 1:
        return {"status": "skip"}
    mode = str(getattr(config, "S1_ZONE_MODE", "") or "")
    zone_meta = trade.get("s1_zone_meta") or {}

    if mode == "swing" and zone_meta.get("enabled"):
        swing = _s1_swing_rule_state(trade, bars, pending=False)
        if swing.get("status") == "fail":
            return swing
    elif mode == "zone" and zone_meta.get("enabled"):
        from strategy1 import evaluate_s1_zone_status
        signal = str(zone_meta.get("signal") or trade.get("signal") or "")
        zone_state = evaluate_s1_zone_status(
            bars,
            signal,
            float(zone_meta.get("zone_price", 0.0) or 0.0),
            tf=str(trade.get("tf") or ""),
        )
        if not zone_state.get("in_zone", True):
            entry = float(trade.get("entry", 0.0) or 0.0)
            pnl = current_price - entry if signal == "BUY" else entry - current_price
            if pnl < 0:
                return {
                    "status": "fail",
                    "reason": f"S1 Zone Loss Exit: outside zone ({zone_state.get('boundary_price', 0.0):.2f})",
                }

    return s1_forward_confirm_state(trade, bars)


def s1_rule_close_type(result: dict) -> str:
    reason = str((result or {}).get("reason", "") or "").upper()
    if "ZONE" in reason:
        return "S1_ZONE_EXIT"
    if "SWING" in reason:
        return "S1_SWING_EXIT"
    if "FORWARD" in reason or "S2/S3" in reason:
        return "S1_FORWARD_EXIT"
    return "S1_RULE_EXIT"


LIMIT_GUARD_SKIP_SIDS = {1, 10, 12, 13, 15, 16, 17, 18, 19}


def limit_guard_cancel(order: dict, open_trades: list[dict], bar: dict, point: float = 0.01) -> dict:
    if not getattr(config, "LIMIT_GUARD", False):
        return {"status": "skip"}
    sid = int(order.get("sid", 0) or 0)
    if sid in LIMIT_GUARD_SKIP_SIDS:
        return {"status": "skip"}

    signal = str(order.get("signal") or order.get("side") or "")
    if signal not in ("BUY", "SELL"):
        return {"status": "skip"}
    limit_tf = str(order.get("tf", "") or "")
    tf_separate = str(getattr(config, "LIMIT_GUARD_TF_MODE", "separate")) == "separate"
    guard_dist = float(getattr(config, "LIMIT_GUARD_POINTS", 200) or 200) * float(point or 0.01) * config.points_scale()
    limit_entry = float(order.get("entry", 0.0) or 0.0)
    price_now = float(bar.get("close", 0.0) or 0.0)

    for trade in open_trades:
        if str(trade.get("signal") or trade.get("side") or "") != signal:
            continue
        if tf_separate and str(trade.get("tf", "") or "") != limit_tf:
            continue
        pos_entry = float(trade.get("entry", 0.0) or 0.0)
        if pos_entry <= 0 or limit_entry <= 0:
            continue
        if signal == "BUY" and limit_entry > pos_entry and price_now > pos_entry + guard_dist:
            return {
                "status": "fail",
                "reason": (
                    f"Limit Guard [{limit_tf}->{trade.get('tf', '?')}]: BUY LIMIT {limit_entry:.2f} > "
                    f"BUY pos {pos_entry:.2f} & price {price_now:.2f} > {pos_entry + guard_dist:.2f}"
                ),
            }
        if signal == "SELL" and limit_entry < pos_entry and price_now < pos_entry - guard_dist:
            return {
                "status": "fail",
                "reason": (
                    f"Limit Guard [{limit_tf}->{trade.get('tf', '?')}]: SELL LIMIT {limit_entry:.2f} < "
                    f"SELL pos {pos_entry:.2f} & price {price_now:.2f} < {pos_entry - guard_dist:.2f}"
                ),
            }
    return {"status": "pass"}


OPPOSITE_ORDER_SKIP_SIDS = set(getattr(config, "OPPOSITE_ORDER_SKIP_SIDS", {10, 12, 13, 15, 16, 17, 18, 19}))


def _trade_profit_points(trade: dict, price_now: float) -> float:
    entry = float(trade.get("entry", 0.0) or 0.0)
    if str(trade.get("signal") or trade.get("side") or "") == "BUY":
        return price_now - entry
    return entry - price_now


def opposite_order_apply(open_trades: list[dict], pending: list[dict], bar: dict, spread: float = 0.0) -> list[tuple[dict, str]]:
    if not getattr(config, "OPPOSITE_ORDER_ENABLED", True):
        return []

    eligible = [
        t for t in open_trades
        if int(t.get("sid", 0) or 0) not in OPPOSITE_ORDER_SKIP_SIDS
        and str(t.get("signal") or t.get("side") or "") in ("BUY", "SELL")
    ]
    if not eligible:
        return []

    mode = str(getattr(config, "OPPOSITE_ORDER_MODE", "sl_protect") or "sl_protect")
    price_now = float(bar.get("close", 0.0) or 0.0)

    if mode == "tp_close":
        for trade in eligible:
            if _trade_profit_points(trade, price_now) <= 0:
                continue
            side = str(trade.get("signal") or trade.get("side") or "")
            opposite = "SELL" if side == "BUY" else "BUY"
            tf = str(trade.get("tf", "") or "")
            for order in pending:
                if int(order.get("sid", 0) or 0) in OPPOSITE_ORDER_SKIP_SIDS:
                    continue
                if str(order.get("signal") or order.get("side") or "") != opposite:
                    continue
                if str(order.get("tf", "") or "") != tf:
                    continue
                new_tp = round(float(order.get("entry", 0.0) or 0.0), 2)
                if new_tp > 0:
                    trade["tp"] = new_tp
                    trade["opposite_tp_linked"] = True

    closes: list[tuple[dict, str]] = []
    buys = [t for t in eligible if str(t.get("signal") or t.get("side") or "") == "BUY"]
    sells = [t for t in eligible if str(t.get("signal") or t.get("side") or "") == "SELL"]
    for buy in buys:
        for sell in sells:
            if str(buy.get("tf", "") or "") != str(sell.get("tf", "") or ""):
                continue
            buy_t = int(buy.get("entry_time_raw", buy.get("detect_time_raw", 0)) or 0)
            sell_t = int(sell.get("entry_time_raw", sell.get("detect_time_raw", 0)) or 0)
            if buy_t == sell_t:
                continue
            if mode == "tp_close":
                if buy_t > sell_t:
                    closes.append((sell, "OPPOSITE_CLOSE"))
                elif sell_t > buy_t:
                    closes.append((buy, "OPPOSITE_CLOSE"))
                continue

            sp = float(spread or 0.0)
            if buy_t > sell_t and not sell.get("opposite_sl_protected"):
                new_sl = round(float(sell.get("entry", 0.0) or 0.0) - sp, 2)
                if new_sl > 0 and (float(sell.get("sl", 0.0) or 0.0) == 0 or new_sl < float(sell.get("sl", 0.0) or 0.0)):
                    sell["sl"] = new_sl
                    sell["opposite_sl_protected"] = True
            elif sell_t > buy_t and not buy.get("opposite_sl_protected"):
                new_sl = round(float(buy.get("entry", 0.0) or 0.0) + sp, 2)
                if new_sl > float(buy.get("sl", 0.0) or 0.0):
                    buy["sl"] = new_sl
                    buy["opposite_sl_protected"] = True
    return closes


TRAIL_SL_SKIP_SIDS = {10, 12, 13, 15, 16, 17, 18, 19}


def _reversal_trail_override_from_bars(
    side: str,
    bars_after: list[dict],
    current_sl: float,
) -> tuple[bool, float, str]:
    if not getattr(config, "TRAIL_SL_REVERSAL_OVERRIDE_ENABLED", False):
        return False, 0.0, ""
    if len(bars_after) < 3:
        return False, 0.0, ""

    cur = bars_after[-1]
    prev = bars_after[-2]
    cur_o = float(cur["open"])
    cur_c = float(cur["close"])
    cur_h = float(cur["high"])
    cur_l = float(cur["low"])
    prev_h = float(prev["high"])
    prev_l = float(prev["low"])

    reversal_found = False
    reversal_type = ""
    if side == "BUY" and cur_c < cur_o:
        if cur_c < prev_l:
            reversal_found = True
            reversal_type = "red engulf"
        elif cur_l < prev_l and prev_l <= cur_c <= prev_h:
            reversal_found = True
            reversal_type = "red rejection"
    elif side == "SELL" and cur_c > cur_o:
        if cur_c > prev_h:
            reversal_found = True
            reversal_type = "green engulf"
        elif cur_h > prev_h and prev_l <= cur_c <= prev_h:
            reversal_found = True
            reversal_type = "green rejection"

    if not reversal_found:
        return False, 0.0, ""

    reversal_idx = len(bars_after) - 1
    best_sl = 0.0
    for idx in range(1, reversal_idx):
        bar = bars_after[idx]
        prev_bar = bars_after[idx - 1]
        bar_o = float(bar["open"])
        bar_c = float(bar["close"])
        bar_h = float(bar["high"])
        bar_l = float(bar["low"])
        prev_h = float(prev_bar["high"])
        prev_l = float(prev_bar["low"])
        if side == "BUY" and bar_c > bar_o and bar_c > prev_h:
            candidate = round(bar_l - 1.0, 2)
            if candidate > best_sl:
                best_sl = candidate
        elif side == "SELL" and bar_c < bar_o and bar_c < prev_l:
            candidate = round(bar_h + 1.0, 2)
            if best_sl == 0.0 or candidate < best_sl:
                best_sl = candidate

    if best_sl == 0.0:
        return False, 0.0, ""
    if side == "BUY" and best_sl <= current_sl:
        return False, 0.0, ""
    if side == "SELL" and current_sl > 0 and best_sl >= current_sl:
        return False, 0.0, ""
    return True, best_sl, reversal_type


def _trail_focus_should_skip(
    trade: dict,
    open_trades: list[dict] | None,
    pending: list[dict] | None,
    bar: dict | None,
    point: float,
    spread: float,
    focus_state: dict | None,
) -> bool:
    if not getattr(config, "TRAIL_SL_FOCUS_NEW_ENABLED", False):
        return False
    if open_trades is None or pending is None or bar is None or focus_state is None:
        return False

    items = list(open_trades) + list(pending)
    has_buy = any(str(item.get("signal") or item.get("side") or "") == "BUY" for item in items)
    has_sell = any(str(item.get("signal") or item.get("side") or "") == "SELL" for item in items)
    frozen_side = focus_state.get("side")
    if frozen_side is None:
        if has_buy and not has_sell:
            frozen_side = "BUY"
        elif has_sell and not has_buy:
            frozen_side = "SELL"
        if frozen_side:
            focus_state["side"] = frozen_side

    if frozen_side not in ("BUY", "SELL"):
        return False

    side = str(trade.get("signal") or trade.get("side") or "")
    if side == frozen_side:
        return True

    tf_mode = str(getattr(config, "TRAIL_SL_FOCUS_NEW_TF_MODE", "separate") or "separate")
    points = int(getattr(config, "TRAIL_SL_FOCUS_NEW_POINTS", 100) or 100) * config.points_scale()
    threshold = float(points) * float(point or 0.01) + float(spread or 0.0)
    price_now = float(bar.get("close", 0.0) or 0.0)
    ref_tf = str(trade.get("tf", "") or "")

    for item in open_trades:
        item_side = str(item.get("signal") or item.get("side") or "")
        if item_side != frozen_side:
            continue
        if tf_mode != "combined" and str(item.get("tf", "") or "") != ref_tf:
            continue
        entry = float(item.get("entry", 0.0) or 0.0)
        if frozen_side == "BUY" and price_now - entry > threshold:
            return False
        if frozen_side == "SELL" and entry - price_now > threshold:
            return False
    return True


def _trend_filter_trail_override_from_history(
    trade: dict,
    trail_rates_by_tf: dict[str, list[dict]],
    upto_ts: int,
    order_tf: str,
) -> bool:
    if not getattr(config, "TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED", True):
        return False
    refs: list[str] = []
    per_tf_map = getattr(config, "TREND_FILTER_PER_TF", {}) or {}
    if per_tf_map.get(order_tf, False):
        refs.append(order_tf)
    if getattr(config, "TREND_FILTER_HIGHER_TF_ENABLED", False):
        higher_tf = getattr(config, "TREND_FILTER_HIGHER_TF", "")
        if higher_tf and higher_tf not in refs:
            refs.append(higher_tf)
    if not refs:
        return False

    side = str(trade.get("signal") or trade.get("side") or "")
    expected_prev = "BEAR" if side == "SELL" else "BULL"
    expected_new = "BULL" if side == "SELL" else "BEAR"
    state = trade.setdefault("trail_trend_last_dir", {})

    for ref_tf in refs:
        rates = trail_rates_by_tf.get(ref_tf)
        if not rates:
            continue
        bars = [r for r in rates if int(r["time"]) < int(upto_ts)]
        if len(bars) < 20:
            continue
        snap = hhll_snapshot_from_bars(bars[-80:])
        if not snap:
            continue
        trend = trend_from_hhll_snapshot(snap) or {}
        trend_name = trend.get("trend", "UNKNOWN")
        strength = trend.get("strength", "-")
        if trend_name == "UNKNOWN":
            continue
        prev = state.get(ref_tf)
        if trend_name == "SIDEWAY":
            state[ref_tf] = trend_name
            continue
        if trend_name not in ("BULL", "BEAR") or strength not in ("weak", "strong"):
            continue
        state[ref_tf] = trend_name
        if prev in (expected_prev, "SIDEWAY") and trend_name == expected_new:
            trade.setdefault("trail_trend_override_events", []).append({
                "time_raw": int(upto_ts),
                "tf": ref_tf,
                "from": prev,
                "to": trend_name,
            })
            return True
    return False


def trail_sl_apply(
    trade: dict,
    trail_rates_by_tf: dict[str, list[dict]],
    upto_ts: int,
    order_tf: str,
    open_trades: list[dict] | None = None,
    pending: list[dict] | None = None,
    bar: dict | None = None,
    point: float = 0.01,
    spread: float = 0.0,
    focus_state: dict | None = None,
) -> None:
    if not getattr(config, "TRAIL_SL_ENABLED", True):
        return
    if int(trade.get("sid", 0) or 0) in TRAIL_SL_SKIP_SIDS:
        return
    if not getattr(config, "TRAIL_SL_IMMEDIATE", True):
        return

    entry = float(trade.get("entry", 0.0) or 0.0)
    if entry <= 0:
        return
    side = str(trade.get("signal") or trade.get("side") or "")
    if side not in ("BUY", "SELL"):
        return
    focus_skip = _trail_focus_should_skip(trade, open_trades, pending, bar, point, spread, focus_state)
    trend_override = False
    if focus_skip:
        trend_override = _trend_filter_trail_override_from_history(
            trade,
            trail_rates_by_tf,
            upto_ts,
            order_tf,
        )
    if focus_skip and not trend_override:
        trade.setdefault("trail_focus_skips", 0)
        trade["trail_focus_skips"] += 1
        return

    group = list(getattr(config, "TRAIL_GROUPS", {}).get(order_tf, [order_tf]))
    if order_tf not in group:
        group.insert(0, order_tf)
    current_sl = float(trade.get("sl", 0.0) or 0.0)
    best_sl = current_sl
    best_tf = ""
    best_kind = ""
    entry_ts = int(trade.get("entry_time_raw", 0) or 0)
    if entry_ts <= 0:
        return

    for trail_tf in group:
        tf_rates = trail_rates_by_tf.get(trail_tf)
        if not tf_rates:
            continue
        bars_after = [r for r in tf_rates if entry_ts <= int(r["time"]) < int(upto_ts)]
        if len(bars_after) < 2:
            continue

        tf_sl = current_sl
        found = False
        for idx in range(1, len(bars_after)):
            cur = bars_after[idx]
            prev = bars_after[idx - 1]
            cur_o = float(cur["open"])
            cur_c = float(cur["close"])
            cur_h = float(cur["high"])
            cur_l = float(cur["low"])
            prev_h = float(prev["high"])
            prev_l = float(prev["low"])
            bull = cur_c > cur_o

            if side == "BUY" and bull and cur_c > prev_h:
                candidate = round(cur_l - 1.0, 2)
                if candidate > tf_sl:
                    tf_sl = candidate
                    found = True
            elif side == "SELL" and not bull and cur_c < prev_l:
                candidate = round(cur_h + 1.0, 2)
                if tf_sl == 0 or candidate < tf_sl:
                    tf_sl = candidate
                    found = True

        if not found or tf_sl == current_sl:
            continue
        if side == "BUY" and tf_sl > best_sl:
            best_sl = tf_sl
            best_tf = trail_tf
            best_kind = "engulf"
        elif side == "SELL" and (best_sl == 0 or tf_sl < best_sl):
            best_sl = tf_sl
            best_tf = trail_tf
            best_kind = "engulf"

    if not best_tf:
        current_sl_in_profit = (
            (side == "BUY" and current_sl > entry)
            or (side == "SELL" and current_sl > 0 and current_sl < entry)
        )
        main_bars_for_reversal = [
            r for r in (trail_rates_by_tf.get(order_tf) or [])
            if entry_ts <= int(r["time"]) < int(upto_ts)
        ]
        if current_sl_in_profit:
            rev_ok, rev_sl, rev_type = _reversal_trail_override_from_bars(
                side,
                main_bars_for_reversal[-50:],
                current_sl,
            )
            if rev_ok:
                best_sl = rev_sl
                best_tf = order_tf
                best_kind = "reversal"
                trade.setdefault("trail_reversal_events", []).append({
                    "time_raw": int(upto_ts),
                    "type": rev_type,
                    "old_sl": round(current_sl, 2),
                    "new_sl": round(best_sl, 2),
                })

    if not best_tf:
        main_tf = group[0] if group else order_tf
        main_bars = [
            r for r in (trail_rates_by_tf.get(main_tf) or [])
            if entry_ts <= int(r["time"]) < int(upto_ts)
        ]
        if len(main_bars) >= 3 and not trade.get("trail_had_engulf"):
            if side == "BUY":
                safe = round(entry + 0.5, 2)
                if safe > best_sl:
                    best_sl = safe
                    best_tf = main_tf
                    best_kind = "safe"
            else:
                safe = round(entry - 0.5, 2)
                if best_sl == 0 or safe < best_sl:
                    best_sl = safe
                    best_tf = main_tf
                    best_kind = "safe"

    if best_tf and best_sl != current_sl:
        trade.setdefault("trail_events", []).append({
            "time_raw": int(upto_ts),
            "tf": best_tf,
            "kind": best_kind or "unknown",
            "old_sl": round(current_sl, 2),
            "new_sl": round(best_sl, 2),
        })
        trade["sl"] = round(best_sl, 2)
        if best_kind == "engulf":
            trade["trail_had_engulf"] = True


class SimSLGuard:
    def __init__(self, point: float = 0.01):
        self.per_tf: dict[tuple[str, str], dict] = {}
        self.combined: dict[str, dict] = {}
        self.group: dict[tuple[str, tuple], dict] = {}
        self.near_price = float(getattr(config, "SL_GUARD_NEAR_POINTS", 200) or 200) * float(point or 0.01) * config.points_scale()

    def _swing_ref(self, side: str, bars: list[dict]) -> float:
        snap = hhll_snapshot_from_bars(bars)
        if not snap:
            return 0.0
        if side == "BUY":
            return float((snap.get("sl") or {}).get("price", 0.0) or 0.0)
        if side == "SELL":
            return float((snap.get("sh") or {}).get("price", 0.0) or 0.0)
        return 0.0

    def _group_keys(self, tf: str) -> list[tuple]:
        keys = []
        for group in list(getattr(config, "SL_GUARD_GROUP_GROUPS", []) or []):
            if tf in group:
                keys.append(tuple(group))
        return keys

    def _latest_time(self, bars: list[dict]) -> int:
        return int(bars[-1]["time"]) if bars else 0

    def _blocked_signal_from_order(self, order: dict, candle_time: int | None = None) -> dict:
        return {
            "sid": int(order.get("sid", 0) or 0),
            "tf": order.get("tf"),
            "signal": order.get("signal") or order.get("side"),
            "side": order.get("side") or order.get("signal"),
            "entry": float(order.get("entry", 0.0) or 0.0),
            "sl": float(order.get("sl", 0.0) or 0.0),
            "tp": float(order.get("tp", 0.0) or 0.0),
            "pattern": order.get("pattern", ""),
            "candle_time": int(candle_time or order.get("detect_time_raw", 0) or 0),
        }

    def _append_blocked_signal(self, bucket: list, signal: dict) -> None:
        duplicate = any(
            item.get("candle_time") == signal.get("candle_time")
            and item.get("sid") == signal.get("sid")
            and item.get("signal") == signal.get("signal")
            for item in bucket
        )
        if not duplicate:
            bucket.append(signal)

    def record_blocked_order(self, tf: str, order: dict, candle_time: int | None = None) -> None:
        side = (order.get("signal") or order.get("side") or "").upper()
        if not side:
            return
        signal = self._blocked_signal_from_order(order, candle_time)

        if getattr(config, "SL_GUARD_ENABLED", False):
            st = self.per_tf.get((tf, side))
            if st and st.get("active"):
                self._append_blocked_signal(st.setdefault("blocked_signals", []), signal)

        if getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
            st = self.combined.get(side)
            if st and st.get("tf_blocked", {}).get(tf):
                bucket = st.setdefault("tf_blocked_signals", {}).setdefault(tf, [])
                self._append_blocked_signal(bucket, signal)

        if getattr(config, "SL_GUARD_GROUP_ENABLED", False):
            for key in self._group_keys(tf):
                st = self.group.get((side, key))
                if st and st.get("tf_blocked", {}).get(tf):
                    bucket = st.setdefault("tf_blocked_signals", {}).setdefault(tf, [])
                    self._append_blocked_signal(bucket, signal)

    def _retry_order_from_signal(self, sig: dict, tf: str, bar: dict) -> dict | None:
        side = (sig.get("signal") or sig.get("side") or "").upper()
        entry = float(sig.get("entry", 0.0) or 0.0)
        sl = float(sig.get("sl", 0.0) or 0.0)
        tp = float(sig.get("tp", 0.0) or 0.0)
        if side not in ("BUY", "SELL") or not (entry and sl and tp):
            return None
        close = float(bar.get("close", 0.0) or 0.0)
        if side == "BUY" and close > entry:
            return None
        if side == "SELL" and close < entry:
            return None
        if side == "BUY" and close < sl:
            return None
        if side == "SELL" and close > sl:
            return None
        return {
            "sid": int(sig.get("sid", 0) or 0),
            "tf": tf,
            "signal": side,
            "side": side,
            "pattern": sig.get("pattern", ""),
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "detect_time_raw": int(bar["time"]),
            "retry_source": "SL_GUARD_RETRY",
        }

    def pop_retry_orders(self, tf: str, bars: list[dict], bar: dict) -> list[dict]:
        orders = []
        for side in ("BUY", "SELL"):
            self.check_unblock(tf, side, bars)

            if getattr(config, "SL_GUARD_ENABLED", False):
                st = self.per_tf.get((tf, side))
                if st:
                    retries = st.pop("retry_signals", [])
                    for sig in retries:
                        order = self._retry_order_from_signal(sig, tf, bar)
                        if order:
                            orders.append(order)

            if getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
                st = self.combined.get(side)
                if st:
                    retries = st.setdefault("tf_retry_signals", {}).pop(tf, [])
                    for sig in retries:
                        order = self._retry_order_from_signal(sig, tf, bar)
                        if order:
                            orders.append(order)

            if getattr(config, "SL_GUARD_GROUP_ENABLED", False):
                for key in self._group_keys(tf):
                    st = self.group.get((side, key))
                    if not st:
                        continue
                    retries = st.setdefault("tf_retry_signals", {}).pop(tf, [])
                    for sig in retries:
                        order = self._retry_order_from_signal(sig, tf, bar)
                        if order:
                            orders.append(order)
        return orders

    def check_unblock(self, tf: str, side: str, bars: list[dict]) -> None:
        if getattr(config, "SL_GUARD_ENABLED", False):
            st = self.per_tf.get((tf, side))
            if st and st.get("active"):
                ref = float(st.get("swing_ref", 0.0) or 0.0)
                since = int(st.get("blocked_since_bar", 0) or 0)
                bars_after = [r for r in bars if int(r["time"]) > since]
                if bars_after and ref > 0:
                    if side == "BUY":
                        swing_bar = min(bars_after, key=lambda r: float(r["low"]))
                        swing_found = float(swing_bar["low"]) < ref
                    else:
                        swing_bar = max(bars_after, key=lambda r: float(r["high"]))
                        swing_found = float(swing_bar["high"]) > ref
                    if swing_found:
                        swing_time = int(swing_bar["time"])
                        retries = [
                            sig for sig in st.get("blocked_signals", [])
                            if int(sig.get("candle_time", 0) or 0) > swing_time
                        ]
                        self.per_tf[(tf, side)] = {
                            "count": 0,
                            "active": False,
                            "swing_ref": 0.0,
                            "blocked_since_bar": 0,
                            "retry_signals": retries,
                        }

        if getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
            st = self.combined.get(side)
            if st and st.get("tf_blocked", {}).get(tf):
                ref = float(st.get("tf_swing_ref", {}).get(tf, 0.0) or 0.0)
                since = int(st.get("tf_since", {}).get(tf, 0) or 0)
                bars_after = [r for r in bars if int(r["time"]) > since]
                if bars_after and ref > 0:
                    if side == "BUY":
                        swing_bar = min(bars_after, key=lambda r: float(r["low"]))
                        swing_found = float(swing_bar["low"]) < ref
                    else:
                        swing_bar = max(bars_after, key=lambda r: float(r["high"]))
                        swing_found = float(swing_bar["high"]) > ref
                    if swing_found:
                        swing_time = int(swing_bar["time"])
                        blocked = st.setdefault("tf_blocked_signals", {}).get(tf, [])
                        retries = [
                            sig for sig in blocked
                            if int(sig.get("candle_time", 0) or 0) >= swing_time
                        ]
                        st["tf_blocked"][tf] = False
                        st.setdefault("tf_retry_signals", {})[tf] = retries
                        st.setdefault("tf_blocked_signals", {})[tf] = []

        if getattr(config, "SL_GUARD_GROUP_ENABLED", False):
            for key in self._group_keys(tf):
                st = self.group.get((side, key))
                if st and st.get("tf_blocked", {}).get(tf):
                    ref = float(st.get("tf_swing_ref", {}).get(tf, 0.0) or 0.0)
                    since = int(st.get("tf_since", {}).get(tf, 0) or 0)
                    bars_after = [r for r in bars if int(r["time"]) > since]
                    if not bars_after:
                        continue
                    if ref <= 0:
                        ref = self._swing_ref(side, bars)
                        st.setdefault("tf_swing_ref", {})[tf] = ref
                    if side == "BUY":
                        swing_bar = min(bars_after, key=lambda r: float(r["low"]))
                        swing_found = float(swing_bar["low"]) < ref
                    else:
                        swing_bar = max(bars_after, key=lambda r: float(r["high"]))
                        swing_found = float(swing_bar["high"]) > ref
                    if not swing_found:
                        st.setdefault("tf_swing_bar_time", {}).pop(tf, None)
                        continue
                    swing_time = int(swing_bar["time"])
                    st.setdefault("tf_swing_bar_time", {})[tf] = swing_time
                    confirm_bars = max(1, int(getattr(config, "SL_GUARD_GROUP_SWING_BARS", 5) or 5))
                    tf_secs = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}.get(tf.upper(), 60)
                    if self._latest_time(bars) < swing_time + confirm_bars * tf_secs:
                        continue
                    blocked = st.setdefault("tf_blocked_signals", {}).get(tf, [])
                    retries = [
                        sig for sig in blocked
                        if int(sig.get("candle_time", 0) or 0) >= swing_time
                    ]
                    st.setdefault("tf_retry_signals", {})[tf] = retries
                    st.setdefault("tf_blocked_signals", {})[tf] = []
                    st.setdefault("tf_swing_bar_time", {}).pop(tf, None)
                    st["tf_blocked"][tf] = False
                    if all(not st["tf_blocked"].get(t) for t in key):
                        preserved = {t: st.get("tf_retry_signals", {}).get(t, []) for t in key}
                        self.group[(side, key)] = {
                            "count": 0,
                            "active": False,
                            "tf_blocked": {},
                            "tf_since": {},
                            "tf_swing_ref": {},
                            "tf_swing_bar_time": {},
                            "tf_blocked_signals": {},
                            "tf_retry_signals": preserved,
                        }

    def is_blocked(self, tf: str, side: str, bars: list[dict]) -> bool:
        self.check_unblock(tf, side, bars)
        if getattr(config, "SL_GUARD_ENABLED", False):
            st = self.per_tf.get((tf, side))
            if st and st.get("active"):
                return True
        if getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
            st = self.combined.get(side)
            if st and st.get("tf_blocked", {}).get(tf):
                return True
        if getattr(config, "SL_GUARD_GROUP_ENABLED", False):
            for key in self._group_keys(tf):
                st = self.group.get((side, key))
                if st and st.get("tf_blocked", {}).get(tf):
                    return True
        return False

    def block_reason_meta(self, tf: str, side: str) -> dict:
        side = side.upper()
        if getattr(config, "SL_GUARD_ENABLED", False):
            st = self.per_tf.get((tf, side))
            if st and st.get("active"):
                return {
                    "sl_guard_scope": "per_tf",
                    "sl_guard_key": tf,
                    "sl_guard_count": st.get("count", ""),
                    "sl_guard_since": st.get("blocked_since_bar", ""),
                    "sl_guard_swing_ref": st.get("swing_ref", ""),
                }
        if getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
            st = self.combined.get(side)
            if st and st.get("tf_blocked", {}).get(tf):
                return {
                    "sl_guard_scope": "combined",
                    "sl_guard_key": ",".join(str(t) for t in getattr(config, "SL_GUARD_COMBINED_TFS", []) or []),
                    "sl_guard_count": st.get("count", ""),
                    "sl_guard_since": st.get("tf_since", {}).get(tf, ""),
                    "sl_guard_swing_ref": st.get("tf_swing_ref", {}).get(tf, ""),
                }
        if getattr(config, "SL_GUARD_GROUP_ENABLED", False):
            for key in self._group_keys(tf):
                st = self.group.get((side, key))
                if st and st.get("tf_blocked", {}).get(tf):
                    return {
                        "sl_guard_scope": "group",
                        "sl_guard_key": ",".join(str(t) for t in key),
                        "sl_guard_count": st.get("count", ""),
                        "sl_guard_since": st.get("tf_since", {}).get(tf, ""),
                        "sl_guard_swing_ref": st.get("tf_swing_ref", {}).get(tf, ""),
                    }
        return {}

    def near_blocked(self, tf: str, side: str, entry: float, bar: dict, bars: list[dict]) -> bool:
        if not self.is_blocked(tf, side, bars):
            return False
        probe = float(bar["low"]) if side == "BUY" else float(bar["high"])
        return abs(probe - float(entry)) <= self.near_price

    def record_close(self, tf: str, side: str, close_type: str, pnl: float, bars: list[dict]) -> bool:
        loss_guard = (
            getattr(config, "SL_GUARD_LOSS_ENABLED", False)
            and float(pnl) < -float(getattr(config, "SL_GUARD_LOSS_THRESHOLD", 5.0) or 5.0)
        )
        if close_type == "TP":
            self._reset_on_tp(tf, side)
            return False
        sl_loss = close_type == "SL" and float(pnl) < 0
        if not sl_loss and not loss_guard:
            return False
        return self._record_sl(tf, side, bars)

    def _record_sl(self, tf: str, side: str, bars: list[dict]) -> bool:
        activated = False
        side = side.upper()
        now_ts = self._latest_time(bars)
        if getattr(config, "SL_GUARD_ENABLED", False):
            st = self.per_tf.setdefault((tf, side), {
                "count": 0,
                "active": False,
                "swing_ref": 0.0,
                "blocked_since_bar": 0,
                "blocked_signals": [],
                "retry_signals": [],
            })
            st["count"] += 1
            if st["count"] >= int(getattr(config, "SL_GUARD_COUNT", 2) or 2) and not st.get("active"):
                st["active"] = True
                st["swing_ref"] = self._swing_ref(side, bars)
                st["blocked_since_bar"] = now_ts
                st.setdefault("blocked_signals", [])
                activated = True

        if getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
            tfs = list(getattr(config, "SL_GUARD_COMBINED_TFS", []) or [])
            if tf in tfs:
                st = self.combined.setdefault(side, {
                    "count": 0,
                    "tf_blocked": {},
                    "tf_swing_ref": {},
                    "tf_since": {},
                    "tf_blocked_signals": {},
                    "tf_retry_signals": {},
                })
                st["count"] += 1
                if st["count"] >= int(getattr(config, "SL_GUARD_COMBINED_COUNT", 2) or 2):
                    was_blocked = any(st.get("tf_blocked", {}).values())
                    for t in tfs:
                        st["tf_blocked"][t] = True
                        st["tf_swing_ref"][t] = self._swing_ref(side, bars) if t == tf else 0.0
                        st.setdefault("tf_since", {})[t] = now_ts
                        st.setdefault("tf_blocked_signals", {}).setdefault(t, [])
                    activated = activated or not was_blocked

        if getattr(config, "SL_GUARD_GROUP_ENABLED", False):
            for key in self._group_keys(tf):
                st = self.group.setdefault((side, key), {
                    "count": 0,
                    "active": False,
                    "tf_blocked": {},
                    "tf_since": {},
                    "tf_swing_ref": {},
                    "tf_swing_bar_time": {},
                    "tf_blocked_signals": {},
                    "tf_retry_signals": {},
                })
                st["count"] += 1
                if st["count"] >= int(getattr(config, "SL_GUARD_GROUP_COUNT", 2) or 2) and not st.get("active"):
                    st["active"] = True
                    was_blocked = any(st.get("tf_blocked", {}).values())
                    for t in key:
                        st["tf_blocked"][t] = True
                        st["tf_swing_ref"][t] = self._swing_ref(side, bars) if t == tf else 0.0
                        st.setdefault("tf_since", {})[t] = now_ts
                        st.setdefault("tf_blocked_signals", {}).setdefault(t, [])
                    activated = activated or not was_blocked
        return activated

    def _reset_on_tp(self, tf: str, side: str) -> None:
        side = side.upper()
        if getattr(config, "SL_GUARD_ENABLED", False):
            self.per_tf[(tf, side)] = {
                "count": 0,
                "active": False,
                "swing_ref": 0.0,
                "blocked_since_bar": 0,
                "blocked_signals": [],
                "retry_signals": [],
            }
        if getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
            self.combined.pop(side, None)
        if getattr(config, "SL_GUARD_GROUP_ENABLED", False):
            for key in self._group_keys(tf):
                self.group.pop((side, key), None)
