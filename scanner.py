from config import *
import config
import asyncio
import time as _time
from bot_log import log_block, log_event
from mt5_utils import connect_mt5, open_order, open_order_stop, open_order_market, get_existing_tp, should_cancel_pending, find_swing_tp, get_structure, has_previous_bar_trade, TF_SECONDS_MAP
from strategy1 import strategy_1
from strategy2 import strategy_2
from strategy3 import strategy_3
from strategy4 import (
    strategy_4,
    _find_prev_swing_high, _find_prev_swing_low, _find_hh, _find_ll,
    _is_pivot_high, _is_pivot_low,
    _find_prev_pivot_swing_high, _find_prev_pivot_swing_low, _find_pivot_hh, _find_pivot_ll,
)
from strategy5 import strategy_5
from strategy8 import strategy_8
from strategy9 import strategy_9
from strategy10 import strategy_10
from strategy11 import strategy_11, record_s1_pattern as s11_record_s1_pattern
from strategy13 import strategy_13
from pending import check_fvg_pending, check_pb_pending
from trailing import check_engulf_trail_sl, check_fvg_candle_quality, check_opposite_order_tp, check_entry_candle_quality, fvg_order_tickets, pending_order_tf, check_cancel_pending_orders, position_tf, check_breakeven_tp, position_sid, position_pattern, check_s6_trail, _s6_state, _s6i_state, _entry_state, _s8_fill_sl, check_s12_management, _get_filling_mode, _close_position, _build_s1_forward_meta
from notifications import check_sl_tp_hits
_first_scan_done = False
_scan_results: dict = {}   # {tf_name: dict}
_scan_lock = None
_last_scan_summary_telegram = ""
_last_scan_summary_cmd = ""
_last_scan_summary_log_time: float = 0.0
SCAN_SUMMARY_FORCE_INTERVAL = 60  # force log/tg ทุก 1 นาที แม้ body จะไม่เปลี่ยน
_s12_scan_status: dict = {}  # สถานะ S12 ล่าสุด สำหรับ scan summary
_last_skip_log_by_tf: dict = {}
_last_skip_notify_by_key: dict = {}
_last_divergence_log_by_key: dict = {}
_last_strategy9_setup_by_key: dict = {}
_last_strategy9_invalid_setup_by_key: dict = {}
_last_pattern_notify_by_key: dict = {}
_swing_data: dict = {}   # {tf_name: {"sh": str, "sl": str, "prev_sh": str, "prev_sl": str, "hh": str, "ll": str}}
_SCAN_TF_ICONS = {"M1": "🟨", "M5": "🟩", "M15": "🟦", "M30": "🟪", "H1": "🟧", "H4": "🟥", "H12": "🟫", "D1": "⬛"}
_SCAN_STRATEGY_ICONS = {"[ท่า1]": "🟡", "[ท่า2]": "🔵", "[ท่า3]": "🟣", "[ท่า4]": "🟢", "[ท่า6]": "🟠", "[ท่า6i]": "🟤", "[ท่า8]": "🩵", "[ท่า9]": "🟥", "[ท่า13]": "🩷"}


def _print_skip_once(tf_name: str, message: str) -> None:
    import re
    normalized = re.sub(r"\[\d{2}:\d{2}(?::\d{2})?\]\s*", "", message)
    key = f"{tf_name}|{normalized}"
    if _last_skip_log_by_tf.get(tf_name) == key:
        return
    _last_skip_log_by_tf[tf_name] = key
    print(message)
    log_event("SCAN_SKIP", normalized, tf=tf_name)


async def _notify_skip_once(app, dedup_key: str, text: str, tf_name: str = "", log_message: str = "") -> bool:
    normalized = (log_message or text or "").replace("\n", " | ").strip()
    key = f"{dedup_key}|{normalized}"
    if _last_skip_notify_by_key.get(dedup_key) == key:
        return False
    _last_skip_notify_by_key[dedup_key] = key
    if normalized:
        log_event("ORDER_SKIPPED", normalized, tf=tf_name)
    await tg(app, text)
    return True


async def _notify_pattern_found_once(app, dedup_key: str, text: str) -> bool:
    if _last_pattern_notify_by_key.get(dedup_key) == text:
        return False
    _last_pattern_notify_by_key[dedup_key] = text
    await tg(app, text, parse_mode="Markdown")
    return True


def _log_divergence_once(tf_name: str, sid: int, signal: str, candle_time: int, result: dict) -> None:
    pattern = result.get("pattern", "") or f"S{sid} {signal}"
    key = f"{tf_name}|{sid}|{signal}|{candle_time}|{pattern}"
    if _last_divergence_log_by_key.get(tf_name) == key:
        return
    _last_divergence_log_by_key[tf_name] = key
    log_event(
        "DIVERGENCE_FOUND",
        pattern,
        tf=tf_name,
        sid=sid,
        signal=signal,
        candle_time=_fmt_swing_dt(candle_time) if candle_time else "",
        entry=result.get("entry"),
        sl=result.get("sl"),
        tp=result.get("tp"),
        div_type=result.get("div_type", ""),
        pivot_prev_index=result.get("pivot_prev_index"),
        pivot_cur_index=result.get("pivot_cur_index"),
        pivot_prev_time=_fmt_swing_dt(result.get("pivot_prev_time", 0)) if result.get("pivot_prev_time") else "",
        pivot_cur_time=_fmt_swing_dt(result.get("pivot_cur_time", 0)) if result.get("pivot_cur_time") else "",
        price_prev=result.get("price_prev"),
        price_cur=result.get("price_cur"),
        rsi_prev=result.get("rsi_prev"),
        rsi_cur=result.get("rsi_cur"),
        swing_price=result.get("swing_price"),
    )


def _same_price(a, b, tol: float = 0.05) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False


def _log_confirm_lookback_block(tf_name: str, sid: int, signal: str, lookback_bars: int, pattern: str = "") -> None:
    log_event(
        "CONFIRM_LOOKBACK_BLOCK",
        f"ยังไม่เจอ S1/S2/S3 ฝั่งเดียวกันใน {lookback_bars} แท่งย้อนหลัง",
        tf=tf_name,
        sid=sid,
        signal=signal,
        pattern=pattern,
    )


def _find_recent_signal_confirmation(rates, signal: str, tf_secs: int, lookback_bars: int) -> dict | None:
    lookback_bars = max(0, int(lookback_bars or 0))
    if lookback_bars <= 0 or rates is None or len(rates) < 4:
        return None

    signal = str(signal or "").upper()
    matches = []
    checkers = (
        (1, strategy_1),
        (2, strategy_2),
        (3, strategy_3),
    )

    for bars_back in range(1, lookback_bars + 1):
        end_idx = len(rates) - bars_back
        if end_idx < 3:
            break
        sliced_rates = rates[:end_idx]
        confirm_bar_time = int(sliced_rates[-1]["time"])
        detect_time = confirm_bar_time + int(tf_secs or 0)

        for sid, checker in checkers:
            try:
                result = checker(sliced_rates)
            except Exception:
                continue
            if sid == 2:
                if str(result.get("signal", "")).upper() != "FVG_DETECTED":
                    continue
                fvg = result.get("fvg") or {}
                if str(fvg.get("signal", "")).upper() != signal:
                    continue
                pattern = str(fvg.get("pattern", "") or "")
            else:
                if str(result.get("signal", "")).upper() != signal:
                    continue
                pattern = str(result.get("pattern", "") or "")
            matches.append({
                "sid": sid,
                "signal": signal,
                "pattern": pattern,
                "bar_time": confirm_bar_time,
                "detect_time": detect_time,
                "bars_back": bars_back,
            })

    if not matches:
        return None

    matches.sort(key=lambda item: (item["detect_time"], -item["sid"]), reverse=True)
    return matches[0]


def _has_active_sid_trade(tf_name: str, sid: int) -> bool:
    for info in pending_order_tf.values():
        if not isinstance(info, dict):
            continue
        if info.get("tf") == tf_name and int(info.get("sid", 0) or 0) == sid:
            return True
    try:
        positions = mt5.positions_get(symbol=SYMBOL) or []
    except Exception:
        positions = []
    for pos in positions:
        ticket = int(getattr(pos, "ticket", 0) or 0)
        if not ticket:
            continue
        if position_tf.get(ticket) == tf_name and int(position_sid.get(ticket, 0) or 0) == sid:
            return True
    return False


def _adjacent_sid_blocked(tf_name: str, sid: int, candle_time: int, tf_secs: int) -> bool:
    prev = config.last_traded_sid_tf.get(tf_name, {}).get(sid)
    if not prev or tf_secs <= 0 or (int(candle_time) - int(prev)) != int(tf_secs):
        return False
    if _has_active_sid_trade(tf_name, sid):
        return True
    tf_map = config.last_traded_sid_tf.get(tf_name)
    if isinstance(tf_map, dict) and tf_map.get(sid) == prev:
        tf_map.pop(sid, None)
        if not tf_map:
            config.last_traded_sid_tf.pop(tf_name, None)
    return False


def _pattern_allows_adjacent_order(sid: int, pattern: str) -> bool:
    if int(sid or 0) != 1:
        return False
    pattern = str(pattern or "")
    return ("Pattern กลืนกิน 2 แดง" in pattern) or ("Pattern กลืนกิน 2 เขียว" in pattern)


async def _clear_opposite_s13_exposure(app, tf_name: str, signal: str) -> bool:
    """Close/cancel opposite S13 exposure on the same TF before opening a new S13 market order."""
    opposite = "SELL" if signal == "BUY" else "BUY"
    opposite_pos_type = mt5.ORDER_TYPE_SELL if signal == "BUY" else mt5.ORDER_TYPE_BUY
    closed_any = False
    failed = False

    orders = mt5.orders_get(symbol=SYMBOL) or []
    for order in orders:
        ticket = int(getattr(order, "ticket", 0) or 0)
        if not ticket:
            continue
        if position_sid.get(ticket) != 13 or position_tf.get(ticket) != tf_name:
            continue
        if opposite == "SELL" and order.type != mt5.ORDER_TYPE_SELL_LIMIT and order.type != mt5.ORDER_TYPE_SELL_STOP:
            continue
        if opposite == "BUY" and order.type != mt5.ORDER_TYPE_BUY_LIMIT and order.type != mt5.ORDER_TYPE_BUY_STOP:
            continue
        r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
        if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
            pending_order_tf.pop(ticket, None)
            position_tf.pop(ticket, None)
            position_sid.pop(ticket, None)
            position_pattern.pop(ticket, None)
            closed_any = True
            log_event("ORDER_CANCELED", f"S13 opposite pending cleared before {signal}", tf=tf_name, sid=13, signal=signal, ticket=ticket)
        else:
            failed = True

    positions = mt5.positions_get(symbol=SYMBOL) or []
    for pos in positions:
        ticket = int(getattr(pos, "ticket", 0) or 0)
        if not ticket:
            continue
        if position_sid.get(ticket) != 13 or position_tf.get(ticket) != tf_name:
            continue
        if int(getattr(pos, "type", -1)) != opposite_pos_type:
            continue
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        ok, close_price = _close_position(pos, pos_type, f"S13 opposite {signal} signal")
        if ok:
            closed_any = True
            log_event("POSITION_CLOSED", f"S13 opposite {signal} signal", tf=tf_name, sid=13, signal=signal, ticket=ticket, close_price=close_price)
        else:
            failed = True

    if closed_any:
        await tg(app, f"↔️ *[{tf_name}] S13 opposite signal*\nล้างฝั่ง `{opposite}` ก่อนเปิด `{signal}`")
    return not failed


def _has_same_side_s13_exposure(tf_name: str, signal: str) -> bool:
    same_pending_buy = {mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP}
    same_pending_sell = {mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP}
    same_pending_types = same_pending_buy if signal == "BUY" else same_pending_sell
    same_pos_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL

    for order in mt5.orders_get(symbol=SYMBOL) or []:
        ticket = order.ticket
        if position_sid.get(ticket) != 13 or position_tf.get(ticket) != tf_name:
            continue
        if int(getattr(order, "type", -1)) in same_pending_types:
            return True

    for pos in mt5.positions_get(symbol=SYMBOL) or []:
        ticket = pos.ticket
        if position_sid.get(ticket) != 13 or position_tf.get(ticket) != tf_name:
            continue
        if int(getattr(pos, "type", -1)) == same_pos_type:
            return True
    return False


async def _place_s13_split_orders(app, tf_name: str, result: dict, last_candle_time: int, current_price: float) -> bool:
    signal = result.get("signal", "")
    entry = float(result.get("entry", 0.0) or 0.0)
    sl = float(result.get("sl", 0.0) or 0.0)
    tp_levels = [float(x) for x in (result.get("tp_levels") or []) if float(x) > 0]
    pattern_base = result.get("pattern", "S13")
    reason = result.get("reason", "")
    now = now_bkk().strftime("%H:%M:%S")
    sig_e = "??" if signal == "BUY" else "??"

    if not tp_levels:
        tp_single = float(result.get("tp", 0.0) or 0.0)
        if tp_single > 0:
            tp_levels = [tp_single]
    if not tp_levels:
        log_event("ORDER_FAILED", "S13 missing TP levels", tf=tf_name, sid=13, signal=signal, entry=entry, sl=sl)
        await tg(app, f"❌ [{tf_name}] S13 ไม่มี TP levels")
        return False

    if _has_same_side_s13_exposure(tf_name, signal):
        _print_skip_once(tf_name, f"⏭️ [{now}] {tf_label(tf_name)} ท่า13: มี {signal} ค้างอยู่แล้ว")
        return False

    market_tickets = []
    limit_tickets = []
    volume = get_volume()
    if signal == "BUY":
        market_targets = [3] if current_price > entry else [1, 2, 3]
        limit_targets = [1, 2, 3] if current_price > entry else [3]
    else:
        market_targets = [3] if current_price < entry else [1, 2, 3]
        limit_targets = [1, 2, 3] if current_price < entry else [3]

    async with _get_lock():
        for idx in market_targets:
            if idx > len(tp_levels):
                continue
            tp = tp_levels[idx - 1]
            pattern = f"{pattern_base} TP{idx}"
            flow_id = f"S13|{tf_name}|{signal}|TP{idx}|E{entry:.2f}|SL{sl:.2f}|TP{tp:.2f}"
            order = open_order_market(
                signal, volume, sl, tp,
                tf=tf_name, sid=13, pattern=pattern,
                order_index=idx,
            )
            if order.get("success"):
                ticket = order["ticket"]
                market_tickets.append((idx, ticket, tp))
                position_tf[ticket] = tf_name
                position_sid[ticket] = 13
                position_pattern[ticket] = pattern
                log_event(
                    "ORDER_CREATED",
                    pattern,
                    tf=tf_name,
                    sid=13,
                    signal=signal,
                    entry=entry,
                    sl=sl,
                    tp=tp,
                    ticket=ticket,
                    order_type=order.get("order_type", signal),
                    flow_id=flow_id,
                )
            elif order.get("skipped"):
                _print_skip_once(tf_name, f"?? [{now}] {tf_label(tf_name)} ???13: Entry {signal} ?????????? | Entry:{entry}")
                if not market_tickets:
                    return False
                break
            else:
                err = order.get("error", "")
                if '10027' in str(err):
                    err = "?? AutoTrading ????????? MT5 ?? Ctrl+E ?????????? AutoTrading ??????????????"
                log_event("ORDER_FAILED", err, tf=tf_name, sid=13, signal=signal, entry=entry, sl=sl, tp=tp, flow_id=flow_id)
                await tg(app, f"❌ [{tf_name}] ท่า13 TP{idx} ไม่สำเร็จ: `{err}`")

        for idx in limit_targets:
            if idx > len(tp_levels):
                continue
            tp = tp_levels[idx - 1]
            limit_pattern = f"{pattern_base} TP{idx} LIMIT"
            limit_flow_id = f"S13|{tf_name}|{signal}|LTP{idx}|E{entry:.2f}|SL{sl:.2f}|TP{tp:.2f}"
            limit_order = open_order(
                signal, volume, sl, tp,
                entry_price=entry, tf=tf_name, sid=13, pattern=limit_pattern,
                order_index=f"L{idx}",
            )
            if limit_order.get("success"):
                ticket = limit_order["ticket"]
                limit_tickets.append((idx, ticket, tp))
                pending_order_tf[ticket] = {
                    "tf": tf_name,
                    "entry": round(entry, 2),
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                    "gap_bot": round(entry - abs(entry - sl), 2),
                    "gap_top": round(entry + abs(entry - sl), 2),
                    "detect_bar_time": last_candle_time,
                    "signal": signal,
                    "sid": 13,
                    "pattern": limit_pattern,
                    "flow_id": limit_flow_id,
                    "tp_index": idx,
                    "is_s13_limit_tp3": idx == 3,
                    "is_s13_limit": True,
                }
                position_tf[ticket] = tf_name
                position_sid[ticket] = 13
                position_pattern[ticket] = limit_pattern
                log_event(
                    "ORDER_CREATED",
                    limit_pattern,
                    tf=tf_name,
                    sid=13,
                    signal=signal,
                    entry=entry,
                    sl=sl,
                    tp=tp,
                    ticket=ticket,
                    order_type=limit_order.get("order_type", "BUY LIMIT" if signal == "BUY" else "SELL LIMIT"),
                    flow_id=limit_flow_id,
                )
            elif limit_order.get("skipped"):
                _print_skip_once(tf_name, f"?? [{now}] {tf_label(tf_name)} ???13: TP{idx} LIMIT ?????????? | Entry:{entry}")
            else:
                err = limit_order.get("error", "")
                if '10027' in str(err):
                    err = "?? AutoTrading ????????? MT5 ?? Ctrl+E ?????????? AutoTrading ??????????????"
                log_event("ORDER_FAILED", err, tf=tf_name, sid=13, signal=signal, entry=entry, sl=sl, tp=tp, flow_id=limit_flow_id)
                await tg(app, f"❌ [{tf_name}] ท่า13 TP{idx} LIMIT ไม่สำเร็จ: `{err}`")

    if not market_tickets and not limit_tickets:
        return False

    last_traded_per_tf[tf_name] = last_candle_time
    config.last_traded_sid_tf.setdefault(tf_name, {})[13] = last_candle_time
    save_runtime_state()

    rr = abs(tp_levels[0] - entry) / max(abs(entry - sl), 0.0001)
    lines = [
        f"{sig_e} *[{tf_name}] S13 {signal}*",
        f"📌 Entry: `{entry:.2f}`",
        f"🛑 SL: `{sl:.2f}`",
    ]
    for idx, ticket, tp in market_tickets:
        lines.append(f"🎯 MARKET TP{idx}: `{tp:.2f}` | Ticket:`{ticket}`")
    for idx, ticket, tp in limit_tickets:
        lines.append(f"🪤 LIMIT TP{idx}: `{tp:.2f}` | Ticket:`{ticket}`")
    if reason:
        lines.append(f"📝 {reason.splitlines()[0]}")
    lines.append(f"⚖️ R:R TP1 `1:{rr:.2f}` | 📦 `{volume}` lot/order")
    await tg(app, "\n".join(lines))
    return True


def _build_strategy9_setup_sig(tf_name: str, signal: str, result: dict) -> str:
    """
    Setup signature สำหรับ dedup — ใช้แค่ pivot identity (ไม่รวม entry/sl/tp)
    เพราะ market mode entry = rates[-1].close จะเปลี่ยนทุก bar ใหม่ —
    setup_sig ที่อิง entry จะ break dedup ตอนแท่งใหม่ปิด
    """
    div_type = result.get("div_type", "") or ""
    pivot_prev_time = int(result.get("pivot_prev_time", 0) or 0)
    pivot_cur_time = int(result.get("pivot_cur_time", 0) or 0)
    if not (div_type and pivot_prev_time and pivot_cur_time):
        return ""
    return f"{tf_name}|{signal}|{div_type}|{pivot_prev_time}|{pivot_cur_time}"


def _is_strategy9_setup_invalidated(setup_sig: str) -> bool:
    return bool(setup_sig and _last_strategy9_invalid_setup_by_key.get(setup_sig))


def _build_order_flow_id(tf_name: str, sid: int, signal: str, candle_time: int,
                         entry: float, sl: float, tp: float, model: int = 0) -> str:
    try:
        entry_s = f"{float(entry):.2f}"
    except Exception:
        entry_s = "0.00"
    try:
        sl_s = f"{float(sl):.2f}"
    except Exception:
        sl_s = "0.00"
    try:
        tp_s = f"{float(tp):.2f}"
    except Exception:
        tp_s = "0.00"
    base = f"{tf_name}|S{sid}|{signal}|T{int(candle_time or 0)}|E{entry_s}|SL{sl_s}|TP{tp_s}"
    if model:
        base += f"|M{int(model)}"
    return base


def _short_flow_id(flow_id: str) -> str:
    if not flow_id:
        return ""
    parts = [p for p in str(flow_id).split("|") if p]
    if len(parts) <= 4:
        return "-".join(parts)
    head = parts[:4]
    model = next((p for p in parts[4:] if p.startswith("M")), "")
    if model:
        head.append(model)
    return "-".join(head)


def _find_duplicate_pending_setup(tf_name: str, sid: int, signal: str,
                                  entry: float, sl: float, tp: float,
                                  setup_sig: str = "",
                                  tol: float = 0.05):
    """หา pending setup เดิมที่ยังค้างอยู่ เพื่อลดการเปิดซ้ำบริเวณเดิม"""
    if setup_sig:
        recent_ticket = _last_strategy9_setup_by_key.get(setup_sig)
        if recent_ticket:
            return recent_ticket, "recent_setup"

    for ticket, info in list(pending_order_tf.items()):
        if not isinstance(info, dict):
            continue
        if info.get("tf") != tf_name:
            continue
        if info.get("sid") != sid:
            continue
        if info.get("signal") != signal:
            continue
        if setup_sig and info.get("setup_sig") == setup_sig:
            return ticket, "setup_sig"
        if not _same_price(info.get("entry"), entry, tol):
            continue
        if not _same_price(info.get("sl"), sl, tol):
            continue
        if not _same_price(info.get("tp"), tp, tol):
            continue
        return ticket, "runtime_state"

    orders = mt5.orders_get(symbol=SYMBOL) or []
    want_types = (
        {mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP}
        if signal == "BUY"
        else {mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP}
    )
    comment_sid_token = f"_S{sid}"
    for order in orders:
        if order.type not in want_types:
            continue
        comment = getattr(order, "comment", "") or ""
        if comment_sid_token not in comment:
            continue
        if not _same_price(getattr(order, "price_open", 0.0), entry, tol):
            continue
        if not _same_price(getattr(order, "sl", 0.0), sl, tol):
            continue
        if not _same_price(getattr(order, "tp", 0.0), tp, tol):
            continue
        return order.ticket, "mt5_pending"

    return None, ""


def _find_previous_swing_info(rates, current_info, finder):
    """หา swing ก่อนหน้าของ swing ปัจจุบัน เพื่อใช้แสดงผล"""
    if not current_info:
        return None
    current_time = int(current_info.get("time", 0) or 0)
    prev_rates = [r for r in rates if int(r["time"]) < current_time]
    if len(prev_rates) < 6:
        return None
    try:
        return finder(prev_rates)
    except Exception:
        return None


def _get_summary_swing_finders(lookback: int):
    mode = str(getattr(config, "SWING_SUMMARY_MODE", "pair") or "pair").lower()
    pivot_left = max(1, int(getattr(config, "SWING_PIVOT_LEFT", 15) or 15))
    pivot_right = max(1, int(getattr(config, "SWING_PIVOT_RIGHT", 10) or 10))

    if mode == "pivot":
        return {
            "mode": "pivot",
            "high": lambda rates: _find_prev_pivot_swing_high(
                rates, lookback=lookback, left=pivot_left, right=pivot_right
            ),
            "low": lambda rates: _find_prev_pivot_swing_low(
                rates, lookback=lookback, left=pivot_left, right=pivot_right
            ),
            "hh": lambda rates, cur: _find_pivot_hh(
                rates, cur, lookback=lookback, left=pivot_left, right=pivot_right
            ),
            "ll": lambda rates, cur: _find_pivot_ll(
                rates, cur, lookback=lookback, left=pivot_left, right=pivot_right
            ),
        }

    return {
        "mode": "pair",
        "high": lambda rates: _find_prev_swing_high(rates, lookback=lookback),
        "low": lambda rates: _find_prev_swing_low(rates, lookback=lookback),
        "hh": lambda rates, cur: _find_hh(rates, cur, lookback=lookback),
        "ll": lambda rates, cur: _find_ll(rates, cur, lookback=lookback),
    }


def _build_summary_pivot_info(rates, idx: int):
    total = len(rates)
    if idx < 0 or idx >= total:
        return None
    bar = rates[idx]
    return {
        "price": None,
        "bar_from_2": (total - 3) - idx,
        "time": int(bar["time"]),
        "candle": {
            "open": float(bar["open"]),
            "high": float(bar["high"]),
            "low": float(bar["low"]),
            "close": float(bar["close"]),
        },
    }


def _collect_summary_pivot_swings(rates, lookback: int, left: int, right: int):
    total = len(rates)
    if total < left + right + 3:
        return {"highs": [], "lows": []}

    start = max(left, total - min(lookback, total))
    end_exclusive = total - right
    highs = []
    lows = []

    for i in range(start, end_exclusive):
        if _is_pivot_high(rates, i, left, right):
            info = _build_summary_pivot_info(rates, i)
            if info:
                info["price"] = float(rates[i]["high"])
                info["candle"]["high"] = info["price"]
                highs.append(info)
        if _is_pivot_low(rates, i, left, right):
            info = _build_summary_pivot_info(rates, i)
            if info:
                info["price"] = float(rates[i]["low"])
                info["candle"]["low"] = info["price"]
                lows.append(info)

    return {"highs": highs, "lows": lows}


def _resolve_summary_pivot_levels(rates, lookback: int, left: int, right: int):
    pivots = _collect_summary_pivot_swings(rates, lookback=lookback, left=left, right=right)
    highs = pivots["highs"]
    lows = pivots["lows"]

    sh = highs[-1] if highs else None
    prev_sh = highs[-2] if len(highs) >= 2 else None
    prev_prev_sh = highs[-3] if len(highs) >= 3 else None

    sl = lows[-1] if lows else None
    prev_sl = lows[-2] if len(lows) >= 2 else None
    prev_prev_sl = lows[-3] if len(lows) >= 3 else None

    hh = None
    if sh:
        cur_price = float(sh["price"])
        for info in reversed(highs[:-1]):
            if float(info["price"]) > cur_price:
                hh = info
                break

    ll = None
    if sl:
        cur_price = float(sl["price"])
        for info in reversed(lows[:-1]):
            if float(info["price"]) < cur_price:
                ll = info
                break

    return {
        "sh": sh,
        "prev_sh": prev_sh,
        "prev_prev_sh": prev_prev_sh,
        "hh": hh,
        "sl": sl,
        "prev_sl": prev_sl,
        "prev_prev_sl": prev_prev_sl,
        "ll": ll,
        "highs": highs,
        "lows": lows,
    }


def _compute_trend_info(sh, prev_sh, prev_prev_sh, sl, prev_sl, prev_prev_sl):
    """
    คำนวณ trend จาก swing H/L 3 จุดล่าสุด:
    - 2 คู่ติดกัน (HH/HL หรือ LH/LL) → confirmed (strong)
    - 1 คู่        → tentative (weak)
    - ผสม / ขาดข้อมูล → SIDEWAY / UNKNOWN
    คืน dict: {trend, strength, label}
    """
    def _hh_streak(cur, prev, prev2):
        if not cur or not prev:
            return 0
        if cur["price"] <= prev["price"]:
            return 0
        if prev2 and prev["price"] > prev2["price"]:
            return 2
        return 1

    def _lh_streak(cur, prev, prev2):
        if not cur or not prev:
            return 0
        if cur["price"] >= prev["price"]:
            return 0
        if prev2 and prev["price"] < prev2["price"]:
            return 2
        return 1

    hh = _hh_streak(sh, prev_sh, prev_prev_sh)
    lh = _lh_streak(sh, prev_sh, prev_prev_sh)
    hl = _hh_streak(sl, prev_sl, prev_prev_sl)
    ll = _lh_streak(sl, prev_sl, prev_prev_sl)

    if hh >= 2 and hl >= 2:
        return {"trend": "BULL", "strength": "strong", "label": "🟢 Bull (strong)"}
    if lh >= 2 and ll >= 2:
        return {"trend": "BEAR", "strength": "strong", "label": "🔴 Bear (strong)"}
    if hh >= 1 and hl >= 1:
        return {"trend": "BULL", "strength": "weak", "label": "🟢 Bull (weak)"}
    if lh >= 1 and ll >= 1:
        return {"trend": "BEAR", "strength": "weak", "label": "🔴 Bear (weak)"}
    if not sh or not sl:
        return {"trend": "UNKNOWN", "strength": "-", "label": "❓ —"}
    return {"trend": "SIDEWAY", "strength": "-", "label": "⚪ SIDEWAY"}


def _compute_breakout_info(rates, sh, sl, prev_sh=None, prev_sl=None):
    """
    ตรวจว่า close แท่งล่าสุดทะลุ SH / SL ปัจจุบัน (แนวนอน) หรือไม่
    (prev_sh / prev_sl รับไว้เผื่ออนาคต — ตอนนี้ไม่ได้ใช้)
    คืน dict: {break_up, break_down, label}
    """
    result = {"break_up": False, "break_down": False, "label": ""}
    if rates is None or len(rates) == 0:
        return result
    last_close = float(rates[-1]["close"])
    if sh and last_close > float(sh["price"]):
        result["break_up"] = True
    if sl and last_close < float(sl["price"]):
        result["break_down"] = True
    parts = []
    if result["break_up"]:
        parts.append("🚀 BREAK↑")
    if result["break_down"]:
        parts.append("💥 BREAK↓")
    result["label"] = " ".join(parts)
    return result


def _export_trend_state_for_mt5():
    """
    เขียนสถานะ trend ต่อ TF ลงไฟล์ trend_state.txt และ trend_state_<symbol>.txt
    ใน MT5 Common\\Files
    ให้ MQL5 indicator (TrendFilterLines.mq5) อ่านไปวาดเส้นบน chart
    เฉพาะ TF ที่ Per-TF ติ๊กไว้ใน Trend Filter เท่านั้น (ดู per_tf_on flag)
    """
    try:
        info = mt5.terminal_info()
        if not info:
            return
        common_path = getattr(info, "commondata_path", None)
        if not common_path:
            return
        import os
        files_dir = os.path.join(common_path, "Files")
        os.makedirs(files_dir, exist_ok=True)
        symbol_name = str(SYMBOL or "").strip() or "UNKNOWN"
        target_default = os.path.join(files_dir, "trend_state.txt")
        target_symbol = os.path.join(files_dir, f"trend_state_{symbol_name}.txt")

        per_tf_map = getattr(config, "TREND_FILTER_PER_TF", {}) or {}
        lines = [
            f"# generated_at={now_bkk().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# symbol={SYMBOL}",
            "# tf,trend,strength,"
            "sh_time,sh_price,prev_sh_time,prev_sh_price,"
            "sl_time,sl_price,prev_sl_time,prev_sl_price,"
            "break_flag,per_tf_on",
        ]
        for tf_name, sw in _swing_data.items():
            trend = sw.get("trend") or {}
            breakout = sw.get("breakout") or {}
            t = trend.get("trend", "UNKNOWN")
            strength = trend.get("strength", "-")
            break_flag = "-"
            if breakout.get("break_up"):
                break_flag = "break_up"
            elif breakout.get("break_down"):
                break_flag = "break_down"
            per_tf_on = 1 if per_tf_map.get(tf_name, False) else 0

            def _num(v, is_price=True):
                if v is None:
                    return "0"
                if is_price:
                    return f"{float(v):.2f}"
                return str(int(v))

            lines.append(
                f"{tf_name},{t},{strength},"
                f"{_num(sw.get('sh_time'), False)},{_num(sw.get('sh_price'))},"
                f"{_num(sw.get('prev_sh_time'), False)},{_num(sw.get('prev_sh_price'))},"
                f"{_num(sw.get('sl_time'), False)},{_num(sw.get('sl_price'))},"
                f"{_num(sw.get('prev_sl_time'), False)},{_num(sw.get('prev_sl_price'))},"
                f"{break_flag},{per_tf_on}"
            )
        payload = "\n".join(lines) + "\n"
        for target in (target_default, target_symbol):
            tmp = target + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp, target)
    except Exception as e:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ export trend_state error: {e}")


def trend_allows_signal(tf_name: str, signal: str) -> tuple[bool, str]:
    """
    ตรวจว่า trend ของ TF ที่เลือก (per-TF และ/หรือ higher TF) ให้ผ่าน signal นี้หรือไม่
    เลือก mode ผ่าน config.TREND_FILTER_MODE:
      "basic" (default):
        - BULL ทุก strength → BUY only (block SELL)
        - BEAR ทุก strength → SELL only (block BUY)
        - SIDEWAY / UNKNOWN → ผ่านทั้งคู่
      "breakout":
        - BULL strong + ไม่ break_down → BUY only
        - BULL strong + break_down     → ผ่านทั้งคู่
        - BEAR strong + ไม่ break_up   → SELL only
        - BEAR strong + break_up       → ผ่านทั้งคู่
        - weak / SIDEWAY / UNKNOWN     → ผ่านทั้งคู่
    return: (allowed: bool, reason: str)
    """
    per_tf_map = getattr(config, "TREND_FILTER_PER_TF", {}) or {}
    per_tf_on = bool(per_tf_map.get(tf_name, False))
    higher_on = bool(getattr(config, "TREND_FILTER_HIGHER_TF_ENABLED", False))
    if not per_tf_on and not higher_on:
        return True, ""

    mode = getattr(config, "TREND_FILTER_MODE", "basic")

    def _check(ref_tf: str) -> tuple[bool, str]:
        sw = _swing_data.get(ref_tf)
        if not sw:
            return True, ""
        trend = sw.get("trend") or {}
        t = trend.get("trend", "UNKNOWN")
        if mode == "breakout":
            if t not in ("BULL", "BEAR"):
                return True, ""
            breakout = sw.get("breakout") or {}
            if t == "BULL":
                if breakout.get("break_down"):
                    if signal == "BUY":
                        return False, f"{ref_tf} BULL break_down"
                else:
                    if signal == "SELL":
                        return False, f"{ref_tf} BULL"
            elif t == "BEAR":
                if breakout.get("break_up"):
                    if signal == "SELL":
                        return False, f"{ref_tf} BEAR break_up"
                else:
                    if signal == "BUY":
                        return False, f"{ref_tf} BEAR"
            return True, ""
        # basic mode
        if t == "BULL" and signal == "SELL":
            return False, f"{ref_tf} BULL"
        if t == "BEAR" and signal == "BUY":
            return False, f"{ref_tf} BEAR"
        return True, ""

    if per_tf_on:
        ok, why = _check(tf_name)
        if not ok:
            return False, why
    if higher_on:
        ht = getattr(config, "TREND_FILTER_HIGHER_TF", "H4")
        if ht and ht != tf_name:
            ok, why = _check(ht)
            if not ok:
                return False, why
    return True, ""


def get_trend_label(tf_name: str) -> str:
    """คืน trend label ของ TF นั้น เช่น 'BULL (strong)', 'BEAR (weak)', 'SIDEWAY'"""
    sw = _swing_data.get(tf_name)
    if not sw:
        return "?"
    trend = sw.get("trend") or {}
    t = trend.get("trend", "UNKNOWN")
    s = trend.get("strength", "")
    return f"{t} ({s})" if s and s != "-" else t


def _trend_filter_setup_note(tf_name: str) -> str:
    """สรุปสถานะ Trend Filter ที่ใช้อ้างอิงตอนแจ้ง setup/order"""
    per_tf_map = getattr(config, "TREND_FILTER_PER_TF", {}) or {}
    per_tf_on = bool(per_tf_map.get(tf_name, False))
    higher_on = bool(getattr(config, "TREND_FILTER_HIGHER_TF_ENABLED", False))
    if not per_tf_on and not higher_on:
        return ""

    def _fmt_ref(ref_tf: str) -> str:
        sw = _swing_data.get(ref_tf) or {}
        trend = sw.get("trend") or {}
        breakout = sw.get("breakout") or {}
        trend_lbl = trend.get("label", "❓ —")
        break_lbl = breakout.get("label", "")
        tail = f" {break_lbl}" if break_lbl else ""
        return f"`{ref_tf}` = {trend_lbl}{tail}"

    lines = ["🧭 *Trend Filter*"]
    if per_tf_on:
        lines.append(f"• Per-TF: {_fmt_ref(tf_name)}")
    if higher_on:
        ht = getattr(config, "TREND_FILTER_HIGHER_TF", "H4")
        if ht:
            lines.append(f"• Higher TF: {_fmt_ref(ht)}")
    return "\n".join(lines)


def _trend_filter_state_keys(tf_name: str) -> list[str]:
    """คืน bucket trend filter ที่ใช้อ้างอิงกับ setup/order นี้"""
    per_tf_map = getattr(config, "TREND_FILTER_PER_TF", {}) or {}
    per_tf_on = bool(per_tf_map.get(tf_name, False))
    higher_on = bool(getattr(config, "TREND_FILTER_HIGHER_TF_ENABLED", False))
    refs = []
    if per_tf_on:
        refs.append(tf_name)
    if higher_on:
        ht = getattr(config, "TREND_FILTER_HIGHER_TF", "H4")
        if ht:
            refs.append(ht)

    keys = []
    for ref_tf in refs:
        sw = _swing_data.get(ref_tf) or {}
        trend = sw.get("trend") or {}
        t = str(trend.get("trend", "UNKNOWN") or "UNKNOWN").upper()
        strength = str(trend.get("strength", "-") or "-").lower()
        key = None
        if t == "BULL" and strength == "strong":
            key = "bull_strong"
        elif t == "BULL" and strength == "weak":
            key = "bull_weak"
        elif t == "BEAR" and strength == "weak":
            key = "bear_weak"
        elif t == "BEAR" and strength == "strong":
            key = "bear_strong"
        elif t == "SIDEWAY":
            key = "sideway"
        if key and key not in keys:
            keys.append(key)
    return keys




def _fmt_swing_dt(ts):
    """แปลงเวลาแท่ง/swing เป็น HH:mm dd-MMM-yyyy"""
    return fmt_mt5_bkk_ts(ts, "%H:%M %d-%b-%Y")


def _parse_pattern(pattern: str, signal: str, description: str,
                   entry=0, sl=0, tp=0) -> dict:
    """แยก pattern string -> skill / zone / pattern_name"""
    skill = ""; zone = ""; pat_name = ""
    if pattern:
        import re
        # zone icon: 🟢/🔴 + BUY/SELL
        zm = re.search(r'(🟢|🔴)\s*(BUY|SELL)', pattern)
        if zm:
            zone = f"{zm.group(1)}{zm.group(2)}"

        # pattern name หลัง " — " และตัด "Pattern " นำหน้าออก
        pm = re.search(r'—\s*(.+)$', pattern)
        if pm:
            pat_name = re.sub(r'^Pattern\s*', '', pm.group(1).strip())

        # skill = ชื่อท่า (ก่อน zone icon)
        sm = re.match(r'(ท่าที่\s*\d+[\w\s/ตำหนิย้อนโครงสร้างกลืนกิน FVG DM SP]+?)(?=🟢|🔴)', pattern)
        if sm:
            skill = sm.group(1).strip()
        elif pattern:
            skill = re.split(r'🟢|🔴', pattern)[0].strip()

    return {
        "status":      signal,
        "skill":       skill,
        "zone":        zone,
        "pattern":     pat_name,
        "description": description,
        "entry": entry, "sl": sl, "tp": tp,
    }


def _vlen(s: str) -> int:
    """visual display width (emoji/wide chars = 2 cols)"""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ('W','F') else 1 for c in s)


def _format_log_block(tf_name: str, d: dict, lead: str, pad: str, max_len: int) -> str:
    """
    🔍 [10:37] M1  : 🔵 Status      : WAIT — (🟢BUY)
                     📘 Skill       : ท่าที่ 1 กลืนกิน/ตำหนิ/ย้อนโครงสร้าง
                     🎯 Pattern     : กลืนกิน
                     📝 Description : ⚠️ ไม่อยู่ Low Zone
    """
    C_FIELD = "\033[38;5;75m"   # ฟ้า — field labels
    C_SEP   = "\033[38;5;240m"  # เทาเข้ม — separator ":"
    COLON   = f"{C_SEP} : {RESET}"
    c    = TF_COLOR.get(tf_name, "")
    name = tf_name.ljust(max_len)
    W    = 11   # "Description" = 11 chars (longest label)

    # sub-line indent ใช้ visual width ของ pad + name + " : "
    sub = " " * (_vlen(pad) + max_len + 3)

    # Icon สำหรับแต่ละ field (icon = 1 wide char = 2 cols + 1 space)
    ICONS = {
        "Status":      "🔵",
        "Skill":       "📘",
        "Pattern":     "🎯",
        "Description": "📝",
    }
    def field(label):
        icon = ICONS.get(label, "  ")
        # icon กว้าง 2 cols + 1 space = 3 → label ลด 3 ออก แต่ align W ยังคงเดิม
        return f"{icon} {C_FIELD}{label:<{W}}{RESET}"

    # Status + Zone รวมในบรรทัดเดียว
    zone     = d.get("zone", "")   # เช่น "🟢BUY" หรือ "🔴SELL"
    status   = d.get("status", "WAIT")
    if zone:
        if status == "WAIT":
            status_val = f"⏳WAIT {zone}"
        else:
            status_val = f"📌Entry {zone}"
    else:
        status_val = f"⏳WAIT" if status == "WAIT" else status

    lines = [
        f"{lead}{c}{name}{RESET}{COLON}{field('Status')}{COLON}{status_val}"
    ]
    # Skill แสดงเฉพาะเมื่อมี entry (ได้ order)
    if d.get("skill") and d.get("entry"):
        lines.append(f"{sub}{field('Skill')}{COLON}{d['skill']}")
    if d.get("pattern"):
        lines.append(f"{sub}{field('Pattern')}{COLON}{d['pattern']}")
    if d.get("description"):
        desc_raw   = d["description"]
        desc_lines = desc_raw.split("\n")
        label_str  = f"{field('Description')}{COLON}"
        # คำนวณ indent ให้ตรงกับค่าหลัง " : "
        # sub + icon(2cols) + space(1) + W + " : "(3) = เริ่มค่า
        indent2 = sub + " " * (2 + 1 + W + 3)
        lines.append(f"{sub}{label_str}{desc_lines[0]}")
        for dl in desc_lines[1:]:
            lines.append(f"{indent2}{dl}")
    if d.get("entry"):
        lines.append(
            f"{sub}{'':>{W + 4}}  "
            f"{C_ENTRY}{BOLD}Entry : {d['entry']}{RESET}  "
            f"{C_SL}{BOLD}SL : {d['sl']}{RESET}  "
            f"{C_TP}{BOLD}TP : {d['tp']}{RESET}"
        )
    return "\n".join(lines)
def _get_lock():
    global _scan_lock
    if _scan_lock is None:
        _scan_lock = asyncio.Lock()
    return _scan_lock
def tf_label(tf_name: str) -> str:
    """แปลง TF name เป็นชื่อพร้อมสี rainbow"""
    return f"{TF_COLOR.get(tf_name, '')}{tf_name}{RESET}"
def _strip_ansi(text: str) -> str:
    """ลบรหัสสี/format ของ terminal ออกจากข้อความก่อนส่ง Telegram"""
    import re
    if not text:
        return ""
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    text = re.sub(r"\[[0-9;]+m", "", text)
    return text.replace(RESET, "").replace(BOLD, "")
def _format_scan_summary_telegram(show_tfs: list[str]) -> tuple[str, str]:
    """สร้าง summary scan สำหรับ Telegram และคืน key สำหรับ dedup"""
    body_lines = []
    for tf in show_tfs:
        d = _scan_results.get(tf, {})
        status = d.get("status", "WAIT")
        desc = d.get("description", "") or "ไม่มีรายละเอียด"
        desc_lines = [line.strip() for line in desc.splitlines() if line.strip()]

        body_lines.append(f"`{tf}` {'⏳ WAIT' if status == 'WAIT' else '📌 ENTRY'}")
        for line in desc_lines:
            body_lines.append(line)
        if d.get("entry"):
            body_lines.append(f"Entry:`{d['entry']}` SL:`{d['sl']}` TP:`{d['tp']}`")
        body_lines.append("")
    body = "\n".join(body_lines).strip()
    text = (
        "🔍 *Scan Summary*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"🕐 `{now_bkk().strftime('%d/%m/%Y %H:%M:%S')}`\n\n"
        f"{body}"
    )
    return text, body
def _format_scan_summary_telegram_clean(show_tfs: list[str]) -> tuple[str, str]:
    """สร้าง summary scan สำหรับ Telegram แบบ plain text และไม่มี ANSI"""
    body_lines = []
    for tf in show_tfs:
        d = _scan_results.get(tf, {})
        status = d.get("status", "WAIT")
        desc = _strip_ansi(d.get("description", "") or "ไม่มีรายละเอียด")
        desc_lines = [line.strip() for line in desc.splitlines() if line.strip()]

        tf_icon = _SCAN_TF_ICONS.get(tf, "⬜")
        status_icon = "⏳" if status == "WAIT" else "📌"
        body_lines.append(f"{tf_icon} {tf} | {status_icon} {status}")
        for line in desc_lines:
            icon = "⚪"
            strategy_label = ""
            clean_line = line
            for key, value in _SCAN_STRATEGY_ICONS.items():
                if key in line:
                    icon = value
                    strategy_label = key.strip("[]")
                    clean_line = clean_line.replace(f"{key} ", "").replace(key, "")
                    break
            prefix = f"{icon} {strategy_label}".strip()
            body_lines.append(f"{prefix} {clean_line.strip()}".strip())
        if d.get("entry"):
            body_lines.append(f"💰 Entry:{d['entry']} | SL:{d['sl']} | TP:{d['tp']}")
        body_lines.append("")

    # Swing summary รวมทุก TF ท้าย
    swing_lines = []
    for tf in _swing_data:
        sw = _swing_data[tf]
        tf_icon = _SCAN_TF_ICONS.get(tf, "⬜")
        trend_lbl = (sw.get("trend") or {}).get("label", "❓ —")
        break_lbl = (sw.get("breakout") or {}).get("label", "")
        asof_lbl = fmt_mt5_bkk_ts(sw.get("asof_time"), "%H:%M %d-%b-%Y") if sw.get("asof_time") else "—"
        sh_confirm_lbl = fmt_mt5_bkk_ts(sw.get("sh_confirm_time"), "%H:%M %d-%b-%Y") if sw.get("sh_confirm_time") else "—"
        sl_confirm_lbl = fmt_mt5_bkk_ts(sw.get("sl_confirm_time"), "%H:%M %d-%b-%Y") if sw.get("sl_confirm_time") else "—"
        trend_line = f"│ 🧭 Trend:{trend_lbl}"
        if break_lbl:
            trend_line += f"  {break_lbl}"
        swing_lines.append(f"┌─ {tf_icon} {tf}")
        swing_lines.append(trend_line)
        if sw.get("mode") == "pivot":
            swing_lines.append(f"│ 🕒 AsOf:{asof_lbl} | H✓:{sh_confirm_lbl} | L✓:{sl_confirm_lbl}")
        swing_lines.append(f"│ 📈 H:{sw['sh']}")
        swing_lines.append(f"│ 📈 HH:{sw.get('hh', '—')}")
        swing_lines.append(f"│ 📈 Prev H:{sw.get('prev_sh', '—')}")
        swing_lines.append(f"│ 📉 L:{sw['sl']}")
        swing_lines.append(f"│ 📉 LL:{sw.get('ll', '—')}")
        swing_lines.append(f"│ 📉 Prev L:{sw.get('prev_sl', '—')}")
        swing_lines.append("└────────────────")
    if swing_lines:
        body_lines.append("━━━━━━━━━━━━━━━━━\n📊 Scan Swing\n\n" + "\n".join(swing_lines))

    if _s12_scan_status and active_strategies.get(12, False) and not _s12_scan_status.get("cooldown"):
        s = _s12_scan_status
        side_lbl  = s.get("side") or "—"
        count_lbl = s.get("count", 0)
        zone_lbl  = s.get("zone", "—")
        bzt = s.get("buy_zone_top",  s.get("swing_low", 0))
        szb = s.get("sell_zone_bot", s.get("swing_high", 0))
        swing_low  = s.get("swing_low", 0)
        swing_high = s.get("swing_high", 0)
        body_lines.append(
            f"━━━━━━━━━━━━━━━━━\n"
            f"📦 S12 Range [M5]\n"
            f"SELL zone: {szb:.2f} – {swing_high:.2f}\n"
            f"BUY  zone: {swing_low:.2f} – {bzt:.2f}\n"
            f"Now: {zone_lbl} | Side: {side_lbl} #{count_lbl}/{config.S12_ORDER_COUNT}"
        )

    body = "\n".join(body_lines).strip()
    text = (
        "🔍 Scan Summary\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now_bkk().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        f"{body}"
    )
    return text, body
async def check_s3_maru_pending(app):
    """
    ท่า 3 Marubozu pending — รอยืนยันแท่งถัดจากแท่ง[0] ตัน
    BUY:  แท่งถัดไปจบเขียว → ตั้ง Limit | จบแดง → ยกเลิก
    SELL: แท่งถัดไปจบแดง  → ตั้ง Limit | จบเขียว → ยกเลิก
    """
    if not s3_maru_pending:
        return
    now      = now_bkk().strftime("%H:%M:%S")
    to_remove = []
    for key, p in list(s3_maru_pending.items()):
        tf         = p["tf"]
        direction  = p["direction"]
        candle_time = p["candle_time"]
        entry      = p["entry"]
        sl         = p["sl"]
        tp         = p["tp"]
        c1_type    = p.get("c1_type", "R")
        tf_val  = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        rates   = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, 5)
        if rates is None or len(rates) < 2:
            continue
        last_bar = rates[-1]
        last_time = int(last_bar["time"])

        # รอแท่งใหม่หลังจากแท่ง[0] ตัน
        if last_time <= candle_time:
            continue   # ยังเป็นแท่งเดิมอยู่

        o  = float(last_bar["open"])
        cl = float(last_bar["close"])
        bull_next = cl > o
        lookback_bars = max(0, int(getattr(config, "S3_CONFIRM_LOOKBACK_BARS", getattr(config, "S2_NORMAL_CONFIRM_LOOKBACK_BARS", 8)) or 0))
        s3_confirm_ref = _find_recent_signal_confirmation(rates, direction, TF_SECONDS_MAP.get(tf, 0), lookback_bars)

        sig_e = "🟢" if direction == "BUY" else "🔴"
        confirm_time = candle_time + int(TF_SECONDS_MAP.get(tf, 0) or 0)
        candle0_lbl = fmt_mt5_bkk_ts(candle_time, "%H:%M") if candle_time else "-"
        confirm_lbl = fmt_mt5_bkk_ts(confirm_time, "%H:%M") if confirm_time else "-"

        if direction == "BUY":
            if bull_next:
                # ✅ จบเขียว → ตั้ง Limit
                _s3_ok, _s3_why = trend_allows_signal(tf, direction)
                _s3_adj = _adjacent_sid_blocked(tf, 3, candle_time, TF_SECONDS_MAP.get(tf, 0)) and has_previous_bar_trade(tf, candle_time)
                if config.TREND_FILTER_SCAN_BLOCK and not _s3_ok:
                    print(f"🧭 [{now}] ท่า3 BUY Maru [{tf}] trend filter block ({_s3_why})")
                    log_event("TREND_FILTER_BLOCK", f"block S3 Maru {direction} ({_s3_why})", tf=tf, sid=3, signal=direction)
                elif not s3_confirm_ref:
                    print(f"⏳ [{now}] ท่า3 BUY Maru [{tf}] ยังไม่เจอ S1/S2/S3 ฝั่งเดียวกันใน {lookback_bars} แท่งย้อนหลัง")
                    _log_confirm_lookback_block(tf, 3, direction, lookback_bars, "ท่าที่ 3 DM SP 🟢 BUY — Marubozu")
                elif _s3_adj:
                    print(f"⏭️ [{now}] ท่า3 BUY Maru [{tf}] ข้าม: แท่งติดกับ order ท่าเดียวกัน")
                elif last_traded_per_tf.get(tf) != candle_time:
                    order = open_order(direction, get_volume(), sl, tp, entry_price=entry, tf=tf, sid=3, pattern=f"ท่าที่ 3 DM SP 🟢 BUY [C1:{c1_type}]")
                    if order["success"]:
                        last_traded_per_tf[tf] = candle_time
                        config.last_traded_sid_tf.setdefault(tf, {})[3] = candle_time
                        position_tf[order["ticket"]] = tf
                        position_pattern[order["ticket"]] = "ท่าที่ 3 DM SP — Marubozu BUY"
                        tick = mt5.symbol_info_tick(SYMBOL)
                        cur_price = (tick.ask if direction == "BUY" else tick.bid) if tick else 0
                        risk = abs(entry - sl)
                        rr   = round(abs(tp - entry) / risk, 2) if risk > 0 else 0
                        await app.bot.send_message(
                            chat_id=MY_USER_ID,
                text=_order_msg(
                    sig_e, f"ท่าที่ 3 DM SP 🟢 BUY — Marubozu", tf, 3,
                    "", 0.0, 0.0,
                    f"แท่ง[0] {candle0_lbl} เขียวตัน → แท่งยืนยัน {confirm_lbl} จบเขียว ✅",
                    cur_price, entry, sl, tp, rr, order["ticket"],
                    _trend_filter_setup_note(tf),
                    entry_label="Limit ที่"
                ),
                            parse_mode="Markdown"
                        )
                        print(f"✅ [{now}] ท่า3 BUY Maru [{tf}] ยืนยันเขียว Entry={entry}")
            else:
                # ❌ จบแดง → ยกเลิก
                await tg(app, (
                        f"❌ *ท่า3 BUY Marubozu ยกเลิก*\n"
                        f"{sig_e} [{tf}] [0] `{candle0_lbl}` → แท่งยืนยัน `{confirm_lbl}` จบแดง\n"
                        f"Entry:{entry} ไม่ตั้ง Limit"
                    ))
                print(f"❌ [{now}] ท่า3 BUY Maru [{tf}] ยกเลิก (แดง)")
            to_remove.append(key)
        else:  # SELL
            if not bull_next:
                # ✅ จบแดง → ตั้ง Limit
                _s3_ok, _s3_why = trend_allows_signal(tf, direction)
                _s3_adj = _adjacent_sid_blocked(tf, 3, candle_time, TF_SECONDS_MAP.get(tf, 0)) and has_previous_bar_trade(tf, candle_time)
                if config.TREND_FILTER_SCAN_BLOCK and not _s3_ok:
                    print(f"🧭 [{now}] ท่า3 SELL Maru [{tf}] trend filter block ({_s3_why})")
                    log_event("TREND_FILTER_BLOCK", f"block S3 Maru {direction} ({_s3_why})", tf=tf, sid=3, signal=direction)
                elif not s3_confirm_ref:
                    print(f"⏳ [{now}] ท่า3 SELL Maru [{tf}] ยังไม่เจอ S1/S2/S3 ฝั่งเดียวกันใน {lookback_bars} แท่งย้อนหลัง")
                    _log_confirm_lookback_block(tf, 3, direction, lookback_bars, "ท่าที่ 3 DM SP 🔴 SELL — Marubozu")
                elif _s3_adj:
                    print(f"⏭️ [{now}] ท่า3 SELL Maru [{tf}] ข้าม: แท่งติดกับ order ท่าเดียวกัน")
                elif last_traded_per_tf.get(tf) != candle_time:
                    order = open_order(direction, get_volume(), sl, tp, entry_price=entry, tf=tf, sid=3, pattern=f"ท่าที่ 3 DM SP 🔴 SELL [C1:{c1_type}]")
                    if order["success"]:
                        last_traded_per_tf[tf] = candle_time
                        config.last_traded_sid_tf.setdefault(tf, {})[3] = candle_time
                        position_tf[order["ticket"]] = tf
                        position_pattern[order["ticket"]] = "ท่าที่ 3 DM SP — Marubozu SELL"
                        tick = mt5.symbol_info_tick(SYMBOL)
                        cur_price = (tick.ask if direction == "BUY" else tick.bid) if tick else 0
                        risk = abs(entry - sl)
                        rr   = round(abs(tp - entry) / risk, 2) if risk > 0 else 0
                        await app.bot.send_message(
                            chat_id=MY_USER_ID,
                text=_order_msg(
                    sig_e, f"ท่าที่ 3 DM SP 🔴 SELL — Marubozu", tf, 3,
                    "", 0.0, 0.0,
                    f"แท่ง[0] {candle0_lbl} แดงตัน → แท่งยืนยัน {confirm_lbl} จบแดง ✅",
                    cur_price, entry, sl, tp, rr, order["ticket"],
                    _trend_filter_setup_note(tf),
                    entry_label="Limit ที่"
                ),
                            parse_mode="Markdown"
                        )
                        print(f"✅ [{now}] ท่า3 SELL Maru [{tf}] ยืนยันแดง Entry={entry}")
            else:
                # ❌ จบเขียว → ยกเลิก
                await tg(app, (
                        f"❌ *ท่า3 SELL Marubozu ยกเลิก*\n"
                        f"{sig_e} [{tf}] [0] `{candle0_lbl}` → แท่งยืนยัน `{confirm_lbl}` จบเขียว\n"
                        f"Entry:{entry} ไม่ตั้ง Limit"
                    ))
                print(f"❌ [{now}] ท่า3 SELL Maru [{tf}] ยกเลิก (เขียว)")
            to_remove.append(key)
    for k in to_remove:
        s3_maru_pending.pop(k, None)
def _order_msg(sig_e, pattern, tf_name, sid, candle_rows, swing_h, swing_l,
               reason_txt, current_price, entry, sl, tp, rr, ticket=None, extra_note="",
               swing_h_text="", swing_l_text="", entry_label="Limit ที่", flow_id=""):
    """สร้าง Telegram message format มาตรฐานสำหรับทุกท่า"""
    price_diff = round(abs(current_price - entry), 2)
    ticket_line = f"\n🔖 Ticket: `{ticket}`" if ticket else ""
    flow_line = f"\nFlow: `{_short_flow_id(flow_id)}`" if flow_id else ""
    note_line = f"\n{extra_note}" if extra_note else ""
    swing_h_suffix = f" {swing_h_text}" if swing_h_text else ""
    swing_l_suffix = f" {swing_l_text}" if swing_l_text else ""
    return (
        f"{sig_e} *{pattern}*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now_bkk().strftime('%d/%m/%Y %H:%M')}\n"
        f"📊 *Timeframe: {tf_name}* | ท่าที่ {sid}\n\n"
        f"{candle_rows}\n"
        f"📈 Swing High:`{swing_h:.2f}`{swing_h_suffix} | Low:`{swing_l:.2f}`{swing_l_suffix}\n\n"
        f"💬 *เหตุผล:*\n{reason_txt}\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💰 ราคาปัจจุบัน: `{current_price:.2f}`\n"
        f"📌 *{entry_label}:* `{entry}` (ห่าง {price_diff})\n"
        f"🛑 SL: `{sl}` | 🎯 TP: `{tp}`\n"
        f"⚖️ R:R `1:{rr}` | 📦 `{AUTO_VOLUME}` lot"
        f"{ticket_line}{flow_line}{note_line}"
    )
def _fvg_find_parallel_intersection(new_tf: str, signal: str, gap_bot: float, gap_top: float):
    """
    หา intersection ของ gap ระหว่าง new_tf กับ TF อื่นในกลุ่มเดียวกัน
    คืน (int_bot, int_top, tfs_list, tickets_to_cancel, patterns_list)
    ถ้าไม่มี overlap คืน (None, None, [new_tf], [], [])
    """
    TF_MIN = {"M1":1,"M5":5,"M15":15,"M30":30,"H1":60,"H4":240,"H12":720,"D1":1440}
    def tf_min(tf): return TF_MIN.get(tf, 9999)

    # หา group ที่ครบ และต้องมี TF อื่นนอกจาก new_tf ด้วย
    my_groups = []
    for group in config.FVG_PARALLEL_GROUPS:
        if new_tf in group and all(tf in TF_ACTIVE for tf in group):
            # group ต้องมี TF อื่นที่ไม่ใช่ new_tf
            if any(tf != new_tf for tf in group):
                my_groups.append(group)
    if not my_groups:
        return None, None, [new_tf], [], []
    orders = mt5.orders_get(symbol=SYMBOL)
    if not orders:
        return None, None, [new_tf], [], []
    target_type = mt5.ORDER_TYPE_BUY_LIMIT if signal == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT

    # รวม gap ของทุก TF ที่ overlap
    all_gaps = [{"tf": new_tf, "bot": gap_bot, "top": gap_top, "ticket": None, "pattern": ""}]
    for order in orders:
        if order.type != target_type:
            continue
        info = pending_order_tf.get(order.ticket)
        if not info or not isinstance(info, dict):
            continue
        ex_tf  = info.get("tf")
        ex_bot = info.get("gap_bot", order.price_open)   # raw gap ของ TF นั้น
        ex_top = info.get("gap_top", order.price_open)

        # ตรวจว่าอยู่ใน group เดียวกัน และไม่ใช่ TF เดียวกัน
        if ex_tf == new_tf:
            continue
        in_group = any(ex_tf in g and new_tf in g for g in my_groups)
        if not in_group:
            continue

        # ตรวจ overlap กับ new_tf gap
        overlap = not (gap_top < ex_bot or gap_bot > ex_top)
        if not overlap:
            continue

        all_gaps.append({
            "tf": ex_tf,
            "bot": ex_bot,
            "top": ex_top,
            "ticket": order.ticket,
            "pattern": info.get("pattern", ""),
        })
    if len(all_gaps) == 1:
        # ไม่มี TF อื่น overlap → ตั้ง order ปกติ
        return None, None, [new_tf], [], []

    # คำนวณ intersection ของทุก gap
    int_bot = max(g["bot"] for g in all_gaps)
    int_top = min(g["top"] for g in all_gaps)
    if int_bot >= int_top:
        return None, None, [new_tf], [], []

    # intersection gap ต้องมีขนาด ≥ 0.5pt (เหมือน FVG ปกติ)
    if int_top - int_bot < 0.5:
        return None, None, [new_tf], [], []

    # เรียง TF จากเล็กไปใหญ่ และ dedup (กัน M15+M15)
    all_gaps.sort(key=lambda g: tf_min(g["tf"]))
    seen_tfs = set()
    deduped  = []
    for g in all_gaps:
        if g["tf"] not in seen_tfs:
            seen_tfs.add(g["tf"])
            deduped.append(g)
        elif g["ticket"]:
            # TF ซ้ำ → cancel order นั้นด้วย
            r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": g["ticket"]})
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                pending_order_tf.pop(g["ticket"], None)
                print(f"[{now_bkk().strftime('%H:%M:%S')}] 🔄 Parallel dedup: ลบ order {g['ticket']} TF={g['tf']} ซ้ำ")
    all_gaps = deduped
    tfs_list = [g["tf"] for g in all_gaps]
    tickets_to_cancel = [g["ticket"] for g in all_gaps if g["ticket"] is not None]
    patterns_list = [g.get("pattern", "") for g in all_gaps]
    return round(int_bot, 2), round(int_top, 2), tfs_list, tickets_to_cancel, patterns_list
async def auto_scan(app):
    """สแกนทุก Timeframe ที่เปิดอยู่พร้อมกัน"""
    global auto_active, _first_scan_done, _last_scan_summary_telegram, _last_scan_summary_cmd, _last_scan_summary_log_time
    if not auto_active:
        return
    if not connect_mt5():
        await tg(app, "\u26a0\ufe0f MT5 \u0e44\u0e21\u0e48\u0e44\u0e14\u0e49\u0e40\u0e0a\u0e37\u0e48\u0e2d\u0e21\u0e15\u0e48\u0e2d")
        return
    await check_sl_tp_hits(app)
    await check_cancel_pending_orders(app)
    await check_engulf_trail_sl(app)
    # await check_breakeven_tp(app)  # ปิดชั่วคราว
    await check_opposite_order_tp(app)
    await check_entry_candle_quality(app)
    await check_s3_maru_pending(app)
    await check_fvg_pending(app)
    await check_pb_pending(app)
    await check_s12_management(app)
    positions  = mt5.positions_get(symbol=SYMBOL)
    open_count = len(positions) if positions else 0
    if open_count >= MAX_ORDERS:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] \u26a0\ufe0f Order \u0e40\u0e15\u0e47\u0e21 {open_count}/{MAX_ORDERS}")
        return
    active_tfs = [tf for tf, on in TF_ACTIVE.items() if on]
    if not active_tfs:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] \u26a0\ufe0f \u0e44\u0e21\u0e48\u0e21\u0e35 Timeframe \u0e17\u0e35\u0e48\u0e40\u0e1b\u0e34\u0e14\u0e2d\u0e22\u0e39\u0e48")
        return
    now = now_bkk().strftime("%H:%M:%S")
    is_first = not _first_scan_done
    if is_first:
        _first_scan_done = True
        strat_names = [STRATEGY_NAMES[k] for k, v in active_strategies.items() if v]
        print(f"\U0001f680 [{now}] Auto Scan \u0e40\u0e23\u0e34\u0e48\u0e21! {'  '.join(tf_label(tf) for tf in active_tfs)}{RESET}")
        print(f"   Strategy: {strat_names}")
        print(f"   Scan Interval: {config.SCAN_INTERVAL} \u0e19\u0e32\u0e17\u0e35")
        await app.bot.send_message(
            chat_id=MY_USER_ID,
            text=(
                "\U0001f680 *Auto Scan \u0e40\u0e23\u0e34\u0e48\u0e21\u0e15\u0e49\u0e19!*\n"
                "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
                f"\U0001f4cb Strategy: *{chr(44).join(strat_names) or chr(0xe44)+chr(0xe21)+chr(0xe48)+chr(0xe21)+chr(0xe35)}*\n"
                f"\u23f0 Interval: *{config.SCAN_INTERVAL} \u0e19\u0e32\u0e17\u0e35*\n"
                f"\U0001f550 Timeframes: *{chr(44).join(active_tfs)}*"
            ),
            parse_mode="Markdown"
        )
        log_tfs = active_tfs
    else:
        log_tfs = [tf for tf in active_tfs if should_log_tf(tf, config.SCAN_INTERVAL)]

    # เคลียร์ log เดิม แล้ว scan ทุก TF พร้อมกัน
    _scan_results.clear()
    _swing_data.clear()
    await asyncio.gather(*[scan_one_tf(app, tf) for tf in active_tfs])

    # export trend state สำหรับ MQL5 indicator (TrendFilterLines.mq5)
    _export_trend_state_for_mt5()

    # print log รวมเป็น block เดียว
    if _scan_results:
        show_tfs = [tf for tf in active_tfs
                    if tf in _scan_results and (is_first or should_log_tf(tf, config.SCAN_INTERVAL))]
        if show_tfs:
            prefix  = f"\U0001f50d [{now}] "
            pad     = " " * _vlen(prefix)   # visual width เพื่อให้ตรงกับ emoji
            max_len = max(len(tf) for tf in show_tfs)
            blocks  = []
            for i, tf in enumerate(show_tfs):
                lead = prefix if i == 0 else pad
                d    = _scan_results[tf]
                blocks.append(_format_log_block(tf, d, lead, pad, max_len))
            tg_text, tg_key = _format_scan_summary_telegram_clean(show_tfs)
            # Swing summary block รวมทุก TF
            C_SW = "\033[38;5;228m"
            swing_lines = []
            for tf in _swing_data:
                sw = _swing_data[tf]
                c = TF_COLOR.get(tf, "")
                trend_lbl = (sw.get("trend") or {}).get("label", "❓ —")
                break_lbl = (sw.get("breakout") or {}).get("label", "")
                asof_lbl = fmt_mt5_bkk_ts(sw.get("asof_time"), "%H:%M %d-%b-%Y") if sw.get("asof_time") else "—"
                sh_confirm_lbl = fmt_mt5_bkk_ts(sw.get("sh_confirm_time"), "%H:%M %d-%b-%Y") if sw.get("sh_confirm_time") else "—"
                sl_confirm_lbl = fmt_mt5_bkk_ts(sw.get("sl_confirm_time"), "%H:%M %d-%b-%Y") if sw.get("sl_confirm_time") else "—"
                trend_line = f"  │ 🧭 {C_SW}Trend:{trend_lbl}{RESET}"
                if break_lbl:
                    trend_line += f"  {C_SW}{break_lbl}{RESET}"
                swing_lines.append(f"  ┌─ {c}{tf}{RESET}")
                swing_lines.append(trend_line)
                if sw.get("mode") == "pivot":
                    swing_lines.append(
                        f"  │ 🕒 {C_SW}AsOf:{asof_lbl} | H✓:{sh_confirm_lbl} | L✓:{sl_confirm_lbl}{RESET}"
                    )
                swing_lines.append(f"  │ 📈 {C_SW}H:{sw['sh']}{RESET}")
                swing_lines.append(f"  │ 📈 {C_SW}HH:{sw.get('hh', '—')}{RESET}")
                swing_lines.append(f"  │ 📈 {C_SW}Prev H:{sw.get('prev_sh', '—')}{RESET}")
                swing_lines.append(f"  │ 📉 {C_SW}L:{sw['sl']}{RESET}")
                swing_lines.append(f"  │ 📉 {C_SW}LL:{sw.get('ll', '—')}{RESET}")
                swing_lines.append(f"  │ 📉 {C_SW}Prev L:{sw.get('prev_sl', '—')}{RESET}")
                swing_lines.append("  └────────────────")
            if swing_lines:
                blocks.append("\n".join(swing_lines))
            _now_t = _time.time()
            _force_log = (_now_t - _last_scan_summary_log_time) >= SCAN_SUMMARY_FORCE_INTERVAL
            if tg_key and (tg_key != _last_scan_summary_cmd or _force_log):
                print("\n".join(blocks))
                log_block("SCAN_SUMMARY", tg_text)
                _last_scan_summary_cmd = tg_key
                _last_scan_summary_log_time = _now_t
            if tg_key and (tg_key != _last_scan_summary_telegram or _force_log):
                await tg(app, tg_text, parse_mode=None)
                _last_scan_summary_telegram = tg_key
                print(f"[{now_bkk().strftime('%H:%M:%S')}] SCAN_SUMMARY_TG queued")
    await scan_s12(app)


async def scan_s12(app):
    """S12 Range Trading — เปิด order เมื่อราคาเข้า zone (M5 only, standalone)"""
    global _s12_scan_status
    from strategy12 import _s12_state, s12_get_zone_levels, s12_get_tp, s12_cleanup_tickets
    from bot_log import log_event

    if not active_strategies.get(12, False):
        _s12_scan_status = {}
        return

    s12_cleanup_tickets()

    # Fix 1: Cooldown หลัง SL hit
    cooldown = config.S12_COOLDOWN_SECONDS
    if cooldown > 0 and _s12_state.get("last_sl_time", 0) > 0:
        elapsed = _time.time() - _s12_state["last_sl_time"]
        if elapsed < cooldown:
            remaining_min = int((cooldown - elapsed) / 60) + 1
            _s12_scan_status = {"cooldown": f"⏳ S12 cooldown {remaining_min} นาที (หลัง SL)"}
            return

    rates_m5  = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5,  0, config.S12_LOOKBACK + 5)
    rates_m15 = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M15, 0, 60)
    tick      = mt5.symbol_info_tick(SYMBOL)
    sym       = mt5.symbol_info(SYMBOL)

    if rates_m5 is None or len(rates_m5) < 10 or tick is None or sym is None:
        return

    pt        = sym.point or 0.01
    scale     = config.points_scale()
    zone_dist = config.S12_ZONE_POINTS * pt * scale
    sl_dist   = config.S12_SL_POINTS   * pt * scale

    levels = s12_get_zone_levels(rates_m5, config.S12_LOOKBACK, zone_dist)
    if not levels:
        return
    swing_high = levels["swing_high"]
    swing_low = levels["swing_low"]

    bid = float(tick.bid)
    ask = float(tick.ask)

    side       = _s12_state["side"]
    count      = _s12_state["order_count"]
    last_price = _s12_state["last_entry_price"]

    # Fix 3: Zone validity — ราคาต้องอยู่ภายใน range ไม่ทะลุ swing
    in_buy_zone  = swing_low  <= ask <= swing_low  + zone_dist
    in_sell_zone = swing_high - zone_dist <= bid <= swing_high

    buy_zone_bot = levels["buy_zone_bot"]
    buy_zone_top = levels["buy_zone_top"]
    sell_zone_bot = levels["sell_zone_bot"]
    sell_zone_top = levels["sell_zone_top"]
    zone_label = "BUY zone" if in_buy_zone else ("SELL zone" if in_sell_zone else "Neutral")
    _s12_scan_status = {
        "swing_high":   swing_high,
        "swing_low":    swing_low,
        "buy_zone_top": buy_zone_top,
        "sell_zone_bot":sell_zone_bot,
        "bid":          bid,
        "ask":          ask,
        "zone":         zone_label,
        "side":         side,
        "count":        count,
    }

    should_buy = (
        in_buy_zone
        and (side is None or side == "BUY")
        and count < config.S12_ORDER_COUNT
        and (last_price is None or ask < last_price)
    )
    should_sell = (
        in_sell_zone
        and (side is None or side == "SELL")
        and count < config.S12_ORDER_COUNT
        and (last_price is None or bid > last_price)
    )

    if not should_buy and not should_sell:
        return

    direction = "BUY" if should_buy else "SELL"

    # Momentum filter — ถ้า M5 ล่าสุด N แท่งทิศเดียวกันทั้งหมด ไม่เปิด order ทวนทิศ
    mb = config.S12_MOMENTUM_BARS
    if mb > 0 and len(rates_m5) >= mb + 1:
        recent = rates_m5[-(mb + 1):-1]  # N แท่งที่ปิดแล้ว
        all_bull = all(float(r["close"]) > float(r["open"]) for r in recent)
        all_bear = all(float(r["close"]) < float(r["open"]) for r in recent)
        if direction == "SELL" and all_bull:
            _s12_scan_status.update({"momentum_block": f"⛔ Momentum block SELL ({mb} bull bars)"})
            return
        if direction == "BUY" and all_bear:
            _s12_scan_status.update({"momentum_block": f"⛔ Momentum block BUY ({mb} bear bars)"})
            return

    entry     = ask if should_buy else bid
    sl        = round(entry - sl_dist, 2) if should_buy else round(entry + sl_dist, 2)
    tp_raw = s12_get_tp(rates_m15, direction)
    tp_valid = (
        tp_raw is not None and (
            (should_buy and float(tp_raw) > entry) or
            (should_sell and float(tp_raw) < entry)
        )
    )
    if tp_valid:
        tp = round(float(tp_raw), 2)
    else:
        tp = round(entry + sl_dist, 2) if should_buy else round(entry - sl_dist, 2)

    req = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       SYMBOL,
        "volume":       config.S12_LOT_SIZE,
        "type":         mt5.ORDER_TYPE_BUY if should_buy else mt5.ORDER_TYPE_SELL,
        "price":        entry,
        "sl":           sl,
        "tp":           tp,
        "deviation":    20,
        "magic":        0,
        "comment":      f"M5_S12_{'BUY' if should_buy else 'SELL'}",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": _get_filling_mode(),
    }
    r = mt5.order_send(req)
    now = now_bkk().strftime("%H:%M:%S")
    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
        retcode = r.retcode if r else "None"
        print(f"❌ [{now}] S12 {direction} FAIL retcode={retcode}")
        return

    ticket = r.order
    _s12_state["side"]             = direction
    _s12_state["order_count"]      = count + 1
    _s12_state["last_entry_price"] = entry
    _s12_state["tickets"].append(ticket)

    new_count = count + 1
    sig_e = "🟢" if should_buy else "🔴"
    print(f"{sig_e} [{now}] S12 {direction} #{new_count} entry={entry:.2f} sl={sl:.2f} tp={tp:.2f} ticket={ticket}")
    log_event("ORDER_CREATED", f"ท่าที่ 12 Range Trading {sig_e} {direction} #{new_count}",
              tf="M5", sid=12, signal=direction,
              entry=entry, sl=sl, tp=tp, ticket=ticket, order_type=direction)
    await tg(app, (
        f"{sig_e} *S12 Range Trading #{new_count}*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"[M5] {direction} Ticket:`{ticket}`\n"
        f"Entry:`{entry:.2f}` | SL:`{sl:.2f}` | TP:`{tp:.2f}`\n"
        f"Range: `{swing_low:.2f}` – `{swing_high:.2f}`\n"
        f"Zone: {'bottom' if should_buy else 'top'} ±{config.S12_ZONE_POINTS}pt"
    ))


async def scan_one_tf(app, tf_name: str) -> bool:
    """สแกน 1 Timeframe — return True ถ้าเปิด Order สำเร็จ"""
    tf_val = TF_OPTIONS[tf_name]
    now    = now_bkk().strftime("%H:%M")
    lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)

    # จำนวนวินาทีต่อแท่งของแต่ละ TF
    TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400}
    tf_secs = TF_SECONDS.get(tf_name, 60)

    # ดึงแท่งปัจจุบัน (index=0) ก่อน เพื่อตรวจสอบว่าแท่งก่อนหน้าปิดสมบูรณ์แล้ว
    current_bar = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 1)
    if current_bar is None or len(current_bar) == 0:
        return False
    current_bar_time = int(current_bar[0]["time"])

    # ดึงแท่งที่ปิดแล้ว (start=1 ข้ามแท่งปัจจุบัน)
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 6)
    if rates is None or len(rates) < lookback + 4:
        return False
    last_candle_time = int(rates[-1]["time"])

    # ── Log Swing High / Low ของ TF นี้ (ทำก่อน guard เพื่อแสดงทุก TF เสมอ) ──
    _swing_finders = _get_summary_swing_finders(lookback)
    _find_sh = _swing_finders["high"]
    _find_sl = _swing_finders["low"]
    _find_higher_h = _swing_finders["hh"]
    _find_lower_l = _swing_finders["ll"]

    if _swing_finders["mode"] == "pivot":
        pivot_left = max(1, int(getattr(config, "SWING_PIVOT_LEFT", 15) or 15))
        pivot_right = max(1, int(getattr(config, "SWING_PIVOT_RIGHT", 10) or 10))
        _pivot_levels = _resolve_summary_pivot_levels(
            rates, lookback=lookback, left=pivot_left, right=pivot_right
        )
        _sh_info = _pivot_levels["sh"]
        _sl_info = _pivot_levels["sl"]
        _prev_sh_info = _pivot_levels["prev_sh"]
        _prev_sl_info = _pivot_levels["prev_sl"]
        _prev_prev_sh_info = _pivot_levels["prev_prev_sh"]
        _prev_prev_sl_info = _pivot_levels["prev_prev_sl"]
        _hh_info = _pivot_levels["hh"]
        _ll_info = _pivot_levels["ll"]
    else:
        _sh_info = _find_sh(rates)
        _sl_info = _find_sl(rates)
        _prev_sh_info = _find_previous_swing_info(rates, _sh_info, _find_sh)
        _prev_sl_info = _find_previous_swing_info(rates, _sl_info, _find_sl)
        _prev_prev_sh_info = _find_previous_swing_info(rates, _prev_sh_info, _find_sh)
        _prev_prev_sl_info = _find_previous_swing_info(rates, _prev_sl_info, _find_sl)
        _hh_info = _find_higher_h(rates, _sh_info)
        _ll_info = _find_lower_l(rates, _sl_info)
    _trend_info = _compute_trend_info(
        _sh_info, _prev_sh_info, _prev_prev_sh_info,
        _sl_info, _prev_sl_info, _prev_prev_sl_info,
    )
    _breakout_info = _compute_breakout_info(
        rates, _sh_info, _sl_info, _prev_sh_info, _prev_sl_info,
    )
    def _swing_fmt(info, label):
        if not info:
            return "?"
        return f"{info['price']:.2f} [{info['bar_from_2']+3}] {fmt_mt5_bkk_ts(info['time'], '%H:%M %d-%b-%Y')}"
    def _confirm_ts(info):
        if not info or _swing_finders["mode"] != "pivot":
            return None
        return int(info["time"]) + (tf_secs * pivot_right)
    _swing_data[tf_name] = {
        "sh": _swing_fmt(_sh_info, "H"),
        "sl": _swing_fmt(_sl_info, "L"),
        "prev_sh": _swing_fmt(_prev_sh_info, "H"),
        "prev_sl": _swing_fmt(_prev_sl_info, "L"),
        "hh": _swing_fmt(_hh_info, "HH"),
        "ll": _swing_fmt(_ll_info, "LL"),
        "mode": _swing_finders["mode"],
        "trend": _trend_info,
        "breakout": _breakout_info,
        "sh_price": float(_sh_info["price"]) if _sh_info else None,
        "sl_price": float(_sl_info["price"]) if _sl_info else None,
        "sh_time": int(_sh_info["time"]) if _sh_info else None,
        "sl_time": int(_sl_info["time"]) if _sl_info else None,
        "prev_sh_price": float(_prev_sh_info["price"]) if _prev_sh_info else None,
        "prev_sh_time": int(_prev_sh_info["time"]) if _prev_sh_info else None,
        "prev_sl_price": float(_prev_sl_info["price"]) if _prev_sl_info else None,
        "prev_sl_time": int(_prev_sl_info["time"]) if _prev_sl_info else None,
        "sh_confirm_time": _confirm_ts(_sh_info),
        "sl_confirm_time": _confirm_ts(_sl_info),
        "asof_time": last_candle_time,
    }
    # Guard: แท่งล่าสุดจะถือว่าปิดสมบูรณ์ ก็ต่อเมื่อแท่งใหม่เริ่มแล้ว
    # ดังนั้นใช้ current_bar_time > last_candle_time ก็พอ
    # ตัวอย่าง M5: last=14:44 และ current=14:45 แปลว่าแท่ง 14:44 ปิดแล้ว
    if current_bar_time <= last_candle_time:
        _scan_results[tf_name] = _parse_pattern("", "WAIT", "แท่ง[0] ยังวิ่งอยู่")
        _print_skip_once(tf_name, f"⏳ [{now}] {tf_label(tf_name)}: แท่ง[0] ยังวิ่งอยู่ (current={current_bar_time} == last={last_candle_time})")
        return False

    # กัน Order ซ้ำในแท่งเดิมของ TF นี้
    if last_traded_per_tf.get(tf_name) == last_candle_time:
        _scan_results[tf_name] = _parse_pattern("", "WAIT", "เทรดแท่งนี้ไปแล้ว")
        _print_skip_once(tf_name, f"⏭️ [{now}] {tf_label(tf_name)}: เทรดแท่งนี้ไปแล้ว")
        return False

    # กัน Order แท่งติดกัน — ย้ายไปเช็กแยกตาม sid ที่จุด order แทน
    # (ท่าต่างกันสามารถ trade แท่งติดกันได้)

    # ── รัน 3 Strategy พร้อมกันอิสระ ────────────────────────────
    r1 = strategy_1(rates) if active_strategies.get(1, False) else {"signal": "WAIT", "reason": "S1 ปิด"}
    r2 = strategy_2(rates) if active_strategies.get(2, False) else {"signal": "WAIT", "reason": "S2 ปิด"}
    r3 = strategy_3(rates) if active_strategies.get(3, False) else {"signal": "WAIT", "reason": "S3 ปิด"}
    r4 = strategy_4(rates) if active_strategies.get(4, False) else {"signal": "WAIT", "reason": "S4 ปิด"}
    r5 = strategy_5(rates) if active_strategies.get(5, False) else {"signal": "WAIT", "reason": "S5 ปิด"}
    r8 = strategy_8(rates) if active_strategies.get(8, False) else {"signal": "WAIT", "reason": "S8 ปิด", "orders": []}
    r9 = strategy_9(rates) if active_strategies.get(9, False) else {"signal": "WAIT", "reason": "S9 ปิด"}
    if r9.get("signal") in ("BUY", "SELL"):
        _log_divergence_once(tf_name, 9, r9["signal"], last_candle_time, r9)
    # S10 CRT TBS — branch ตาม CRT_ENTRY_MODE
    if active_strategies.get(10, False):
        crt_entry_mode = getattr(config, "CRT_ENTRY_MODE", "htf")
        if crt_entry_mode == "mtf":
            # MTF mode: HTF detect → arm; LTF (M1/M5/M15) เช็ก color shift trigger
            r10 = strategy_10(rates, tf_name)

            # ── Pre-arm: ถ้ายังไม่มี armed state ให้ลองหา HTF sweep in-progress ──
            # เช่น M30 parent ปิด 19:30 → M30 sweep bar เปิด 19:30 กำลัง sweep อยู่
            # Phase 1 + Model อาจเจอบน M1 ได้ตั้งแต่ 19:35 โดยไม่ต้องรอ M30 ปิด 20:00
            # S10_SWEEP_RECHECK ใน trailing.py จะ validate sweep เมื่อ HTF bar ปิด
            if r10.get("signal") == "WAIT":
                from strategy10 import try_pre_arm_htf, _LTF_TO_HTFS
                _s10_htf_list = _LTF_TO_HTFS.get(tf_name, [])
                for _s10_htf in _s10_htf_list:
                    _s10_htf_val = TF_OPTIONS.get(_s10_htf)
                    if _s10_htf_val is None:
                        continue
                    # copy_rates_from_pos pos=0 รวม current open bar ด้วย
                    _s10_htf_rates = mt5.copy_rates_from_pos(
                        SYMBOL, _s10_htf_val, 0, 15
                    )
                    if _s10_htf_rates is None or len(_s10_htf_rates) < 2:
                        continue
                    if try_pre_arm_htf(_s10_htf, _s10_htf_rates):
                        # armed แล้ว → re-run LTF เพื่อหา Phase 1 + Model
                        r10 = strategy_10(rates, tf_name)
                        if r10.get("signal") in ("BUY", "SELL"):
                            break  # เจอ signal แล้ว หยุดเช็ก HTF อื่น

        elif tf_name in ("M15", "M30", "H1", "H4", "H12", "D1"):
            # HTF mode: detect + entry บน HTF เท่านั้น
            r10 = strategy_10(rates, tf_name)
        else:
            r10 = {"signal": "WAIT", "reason": f"S10 HTF mode รันเฉพาะ M15+ (TF นี้: {tf_name})"}
    else:
        r10 = {"signal": "WAIT", "reason": "S10 ปิด"}

    # S11 Fibo S1 — hook กับ S1 result เพื่อตี Fibo grid
    if active_strategies.get(11, False) and r1.get("signal") in ("BUY", "SELL"):
        s11_record_s1_pattern(
            tf_name,
            r1.get("signal"),
            r1.get("candles") or [],
            int(rates[-1]["time"]) if len(rates) else 0,
            r1.get("pattern", ""),
        )
    if active_strategies.get(11, False):
        r11 = strategy_11(rates, tf_name)
    else:
        r11 = {"signal": "WAIT", "reason": "S11 ปิด"}
    r13 = strategy_13(rates) if active_strategies.get(13, False) else {"signal": "WAIT", "reason": "S13 ปิด"}

    # ── S2 FVG — ตั้ง Limit ทันที ────────────────────────────────
    if r2.get("signal") == "FVG_DETECTED":
        fvg     = r2["fvg"]
        fvg_key = f"{tf_name}_{last_candle_time}"
        _s2_allowed, _s2_why = trend_allows_signal(tf_name, fvg["signal"])
        if config.TREND_FILTER_SCAN_BLOCK and not _s2_allowed:
            _print_skip_once(
                tf_name,
                f"🧭 [{now}] {tf_label(tf_name)} ท่า2 FVG: trend filter block {fvg['signal']} ({_s2_why})"
            )
            log_event(
                "TREND_FILTER_BLOCK",
                f"block FVG {fvg['signal']} ({_s2_why})",
                tf=tf_name, sid=2, signal=fvg["signal"],
            )
            return False
        # adjacent bar check per-sid
        _s2_adjacent = _adjacent_sid_blocked(tf_name, 2, last_candle_time, tf_secs)
        if fvg_key not in fvg_pending and last_traded_per_tf.get(tf_name) != last_candle_time and not _s2_adjacent:
            tp_swing = find_swing_tp(rates, fvg["signal"], fvg["entry"], fvg["sl"])
            tp = tp_swing if tp_swing else round(
                fvg["entry"] + abs(fvg["entry"] - fvg["sl"]) if fvg["signal"] == "BUY"
                else fvg["entry"] - abs(fvg["sl"] - fvg["entry"]), 2
            )
            tp_note = ("Swing High:" + str(tp)) if (tp_swing and fvg["signal"] == "BUY") else \
                      ("Swing Low:"  + str(tp)) if tp_swing else "RR1:1 (fallback)"
            sig_e = "🟢" if fvg["signal"] == "BUY" else "🔴"

            # ── Parallel mode: หา intersection gap ก่อนตั้ง order ──
            final_gap_bot = fvg["gap_bot"]
            final_gap_top = fvg["gap_top"]
            parallel_tfs  = [tf_name]   # TF ที่ gap ซ้อนกัน
            parallel_patterns = [fvg["pattern"]]

            if config.FVG_PARALLEL:
                int_bot, int_top, int_tfs, to_cancel_tickets, int_patterns = \
                    _fvg_find_parallel_intersection(
                        tf_name, fvg["signal"], fvg["gap_bot"], fvg["gap_top"]
                    )
                if int_bot is not None:
                    final_gap_bot = int_bot
                    final_gap_top = int_top
                    parallel_tfs  = int_tfs
                    parallel_patterns = list(int_patterns or [])
                    for idx, ptf in enumerate(parallel_tfs):
                        if ptf == tf_name and (idx >= len(parallel_patterns) or not parallel_patterns[idx]):
                            while len(parallel_patterns) <= idx:
                                parallel_patterns.append("")
                            parallel_patterns[idx] = fvg["pattern"]
                    # ลบ order ของ TF ที่ซ้อนออก (จะตั้ง order ใหม่แทน)
                    for t in to_cancel_tickets:
                        # หา tf ของ order ก่อน pop
                        t_info = pending_order_tf.get(t)
                        t_tf   = t_info.get("tf") if isinstance(t_info, dict) else t_info
                        mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": t})
                        pending_order_tf.pop(t, None)
                        if t_tf:
                            last_traded_per_tf.pop(t_tf, None)

            # ทั้งปกติและ parallel ปิดหมด → ไม่ order
            if not config.FVG_NORMAL and not config.FVG_PARALLEL:
                return False

            # parallel เปิดอยู่แต่เจอ TF เดียว → ข้ามถ้าไม่ได้เปิด normal ด้วย
            if len(parallel_tfs) < 2 and config.FVG_PARALLEL and not config.FVG_NORMAL:
                scan_results.append({"tf": tf_name, "sid": 2, "signal": "WAIT",
                    "reason": f"FVG {fvg['signal']} [{tf_name}] รอ TF อื่นซ้อนทับ (parallel)"})
                fvg_pending[fvg_key] = True
                return False

            s2_confirm_ref = None
            if len(parallel_tfs) == 1:
                s2_confirm_ref = _find_recent_signal_confirmation(
                    rates,
                    fvg["signal"],
                    tf_secs,
                    getattr(config, "S2_NORMAL_CONFIRM_LOOKBACK_BARS", 8),
                )
                if not s2_confirm_ref:
                    lookback_bars = max(0, int(getattr(config, "S2_NORMAL_CONFIRM_LOOKBACK_BARS", 5) or 0))
                    wait_reason = (
                        f"FVG {fvg['signal']} [{tf_name}] ยังไม่เจอ S1/S2/S3 ฝั่งเดียวกัน "
                        f"ใน {lookback_bars} แท่งย้อนหลัง"
                    )
                    _log_confirm_lookback_block(tf_name, 2, fvg["signal"], lookback_bars, fvg["pattern"])
                    scan_results.append({"tf": tf_name, "sid": 2, "signal": "WAIT", "reason": wait_reason})
                    fvg_pending[fvg_key] = True
                    _print_skip_once(
                        tf_name,
                        f"⏳ [{now}] {tf_label(tf_name)} ท่า2 FVG: {wait_reason}"
                    )
                    return False

            # คำนวณ entry จาก final gap
            gap_size   = final_gap_top - final_gap_bot
            if fvg["signal"] == "BUY":
                final_entry = round(final_gap_bot + gap_size * 0.98, 2)
            else:
                final_entry = round(final_gap_top - gap_size * 0.98, 2)
            tf_label_str = "+".join(parallel_tfs) if len(parallel_tfs) > 1 else tf_name
            fvg_tp = get_existing_tp(fvg["signal"], final_entry, tf_name, requester_sid=2) or tp
            order  = open_order(
                fvg["signal"], get_volume(), fvg["sl"], fvg_tp,
                entry_price=final_entry, tf=tf_name, sid=2, pattern=fvg["pattern"],
                parallel_tfs=parallel_tfs, parallel_patterns=parallel_patterns,
            )
            if order["success"]:
                # mark ทุก TF ใน parallel group เพื่อกัน re-detect
                for ptf in parallel_tfs:
                    last_traded_per_tf[ptf] = last_candle_time
                    config.last_traded_sid_tf.setdefault(ptf, {})[2] = last_candle_time
                last_traded_per_tf[tf_name] = last_candle_time
                config.last_traded_sid_tf.setdefault(tf_name, {})[2] = last_candle_time
                ot_name = order.get("order_type", "LIMIT")
                if order.get("ticket"):
                    # Parallel: ใช้ TF เล็กสุดใน group สำหรับ entry candle check
                    TF_MIN_MAP = {"M1":1,"M5":5,"M15":15,"M30":30,"H1":60,"H4":240,"H12":720,"D1":1440}
                    check_tf = min(parallel_tfs, key=lambda t: TF_MIN_MAP.get(t, 9999))
                    fvg_order_tickets[order["ticket"]] = {
                        "tf": check_tf, "signal": fvg["signal"], "checked": False,
                    }
                    _pend_info = {
                        "tf":              tf_name,
                        "gap_bot":         fvg["gap_bot"],   # raw gap ของ TF นี้ (ไม่ใช่ intersection)
                        "gap_top":         fvg["gap_top"],   # ใช้สำหรับ intersection ครั้งต่อไป
                        "final_gap_bot":   final_gap_bot,    # intersection ที่ใช้ตั้ง order
                        "final_gap_top":   final_gap_top,
                        "detect_bar_time": last_candle_time,
                        "signal":          fvg["signal"],
                        "sid":             2,
                        "pattern":         fvg["pattern"],
                        "c3_type":         fvg.get("c3_type", ""),
                    }
                    _trend_keys = _trend_filter_state_keys(tf_name)
                    if _trend_keys:
                        _pend_info["trend_filter"] = ",".join(_trend_keys)
                    # Pattern "ปฏิเสธราคา" → ยกเลิก limit ถ้าไม่ fill ภายใน 1 แท่ง
                    if fvg.get("c3_type") == "ปฏิเสธราคา":
                        _pend_info["cancel_bars"] = 1
                    pending_order_tf[order["ticket"]] = _pend_info
                    position_tf[order["ticket"]] = check_tf
                    position_sid[order["ticket"]] = 2
                    position_pattern[order["ticket"]] = f"ท่าที่ 2 FVG {fvg['signal']} [{tf_label_str}]"
                    if _trend_keys:
                        from trailing import position_trend_filter as _pos_trend
                        _pos_trend[order["ticket"]] = ",".join(_trend_keys)
                    log_event(
                        "ORDER_CREATED",
                        fvg["pattern"],
                        tf=tf_label_str,
                        sid=2,
                        signal=fvg["signal"],
                        entry=final_entry,
                        sl=fvg["sl"],
                        tp=tp,
                        ticket=order["ticket"],
                        order_type=ot_name,
                        trend_filter=",".join(_trend_keys) if _trend_keys else "",
                    )
                save_runtime_state()

                def _format_s2_tf_candles(tf_for_candles: str) -> str:
                    tf_val = TF_OPTIONS.get(tf_for_candles)
                    if tf_val is None:
                        return ""
                    tf_rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 4)
                    if tf_rates is None or len(tf_rates) < 4:
                        return ""
                    labels_local = ["[2]", "[1]", "[0]"]
                    rows = [f"📚 แท่ง {tf_for_candles}"]
                    for idx_local, bar_idx in enumerate((-3, -2, -1)):
                        bar = tf_rates[bar_idx]
                        o = float(bar["open"])
                        h = float(bar["high"])
                        l = float(bar["low"])
                        c = float(bar["close"])
                        clr = "🟢" if c > o else "🔴"
                        candle_ts = int(bar["time"])
                        rows.append(
                            f"{clr} แท่ง{labels_local[idx_local]}: O:`{o:.2f}` H:`{h:.2f}` "
                            f"L:`{l:.2f}` C:`{c:.2f}` {_fmt_swing_dt(candle_ts)}"
                        )
                    return "\n".join(rows)

                candle_blocks = []
                if len(parallel_tfs) > 1:
                    for ptf in parallel_tfs:
                        block = _format_s2_tf_candles(ptf)
                        if block:
                            candle_blocks.append(block)
                else:
                    block = _format_s2_tf_candles(tf_name)
                    if block:
                        candle_blocks.append(block)
                candle_txt = "\n\n".join(candle_blocks)

                tick          = mt5.symbol_info_tick(SYMBOL)
                current_price = (tick.ask if fvg["signal"] == "BUY" else tick.bid) if tick else 0
                price_diff    = round(abs(current_price - final_entry), 2)
                rr_val        = round(abs(tp - final_entry) / abs(final_entry - fvg["sl"]), 2) if abs(final_entry - fvg["sl"]) > 0 else 0
                tf_label_str  = "+".join(parallel_tfs) if len(parallel_tfs) > 1 else tf_name
                intersect_note = f" (Intersection {'+'.join(parallel_tfs)})" if len(parallel_tfs) > 1 else ""
                ms = get_structure(rates)
                gap_note = f"📐 Gap: `{final_gap_bot}` – `{final_gap_top}` ({round(final_gap_top-final_gap_bot,2)}pt)"
                confirm_note = ""
                if s2_confirm_ref:
                    confirm_sid = s2_confirm_ref["sid"]
                    confirm_scan_ts = s2_confirm_ref["detect_time"]
                    confirm_bar_ts = s2_confirm_ref["bar_time"]
                    confirm_note = (
                        f"\n🔗 Confirm: S{confirm_sid} {fvg['signal']} | "
                        f"scan {fmt_mt5_bkk_ts(confirm_scan_ts, '%H:%M')} | "
                        f"[0] {fmt_mt5_bkk_ts(confirm_bar_ts, '%H:%M')}"
                    )
                reason_txt = f"แท่ง[0]: {fvg.get('c3_type','')} | {fvg['zone_note']}\n{gap_note}{confirm_note}"
                swing_h_text = _fmt_swing_dt(_sh_info["time"]) if _sh_info else ""
                swing_l_text = _fmt_swing_dt(_sl_info["time"]) if _sl_info else ""
                trend_note = _trend_filter_setup_note(tf_name)
                extra_parts = []
                if intersect_note:
                    extra_parts.append(intersect_note.strip())
                if trend_note:
                    extra_parts.append(trend_note)
                await app.bot.send_message(
                    chat_id=MY_USER_ID,
                    text=_order_msg(
                        sig_e, fvg["pattern"], tf_label_str, 2,
                        candle_txt, ms["swing_high"], ms["swing_low"],
                        reason_txt, current_price, final_entry, fvg["sl"], tp, rr_val,
                        order["ticket"], "\n".join(extra_parts),
                        swing_h_text=swing_h_text,
                        swing_l_text=swing_l_text,
                    ),
                    parse_mode="Markdown"
                )
                print(f"✅ [{now}] FVG {fvg['signal']} [{tf_label_str}] Entry={final_entry}")

            elif order.get("skipped"):
                log_event(
                    "ORDER_SKIPPED",
                    order.get("error", ""),
                    tf=tf_name,
                    sid=2,
                    signal=fvg["signal"],
                    entry=final_entry,
                    sl=fvg["sl"],
                    tp=tp,
                )
                fvg_pending[fvg_key] = {
                    "tf": tf_name, "signal": fvg["signal"],
                    "entry": final_entry, "sl": fvg["sl"], "tp": tp,
                    "tp_note": tp_note, "gap_top": final_gap_top,
                    "gap_bot": final_gap_bot, "c3_type": fvg.get("c3_type", ""),
                    "pattern": fvg["pattern"],
                    "candle_key": last_candle_time,
                }
                await app.bot.send_message(
                    chat_id=MY_USER_ID,
                    text=(
                        f"{sig_e} *FVG {fvg['signal']} [{tf_name}]*\n"
                        f"Gap: `{final_gap_bot}` – `{final_gap_top}`\n"
                        f"📌 Entry: `{final_entry}`\n"
                        f"⏭️ ราคาผ่าน entry ไปแล้ว รอย้อนกลับ..."
                    ),
                    parse_mode="Markdown"
                )
            else:
                log_event(
                    "ORDER_FAILED",
                    order.get("error", ""),
                    tf=tf_name,
                    sid=2,
                    signal=fvg["signal"],
                    entry=final_entry,
                    sl=fvg["sl"],
                    tp=tp,
                )
                await app.bot.send_message(
                    chat_id=MY_USER_ID,
                    text=f"⚠️ FVG {fvg['signal']} [{tf_name}] ตั้ง order ไม่สำเร็จ: {order.get('error','')}")

    # ท่า 4 execute ตรงเหมือนท่า 1 (ไม่ใช้ fvg_pending)

    # ── ท่า 3 Marubozu pending — register ถ้า r3 คืน marubozu_pending ──
    if active_strategies.get(3, False) and r3.get("marubozu_pending"):
        mp  = r3["marubozu_pending"]
        key = f"{tf_name}_{mp['candle_time']}_s3maru"
        if key not in s3_maru_pending and last_traded_per_tf.get(tf_name) != last_candle_time:
            s3_maru_pending[key] = {
                "tf":          tf_name,
                "direction":   mp["direction"],
                "entry":       mp["entry"],
                "sl":          mp["sl"],
                "tp":          mp["tp"],
                "candle_time": mp["candle_time"],
                "c1_type":     mp.get("c1_type", "R"),
            }
            sig_e = "🟢" if mp["direction"] == "BUY" else "🔴"
            print(f"📋 [{now_bkk().strftime('%H:%M:%S')}] {tf_label(tf_name)}: ท่า3 Maru {mp['direction']} รอยืนยันแท่งถัดไป Entry={mp['entry']}")
            pending_candle0_lbl = fmt_mt5_bkk_ts(mp["candle_time"], "%H:%M") if mp.get("candle_time") else "-"
            pending_confirm_lbl = fmt_mt5_bkk_ts(
                int(mp["candle_time"]) + int(TF_SECONDS_MAP.get(tf_name, 0) or 0),
                "%H:%M"
            ) if mp.get("candle_time") else "-"
            await tg(app, (
                    f"⏳ *ท่า3 DM SP {mp['direction']} Marubozu*\n"
                    f"{sig_e} [{tf_name}] [0] `{pending_candle0_lbl}` แท่งตัน\n"
                    f"🕯️ แท่งยืนยัน: `{pending_confirm_lbl}`\n"
                    f"📌 Entry:`{mp['entry']}` 🛑 SL:`{mp['sl']}` 🎯 TP:`{mp['tp']}`\n"
                    f"รอแท่งถัดไป..."
                ))

    # ── ท่า 2 Marubozu pending (แท่ง[0] ตัน) ──────────────────────
    if active_strategies.get(2, False) and r2.get("marubozu_pending"):
        mp  = r2["marubozu_pending"]
        key = f"{tf_name}_{mp['candle_time']}_s2maru"
        if key not in s3_maru_pending and last_traded_per_tf.get(tf_name) != last_candle_time:
            s3_maru_pending[key] = {
                "tf":          tf_name,
                "direction":   mp["direction"],
                "entry":       mp["entry"],
                "sl":          mp["sl"],
                "tp":          mp["tp"],
                "candle_time": mp["candle_time"],
            }
            sig_e = "🟢" if mp["direction"] == "BUY" else "🔴"
            print(f"📋 [{now_bkk().strftime('%H:%M:%S')}] {tf_label(tf_name)}: ท่า2 FVG Maru {mp['direction']} รอยืนยัน Entry={mp['entry']}")
            await tg(app, (
                    f"⏳ *ท่า2 FVG {mp['direction']} Marubozu*\n"
                    f"{sig_e} [{tf_name}] [0] แท่งตัน\n"
                    f"📌 Entry:`{mp['entry']}` 🛑 SL:`{mp['sl']}` 🎯 TP:`{mp['tp']}`\n"
                    f"รอแท่งถัดไป..."
                ))

    # ── เลือก result ที่ดีที่สุดสำหรับ execute order ──────────────
    # ── เลือก result ที่จะ execute — แต่ละท่าอิสระ ───────────────
    # ท่า 1, 3, 4 execute ตรง | ท่า 2 FVG_DETECTED รอ pending
    signal_results = []
    for sid, r in [(1, r1), (3, r3), (4, r4), (5, r5), (9, r9), (2, r2), (10, r10), (11, r11), (13, r13)]:
        if not active_strategies.get(sid, False):
            continue
        sig = r.get("signal", "WAIT")
        if sig not in ("WAIT", "FVG_DETECTED"):
            signal_results.append((sid, r))

    # ── S8 Swing Limit — ตั้งทั้ง 2 ฝั่งพร้อมกัน ────────────────
    if r8.get("signal") == "MULTI":
        for s8_order in r8["orders"]:
            signal_results.append((8, s8_order))
    # ── สรุปผลทุกท่าใน TF เดียวกัน เพื่อให้ Scan Summary เห็นครบทุก strategy ──
    parts = []
    has_entry_signal = False
    first_entry_part = None

    for sid, r in [(1, r1), (2, r2), (3, r3), (4, r4), (5, r5), (9, r9), (10, r10), (11, r11), (13, r13)]:
        if not active_strategies.get(sid, False):
            continue
        sig = r.get("signal", "WAIT")
        pat = r.get("pattern", "") or f"ท่าที่ {sid}"
        reas = r.get("reason", "")

        if sig == "FVG_DETECTED":
            fvg_d = r.get("fvg", {})
            pat = fvg_d.get("pattern", "") or "ท่าที่ 2 FVG"
            reas = f"รอราคาย้อน Entry:{fvg_d.get('entry', '')}"
            parsed = _parse_pattern(pat, "WAIT", reas)
        else:
            flat = " | ".join(line.strip() for line in reas.splitlines() if line.strip())
            parsed = _parse_pattern(
                pat, sig, flat,
                r.get("entry", 0), r.get("sl", 0), r.get("tp", 0)
            )
            if sig != "WAIT":
                has_entry_signal = True
                if first_entry_part is None:
                    first_entry_part = parsed.copy()
                extra = f"Entry:{r.get('entry', 0)} | SL:{r.get('sl', 0)} | TP:{r.get('tp', 0)}"
                parsed["description"] = f"{parsed.get('description', '')} | {extra}".strip(" |")
        parts.append((sid, parsed))

    if active_strategies.get(8, False):
        r8_reason = r8.get("reason", "")
        if r8.get("signal") == "WAIT":
            parts.append((8, _parse_pattern("ท่าที่ 8", "WAIT", r8_reason)))
        elif r8.get("signal") == "MULTI":
            s8_descs = []
            for o in r8["orders"]:
                has_entry_signal = True
                if first_entry_part is None:
                    first_entry_part = _parse_pattern(
                        o.get("pattern", "ท่าที่ 8"),
                        o.get("signal", "WAIT"),
                        o.get("reason", ""),
                        o.get("entry", 0), o.get("sl", 0), o.get("tp", 0)
                    )
                s8_descs.append(f"{o['signal']} Entry:{o['entry']} | SL:{o['sl']} | TP:{o['tp']}")
            parts.append((8, _parse_pattern("ท่าที่ 8 กินไส้ Swing", "WAIT", " | ".join(s8_descs))))

    if active_strategies.get(6, False):
        s6_tickets = [t for t, tf in position_tf.items()
                      if tf == tf_name and position_sid.get(t) in (2, 3)]
        if s6_tickets:
            s6_bits = []
            for t in s6_tickets:
                st = _s6_state.get(t)
                if st:
                    phase = st.get("phase", "?")
                    swing = st.get("swing_h", 0)
                    count = st.get("count", 0)
                    trails = st.get("trail_count", 0)
                    if phase == "wait":
                        s6_bits.append(f"#{t} phase=wait swing={swing:.2f}")
                    else:
                        s6_bits.append(f"#{t} phase=count {count}/5 swing={swing:.2f} trail={trails}")
                else:
                    es = _entry_state.get(t, "?")
                    s6_bits.append(f"#{t} รอ entry done (state={es})")
            s6_desc = " | ".join(s6_bits)
        else:
            s6_desc = "ไม่มี position ท่า 2/3"
        parts.append((6, _parse_pattern("", "WAIT", s6_desc)))

    if active_strategies.get(7, False):
        s6i_tickets = [t for t, tf in position_tf.items()
                       if tf == tf_name and t not in _s6_state
                       and _entry_state.get(t) == "done"]
        if s6i_tickets:
            s6i_bits = []
            for t in s6i_tickets:
                st = _s6i_state.get(t)
                if st:
                    phase = st.get("phase", "?")
                    swing = st.get("swing_h1", 0)
                    count = st.get("count", 0)
                    s1 = "S1" if st.get("s1_found") else "-"
                    s6i_bits.append(f"#{t} phase={phase} swing={swing:.2f} cnt={count} {s1}")
                else:
                    s6i_bits.append(f"#{t} รอ init")
            s6i_desc = " | ".join(s6i_bits)
        else:
            s6i_desc = "ไม่มี position"
        parts.append((7, _parse_pattern("", "WAIT", s6i_desc)))

    if parts:
        S_COLOR = {
            1: "\033[38;5;220m",
            2: "\033[38;5;117m",
            3: "\033[38;5;183m",
            4: "\033[38;5;120m",
            6: "\033[38;5;214m",
            7: "\033[38;5;209m",
            8: "\033[38;5;159m",
            13: "\033[38;5;45m",
        }
        SID_LABEL = {7: "6i"}
        desc_lines = [
            f"{S_COLOR.get(sid,'')}{BOLD}[ท่า{SID_LABEL.get(sid, sid)}]{RESET} {p['description']}"
            for sid, p in parts if p.get("description")
        ]
        merged = (first_entry_part or parts[0][1]).copy()
        merged["status"] = "ENTRY" if has_entry_signal else "WAIT"
        merged["description"] = "\n".join(desc_lines)
        merged["desc_multiline"] = True
        if not has_entry_signal:
            merged["entry"] = 0
            merged["sl"] = 0
            merged["tp"] = 0
        _scan_results[tf_name] = merged
    else:
        _scan_results[tf_name] = _parse_pattern("", "WAIT", "ไม่มี Setup ที่ตรงเงื่อนไข")

    if not signal_results:
        return False

    # ── execute แต่ละท่าที่มีสัญญาณ — ทำงานอิสระ ────────────────
    any_success = False
    for sid, result in signal_results:
        signal     = result.get("signal", "WAIT")
        pattern    = result.get("pattern", "")
        raw_reason = result.get("reason", "")
        reason_flat = " | ".join(line.strip() for line in raw_reason.splitlines() if line.strip())
        if signal == "WAIT":
            continue
        if sid == 3:
            s3_lookback_bars = max(
                0,
                int(getattr(config, "S3_CONFIRM_LOOKBACK_BARS", getattr(config, "S2_NORMAL_CONFIRM_LOOKBACK_BARS", 8)) or 0),
            )
            s3_confirm_ref = _find_recent_signal_confirmation(rates, signal, tf_secs, s3_lookback_bars)
            if not s3_confirm_ref:
                _log_confirm_lookback_block(tf_name, 3, signal, s3_lookback_bars, pattern)
                _print_skip_once(
                    tf_name,
                    f"⏳ [{now}] {tf_label(tf_name)} ท่า3: ยังไม่เจอ S1/S2/S3 ฝั่งเดียวกันใน {s3_lookback_bars} แท่งย้อนหลัง"
                )
                continue
        # S9 RSI Divergence, S10 CRT TBS และ S13 EzAlgo bypass trend filter
        if sid not in (9, 10, 13) and config.TREND_FILTER_SCAN_BLOCK:
            allowed, tf_reason = trend_allows_signal(tf_name, signal)
            if not allowed:
                _print_skip_once(
                    tf_name,
                    f"🧭 [{now}] {tf_label(tf_name)} ท่า{sid}: trend filter block {signal} ({tf_reason})"
                )
                log_event(
                    "TREND_FILTER_BLOCK",
                    f"block {signal} ({tf_reason})",
                    tf=tf_name, sid=sid, signal=signal,
                )
                continue
        # Pattern B pending
        if "Pattern B" in pattern:
            pb_key = f"{tf_name}_{last_candle_time}_{sid}"
            if pb_key not in pb_pending and last_traded_per_tf.get(tf_name) != last_candle_time:
                pb_pending[pb_key] = {
                    "tf": tf_name, "signal": signal,
                    "entry": result["entry"], "sl": result["sl"], "tp": result["tp"],
                    "pattern": pattern,
                    "candle_key": last_candle_time,
                }
                print(f"📋 [{now}] {tf_label(tf_name)}: บันทึก Pattern B ท่า{sid} Entry={result['entry']}")

        sig_e = "🟢" if signal == "BUY" else "🔴"
        entry = result["entry"]
        sl    = result["sl"]
        tp    = result["tp"]
        candle_txt = ""
        # S10 MTF: แสดงแท่ง HTF ที่เจอ CRT pattern ก่อน
        _htf_candles = result.get("htf_candles") or []
        _htf_tf = result.get("htf_tf", "")
        if _htf_candles:
            _hn = len(_htf_candles)
            _hlabels = [f"[{_hn - 1 - i}]" for i in range(_hn)]
            candle_txt += f"📍 *HTF {_htf_tf}* (เจอ CRT):\n"
            for i, c in enumerate(_htf_candles):
                o, h, l, cl = float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])
                clr = "🟢" if cl > o else "🔴"
                ts = int(c.get("time", 0))
                candle_txt += (
                    f"{clr} แท่ง{_hlabels[i]}: O:`{o:.2f}` H:`{h:.2f}` "
                    f"L:`{l:.2f}` C:`{cl:.2f}` {_fmt_swing_dt(ts)}\n"
                )
            candle_txt += f"📍 *LTF {tf_name}* (trigger):\n"
        _candles_list = result.get("candles", [])
        _n = len(_candles_list)
        labels = [f"[{_n - 1 - i}]" for i in range(_n)]
        for i, c in enumerate(_candles_list):
            o, h, l, cl = float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])
            clr = "🟢" if cl > o else "🔴"
            rate_idx = -(_n - i)
            candle_ts = int(rates[rate_idx]["time"]) if len(rates) >= (_n - i) else 0
            candle_txt += (
                f"{clr} แท่ง{labels[i]}: O:`{o:.2f}` H:`{h:.2f}` "
                f"L:`{l:.2f}` C:`{cl:.2f}` {_fmt_swing_dt(candle_ts)}\n"
            )
        tick          = mt5.symbol_info_tick(SYMBOL)
        current_price = (tick.ask if signal == "BUY" else tick.bid) if tick else 0
        if sid == 9:
            setup_sig = _build_strategy9_setup_sig(tf_name, signal, result)
            if _is_strategy9_setup_invalidated(setup_sig):
                _print_skip_once(
                    tf_name,
                    f"⏭️ [{now}] {tf_label(tf_name)} ท่า9: setup เดิมถูกยกเลิกแล้ว source=passed_entry entry={entry}"
                )
                continue
            dup_ticket, dup_source = _find_duplicate_pending_setup(tf_name, sid, signal, entry, sl, tp, setup_sig=setup_sig)
            if dup_ticket:
                _print_skip_once(
                    tf_name,
                    f"⏭️ [{now}] {tf_label(tf_name)} ท่า9: setup เดิมถูกใช้แล้ว ticket={dup_ticket} source={dup_source} entry={entry}"
                )
                await _notify_skip_once(
                    app,
                    f"{tf_name}|sid9|{signal}|dup_pending|{setup_sig or f'{entry:.2f}|{sl:.2f}|{tp:.2f}'}",
                    (
                        f"⏭️ *[{tf_name}] ท่า9 setup เดิมถูกใช้แล้ว*\n"
                        f"Ticket:`{dup_ticket}` source:`{dup_source}`\n"
                        f"Entry:`{entry:.2f}` | SL:`{sl:.2f}` | TP:`{tp:.2f}`"
                    ),
                    tf_name=tf_name,
                    log_message=f"sid=9 duplicate setup ticket={dup_ticket} source={dup_source} signal={signal} entry={entry} sl={sl} tp={tp} setup_sig={setup_sig}",
                )
                continue
        elif result.get("order_mode") != "market":
            dup_ticket, dup_source = _find_duplicate_pending_setup(tf_name, sid, signal, entry, sl, tp)
            if dup_ticket:
                _print_skip_once(
                    tf_name,
                    f"⏭️ [{now}] {tf_label(tf_name)} ท่า{sid}: setup เดิมถูกใช้แล้ว ticket={dup_ticket} source={dup_source} entry={entry}"
                )
                await _notify_skip_once(
                    app,
                    f"{tf_name}|sid{sid}|{signal}|dup_pending|{entry:.2f}|{sl:.2f}|{tp:.2f}",
                    (
                        f"⏭️ *[{tf_name}] ท่า{sid} setup เดิมถูกใช้แล้ว*\n"
                        f"Ticket:`{dup_ticket}` source:`{dup_source}`\n"
                        f"Entry:`{entry:.2f}` | SL:`{sl:.2f}` | TP:`{tp:.2f}`"
                    ),
                    tf_name=tf_name,
                    log_message=f"sid={sid} duplicate setup ticket={dup_ticket} source={dup_source} signal={signal} entry={entry} sl={sl} tp={tp}",
                )
                continue
        # adjacent bar check per-sid (ท่า 8 ข้ามเช็กนี้ — ตั้งแท่งติดกันได้)
        if sid != 8 and not _pattern_allows_adjacent_order(sid, pattern):
            if _adjacent_sid_blocked(tf_name, sid, last_candle_time, tf_secs):
                _print_skip_once(tf_name, f"⏭️ [{now}] {tf_label(tf_name)} ท่า{sid}: แท่งติดกับ order ท่าเดียวกัน → ข้าม")
                continue
        # Market order ใช้ราคาปัจจุบัน — ไม่ต้องเช็ก "ราคาผ่าน entry แล้วหรือยัง"
        if result.get("order_mode") != "market" and not (sid == 10 and result.get("s10_model_orders")):
            cancel, cancel_reason = should_cancel_pending(rates, signal, entry)
            if cancel:
                print(f"🚫 [{now}] {tf_label(tf_name)} ท่า{sid}: {cancel_reason[:60]}")
                await tg(app, f"🚫 *[{tf_name}] ท่า{sid} ยกเลิก*\n{cancel_reason}")
                continue
        base_flow_id = _build_order_flow_id(tf_name, sid, signal, last_candle_time, entry, sl, tp)
        risk  = abs(entry - sl)
        rr    = round(abs(tp - entry) / risk, 2) if risk > 0 else 0
        if sid == 10 and result.get("s10_model_orders"):
            order_mode = result.get("order_mode", "limit")
            use_delay_sl = (order_mode == "limit") and (sid == 8 or config.DELAY_SL_MODE != "off")
            placed_orders = []
            async with _get_lock():
                _pos_now = mt5.positions_get(symbol=SYMBOL)
                if _pos_now and len(_pos_now) >= MAX_ORDERS:
                    print(f"⚠️ [{now}] {tf_label(tf_name)}: Order เต็ม ({len(_pos_now)}/{MAX_ORDERS})")
                    continue

                existing_tp = get_existing_tp(signal, entry, tf_name, requester_sid=sid)
                if existing_tp > 0:
                    print(f"📌 [{now}] Shared TP {signal} [{tf_name}]: {existing_tp} (ท่า{sid} เดิม: {tp})")
                    tp = existing_tp
                    base_flow_id = _build_order_flow_id(tf_name, sid, signal, last_candle_time, entry, sl, tp)
                    rr = round(abs(tp - entry) / risk, 2) if risk > 0 else 0

                log_event(
                    "PATTERN_FOUND",
                    pattern,
                    tf=tf_name,
                    sid=sid,
                    signal=signal,
                    entry=entry,
                    sl=sl,
                    tp=tp,
                    flow_id=base_flow_id,
                )
                swing_h_text = _fmt_swing_dt(_sh_info["time"]) if _sh_info else ""
                swing_l_text = _fmt_swing_dt(_sl_info["time"]) if _sl_info else ""
                await _notify_pattern_found_once(
                    app,
                    f"pattern|{base_flow_id}",
                    _order_msg(
                        sig_e,
                        pattern,
                        tf_name,
                        sid,
                        candle_txt,
                        result.get("swing_high", 0),
                        result.get("swing_low", 0),
                        raw_reason,
                        current_price,
                        entry,
                        sl,
                        tp,
                        rr,
                        None,
                        _trend_filter_setup_note(tf_name),
                        swing_h_text=swing_h_text,
                        swing_l_text=swing_l_text,
                        entry_label=result.get("entry_label", "Limit ที่"),
                        flow_id=base_flow_id,
                    ),
                )

                for spec in result.get("s10_model_orders", []):
                    place_entry = round(float(spec.get("entry", entry)), 2)
                    place_pattern = spec.get("pattern", pattern)
                    place_label = spec.get("entry_label", result.get("entry_label", "Limit ที่"))
                    place_model = int(spec.get("model", 0) or 0)
                    place_flow_id = _build_order_flow_id(tf_name, sid, signal, last_candle_time, place_entry, sl, tp, place_model)
                    order_sl = 0.0 if use_delay_sl else sl
                    if order_mode == "stop":
                        order = open_order_stop(signal, get_volume(), order_sl, tp, entry_price=place_entry, tf=tf_name, sid=sid, pattern=place_pattern)
                    elif order_mode == "market":
                        order = open_order_market(signal, get_volume(), order_sl, tp, tf=tf_name, sid=sid, pattern=place_pattern)
                    else:
                        order = open_order(signal, get_volume(), order_sl, tp, entry_price=place_entry, tf=tf_name, sid=sid, pattern=place_pattern)
                    order["_entry"] = place_entry
                    order["_pattern"] = place_pattern
                    order["_entry_label"] = place_label
                    order["_model"] = place_model
                    order["_flow_id"] = place_flow_id
                    placed_orders.append(order)

            success_tickets = [o["ticket"] for o in placed_orders if o.get("success") and o.get("ticket")]
            s10_group_id = ""
            if len(success_tickets) > 1:
                s10_group_id = f"{tf_name}|{signal}|{int(result.get('armed_at', 0) or 0)}|{int(result.get('s10_parent_time', 0) or 0)}|{int(result.get('s10_sweep_time', 0) or 0)}"

            for order in placed_orders:
                place_entry = round(float(order.get("_entry", entry)), 2)
                place_pattern = order.get("_pattern", pattern)
                place_label = order.get("_entry_label", result.get("entry_label", "Limit ที่"))
                place_model = int(order.get("_model", 0) or 0)
                place_flow_id = order.get("_flow_id", base_flow_id)

                if order.get("success"):
                    last_traded_per_tf[tf_name] = last_candle_time
                    config.last_traded_sid_tf.setdefault(tf_name, {})[sid] = last_candle_time
                    any_success = True
                    ot_name = order.get("order_type", "LIMIT")
                    if order.get("ticket"):
                        _pend_info = {
                            "tf": tf_name,
                            "entry": round(place_entry, 2),
                            "sl": round(sl, 2),
                            "tp": round(tp, 2),
                            "gap_bot": round(place_entry - abs(place_entry - sl), 2),
                            "gap_top": round(place_entry + abs(place_entry - sl), 2),
                            "detect_bar_time": last_candle_time,
                            "signal": signal,
                            "sid": sid,
                            "pattern": place_pattern,
                            "s10_htf_tf": result.get("htf_tf", tf_name),
                            "s10_armed_at": int(result.get("armed_at", 0) or 0),
                            "s10_parent_time": int(result.get("s10_parent_time", 0) or 0),
                            "s10_sweep_time": int(result.get("s10_sweep_time", 0) or 0),
                            "s10_parent_high": float(result.get("s10_parent_high", 0.0) or 0.0),
                            "s10_parent_low": float(result.get("s10_parent_low", 0.0) or 0.0),
                            "s10_bar_mode": result.get("s10_bar_mode", ""),
                            "s10_sweep_checked": False,
                            "s10_model": place_model,
                            "flow_id": place_flow_id,
                            "parent_flow_id": base_flow_id,
                        }
                        _trend_keys = _trend_filter_state_keys(tf_name)
                        if _trend_keys:
                            _pend_info["trend_filter"] = ",".join(_trend_keys)
                        if result.get("cancel_bars"):
                            _pend_info["cancel_bars"] = result["cancel_bars"]
                        if sid == 1 and result.get("s1_zone_meta"):
                            _pend_info["s1_zone_meta"] = dict(result["s1_zone_meta"])
                        if sid == 1:
                            _pend_info["s1_forward_meta"] = _build_s1_forward_meta(signal, last_candle_time, 5)
                        if result.get("swing_price"):
                            _pend_info["swing_price"] = result["swing_price"]
                            _pend_info["swing_bar_time"] = result.get("swing_bar_time", 0)
                        if s10_group_id:
                            _pend_info["s10_group_id"] = s10_group_id
                            _pend_info["s10_sibling_tickets"] = [t for t in success_tickets if t != order["ticket"]]
                        if use_delay_sl:
                            _pend_info["intended_sl"] = sl
                            _pend_info["sl_armed"] = False
                            _s8_fill_sl[order["ticket"]] = sl
                        pending_order_tf[order["ticket"]] = _pend_info
                        position_tf[order["ticket"]] = tf_name
                        position_sid[order["ticket"]] = sid
                        position_pattern[order["ticket"]] = place_pattern
                        if _trend_keys:
                            from trailing import position_trend_filter as _pos_trend
                            _pos_trend[order["ticket"]] = ",".join(_trend_keys)
                        log_event(
                            "ORDER_CREATED",
                            place_pattern,
                            tf=tf_name,
                            sid=sid,
                            signal=signal,
                            entry=place_entry,
                            sl=sl,
                            tp=tp,
                            ticket=order["ticket"],
                            order_type=ot_name,
                            trend_filter=",".join(_trend_keys) if _trend_keys else "",
                            model=place_model,
                            group_id=s10_group_id if s10_group_id else "",
                            flow_id=place_flow_id,
                            parent_flow_id=base_flow_id,
                            htf_ltf=f"{result.get('htf_tf', tf_name)}_{tf_name}",
                        )
                    save_runtime_state()
                    swing_h_text = _fmt_swing_dt(_sh_info["time"]) if _sh_info else ""
                    swing_l_text = _fmt_swing_dt(_sl_info["time"]) if _sl_info else ""
                    await app.bot.send_message(
                        chat_id=MY_USER_ID,
                        text=_order_msg(
                            sig_e,
                            place_pattern,
                            tf_name,
                            sid,
                            candle_txt,
                            result.get("swing_high", 0), result.get("swing_low", 0),
                            raw_reason, current_price, place_entry, sl, tp, rr,
                            order.get("ticket"),
                            _trend_filter_setup_note(tf_name),
                            swing_h_text=swing_h_text,
                            swing_l_text=swing_l_text,
                            entry_label=place_label,
                            flow_id=place_flow_id,
                        ),
                        parse_mode="Markdown"
                    )
                elif order.get("skipped"):
                    if sid == 9 and setup_sig:
                        _last_strategy9_invalid_setup_by_key[setup_sig] = {
                            "reason": "passed_entry",
                            "time": int(last_candle_time or 0),
                            "entry": round(place_entry, 2),
                        }
                    _print_skip_once(
                        tf_name,
                        f"⏭️ [{now}] {tf_label(tf_name)} ท่า{sid}: Entry {signal} ผ่านไปแล้ว | Entry:{place_entry}",
                    )
                else:
                    err = order.get('error', '')
                    if '10027' in str(err):
                        err = "⚠️ AutoTrading ปิดอยู่ใน MT5 กด Ctrl+E หรือกดปุ่ม AutoTrading ให้เป็นสีเขียว"
                    log_event(
                        "ORDER_FAILED",
                        err,
                        tf=tf_name,
                        sid=sid,
                        signal=signal,
                        entry=place_entry,
                        sl=sl,
                        tp=tp,
                        model=place_model,
                        flow_id=place_flow_id,
                        parent_flow_id=base_flow_id,
                        htf_ltf=f"{result.get('htf_tf', tf_name)}_{tf_name}",
                    )
                    await tg(app, f"❌ [{tf_name}] ท่า{sid} Limit ไม่สำเร็จ: `{err}`\nFlow: `{_short_flow_id(place_flow_id)}`")
            continue
        if sid == 13:
            clear_ok = await _clear_opposite_s13_exposure(app, tf_name, signal)
            if not clear_ok:
                await tg(app, f"⚠️ *[{tf_name}] S13*\nปิดฝั่งตรงข้ามไม่สำเร็จ เลยยังไม่เปิด `{signal}`")
                continue
            ok = await _place_s13_split_orders(app, tf_name, result, last_candle_time, current_price)
            if ok:
                any_success = True
            continue
        async with _get_lock():
            _pos_now = mt5.positions_get(symbol=SYMBOL)
            if _pos_now and len(_pos_now) >= MAX_ORDERS:
                print(f"⚠️ [{now}] {tf_label(tf_name)}: Order เต็ม ({len(_pos_now)}/{MAX_ORDERS})")
                continue

            # ── Shared TP: ถ้ามี Order ทิศเดียวกันอยู่แล้ว ──────────
            # BUY → TP = Swing High ย่อย ร่วมกัน
            # SELL → TP = Swing Low ย่อย ร่วมกัน
            existing_tp = get_existing_tp(signal, entry, tf_name, requester_sid=sid)
            if existing_tp > 0:
                print(f"📌 [{now}] Shared TP {signal} [{tf_name}]: {existing_tp} (ท่า{sid} เดิม: {tp})")
                tp = existing_tp
                base_flow_id = _build_order_flow_id(tf_name, sid, signal, last_candle_time, entry, sl, tp)
                rr = round(abs(tp - entry) / risk, 2) if risk > 0 else 0
            log_event(
                "PATTERN_FOUND",
                pattern,
                tf=tf_name,
                sid=sid,
                signal=signal,
                entry=entry,
                sl=sl,
                tp=tp,
                flow_id=base_flow_id,
            )
            swing_h_text = _fmt_swing_dt(_sh_info["time"]) if _sh_info else ""
            swing_l_text = _fmt_swing_dt(_sl_info["time"]) if _sl_info else ""
            await _notify_pattern_found_once(
                app,
                f"pattern|{base_flow_id}",
                _order_msg(
                    sig_e,
                    pattern,
                    tf_name,
                    sid,
                    candle_txt,
                    result.get("swing_high", 0),
                    result.get("swing_low", 0),
                    raw_reason,
                    current_price,
                    entry,
                    sl,
                    tp,
                    rr,
                    None,
                    _trend_filter_setup_note(tf_name),
                    swing_h_text=swing_h_text,
                    swing_l_text=swing_l_text,
                    entry_label=result.get("entry_label", "Limit ที่"),
                    flow_id=base_flow_id,
                ),
            )
            order_mode = result.get("order_mode", "limit")
            use_delay_sl = (order_mode == "limit") and (sid == 8 or config.DELAY_SL_MODE != "off")
            order_sl = 0.0 if use_delay_sl else sl
            if order_mode == "stop":
                order = open_order_stop(signal, get_volume(), order_sl, tp, entry_price=entry, tf=tf_name, sid=sid, pattern=pattern)
            elif order_mode == "market":
                order = open_order_market(signal, get_volume(), order_sl, tp, tf=tf_name, sid=sid, pattern=pattern)
            else:
                order = open_order(signal, get_volume(), order_sl, tp, entry_price=entry, tf=tf_name, sid=sid, pattern=pattern)
        if order["success"]:
            last_traded_per_tf[tf_name] = last_candle_time
            config.last_traded_sid_tf.setdefault(tf_name, {})[sid] = last_candle_time
            any_success = True
            ot_name = order.get("order_type", "LIMIT")
            if order.get("ticket"):
                _pend_info = {
                    "tf":              tf_name,
                    "entry":           round(entry, 2),
                    "sl":              round(sl, 2),
                    "tp":              round(tp, 2),
                    "gap_bot":         round(entry - abs(entry - sl), 2),
                    "gap_top":         round(entry + abs(entry - sl), 2),
                    "detect_bar_time": last_candle_time,
                    "signal":          signal,
                    "sid":             sid,
                    "pattern":         pattern,
                }
                _trend_keys = _trend_filter_state_keys(tf_name)
                if _trend_keys:
                    _pend_info["trend_filter"] = ",".join(_trend_keys)
                if result.get("cancel_bars"):
                    _pend_info["cancel_bars"] = result["cancel_bars"]
                if sid == 1 and result.get("s1_zone_meta"):
                    _pend_info["s1_zone_meta"] = dict(result["s1_zone_meta"])
                if sid == 1:
                    _pend_info["s1_forward_meta"] = _build_s1_forward_meta(signal, last_candle_time, 5)
                if result.get("swing_price"):
                    _pend_info["swing_price"] = result["swing_price"]
                    _pend_info["swing_bar_time"] = result.get("swing_bar_time", 0)
                if sid == 10:
                    _pend_info["s10_htf_tf"] = result.get("htf_tf", tf_name)
                    _pend_info["s10_armed_at"] = int(result.get("armed_at", 0) or 0)
                    _pend_info["s10_parent_time"] = int(result.get("s10_parent_time", 0) or 0)
                    _pend_info["s10_sweep_time"] = int(result.get("s10_sweep_time", 0) or 0)
                    _pend_info["s10_parent_high"] = float(result.get("s10_parent_high", 0.0) or 0.0)
                    _pend_info["s10_parent_low"] = float(result.get("s10_parent_low", 0.0) or 0.0)
                    _pend_info["s10_bar_mode"] = result.get("s10_bar_mode", "")
                    _pend_info["s10_sweep_checked"] = False
                if sid == 9 and setup_sig:
                    _pend_info["setup_sig"] = setup_sig
                    _last_strategy9_setup_by_key[setup_sig] = order["ticket"]
                if use_delay_sl:
                    _pend_info["intended_sl"] = sl
                    _pend_info["sl_armed"] = False
                    _s8_fill_sl[order["ticket"]] = sl
                _pend_info["flow_id"] = base_flow_id
                pending_order_tf[order["ticket"]] = _pend_info
                position_tf[order["ticket"]] = tf_name
                position_sid[order["ticket"]] = sid
                position_pattern[order["ticket"]] = pattern
                if _trend_keys:
                    from trailing import position_trend_filter as _pos_trend
                    _pos_trend[order["ticket"]] = ",".join(_trend_keys)
                log_event(
                    "ORDER_CREATED",
                    pattern,
                    tf=tf_name,
                    sid=sid,
                    signal=signal,
                    entry=entry,
                    sl=sl,
                    tp=tp,
                    ticket=order["ticket"],
                    order_type=ot_name,
                    trend_filter=",".join(_trend_keys) if _trend_keys else "",
                    flow_id=base_flow_id,
                    htf_ltf=f"{result.get('htf_tf', tf_name)}_{tf_name}" if sid == 10 else "",
                )
            save_runtime_state()
            swing_h_text = _fmt_swing_dt(_sh_info["time"]) if _sh_info else ""
            swing_l_text = _fmt_swing_dt(_sl_info["time"]) if _sl_info else ""
            await app.bot.send_message(
                chat_id=MY_USER_ID,
                text=_order_msg(
                    sig_e,
                    pattern,
                    tf_name,
                    sid,
                    candle_txt,
                    result.get("swing_high", 0), result.get("swing_low", 0),
                    raw_reason, current_price, entry, sl, tp, rr,
                    order.get("ticket"),
                            _trend_filter_setup_note(tf_name),
                            swing_h_text=swing_h_text,
                            swing_l_text=swing_l_text,
                            entry_label=result.get("entry_label", "Limit ที่"),
                            flow_id=base_flow_id,
                        ),
                parse_mode="Markdown"
            )
        elif order.get("skipped"):
            if sid == 9 and setup_sig:
                _last_strategy9_invalid_setup_by_key[setup_sig] = {
                    "reason": "passed_entry",
                    "time": int(last_candle_time or 0),
                    "entry": round(entry, 2),
                }
            _print_skip_once(
                tf_name,
                f"⏭️ [{now}] {tf_label(tf_name)} ท่า{sid}: Entry {signal} ผ่านไปแล้ว | Entry:{entry}",
            )
        else:
            err = order.get('error','')
            if '10027' in str(err):
                err = "⚠️ AutoTrading ปิดอยู่ใน MT5 กด Ctrl+E หรือกดปุ่ม AutoTrading ให้เป็นสีเขียว"
            log_event(
                "ORDER_FAILED",
                err,
                tf=tf_name,
                sid=sid,
                signal=signal,
                entry=entry,
                sl=sl,
                tp=tp,
                flow_id=base_flow_id,
                htf_ltf=f"{result.get('htf_tf', tf_name)}_{tf_name}" if sid == 10 else "",
            )
            await tg(app, f"❌ [{tf_name}] ท่า{sid} Limit ไม่สำเร็จ: `{err}`\nFlow: `{_short_flow_id(base_flow_id)}`")

    return any_success
