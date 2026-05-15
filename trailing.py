from config import *
import config
import re
import inspect
import os
from bot_log import LOG_DIR, log_event
from mt5_utils import connect_mt5
from strategy4 import (
    _find_prev_swing_high,
    _find_prev_swing_low,
    _find_prev_pivot_swing_high,
    _find_prev_pivot_swing_low,
    _find_hh,
    _find_ll,
)
from strategy2 import strategy_2
from strategy3 import strategy_3
from strategy11 import reset_state as s11_reset_state

# FVG order quality tracking
fvg_order_tickets: dict = {}

# mapping: ticket -> {tf, gap_bot, gap_top} for limit orders
pending_order_tf: dict = {}   # {ticket: {tf, gap_bot, gap_top}}

# mapping: position ticket -> tf_name (all strategies)
position_tf: dict = {}   # {ticket: tf_name}

# mapping: position ticket -> strategy id
position_sid: dict = {}  # {ticket: 2|3}

# mapping: position ticket -> pattern name
position_pattern: dict = {}  # {ticket: "pattern string"}
position_trend_filter: dict = {}  # {ticket: "bull_strong,sideway"}
position_zone_meta: dict = {}  # {ticket: {"enabled", "signal", "zone_price", "swing_price", "zone_ok_initial"}}
position_forward_meta: dict = {}  # {ticket: {"enabled", "signal", "detect_bar_time", "forward_bars", "confirmed"}}

# Trail SL state per ticket
_trail_state: dict = {}
_trend_filter_last_dir: dict = {}  # {"ticket|tf": "BULL"|"BEAR"|"SIDEWAY"}

# Rule 4: count bars after order entry
_bar_count: dict = {}

# Rule 5: entry candle state
_entry_state: dict = {}   # {ticket: "done" | "waiting_next"}

# Fill notification tracking
_fill_notified: dict = {}        # {ticket: True} if fill was already notified
_entry_bar_notified: dict = {}   # {ticket: True} if entry candle close was already notified
_fill_initialized: bool = False  # True after first pre-populate of _fill_notified
_entry_bar_none_first: dict = {} # {ticket: monotonic_time} first time entry_bar=None
_reverse_tickets: set = set()    # tickets opened from reverse logic
_FILL_INIT_SUPPRESS_SEC = 180    # suppress fill notify only for positions older than this on init
_last_meta_map_key = ""
_last_trail_tg_key = ""
SLTP_AUDIT_DIR = os.path.join(LOG_DIR, "debug")
SLTP_AUDIT_FILE = os.path.join(SLTP_AUDIT_DIR, "sltp_audit.log")
_last_sltp_cmd_key = ""
_last_sltp_tg_key = ""
_closed_sltp_summary_sent: set[int] = set()
_sl_protect_applied: set[int] = set()
_last_sl_protect_tg_key = ""
_s8_fill_sl: dict = {}   # {ticket: intended_sl} for S8 that filled before SL arm
_fill_rsi_checked: set[int] = set()

# Strategy 6: 2 High 2 Low trail state
# {ticket: {
#   "swing_h": float,        current swing high to watch
#   "phase": "wait"|"count", wait=touch not reached, count=bar counting 1-5
#   "count": int,
#   "last_bar_time": int,
#   "trail_count": int,      number of completed trail rounds
# }}
_s6_state: dict = {}

# Strategy 6 Independent: trail all positions, not limited to strategy 2/3
_s6i_state: dict = {}

# Limit Sweep: track last checked bar per ticket
_sweep_last_bar: dict = {}  # {ticket: last_checked_bar_time}

# Focus Opposite: frozen_side marker per feature
# "trail_sl"     -> used by check_engulf_trail_sl / SL protect
# "entry_candle" -> used by check_entry_candle_quality
# value: "BUY" | "SELL" | None
_focus_frozen_side: dict = {"trail_sl": None, "entry_candle": None}


def _get_s6_prev_swing_high(rates, lookback=100):
    left = max(1, int(getattr(config, "SWING_PIVOT_LEFT", 15) or 15))
    right = max(1, int(getattr(config, "SWING_PIVOT_RIGHT", 10) or 10))
    return _find_prev_pivot_swing_high(rates, lookback=lookback, left=left, right=right) or _find_prev_swing_high(rates, lookback=lookback)


def _get_s6_prev_swing_low(rates, lookback=100):
    left = max(1, int(getattr(config, "SWING_PIVOT_LEFT", 15) or 15))
    right = max(1, int(getattr(config, "SWING_PIVOT_RIGHT", 10) or 10))
    return _find_prev_pivot_swing_low(rates, lookback=lookback, left=left, right=right) or _find_prev_swing_low(rates, lookback=lookback)


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


def _parse_bot_comment(comment: str):
    """Parse comment like M1_S2, H4_S3, M1_S6i_buy -> (tf, sid)."""
    if not comment:
        return None, None
    m = re.match(r"(\[[\w-]+\]|M\d+|H\d+|D\d+)(?:_S(\w+))?", comment)
    if not m:
        return None, None
    tf = m.group(1)
    sid_raw = m.group(2)
    if sid_raw is None:
        return tf, None
    if sid_raw == "6i":
        return tf, 7
    m_sid = re.match(r"(\d+)", sid_raw)
    if m_sid:
        try:
            return tf, int(m_sid.group(1))
        except ValueError:
            return tf, None
    try:
        return tf, int(sid_raw)
    except ValueError:
        return tf, None


def _infer_position_meta_from_comment(pos):
    """Infer tf/sid from position comment or entry deal history."""
    tf = sid = None

    pos_comment = getattr(pos, "comment", "") or ""
    tf, sid = _parse_bot_comment(pos_comment)
    if tf or sid is not None:
        return tf, sid, "position_comment"

    try:
        deals = mt5.history_deals_get(position=pos.ticket)
    except Exception:
        deals = None

    if deals:
        entry_deal = sorted(deals, key=lambda d: d.time)[0]
        deal_comment = getattr(entry_deal, "comment", "") or ""
        tf, sid = _parse_bot_comment(deal_comment)
        if tf or sid is not None:
            return tf, sid, "deal_history"

    return None, None, None


def _pending_order_side(order) -> str:
    if order.type in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP):
        return "BUY"
    if order.type in (mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP):
        return "SELL"
    return ""


def _pending_order_type_name(order) -> str:
    return {
        mt5.ORDER_TYPE_BUY_LIMIT: "BUY LIMIT",
        mt5.ORDER_TYPE_BUY_STOP: "BUY STOP",
        mt5.ORDER_TYPE_SELL_LIMIT: "SELL LIMIT",
        mt5.ORDER_TYPE_SELL_STOP: "SELL STOP",
    }.get(order.type, "PENDING")


def _pending_order_icon(order) -> str:
    return "🟢" if _pending_order_side(order) == "BUY" else "🔴"


def _latest_pending_rsi(tf: str) -> float | None:
    period = max(2, int(getattr(config, "PENDING_RSI_PERIOD", 14) or 14))
    tf_val = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, period + 40)
    if rates is None or len(rates) <= period:
        return None
    try:
        from strategy9 import _calc_rsi_values

        rsi_values = _calc_rsi_values(
            rates,
            period=period,
            applied_price=getattr(config, "PENDING_RSI_APPLIED_PRICE", "close"),
        )
        for value in reversed(rsi_values):
            if value is not None:
                return float(value)
    except Exception as e:
        log_event("PENDING_RSI_RECHECK_ERROR", str(e), tf=tf)
    return None


def _pending_rsi_rule_result(side: str, tf: str) -> dict | None:
    if side not in ("BUY", "SELL"):
        return None

    rsi_value = _latest_pending_rsi(tf)
    if rsi_value is None:
        return None

    if side == "BUY":
        threshold = float(getattr(config, "PENDING_RSI_BUY_MAX", 50.0))
        allowed = rsi_value < threshold
        rule = f"RSI<{threshold:g}"
    else:
        threshold = float(getattr(config, "PENDING_RSI_SELL_MIN", 50.0))
        allowed = rsi_value > threshold
        rule = f"RSI>{threshold:g}"

    return {
        "rsi": float(rsi_value),
        "threshold": threshold,
        "allowed": bool(allowed),
        "rule": rule,
        "threshold_text": f"{threshold:.2f}",
    }


# -------------------------------------------------------------
def _get_filling_mode():
    """Return the first supported broker fill type (IOC -> FOK -> RETURN)."""
    sym = mt5.symbol_info(SYMBOL)
    if sym:
        fm = sym.filling_mode
        if fm & 2: return mt5.ORDER_FILLING_IOC
        if fm & 1: return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def _append_sltp_audit(line: str) -> None:
    if not getattr(config, "SLTP_AUDIT_DEBUG", False):
        return
    try:
        os.makedirs(SLTP_AUDIT_DIR, exist_ok=True)
        with open(SLTP_AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ SLTP audit write error: {e}")


def _sltp_dedup_key(source: str, pos, old_sl: float, old_tp: float,
                    new_sl: float, new_tp: float, ok: bool) -> str:
    pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    return (
        f"{source}|{pos.ticket}|{pos_type}|"
        f"{float(old_sl):.2f}|{float(old_tp):.2f}|"
        f"{float(new_sl):.2f}|{float(new_tp):.2f}|{ok}"
    )


def _audit_sltp_event(source: str, pos, old_sl: float, old_tp: float,
                      new_sl: float, new_tp: float, ok: bool, result=None) -> None:
    if not getattr(config, "SLTP_AUDIT_DEBUG", False):
        return
    global _last_sltp_cmd_key
    tick = mt5.symbol_info_tick(SYMBOL)
    bid = float(getattr(tick, "bid", 0.0)) if tick else 0.0
    ask = float(getattr(tick, "ask", 0.0)) if tick else 0.0
    spread = round(ask - bid, 2) if tick else 0.0
    retcode = getattr(result, "retcode", None) if result is not None else None
    comment = getattr(result, "comment", "") if result is not None else ""
    pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    line = (
        f"[{now_bkk().strftime('%Y-%m-%d %H:%M:%S')}] source={source} "
        f"ticket={pos.ticket} type={pos_type} entry={float(pos.price_open):.2f} "
        f"old_sl={float(old_sl):.2f} old_tp={float(old_tp):.2f} "
        f"new_sl={float(new_sl):.2f} new_tp={float(new_tp):.2f} "
        f"bid={bid:.2f} ask={ask:.2f} spread={spread:.2f} ok={ok} retcode={retcode} comment={comment}"
    )
    _append_sltp_audit(line)
    key = _sltp_dedup_key(source, pos, old_sl, old_tp, new_sl, new_tp, ok)
    if key != _last_sltp_cmd_key:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] SLTP_AUDIT {line}")
        _last_sltp_cmd_key = key


async def _notify_sltp_audit(app, source: str, pos, old_sl: float, old_tp: float,
                             new_sl: float, new_tp: float, ok: bool):
    return await _notify_sltp_audit_v2(app, source, pos, old_sl, old_tp, new_sl, new_tp, ok)
    global _last_sltp_tg_key
    key = _sltp_dedup_key(source, pos, old_sl, old_tp, new_sl, new_tp, ok)
    if key == _last_sltp_tg_key:
        return
    pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    sig_e = "🟢" if pos_type == "BUY" else "🔴"
    status = "สำเร็จ" if ok else "ไม่สำเร็จ"
    await tg(app, (
        f"🧾 *SL/TP Update {status}*\n"
        f"{sig_e} Ticket:`{pos.ticket}` [{pos_type}]\n"
        f"Source: `{source}`\n"
        f"SL: `{old_sl:.2f}` -> `{new_sl:.2f}`\n"
        f"TP: `{old_tp:.2f}` -> `{new_tp:.2f}`"
    ))
    _last_sltp_tg_key = key


async def _notify_sltp_audit_v2(app, source: str, pos, old_sl: float, old_tp: float,
                                new_sl: float, new_tp: float, ok: bool):
    if not getattr(config, "SLTP_AUDIT_DEBUG", False):
        return
    global _last_sltp_tg_key, _closed_sltp_summary_sent
    key = _sltp_dedup_key(source, pos, old_sl, old_tp, new_sl, new_tp, ok)
    if key == _last_sltp_tg_key:
        return

    pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    sig_e = "🟢" if pos_type == "BUY" else "🔴"
    status = "สำเร็จ" if ok else "ไม่สำเร็จ"
    event_time = now_bkk().strftime("%H:%M:%S %d/%m/%Y")
    still_open = bool(mt5.positions_get(ticket=pos.ticket))

    if not still_open:
        if pos.ticket in _closed_sltp_summary_sent:
            return
        await tg(app, (
            f"🧾 *SL/TP Update Summary ({status})*\n"
            f"{sig_e} Ticket:`{pos.ticket}` [{pos_type}]\n"
            f"Event Time: `{event_time}`\n"
            f"Source: `{source}`\n"
            f"SL: `{old_sl:.2f}` -> `{new_sl:.2f}`\n"
            f"TP: `{old_tp:.2f}` -> `{new_tp:.2f}`\n"
            f"Status: `order already closed`"
        ))
        _closed_sltp_summary_sent.add(pos.ticket)
        _last_sltp_tg_key = key
        return

    await tg(app, (
        f"🧾 *SL/TP Update {status}*\n"
        f"{sig_e} Ticket:`{pos.ticket}` [{pos_type}]\n"
        f"Event Time: `{event_time}`\n"
        f"Source: `{source}`\n"
        f"SL: `{old_sl:.2f}` -> `{new_sl:.2f}`\n"
        f"TP: `{old_tp:.2f}` -> `{new_tp:.2f}`"
    ))
    _last_sltp_tg_key = key


def _close_position(pos, pos_type, comment):
    """Close a position immediately and return (success, close_price)."""
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return False, 0.0
    bid = float(getattr(tick, "bid", 0.0))
    ask = float(getattr(tick, "ask", 0.0))
    spread = round(ask - bid, 2)
    close_price = bid if pos_type == "BUY" else ask
    caller = _get_sltp_caller()
    r = mt5.order_send({
        "action":        mt5.TRADE_ACTION_DEAL,
        "symbol":        SYMBOL,
        "volume":        pos.volume,
        "type":          mt5.ORDER_TYPE_SELL if pos_type == "BUY" else mt5.ORDER_TYPE_BUY,
        "position":      pos.ticket,
        "price":         close_price,
        "deviation":     20,
        "magic":         0,
        "comment":       comment,
        "type_time":     mt5.ORDER_TIME_GTC,
        "type_filling":  _get_filling_mode(),
    })
    success = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
    if success:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] CLOSE_DEBUG ok {pos_type} ticket={pos.ticket} close={close_price:.2f} bid={bid:.2f} ask={ask:.2f} spread={spread:.2f} entry={float(pos.price_open):.2f} reason=[{comment}]")
        print(f"[{now_bkk().strftime('%H:%M:%S')}] CLOSE {pos_type} ticket={pos.ticket} price={close_price:.2f} reason=[{comment}]")
        log_event("POSITION_CLOSE_REQUEST", comment, ticket=pos.ticket, side=pos_type, close_price=close_price, entry=pos.price_open, bid=bid, ask=ask, spread=spread, ok=True)
    else:
        retcode = r.retcode if r is not None else "None"
        print(f"[{now_bkk().strftime('%H:%M:%S')}] CLOSE_DEBUG fail {pos_type} ticket={pos.ticket} bid={bid:.2f} ask={ask:.2f} spread={spread:.2f} entry={float(pos.price_open):.2f} retcode={retcode} reason=[{comment}]")
        print(f"[{now_bkk().strftime('%H:%M:%S')}] CLOSE FAIL {pos_type} ticket={pos.ticket} retcode={retcode} reason=[{comment}]")
        log_event("POSITION_CLOSE_REQUEST", comment, ticket=pos.ticket, side=pos_type, entry=pos.price_open, bid=bid, ask=ask, spread=spread, ok=False, retcode=retcode)
    return success, close_price


def _build_s1_forward_meta(signal: str, detect_bar_time: int, forward_bars: int = 5) -> dict:
    return {
        "enabled": True,
        "signal": str(signal or "").upper(),
        "detect_bar_time": int(detect_bar_time or 0),
        "forward_bars": max(1, int(forward_bars or 5)),
        "confirmed": False,
        "confirmed_sid": 0,
        "confirmed_bar_time": 0,
    }


async def _close_linked_s11_for_tf(app, tf_name: str, trigger_reason: str) -> None:
    if not tf_name:
        return

    orders = mt5.orders_get(symbol=SYMBOL) or []
    positions = mt5.positions_get(symbol=SYMBOL) or []
    canceled_orders = []
    closed_positions = []

    for order in orders:
        ticket = int(order.ticket)
        if int(position_sid.get(ticket, 0) or 0) != 11:
            continue
        if str(position_tf.get(ticket, "")) != str(tf_name):
            continue
        r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            info = pending_order_tf.pop(ticket, None)
            position_tf.pop(ticket, None)
            position_sid.pop(ticket, None)
            position_pattern.pop(ticket, None)
            position_trend_filter.pop(ticket, None)
            position_zone_meta.pop(ticket, None)
            position_forward_meta.pop(ticket, None)
            canceled_orders.append(ticket)
            log_event(
                "ORDER_CANCELED",
                f"S11 canceled because {trigger_reason}",
                ticket=ticket,
                tf=tf_name,
                sid=11,
                signal=(info or {}).get("signal", "") if isinstance(info, dict) else "",
                entry=(info or {}).get("entry") if isinstance(info, dict) else None,
                sl=(info or {}).get("sl") if isinstance(info, dict) else None,
                tp=(info or {}).get("tp") if isinstance(info, dict) else None,
            )

    for pos in positions:
        ticket = int(pos.ticket)
        if int(position_sid.get(ticket, 0) or 0) != 11:
            continue
        if str(position_tf.get(ticket, "")) != str(tf_name):
            continue
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        ok_close, close_price = _close_position(pos, pos_type, f"s11 linked close [{tf_name}]")
        if ok_close:
            position_tf.pop(ticket, None)
            position_sid.pop(ticket, None)
            position_pattern.pop(ticket, None)
            position_trend_filter.pop(ticket, None)
            position_zone_meta.pop(ticket, None)
            position_forward_meta.pop(ticket, None)
            closed_positions.append((ticket, close_price, pos_type))

    if canceled_orders or closed_positions:
        s11_reset_state(tf_name)
        lines = [f"🧹 *S11 linked cleanup* [{tf_name}]"]
        if canceled_orders:
            lines.append(f"🗑️ Pending S11: `{', '.join(map(str, canceled_orders))}`")
        if closed_positions:
            lines.append(
                "🔒 Position S11: " + ", ".join(
                    f"`{ticket}` {side} @{close_price:.2f}" for ticket, close_price, side in closed_positions
                )
            )
        lines.append(f"เหตุผล: {trigger_reason}")
        await tg(app, "\n".join(lines))


def _evaluate_s1_forward_confirm(rates, signal: str, detect_bar_time: int, tf_secs: int, forward_bars: int) -> dict:
    signal = str(signal or "").upper()
    detect_bar_time = int(detect_bar_time or 0)
    tf_secs = int(tf_secs or 0)
    forward_bars = max(1, int(forward_bars or 5))
    if rates is None or len(rates) < 4 or detect_bar_time <= 0 or tf_secs <= 0:
        return {
            "confirmed": False,
            "expired": False,
            "last_closed_time": int(rates[-1]["time"]) if rates is not None and len(rates) else 0,
            "checked_bars": 0,
            "matched_sid": 0,
            "matched_bar_time": 0,
        }

    deadline_time = detect_bar_time + (tf_secs * forward_bars)
    last_closed_time = int(rates[-1]["time"])
    matched_sid = 0
    matched_bar_time = 0
    checked_bars = 0

    for idx in range(len(rates)):
        bar_time = int(rates[idx]["time"])
        if bar_time <= detect_bar_time:
            continue
        if bar_time > deadline_time:
            break
        if idx < 2:
            continue
        checked_bars += 1
        sliced_rates = rates[: idx + 1]

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

    return {
        "confirmed": matched_sid in (2, 3),
        "expired": last_closed_time >= deadline_time,
        "last_closed_time": last_closed_time,
        "checked_bars": checked_bars,
        "matched_sid": matched_sid,
        "matched_bar_time": matched_bar_time,
        "deadline_time": deadline_time,
    }


async def check_s1_zone_rules(app):
    if getattr(config, "S1_ZONE_MODE", "") != "zone":
        return

    from strategy1 import evaluate_s1_zone_status

    now = now_bkk().strftime("%H:%M:%S")
    orders = mt5.orders_get(symbol=SYMBOL) or []
    positions = mt5.positions_get(symbol=SYMBOL) or []
    open_order_tickets = {int(o.ticket) for o in orders}
    open_pos_tickets = {int(p.ticket) for p in positions}

    for t in list(position_zone_meta.keys()):
        if t not in open_order_tickets and t not in open_pos_tickets:
            position_zone_meta.pop(t, None)

    # Pending S1: if still outside zone -> cancel limit, otherwise keep it.
    for order in orders:
        ticket = int(order.ticket)
        info = pending_order_tf.get(ticket)
        if not isinstance(info, dict) or int(info.get("sid", 0) or 0) != 1:
            continue
        zone_meta = info.get("s1_zone_meta") or {}
        if not zone_meta.get("enabled"):
            continue

        tf = info.get("tf") or position_tf.get(ticket)
        if not tf:
            continue
        tf_val = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        lookback = TF_LOOKBACK.get(tf, SWING_LOOKBACK)
        rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 6)
        if rates is None or len(rates) < 5:
            continue

        zone_state = evaluate_s1_zone_status(
            rates,
            str(zone_meta.get("signal") or info.get("signal") or ""),
            float(zone_meta.get("zone_price", 0.0) or 0.0),
        )
        if zone_state.get("in_zone", True):
            continue

        r = mt5.order_send({
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket,
        })
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            pending_order_tf.pop(ticket, None)
            sig = str(zone_meta.get("signal") or info.get("signal") or "")
            side_icon = "🟢" if sig == "BUY" else "🔴"
            zone_side = "Low Zone" if sig == "BUY" else "High Zone"
            reason = (
                f"S1 Zone Cancel [{tf}]: pending still outside {zone_side} | "
                f"zone_price:{float(zone_state.get('zone_price', 0.0)):.2f} | "
                f"boundary:{float(zone_state.get('boundary_price', 0.0)):.2f} | "
                f"swing:{float(zone_state.get('swing_price', 0.0)):.2f}"
            )
            log_event(
                "ORDER_CANCELED",
                reason,
                ticket=ticket,
                tf=tf,
                side=sig,
                sid=1,
                order_type=_pending_order_type_name(order),
                entry=info.get("entry"),
                sl=info.get("sl"),
                tp=info.get("tp"),
                flow_id=info.get("flow_id", ""),
            )
            await tg(app, (
                f"🗑️ *S1 Zone Cancel*\n"
                f"{side_icon} [{tf}] Ticket:`{ticket}`\n"
                f"Entry:`{float(info.get('entry', 0.0)):.2f}`\n"
                f"เหตุผล: {reason}"
            ))
            print(f"🗑️ [{now}] S1 zone cancel {ticket} [{tf}]: {reason}")

    # Filled S1: if outside zone and losing -> close. If in profit, keep it.
    for pos in positions:
        ticket = int(pos.ticket)
        if position_sid.get(ticket) != 1:
            continue
        zone_meta = position_zone_meta.get(ticket) or {}
        if not zone_meta.get("enabled"):
            continue

        tf = position_tf.get(ticket)
        if not tf:
            continue
        tf_val = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        lookback = TF_LOOKBACK.get(tf, SWING_LOOKBACK)
        rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 6)
        if rates is None or len(rates) < 5:
            continue

        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        zone_state = evaluate_s1_zone_status(
            rates,
            str(zone_meta.get("signal") or pos_type or ""),
            float(zone_meta.get("zone_price", 0.0) or 0.0),
        )
        if zone_state.get("in_zone", True) or float(pos.profit) >= 0.0:
            continue

        zone_side = "Low Zone" if pos_type == "BUY" else "High Zone"
        reason = (
            f"S1 Zone Loss Exit [{tf}]: outside {zone_side} with loss | "
            f"profit:{float(pos.profit):.2f} | "
            f"zone_price:{float(zone_state.get('zone_price', 0.0)):.2f} | "
            f"boundary:{float(zone_state.get('boundary_price', 0.0)):.2f} | "
            f"swing:{float(zone_state.get('swing_price', 0.0)):.2f}"
        )
        ok_close, close_price = _close_position(pos, pos_type, f"s1 zone loss exit [{tf}]")
        if ok_close:
            sig_e = "🟢" if pos_type == "BUY" else "🔴"
            await tg(app, (
                f"⚠️ *S1 Zone Loss Exit*\n"
                f"{sig_e} Ticket:`{ticket}` [{pos_type}] [{tf}]\n"
                f"Profit:`{float(pos.profit):.2f}`\n"
                f"ปิดที่:`{close_price:.2f}`\n"
                f"เหตุผล: {reason}"
            ))
            print(f"⚠️ [{now}] S1 zone loss exit {ticket} [{tf}] close={close_price:.2f} | {reason}")
            await _close_linked_s11_for_tf(app, tf, f"S1 closed by zone loss exit [{tf}]")


async def check_s1_forward_confirm_rules(app):
    now = now_bkk().strftime("%H:%M:%S")
    orders = mt5.orders_get(symbol=SYMBOL) or []
    positions = mt5.positions_get(symbol=SYMBOL) or []
    open_order_tickets = {int(o.ticket) for o in orders}
    open_pos_tickets = {int(p.ticket) for p in positions}

    for t in list(position_forward_meta.keys()):
        if t not in open_order_tickets and t not in open_pos_tickets:
            position_forward_meta.pop(t, None)

    for order in orders:
        ticket = int(order.ticket)
        info = pending_order_tf.get(ticket)
        if not isinstance(info, dict) or int(info.get("sid", 0) or 0) != 1:
            continue
        forward_meta = info.get("s1_forward_meta") or {}
        if not forward_meta.get("enabled") or forward_meta.get("confirmed"):
            continue

        tf = info.get("tf") or position_tf.get(ticket)
        if not tf:
            continue
        tf_val = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        forward_bars = int(forward_meta.get("forward_bars", 5) or 5)
        lookback = max(TF_LOOKBACK.get(tf, SWING_LOOKBACK), forward_bars + 8)
        rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 10)
        if rates is None or len(rates) < 5:
            continue

        state = _evaluate_s1_forward_confirm(
            rates,
            str(forward_meta.get("signal") or info.get("signal") or ""),
            int(forward_meta.get("detect_bar_time", 0) or 0),
            int(TF_SECONDS_MAP.get(tf, 0) or 0),
            forward_bars,
        )
        if state.get("confirmed"):
            forward_meta["confirmed"] = True
            forward_meta["confirmed_sid"] = int(state.get("matched_sid", 0) or 0)
            forward_meta["confirmed_bar_time"] = int(state.get("matched_bar_time", 0) or 0)
            info["s1_forward_meta"] = forward_meta
            continue
        if not state.get("expired"):
            continue

        r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            pending_order_tf.pop(ticket, None)
            position_forward_meta.pop(ticket, None)
            sig = str(forward_meta.get("signal") or info.get("signal") or "")
            side_icon = "🟢" if sig == "BUY" else "🔴"
            reason = f"S1 Forward Cancel [{tf}]: ไม่เจอ S2/S3 ฝั่งเดียวกันใน {forward_bars} แท่งข้างหน้า"
            log_event(
                "ORDER_CANCELED",
                reason,
                ticket=ticket,
                tf=tf,
                side=sig,
                sid=1,
                order_type=_pending_order_type_name(order),
                entry=info.get("entry"),
                sl=info.get("sl"),
                tp=info.get("tp"),
                flow_id=info.get("flow_id", ""),
            )
            await tg(app, (
                f"🗑️ *S1 Forward Cancel*\n"
                f"{side_icon} [{tf}] Ticket:`{ticket}`\n"
                f"Entry:`{float(info.get('entry', 0.0)):.2f}`\n"
                f"เหตุผล: {reason}"
            ))
            print(f"🗑️ [{now}] S1 forward cancel {ticket} [{tf}]: {reason}")

    for pos in positions:
        ticket = int(pos.ticket)
        if position_sid.get(ticket) != 1:
            continue
        forward_meta = position_forward_meta.get(ticket) or {}
        if not forward_meta.get("enabled") or forward_meta.get("confirmed"):
            continue

        tf = position_tf.get(ticket)
        if not tf:
            continue
        tf_val = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        forward_bars = int(forward_meta.get("forward_bars", 5) or 5)
        lookback = max(TF_LOOKBACK.get(tf, SWING_LOOKBACK), forward_bars + 8)
        rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 10)
        if rates is None or len(rates) < 5:
            continue

        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        state = _evaluate_s1_forward_confirm(
            rates,
            str(forward_meta.get("signal") or pos_type or ""),
            int(forward_meta.get("detect_bar_time", 0) or 0),
            int(TF_SECONDS_MAP.get(tf, 0) or 0),
            forward_bars,
        )
        if state.get("confirmed"):
            forward_meta["confirmed"] = True
            forward_meta["confirmed_sid"] = int(state.get("matched_sid", 0) or 0)
            forward_meta["confirmed_bar_time"] = int(state.get("matched_bar_time", 0) or 0)
            position_forward_meta[ticket] = forward_meta
            continue
        if not state.get("expired"):
            continue

        reason = f"S1 Forward Exit [{tf}]: ไม่เจอ S2/S3 ฝั่งเดียวกันใน {forward_bars} แท่งข้างหน้า"
        ok_close, close_price = _close_position(pos, pos_type, f"s1 forward exit [{tf}]")
        if ok_close:
            position_forward_meta.pop(ticket, None)
            side_icon = "🟢" if pos_type == "BUY" else "🔴"
            await tg(app, (
                f"🔒 *S1 Forward Exit*\n"
                f"{side_icon} [{tf}] Ticket:`{ticket}`\n"
                f"ปิดที่:`{close_price:.2f}`\n"
                f"เหตุผล: {reason}"
            ))
            print(f"🔒 [{now}] S1 forward exit {ticket} [{tf}] close={close_price:.2f} | {reason}")
            await _close_linked_s11_for_tf(app, tf, f"S1 closed by forward confirm miss [{tf}]")


async def _cancel_s10_sibling_orders(app, filled_ticket: int, filled_info: dict, source_ticket: int | None = None) -> None:
    if not isinstance(filled_info, dict):
        return
    if int(filled_info.get("sid", 0) or 0) != 10:
        return
    sibling_tickets = [int(t) for t in (filled_info.get("s10_sibling_tickets") or []) if int(t) > 0]
    if not sibling_tickets:
        return

    open_orders = {int(o.ticket): o for o in (mt5.orders_get(symbol=SYMBOL) or [])}
    canceled = []
    for sibling_ticket in sibling_tickets:
        if source_ticket and sibling_ticket == int(source_ticket):
            continue
        if sibling_ticket not in open_orders:
            pending_order_tf.pop(sibling_ticket, None)
            continue
        r = mt5.order_send({
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": sibling_ticket,
        })
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            canceled.append(sibling_ticket)
            pending_order_tf.pop(sibling_ticket, None)
            log_event(
                "S10_SIBLING_CANCEL",
                "filled_other_model",
                ticket=sibling_ticket,
                filled_ticket=filled_ticket,
                tf=filled_info.get("tf", ""),
                signal=filled_info.get("signal", ""),
                group_id=filled_info.get("s10_group_id", ""),
            )

    if canceled:
        save_runtime_state()
        model_label = filled_info.get("s10_model", "?")
        await tg(app, (
            f"🧹 *S10 Cancel Sibling Pending*\n"
            f"Ticket Fill:`{filled_ticket}` Model:`{model_label}`\n"
            f"Cancel: `{', '.join(str(t) for t in canceled)}`"
        ))


def _get_sltp_caller():
    """Find the actual caller that requested an SL/TP change."""
    skip = {"_modify_sl", "_modify_sl_tp", "_apply_entry_sl_tp", "_get_sltp_caller", "_log_sltp_change"}
    for frame in inspect.stack()[1:]:
        if frame.function not in skip:
            return f"{frame.function}:{frame.lineno}"
    return "unknown"


def _trade_debug_enabled() -> bool:
    return bool(getattr(config, "TRADE_DEBUG", False))


def _log_sltp_change(mode, caller, pos, new_sl, new_tp, ok, result):
    """Forensic audit log for tracing who changed SL/TP."""
    if not getattr(config, "SLTP_AUDIT_DEBUG", False):
        return
    tick = mt5.symbol_info_tick(SYMBOL)
    bid = float(getattr(tick, "bid", 0.0)) if tick else 0.0
    ask = float(getattr(tick, "ask", 0.0)) if tick else 0.0
    spread = round(ask - bid, 2) if tick else 0.0
    retcode = getattr(result, "retcode", None) if result is not None else None
    comment = getattr(result, "comment", "") if result is not None else ""
    key = _sltp_dedup_key(f"{mode}:{caller}", pos, float(pos.sl), float(pos.tp), float(new_sl), float(new_tp), ok)
    if key != _last_sltp_cmd_key:
        print(
            f"[{now_bkk().strftime('%H:%M:%S')}] SLTP_TRACE mode={mode} caller={caller} "
            f"ticket={pos.ticket} type={'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL'} "
            f"old_sl={float(pos.sl):.2f} old_tp={float(pos.tp):.2f} "
            f"new_sl={float(new_sl):.2f} new_tp={float(new_tp):.2f} "
            f"entry={float(pos.price_open):.2f} bid={bid:.2f} ask={ask:.2f} spread={spread:.2f} "
            f"ok={ok} retcode={retcode} comment={comment}"
        )
    _audit_sltp_event(f"{mode}:{caller}", pos, float(pos.sl), float(pos.tp), float(new_sl), float(new_tp), ok, result)


def _modify_sl(pos, new_sl):
    caller = _get_sltp_caller()
    """Modify SL for an open position."""
    r = mt5.order_send({
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   SYMBOL,
        "position": pos.ticket,
        "sl":       new_sl,
        "tp":       pos.tp,
    })
    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
    _log_sltp_change("SL_ONLY", caller, pos, new_sl, pos.tp, ok, r)
    return ok


def _modify_sl_tp(pos, new_sl, new_tp):
    caller = _get_sltp_caller()
    """Modify SL and TP for an open position together."""
    r = mt5.order_send({
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   SYMBOL,
        "position": pos.ticket,
        "sl":       new_sl,
        "tp":       new_tp,
    })
    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
    _log_sltp_change("SL_TP", caller, pos, new_sl, new_tp, ok, r)
    if not ok:
        retcode = r.retcode if r else "None"
        comment = r.comment if r else ""
        print(f"⚠️ _modify_sl_tp FAIL ticket={pos.ticket} SL={new_sl} TP={new_tp} retcode={retcode} comment={comment}")
    return ok


def _modify_pending_sl(order, new_sl):
    """Modify SL for a pending order."""
    r = mt5.order_send({
        "action": mt5.TRADE_ACTION_MODIFY,
        "order": order.ticket,
        "symbol": order.symbol,
        "price": order.price_open,
        "sl": new_sl,
        "tp": order.tp,
        "type_time": order.type_time,
        "type_filling": order.type_filling,
    })
    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
    return ok, r


def _apply_entry_sl_tp(pos, new_sl, new_tp):
    """Apply entry SL/TP update based on config; default updates only SL."""
    if getattr(config, "ENTRY_CANDLE_UPDATE_TP", False):
        return _modify_sl_tp(pos, new_sl, new_tp)
    return _modify_sl(pos, new_sl)


def _price_differs(a: float, b: float, tol: float = 0.01) -> bool:
    return abs(float(a) - float(b)) > tol


def _bar_close(bar) -> float:
    return float(bar["close"])


def _bar_open(bar) -> float:
    return float(bar["open"])


def _bar_high(bar) -> float:
    return float(bar["high"])


def _bar_low(bar) -> float:
    return float(bar["low"])


def _is_green_engulf_break(cur_bar, prev_bar, level: float) -> bool:
    return (
        _bar_close(cur_bar) > _bar_open(cur_bar)
        and _bar_close(prev_bar) > _bar_open(prev_bar)
        and _bar_close(cur_bar) > float(level)
        and _bar_close(cur_bar) > _bar_high(prev_bar)
    )


def _is_red_engulf_break(cur_bar, prev_bar, level: float) -> bool:
    return (
        _bar_close(cur_bar) < _bar_open(cur_bar)
        and _bar_close(prev_bar) < _bar_open(prev_bar)
        and _bar_close(cur_bar) < float(level)
        and _bar_close(cur_bar) < _bar_low(prev_bar)
    )


def _get_closed_bar(pos, tf_val=None):
    """
    Get the correct closed bars for the current entry state.

    Returns `(entry_bar, next_bar)` where:
    - `entry_bar` is the candle where the fill actually happened
    - `next_bar` is the fully closed candle after `entry_bar`

    Uses `start=1` to skip the live candle `[0]`, so `rates[-1]`
    is always the latest fully closed candle.

    Timing example on M1:
      13:22:xx fill -> wait for candle 13:22 to close
      13:23:xx -> entry_bar=13:22, next_bar=None, can evaluate entry candle
      13:24:xx -> entry_bar=13:22, next_bar=13:23, can evaluate waiting_next / waiting_bad
    """
    if tf_val is None:
        tf_val = mt5.TIMEFRAME_M1
    # start=1: skip the live candle [0], so rates[-1] is always the latest closed candle
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, 20)
    if rates is None or len(rates) < 2:
        return None, None

    fill_time = int(pos.time)

    tf_seconds = _get_tf_seconds(tf_val)

    # rates[-1] is the latest fully closed candle
    # entry_bar is valid once fill_time is earlier than that candle close time
    latest_closed_open = int(rates[-1]["time"])
    latest_closed_close = latest_closed_open + tf_seconds
    if fill_time >= latest_closed_close:
        return None, None

    # Find entry_bar and next_bar
    entry_bar = None
    next_bar  = None
    for i, bar in enumerate(rates):
        bar_open = int(bar["time"])
        if bar_open <= fill_time:
            if i + 1 < len(rates) and int(rates[i+1]["time"]) > fill_time:
                entry_bar = bar
                next_bar  = rates[i+1]
                break
            elif i + 1 >= len(rates):
                entry_bar = bar
                break

    return entry_bar, next_bar


def _get_tf_seconds(tf_val):
    tf_seconds_map = {
        mt5.TIMEFRAME_M1: 60,
        mt5.TIMEFRAME_M5: 300,
        mt5.TIMEFRAME_M15: 900,
        mt5.TIMEFRAME_M30: 1800,
        mt5.TIMEFRAME_H1: 3600,
        mt5.TIMEFRAME_H4: 14400,
        mt5.TIMEFRAME_H12: 43200,
        mt5.TIMEFRAME_D1: 86400,
    }
    return tf_seconds_map.get(tf_val, 60)


def _get_current_price(pos_type):
    """Get the current decision-side price for a position."""
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick:
        return float(tick.bid if pos_type == "BUY" else tick.ask)
    return 0.0


def _focus_side_presence(positions, pending_orders):
    """Return `(has_buy, has_sell)` including positions and pending limit/stop orders."""
    has_buy = any(p.type == mt5.ORDER_TYPE_BUY for p in positions) or any(
        o.type in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP)
        for o in pending_orders
    )
    has_sell = any(p.type == mt5.ORDER_TYPE_SELL for p in positions) or any(
        o.type in (mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP)
        for o in pending_orders
    )
    return has_buy, has_sell


def _focus_update_frozen_side(feature: str, positions, pending_orders):
    """
    Update the marker for a feature (`trail_sl` or `entry_candle`) based on current state:
    - if no buy/sell orders remain, reset marker to None
    - if marker is None and only one side exists, freeze to that side
    - if marker is None and both sides exist, wait until one side disappears first
    - if marker already exists, keep it

    Returns the marker after update.
    """
    current = _focus_frozen_side.get(feature)
    has_buy, has_sell = _focus_side_presence(positions, pending_orders)

    if not has_buy and not has_sell:
        if current is not None:
            _focus_frozen_side[feature] = None
            try:
                save_runtime_state()
            except Exception:
                pass
        return None

    if current is None:
        new_side = None
        if has_buy and not has_sell:
            new_side = "BUY"
        elif has_sell and not has_buy:
            new_side = "SELL"
        if new_side is not None:
            _focus_frozen_side[feature] = new_side
            try:
                save_runtime_state()
            except Exception:
                pass
        return new_side

    return current


def _focus_gate_passed(feature: str, frozen_side: str, positions, ref_tf) -> bool:
    """
    Check whether the frozen side has a position with profit above threshold.
    If yes, the opposite side is allowed to continue its trail/ECM logic normally.

    `feature` is `trail_sl` or `entry_candle` and uses its own config group.
    """
    if feature == "trail_sl":
        points = int(getattr(config, "TRAIL_SL_FOCUS_NEW_POINTS", 100))
        tf_mode = getattr(config, "TRAIL_SL_FOCUS_NEW_TF_MODE", "separate")
    else:
        points = int(getattr(config, "ENTRY_CANDLE_FOCUS_NEW_POINTS", 100))
        tf_mode = getattr(config, "ENTRY_CANDLE_FOCUS_NEW_TF_MODE", "separate")
    points = points * config.points_scale()   # BTC uses 4x point scaling relative to XAU base

    tick = mt5.symbol_info_tick(SYMBOL)
    info = mt5.symbol_info(SYMBOL)
    if not tick or not info:
        return False

    pt = float(info.point) if info.point else 0.01
    threshold = points * pt + _get_spread_price()
    bid_cur = float(tick.bid)
    ask_cur = float(tick.ask)

    if frozen_side == "BUY":
        for p in positions:
            if p.type != mt5.ORDER_TYPE_BUY:
                continue
            if (bid_cur - float(p.price_open)) > threshold:
                if tf_mode == "combined" or position_tf.get(p.ticket) == ref_tf:
                    return True
        return False

    for p in positions:
        if p.type != mt5.ORDER_TYPE_SELL:
            continue
        if (float(p.price_open) - ask_cur) > threshold:
            if tf_mode == "combined" or position_tf.get(p.ticket) == ref_tf:
                return True
    return False


def _trend_filter_refs_for_tf(tf_name: str) -> list[str]:
    """Return the enabled trend-filter TFs relevant to this order TF."""
    refs: list[str] = []
    per_tf_map = getattr(config, "TREND_FILTER_PER_TF", {}) or {}
    if per_tf_map.get(tf_name, False):
        refs.append(tf_name)
    if getattr(config, "TREND_FILTER_HIGHER_TF_ENABLED", False):
        higher_tf = getattr(config, "TREND_FILTER_HIGHER_TF", "")
        if higher_tf and higher_tf not in refs:
            refs.append(higher_tf)
    return refs


def _trend_filter_trail_override(ticket: int, pos_type: str, order_tf: str) -> tuple[bool, str]:
    """
    Allow Trail SL to bypass Focus Opposite only when trend filter truly flips side:
    - SELL expects BEAR/SIDEWAY -> BULL
    - BUY expects BULL/SIDEWAY -> BEAR
    UNKNOWN does not count as a new trend and does not clear prior direction.
    """
    if not getattr(config, "TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED", True):
        return False, ""
    refs = _trend_filter_refs_for_tf(order_tf)
    if not refs:
        return False, ""
    try:
        import scanner
        swing_data = getattr(scanner, "_swing_data", {}) or {}
    except Exception:
        return False, ""

    expected_prev = "BEAR" if pos_type == "SELL" else "BULL"
    expected_new = "BULL" if pos_type == "SELL" else "BEAR"
    for ref_tf in refs:
        sw = swing_data.get(ref_tf) or {}
        trend = sw.get("trend") or {}
        t = trend.get("trend", "UNKNOWN")
        strength = trend.get("strength", "-")
        label = trend.get("label", t)
        if t == "UNKNOWN":
            continue

        key = f"{ticket}|{ref_tf}"
        prev = _trend_filter_last_dir.get(key)

        if t == "SIDEWAY":
            _trend_filter_last_dir[key] = t
            continue

        if t not in ("BULL", "BEAR") or strength not in ("weak", "strong"):
            continue

        _trend_filter_last_dir[key] = t
        if prev in (expected_prev, "SIDEWAY") and t == expected_new:
            return True, f"Trend Filter {ref_tf}: {expected_prev} -> {label}"
    return False, ""


def _reversal_trail_override(pos_type: str, order_tf: str, current_sl: float) -> tuple[bool, float, str]:
    """
    Allow Trail SL to bypass Focus Opposite when the latest closed candle shows
    an opposite-side reversal pattern on the order TF.

    BUY position  -> bearish reversal candle
    SELL position -> bullish reversal candle
    """
    if not getattr(config, "TRAIL_SL_REVERSAL_OVERRIDE_ENABLED", False):
        return False, 0.0, ""

    tf_val = TF_OPTIONS.get(order_tf, mt5.TIMEFRAME_M1)
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, 3)
    if rates is None or len(rates) < 2:
        return False, 0.0, ""

    cur = rates[-1]
    prev = rates[-2]

    cur_o = float(cur["open"])
    cur_c = float(cur["close"])
    cur_h = float(cur["high"])
    cur_l = float(cur["low"])
    prev_h = float(prev["high"])
    prev_l = float(prev["low"])

    if pos_type == "BUY":
        if cur_c >= cur_o:
            return False, 0.0, ""
        candidate = round(cur_l - 1.0, 2)
        if cur_c < prev_l and candidate > current_sl:
            return True, candidate, f"reversal override [{order_tf}] red engulf"
        if cur_l < prev_l and prev_l <= cur_c <= prev_h and candidate > current_sl:
            return True, candidate, f"reversal override [{order_tf}] red rejection"
        return False, 0.0, ""

    candidate = round(cur_h + 1.0, 2)
    if cur_c <= cur_o:
        return False, 0.0, ""
    if cur_c > prev_h and (current_sl == 0 or candidate < current_sl):
        return True, candidate, f"reversal override [{order_tf}] green engulf"
    if cur_h > prev_h and prev_l <= cur_c <= prev_h and (current_sl == 0 or candidate < current_sl):
        return True, candidate, f"reversal override [{order_tf}] green rejection"
    return False, 0.0, ""


def reset_focus_frozen_side(feature: str):
    """Call this when the user toggles Focus Opposite from OFF back to ON."""
    if feature in _focus_frozen_side and _focus_frozen_side[feature] is not None:
        _focus_frozen_side[feature] = None
        try:
            save_runtime_state()
        except Exception:
            pass


def _get_spread_price():
    """Return spread as a price value."""
    info = mt5.symbol_info(SYMBOL)
    if not info:
        return 0.0
    try:
        return float(info.spread) * float(info.point)
    except Exception:
        return 0.0


def _fmt_bkk_ts(ts: int | float | None) -> str:
    """Convert an MT5 server timestamp to Bangkok display time."""
    return fmt_mt5_bkk_ts(ts)


def _tp_valid_for_side(pos_type: str, entry: float, tp: float, tol: float = 0.0) -> bool:
    if pos_type == "BUY":
        return tp >= entry - tol
    return tp <= entry + tol


def _entry_update_msg(title: str, sig_e: str, ticket: int, sl: float, sl_note: str,
                      tp: float | None = None, tp_note: str = "") -> str:
    lines = [
        title,
        f"{sig_e} Ticket:`{ticket}`",
        f"🛑 SL: `{sl}` ({sl_note})",
    ]
    if config.ENTRY_CANDLE_UPDATE_TP and tp is not None:
        tail = f" ({tp_note})" if tp_note else ""
        lines.append(f"🎯 TP: `{tp}`{tail}")
    return "\n".join(lines)


async def _run_limit_sweep_followup(app, ticket: int, pos_type: str, tf: str,
                                    rates, bar, prev_bar, reason_detail: str) -> None:
    """Continue Limit Sweep flow after a position is closed (cancel limits / place S8)."""
    now = now_bkk().strftime("%H:%M:%S")
    bar_close = float(bar["close"])
    bar_time = int(bar["time"])

    sh_info = _find_prev_swing_high(rates)
    sl_info = _find_prev_swing_low(rates)

    if pos_type == "BUY":
        target_info = _find_ll(rates, sl_info)
        while target_info and bar_close <= float(target_info["price"]):
            target_info = _find_ll(rates, target_info)
        target_price = target_info["price"] if target_info else None
    else:
        target_info = _find_hh(rates, sh_info)
        while target_info and bar_close >= float(target_info["price"]):
            target_info = _find_hh(rates, target_info)
        target_price = target_info["price"] if target_info else None

    h_price = sh_info["price"] if sh_info else None
    l_price = sl_info["price"] if sl_info else None
    orders = mt5.orders_get(symbol=SYMBOL)
    in_range_limits = []
    if orders:
        for o in orders:
            o_info = pending_order_tf.get(o.ticket)
            o_tf = o_info.get("tf") if isinstance(o_info, dict) else o_info
            if o_tf != tf:
                continue
            o_sid = o_info.get("sid") if isinstance(o_info, dict) else None
            ep = o.price_open
            if pos_type == "BUY" and o.type == mt5.ORDER_TYPE_BUY_LIMIT:
                in_rng = target_price and h_price and target_price <= ep <= h_price
                if in_rng or o_sid == 8:
                    in_range_limits.append(o)
            elif pos_type == "SELL" and o.type == mt5.ORDER_TYPE_SELL_LIMIT:
                in_rng = target_price and l_price and l_price <= ep <= target_price
                if in_rng or o_sid == 8:
                    in_range_limits.append(o)

    kept_ticket = None
    if target_price and in_range_limits:
        in_range_limits.sort(key=lambda o: abs(o.price_open - target_price))
        kept_ticket = in_range_limits[0].ticket
        for o in in_range_limits[1:]:
            r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
            ok_cancel = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
            status = "OK" if ok_cancel else "FAIL"
            print(f"[{now}] SWEEP cancel {pos_type} LIMIT #{o.ticket} [{tf}] entry={o.price_open:.2f} {status}")
            pending_order_tf.pop(o.ticket, None)
        rng = f"{'LL' if pos_type == 'BUY' else 'L'}-{'H' if pos_type == 'BUY' else 'HH'}"
        print(f"[{now}] SWEEP keep #{kept_ticket} [{tf}] near {'LL' if pos_type == 'BUY' else 'HH'}={target_price:.2f} (range {rng})")

    if target_info and not kept_ticket:
        candle = target_info.get("candle", {})
        c_high = candle.get("high", 0)
        c_low = candle.get("low", 0)
        c_range = c_high - c_low

        if c_range > 0:
            from mt5_utils import open_order
            if pos_type == "BUY":
                s8_entry = round(c_low - c_range * 0.17, 2)
                s8_sl = round(c_low - c_range * 0.31, 2)
                s8_tp = sh_info["price"] if sh_info else round(c_high, 2)
                s8_signal = "BUY"
            else:
                s8_entry = round(c_high + c_range * 0.17, 2)
                s8_sl = round(c_high + c_range * 0.31, 2)
                s8_tp = sl_info["price"] if sl_info else round(c_low, 2)
                s8_signal = "SELL"

            s8_pattern = f"ท่าที่ 8 กินไส้ Swing [Limit Sweep] {'🟢 BUY' if s8_signal == 'BUY' else '🔴 SELL'}"
            vol = config.get_volume()
            res = open_order(s8_signal, vol, s8_sl, s8_tp,
                             entry_price=s8_entry, tf=tf, sid="8", pattern=s8_pattern)
            if res.get("success"):
                s8_ticket = res["ticket"]
                pending_order_tf[s8_ticket] = {
                    "tf": tf, "signal": s8_signal,
                    "detect_bar_time": bar_time,
                    "sid": 8, "pattern": s8_pattern,
                    "source": "limit_sweep",
                    "swing_price": target_price,
                    "swing_bar_time": int(target_info.get("time", 0)),
                }
                position_pattern[s8_ticket] = s8_pattern
                log_event(
                    "ORDER_CREATED",
                    s8_pattern,
                    tf=tf,
                    sid=8,
                    signal=s8_signal,
                    entry=s8_entry,
                    sl=s8_sl,
                    tp=s8_tp,
                    ticket=s8_ticket,
                    order_type=res.get("order_type", "LIMIT"),
                    source="limit_sweep",
                    from_ticket=ticket,
                )
                print(f"[{now}] SWEEP -> S8 {s8_signal} LIMIT #{s8_ticket} [{tf}] "
                      f"Entry={s8_entry:.2f} SL={s8_sl:.2f} TP={s8_tp:.2f} "
                      f"{'LL' if pos_type == 'BUY' else 'HH'}={target_price:.2f}")
                await tg(app,
                    f"🧹 *Limit Sweep -> S8*\n"
                    f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                    f"{reason_detail}\n\n"
                    f"ตั้ง {s8_signal} LIMIT `#{s8_ticket}`\n"
                    f"📌 Entry: `{s8_entry:.2f}`\n"
                    f"🛑 SL: `{s8_sl:.2f}` | 🎯 TP: `{s8_tp:.2f}`\n"
                    f"{'📉 LL' if pos_type == 'BUY' else '📈 HH'}: `{target_price:.2f}`"
                )
            else:
                err = res.get("error", "?")
                print(f"[{now}] SWEEP S8 failed: {err}")
                await tg(app,
                    f"🧹 *Limit Sweep*\n"
                    f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                    f"{reason_detail}\n\n"
                    f"⚠️ S8 {'LL' if pos_type == 'BUY' else 'HH'} ตั้งไม่สำเร็จ: {err}"
                )
        else:
            await tg(app,
                f"🧹 *Limit Sweep*\n"
                f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                f"{reason_detail}\n\n"
                f"{'📉 LL' if pos_type == 'BUY' else '📈 HH'}: `{target_price:.2f}` (range=0 ข้าม S8)"
            )
    else:
        sweep_msg = ""
        if kept_ticket:
            sweep_msg = f"\nเหลือ LIMIT `#{kept_ticket}` ใกล้ {'LL' if pos_type == 'BUY' else 'HH'}"
        elif target_price:
            sweep_msg = f"\nไม่มี LIMIT ใน TF"
        await tg(app,
            f"🧹 *Limit Sweep*\n"
            f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
            f"{reason_detail}{sweep_msg}"
        )


# -------------------------------------------------------------
async def check_entry_candle_quality(app):
    """
    Check the entry candle for all strategies.

    BUY entry candle:
      green body >= 35%  -> done
      green body < 35%   -> waiting_next
      red any body       -> waiting_bad: SL=swing_low-1.0, TP=entry.open

    SELL entry candle:
      red body >= 35%    -> done
      red body < 35%     -> waiting_next
      green any body     -> waiting_bad: SL=swing_high+1.0, TP=entry.open

    waiting_bad on the next closed candle:
      BUY:  close>=entry -> close position | close<entry -> SL=next.low-1.0, TP=next.open -> done
      SELL: close<=entry -> close position | close>entry -> SL=next.high+1.0, TP=next.open -> done
    """
    global _fill_initialized, _last_meta_map_key
    if not getattr(config, "ENTRY_CANDLE_ENABLED", True):
        return
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        _entry_state.clear()
        _entry_bar_none_first.clear()
        return
    open_pos_tickets = {p.ticket for p in positions}
    open_order_tickets = {o.ticket for o in (mt5.orders_get(symbol=SYMBOL) or [])}
    for t in list(_s8_fill_sl.keys()):
        if t not in open_pos_tickets and t not in open_order_tickets:
            _s8_fill_sl.pop(t, None)

    # First run: suppress only truly old positions to avoid re-notify after restart.
    # Newly filled positions should still get Limit Fill even if the bot just started.
    if not _fill_initialized:
        _fill_initialized = True
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for p in positions:
            fill_age = max(0, now_ts - int(getattr(p, "time", 0) or 0))
            if fill_age >= _FILL_INIT_SUPPRESS_SEC:
                _fill_notified[p.ticket] = True

    now = now_bkk().strftime("%H:%M:%S")
    open_tickets = {p.ticket for p in positions}
    for t in list(_entry_bar_none_first.keys()):
        if t not in open_tickets:
            _entry_bar_none_first.pop(t, None)

    # Entry Candle Focus Opposite (frozen_side marker)
    # Same side as marker -> skip ECM
    # Opposite side -> ECM works only when gate passes
    entry_focus_skip_tickets: set[int] = set()
    if getattr(config, "ENTRY_CANDLE_FOCUS_NEW_ENABLED", False):
        pending_efn = mt5.orders_get(symbol=SYMBOL) or []
        frozen_side_ec = _focus_update_frozen_side("entry_candle", positions, pending_efn)
        if frozen_side_ec is not None:
            for p in positions:
                p_side = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                if p_side == frozen_side_ec:
                    entry_focus_skip_tickets.add(p.ticket)
                elif not _focus_gate_passed(
                    "entry_candle", frozen_side_ec, positions, position_tf.get(p.ticket)
                ):
                    entry_focus_skip_tickets.add(p.ticket)

    for pos in positions:
        ticket   = pos.ticket
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        sid      = position_sid.get(ticket)
        if sid in (10, 12, 13):
            continue
        sig_e    = "🟢" if pos_type == "BUY" else "🔴"
        state    = _entry_state.get(ticket)
        if _trade_debug_enabled():
            print(f"[{now}] entry_check: {pos_type} {ticket} state={state} fvg={bool(fvg_order_tickets.get(ticket))} pos_tf={position_tf.get(ticket)}")

        # Notify Limit fill the first time before any focus-skip branch can hide it
        fvg_info = fvg_order_tickets.get(ticket)
        pattern_name = position_pattern.get(ticket, "") or ""
        reverse_tag = " [Reverse]" if pattern_name.startswith("Reverse ") else ""
        if ticket not in _fill_notified:
            _fill_notified[ticket] = True
            fill_time = _fmt_bkk_ts(int(pos.time))
            _fill_tf = position_tf.get(ticket, fvg_info.get("tf", "M1") if fvg_info else "M1")
            try:
                from scanner import get_trend_label as _gtl
                _fill_trend = _gtl(_fill_tf)
            except Exception:
                _fill_trend = "?"
            log_event(
                "ENTRY_FILL",
                "Limit fill detected",
                ticket=ticket,
                side=pos_type,
                tf=_fill_tf,
                sid=position_sid.get(ticket),
                pattern=position_pattern.get(ticket, ""),
                price=pos.price_open,
                sl=pos.sl,
                tp=pos.tp,
                fill_time=fill_time,
                trend=_fill_trend,
            )
            await tg(app, (f"🔔 *Limit Fill - {pos_type}{reverse_tag}*\n"
                          f"{sig_e} Ticket:`{ticket}`\n"
                          f"📝 Pattern: `{pattern_name or '-'}`\n"
                          f"📌 เปิดที่: `{pos.price_open:.2f}`\n"
                          f"🛑 SL: `{pos.sl:.2f}` | 🎯 TP: `{pos.tp:.2f}`\n"
                          f"🕐 Fill Time: `{fill_time}`"))
            print(f"[{now}] fill {pos_type} {ticket}={pos.price_open:.2f}")

            await tg(app, f"Trend At Fill: TF `{_fill_tf}` | Trend `{_fill_trend}`")

        if (
            sid != 13
            and ticket not in _fill_rsi_checked
            and getattr(config, "PENDING_RSI_RECHECK_ENABLED", False)
        ):
            _fill_tf = position_tf.get(ticket, fvg_info.get("tf", "M1") if fvg_info else "M1")
            _rsi_result = _pending_rsi_rule_result(pos_type, _fill_tf)
            if _rsi_result is None:
                log_event(
                    "ENTRY_FILL_RSI_RECHECK_SKIP",
                    "RSI unavailable after fill",
                    ticket=ticket,
                    side=pos_type,
                    tf=_fill_tf,
                    sid=position_sid.get(ticket),
                    pattern=position_pattern.get(ticket, ""),
                )
            elif not _rsi_result["allowed"]:
                _reason = (
                    f"Fill RSI Recheck Fail [{_fill_tf}]: {pos_type} entry:{float(pos.price_open):.2f} | "
                    f"RSI({config.PENDING_RSI_PERIOD})={_rsi_result['rsi']:.2f} | "
                    f"เกณฑ์: BUY < {_rsi_result['threshold_text']} / SELL > {_rsi_result['threshold_text']} | "
                    f"ไม่ผ่าน {_rsi_result['rule']}"
                )
                log_event(
                    "ENTRY_FILL_RSI_RECHECK_FAIL",
                    _reason,
                    ticket=ticket,
                    side=pos_type,
                    tf=_fill_tf,
                    sid=position_sid.get(ticket),
                    pattern=position_pattern.get(ticket, ""),
                    price=pos.price_open,
                    rsi=_rsi_result["rsi"],
                )
                ok_close, close_price = _close_position(pos, pos_type, f"fill rsi fail [{_fill_tf}]")
                status = "ส่งปิดแล้ว" if ok_close else "ส่งปิดไม่สำเร็จ"
                await tg(app, (
                    f"⚠️ *Fill RSI Recheck ไม่ผ่าน - ปิดทันที*\n"
                    f"{sig_e} Ticket:`{ticket}` [{pos_type}]\n"
                    f"📝 Pattern: `{pattern_name or '-'}`\n"
                    f"📍 TF: `{_fill_tf}`\n"
                    f"📌 Entry: `{float(pos.price_open):.2f}`\n"
                    f"📊 RSI({config.PENDING_RSI_PERIOD}): `{_rsi_result['rsi']:.2f}`\n"
                    f"📏 เกณฑ์: `BUY < {_rsi_result['threshold_text']} / SELL > {_rsi_result['threshold_text']}`\n"
                    f"สถานะ: `{status}`"
                ))
                if ok_close:
                    _fill_rsi_checked.add(ticket)
                    print(f"[{now}] fill_rsi_close {pos_type} {ticket} close={close_price:.2f}")
                    continue
            else:
                _fill_rsi_checked.add(ticket)

        if ticket in entry_focus_skip_tickets:
            continue

        if state == "done":
            fvg_order_tickets.pop(ticket, None)
            save_runtime_state()
            continue

        if pos.sl == 0 and ticket in _s8_fill_sl:
            intended_sl = float(_s8_fill_sl.get(ticket, 0) or 0)
            if intended_sl > 0:
                _arm_fill = False
                _arm_fill_reason = ""
                _pos_sid = position_sid.get(ticket)
                if config.DELAY_SL_MODE == "off":
                    # Original S8 fallback or disabled mode -> arm immediately
                    _arm_fill = True
                    _arm_fill_reason = "fill fallback"
                elif config.DELAY_SL_MODE == "time":
                    import time as _time
                    _now_ts = int(_time.time())
                    _pos_tf = position_tf.get(ticket, "M1")
                    _tf_val_fill = TF_OPTIONS.get(_pos_tf, mt5.TIMEFRAME_M1)
                    _tf_secs_fill = _get_tf_seconds(_tf_val_fill)
                    _threshold_fill = _tf_secs_fill * 0.10
                    _rates_fill = mt5.copy_rates_from_pos(SYMBOL, _tf_val_fill, 1, 3)
                    if _rates_fill is not None and len(_rates_fill) > 0:
                        _candle_end_fill = int(_rates_fill[-1]["time"]) + _tf_secs_fill
                        _time_left_fill = _candle_end_fill - _now_ts
                        if _time_left_fill <= _threshold_fill:
                            _arm_fill = True
                            _arm_fill_reason = f"time เหลือ {_time_left_fill}s"
                elif config.DELAY_SL_MODE == "price":
                    _tick_fill = mt5.symbol_info_tick(SYMBOL)
                    if _tick_fill:
                        _spread_fill = abs(float(_tick_fill.ask) - float(_tick_fill.bid))
                        if pos_type == "BUY" and float(_tick_fill.ask) > pos.price_open + _spread_fill:
                            _arm_fill = True
                            _arm_fill_reason = f"ask {float(_tick_fill.ask):.2f} > entry+spread"
                        elif pos_type == "SELL" and float(_tick_fill.bid) < pos.price_open - _spread_fill:
                            _arm_fill = True
                            _arm_fill_reason = f"bid {float(_tick_fill.bid):.2f} < entry-spread"

                if _arm_fill:
                    ok_s8 = _modify_sl(pos, intended_sl)
                    if ok_s8:
                        log_event(
                            "SL_CHANGED",
                            "delay_sl_fill_arm",
                            ticket=ticket,
                            side=pos_type,
                            tf=position_tf.get(ticket, fvg_info.get("tf", "M1") if fvg_info else "M1"),
                            old_sl=0.0,
                            new_sl=float(intended_sl),
                            old_tp=float(pos.tp),
                            new_tp=float(pos.tp),
                        )
                        await tg(app, (
                            f"🛡️ *ตั้ง SL หลัง Fill*\n"
                            f"{sig_e} Ticket:`{ticket}`\n"
                            f"🛑 SL: `0.00` -> `{intended_sl:.2f}`\n"
                            f"เหตุผล: {_arm_fill_reason}"
                        ))
                        _s8_fill_sl.pop(ticket, None)
                    else:
                        print(f"⚠️ [{now}] fill arm SL failed ticket={ticket} sl={intended_sl:.2f} -> retry next cycle")

        # If bot restarted and position already has solid profit (>= 5 USD),
        # treat entry candle flow as already done.
        if state is None and pos.profit >= 5.0:
            _entry_state[ticket] = "done"
            fvg_order_tickets.pop(ticket, None)
            save_runtime_state()
            print(f"ℹ️ [{now}] {pos_type} {ticket} profit={pos.profit:.2f} -> auto done")
            continue

        # Get TF from position_tf (all strategies) or fvg_order_tickets (FVG)
        pos_tf   = position_tf.get(ticket)
        meta_source = "in_memory" if pos_tf else None

        # Try infer TF/SID from comment first; it is more reliable than price matching.
        matched_pending_ticket = None
        matched_pending_info = None
        for _pticket, _pinfo in list(pending_order_tf.items()):
            if not isinstance(_pinfo, dict):
                continue
            _pgap_bot = _pinfo.get("gap_bot", 0)
            _pgap_top = _pinfo.get("gap_top", 0)
            if _pgap_bot <= pos.price_open <= _pgap_top or \
               abs(pos.price_open - _pgap_bot) < 2 or \
               abs(pos.price_open - _pgap_top) < 2:
                matched_pending_ticket = _pticket
                matched_pending_info = _pinfo
                break

        if not pos_tf and not fvg_info:
            c_tf, c_sid, c_source = _infer_position_meta_from_comment(pos)
            if c_tf:
                position_tf[ticket] = c_tf
                pos_tf = c_tf
                meta_source = c_source
            if ticket not in position_sid and c_sid is not None:
                position_sid[ticket] = c_sid

        # If a new position still has no position_tf, fallback from pending_order_tf by nearby entry price.
        if not pos_tf and not fvg_info:
            for pticket, pinfo in list(pending_order_tf.items()):
                if isinstance(pinfo, dict):
                    # pending order whose price is close to this position entry
                    pgap_bot = pinfo.get("gap_bot", 0)
                    pgap_top = pinfo.get("gap_top", 0)
                    if pgap_bot <= pos.price_open <= pgap_top or \
                       abs(pos.price_open - pgap_bot) < 2 or \
                       abs(pos.price_open - pgap_top) < 2:
                        position_tf[ticket]  = pinfo.get("tf", "M1")
                        if ticket not in position_sid:
                            position_sid[ticket] = pinfo.get("sid", 0)
                        if ticket not in position_pattern and pinfo.get("pattern"):
                            position_pattern[ticket] = pinfo.get("pattern", "")
                        if ticket not in position_trend_filter and pinfo.get("trend_filter"):
                            position_trend_filter[ticket] = pinfo.get("trend_filter", "")
                        if ticket not in position_zone_meta and pinfo.get("s1_zone_meta"):
                            position_zone_meta[ticket] = dict(pinfo.get("s1_zone_meta") or {})
                        if ticket not in position_forward_meta and pinfo.get("s1_forward_meta"):
                            position_forward_meta[ticket] = dict(pinfo.get("s1_forward_meta") or {})
                        pos_tf = position_tf[ticket]
                        meta_source = f"pending_price_match:{pticket}"
                        break

        if matched_pending_ticket and matched_pending_info:
            if ticket not in position_sid:
                position_sid[ticket] = matched_pending_info.get("sid", 0)
            if ticket not in position_pattern and matched_pending_info.get("pattern"):
                position_pattern[ticket] = matched_pending_info.get("pattern", "")
            if ticket not in position_trend_filter and matched_pending_info.get("trend_filter"):
                position_trend_filter[ticket] = matched_pending_info.get("trend_filter", "")
            if ticket not in position_zone_meta and matched_pending_info.get("s1_zone_meta"):
                position_zone_meta[ticket] = dict(matched_pending_info.get("s1_zone_meta") or {})
            if ticket not in position_forward_meta and matched_pending_info.get("s1_forward_meta"):
                position_forward_meta[ticket] = dict(matched_pending_info.get("s1_forward_meta") or {})
            await _cancel_s10_sibling_orders(app, ticket, matched_pending_info, matched_pending_ticket)

        debug_tf = fvg_info.get("tf", "M1") if fvg_info else position_tf.get(ticket, pos_tf or "?")
        debug_sid = position_sid.get(ticket)
        debug_source = "fvg_memory" if fvg_info else (meta_source or "unknown")
        if _trade_debug_enabled():
            meta_key = f"{ticket}|{debug_tf}|{debug_sid}|{debug_source}"
            if meta_key != _last_meta_map_key:
                print(f"[{now}] meta_map: ticket={ticket} tf={debug_tf} sid={debug_sid} source={debug_source}")
                _last_meta_map_key = meta_key

        if fvg_info:
            tf_val = TF_OPTIONS.get(fvg_info.get("tf","M1"), mt5.TIMEFRAME_M1)
        elif pos_tf:
            tf_val = TF_OPTIONS.get(pos_tf, mt5.TIMEFRAME_M1)
        else:
            tf_val = mt5.TIMEFRAME_M1

        entry_bar, next_bar = _get_closed_bar(pos, tf_val)
        if entry_bar is None:
            tf_seconds = _get_tf_seconds(tf_val)
            expected_entry_close = ((int(pos.time) // tf_seconds) + 1) * tf_seconds
            now_ts = int(datetime.now().timestamp())
            warn_after = expected_entry_close + 60
            first_warn_ts = _entry_bar_none_first.get(ticket)
            if first_warn_ts is None:
                _entry_bar_none_first[ticket] = now_ts
            if now_ts >= warn_after and first_warn_ts is None:
                await tg(app, (f"⚠️ *entry_bar=None นาน >60s*\n"
                               f"{sig_e} Ticket:`{ticket}` pos.time=`{int(pos.time)}`\n"
                               f"fill={fmt_mt5_bkk_ts(int(pos.time), '%H:%M:%S')} tf={position_tf.get(ticket,'?')}"))
            continue
        _entry_bar_none_first.pop(ticket, None)

        # Notify entry candle close with OHLC + body%
        if ticket not in _entry_bar_notified:
            _entry_bar_notified[ticket] = True
            _o = float(entry_bar["open"]);  _h = float(entry_bar["high"])
            _l = float(entry_bar["low"]);   _c = float(entry_bar["close"])
            _rng  = _h - _l
            _body = abs(_c - _o)
            _body_pct = round(_body / _rng * 100 if _rng > 0 else 0)
            _bull = _c > _o
            _clr  = "🟢" if _bull else "🔴"
            _tf_name = position_tf.get(ticket, fvg_info.get("tf","M1") if fvg_info else "M1")
            _entry_close_time = _fmt_bkk_ts(int(entry_bar["time"]) + _get_tf_seconds(tf_val))
            log_event(
                "ENTRY_CANDLE",
                "Entry candle closed",
                ticket=ticket,
                side=pos_type,
                tf=_tf_name,
                open=f"{_o:.2f}",
                high=f"{_h:.2f}",
                low=f"{_l:.2f}",
                close=f"{_c:.2f}",
                body_pct=_body_pct,
                candle_close=_entry_close_time,
            )
            await tg(app, (f"🕯️ *แท่ง Entry จบ - {pos_type}{reverse_tag}*\n"
                          f"{sig_e} Ticket:`{ticket}` `{_tf_name}`\n"
                          f"📝 Pattern: `{pattern_name or '-'}`\n"
                          f"{_clr} O:`{_o:.2f}` H:`{_h:.2f}` L:`{_l:.2f}` C:`{_c:.2f}`\n"
                          f"📊 Body: `{_body_pct}%`\n"
                          f"🕐 Candle Close: `{_entry_close_time}`"))
            print(f"[{now}] {pos_type} {ticket} entry bar closed body={_body_pct}%")

        def bar_info(bar):
            o = float(bar["open"]); h = float(bar["high"])
            l = float(bar["low"]);  c = float(bar["close"])
            rng = h - l
            return c > o, abs(c-o)/rng if rng > 0 else 0, round(abs(c-o)/rng*100 if rng > 0 else 0)

        spread_price = _get_spread_price()
        current_price = float(entry_bar["close"])

        if state is None:
            # Evaluate the entry candle
            bull, body_pct, body_pct_int = bar_info(entry_bar)

            # Find prev_bar (the candle before entry_bar)
            entry_idx = None
            _rates_25 = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 25)
            _rates_1  = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 1)
            _rates_25 = _rates_25 if _rates_25 is not None else []
            _rates_1  = _rates_1  if _rates_1  is not None else [{"time": 0}]
            _current_time = int(_rates_1[0]["time"])
            closed_all = [r for r in _rates_25 if int(r["time"]) != _current_time]
            for i, r in enumerate(closed_all):
                if int(r["time"]) == int(entry_bar["time"]) and i > 0:
                    prev_bar = closed_all[i-1]
                    prev_high = float(prev_bar["high"])
                    prev_low  = float(prev_bar["low"])
                    break
            else:
                prev_high = float(entry_bar["high"])
                prev_low  = float(entry_bar["low"])

            entry_high = float(entry_bar["high"])
            entry_low  = float(entry_bar["low"])

                # Reverse position: special immediate close conditions
            if ticket in _reverse_tickets:
                if pos_type == "SELL" and bull and current_price > prev_high:
                # SELL reverse: green candle + close > prev high -> close immediately
                    reason_rev = f"Reverse SELL green close={current_price:.2f} > prev_high={prev_high:.2f}"
                    ok_rev, cp_rev = _close_position(pos, pos_type, "reverse entry green > prev high")
                    if ok_rev:
                        _entry_state[ticket] = "done"
                        _reverse_tickets.discard(ticket)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "reverse_close", ticket=ticket, side=pos_type, state="done", close_price=cp_rev, reason=reason_rev)
                        await tg(app, f"❌ *ปิด SELL Reverse - เขียว > prev High*\n🔴 Ticket:`{ticket}` ปิดที่`{cp_rev}`\n📊 Close:`{current_price:.2f}` > PrevHigh:`{prev_high:.2f}`")
                        print(f"❌ [{now}] {reason_rev} -> ปิดที่ {cp_rev}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                    continue
                elif pos_type == "BUY" and not bull and current_price < prev_low:
                # BUY reverse: red candle + close < prev low -> close immediately
                    reason_rev = f"Reverse BUY red close={current_price:.2f} < prev_low={prev_low:.2f}"
                    ok_rev, cp_rev = _close_position(pos, pos_type, "reverse entry red < prev low")
                    if ok_rev:
                        _entry_state[ticket] = "done"
                        _reverse_tickets.discard(ticket)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "reverse_close", ticket=ticket, side=pos_type, state="done", close_price=cp_rev, reason=reason_rev)
                        await tg(app, f"❌ *ปิด BUY Reverse - แดง < prev Low*\n🟢 Ticket:`{ticket}` ปิดที่`{cp_rev}`\n📊 Close:`{current_price:.2f}` < PrevLow:`{prev_low:.2f}`")
                        print(f"❌ [{now}] {reason_rev} -> ปิดที่ {cp_rev}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                    continue
                else:
                    # Reverse position: normal entry candle -> done
                    if config.ENTRY_CANDLE_MODE == "close_percentage" and current_price > pos.price_open:
                        new_sl = round(float(pos.price_open) + spread_price, 2)
                        _apply_entry_sl_tp(pos, new_sl, pos.tp)
                    _entry_state[ticket] = "done"
                    _reverse_tickets.discard(ticket)
                    save_runtime_state()
                    print(f"OK [{now}] Reverse {pos_type} {ticket} entry candle OK -> done")
                    continue

            pattern_name = position_pattern.get(ticket, "") or ""
            is_reverse_entry = pattern_name.startswith("Reverse ")
            if is_reverse_entry:
                reverse_sl = None
                reverse_note = ""
                if pos_type == "BUY" and current_price > pos.price_open:
                    reverse_sl = round(float(pos.price_open) + spread_price, 2)
                    reverse_note = "entry + spread"
                elif pos_type == "SELL" and current_price < pos.price_open:
                    reverse_sl = round(float(pos.price_open) + spread_price, 2)
                    reverse_note = "entry + spread"

                if reverse_sl is not None and _price_differs(pos.sl, reverse_sl, max(spread_price / 2.0, 0.01)):
                    ok = _apply_entry_sl_tp(pos, reverse_sl, pos.tp)
                    _entry_state[ticket] = "done"
                    save_runtime_state()
                    log_event(
                        "ENTRY_QUALITY",
                        "reverse done",
                        ticket=ticket,
                        side=pos_type,
                        state="done",
                        sl=reverse_sl,
                        tp=pos.tp,
                        reason=reverse_note,
                    )
                    if ok:
                        await tg(app, _entry_update_msg(
                            f"✅ *{pos_type} Reverse Entry จบ*",
                            sig_e, ticket, reverse_sl, reverse_note
                        ))
                    print(f"OK [{now}] Reverse {pos_type} {ticket} entry done SL={reverse_sl} ({reverse_note})")
                    continue

            if pos_type == "BUY":
                if bull and body_pct >= 0.35:
                    if config.ENTRY_CANDLE_MODE == "close_percentage" and current_price > pos.price_open:
                        new_sl = round(float(pos.price_open) + spread_price, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] BUY modify SL failed ticket={ticket} sl={new_sl} -> retry next cycle")
                            continue
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "done", ticket=ticket, side=pos_type, state="done", reason=f"green body={body_pct_int}%")
                    print(f"[ENTRY] BUY {ticket} done green body={body_pct_int}%")

                elif bull and body_pct < 0.35:
                    if config.ENTRY_CANDLE_MODE == "close_percentage" and current_price > pos.price_open:
                        new_sl = round(float(pos.price_open) + spread_price, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] BUY modify SL failed ticket={ticket} sl={new_sl} -> retry next cycle")
                            continue
                    _entry_state[ticket] = "waiting_next"
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_next", ticket=ticket, side=pos_type, state="waiting_next", reason=f"green body={body_pct_int}%")
                    print(f"[ENTRY] BUY {ticket} waiting_next green body={body_pct_int}%")

                elif not bull and current_price < prev_low:
                    reason = f"entry_red close={current_price:.2f}<prev_low={prev_low:.2f} immediate"
                    ok, cp = _close_position(pos, pos_type, "entry red close < prev low")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                        await tg(app, f"CLOSE BUY - Entry Red < Prev Low\n{sig_e} Ticket:`{ticket}`\nEntry Close: `{current_price:.2f}`\nPrev Low: `{prev_low:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                        print(f"[CLOSE_IMMEDIATE] BUY ticket={ticket} reason={reason} close={cp}")
                        if config.LIMIT_SWEEP:
                            tf_name = position_tf.get(ticket, "M1")
                            lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                            rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                            if rates_sweep is not None and len(rates_sweep) >= 6:
                                reason_detail = f"แท่งจบแดง close={current_price:.2f} < prev low={prev_low:.2f}"
                                await _run_limit_sweep_followup(
                                    app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                )
                        continue
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด BUY ไม่สำเร็จ (entry แดง < prev low)*\n{sig_e} Ticket:`{ticket}`")

                elif not bull and config.ENTRY_CANDLE_MODE == "close_percentage" and body_pct < 0.70:
                    tick_check = mt5.symbol_info_tick(SYMBOL)
                    ask_price = float(tick_check.ask) if tick_check else None
                    entry_plus_spread = float(pos.price_open) + spread_price
                    if ask_price is not None and ask_price > entry_plus_spread:
                        new_sl = round(entry_plus_spread, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] BUY modify SL failed ticket={ticket} sl={new_sl} -> retry next cycle")
                            continue
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "done_sl_protect", ticket=ticket, side=pos_type, state="done", sl=new_sl, reason=f"red body={body_pct_int}% ask={ask_price:.2f}>entry+spread={entry_plus_spread:.2f}")
                        await tg(app, f"🛡️ *BUY Entry แดง - SL Protect*\n{sig_e} Ticket:`{ticket}`\n🛑 SL: `{new_sl}` (Entry+Spread)\n📊 Ask: `{ask_price:.2f}` > Entry+Spread: `{entry_plus_spread:.2f}`\nBody: `{body_pct_int}%`")
                        print(f"[ENTRY] BUY {ticket} done_sl_protect red body={body_pct_int}% ask={ask_price:.2f}>entry+spread SL={new_sl}")
                        if config.LIMIT_SWEEP:
                            tf_name = position_tf.get(ticket, "M1")
                            lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                            rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                            if rates_sweep is not None and len(rates_sweep) >= 6:
                                reason_detail = f"แท่งจบแดง body={body_pct_int}% ask={ask_price:.2f} > entry+spread={entry_plus_spread:.2f}"
                                await _run_limit_sweep_followup(
                                    app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                )
                    else:
                        reason = f"entry_red body={body_pct_int}% ask<=entry+spread close_percentage"
                        ok, cp = _close_position(pos, pos_type, "entry red ask<=entry+spread")
                        if ok:
                            _entry_state[ticket] = "done"
                            fvg_order_tickets.pop(ticket, None)
                            save_runtime_state()
                            log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                            await tg(app, f"❌ *CLOSE BUY - Entry แดง ask<=entry+spread*\n{sig_e} Ticket:`{ticket}`\nAsk: `{ask_price}`\nEntry+Spread: `{entry_plus_spread:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                            print(f"[CLOSE_IMMEDIATE] BUY ticket={ticket} reason={reason} close={cp}")
                            if config.LIMIT_SWEEP:
                                tf_name = position_tf.get(ticket, "M1")
                                lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                                rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                                if rates_sweep is not None and len(rates_sweep) >= 6:
                                    reason_detail = f"แท่งจบแดง body={body_pct_int}% ask<=entry+spread ปิดทันที"
                                    await _run_limit_sweep_followup(
                                        app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                    )
                            continue
                        else:
                            _entry_state[ticket] = "closing_fail"
                            save_runtime_state()
                            await tg(app, f"⚠️ *ปิด BUY ไม่สำเร็จ (entry แดง ask<=entry+spread)*\n{sig_e} Ticket:`{ticket}`")

                elif not bull and config.ENTRY_CANDLE_MODE == "close_percentage":
                    reason = f"entry_red body={body_pct_int}% mode=close_percentage immediate"
                    ok, cp = _close_position(pos, pos_type, "entry red candle close mode")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                        await tg(app, f"CLOSE BUY - Entry Red\n{sig_e} Ticket:`{ticket}`\nEntry Close: `{current_price:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                        print(f"[CLOSE_IMMEDIATE] BUY ticket={ticket} reason={reason} close={cp}")
                        if config.LIMIT_SWEEP and current_price < prev_low:
                            tf_name = position_tf.get(ticket, "M1")
                            lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                            rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                            if rates_sweep is not None and len(rates_sweep) >= 6:
                                reason_detail = f"แท่งจบแดง close={current_price:.2f} < prev low={prev_low:.2f}"
                                await _run_limit_sweep_followup(
                                    app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                )
                        # close_percentage: close immediately only, no reverse market/limit
                        continue

                        tf_name = position_tf.get(ticket, "M1")
                        sid = position_sid.get(ticket, 1)
                        candle_range = entry_high - entry_low
                        rates_swing = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 120)
                        swing_info = _find_prev_swing_low(rates_swing) if rates_swing is not None else None
                        rev_tp = round(swing_info["price"], 2) if swing_info else None

                        if config.ENTRY_CLOSE_REVERSE_MARKET and rev_tp:
                            mkt_sl = round(entry_high + SL_BUFFER(), 2)
                            tick_r = mt5.symbol_info_tick(SYMBOL)
                            if tick_r:
                                vol = SYMBOL_CONFIG[SYMBOL]["volume"]
                                rev_r = mt5.order_send({
                                    "action":       mt5.TRADE_ACTION_DEAL,
                                    "symbol":       SYMBOL,
                                    "volume":       vol,
                                    "type":         mt5.ORDER_TYPE_SELL,
                                    "price":        float(tick_r.bid),
                                    "sl":           mkt_sl,
                                    "tp":           rev_tp,
                                    "deviation":    20,
                                    "magic":        234001,
                                    "comment":      f"{tf_name}_S{sid}_rev_market",
                                    "type_time":    mt5.ORDER_TIME_GTC,
                                    "type_filling": _get_filling_mode(),
                                })
                                if rev_r and rev_r.retcode == mt5.TRADE_RETCODE_DONE:
                                    rev_ticket = rev_r.order
                                    position_tf[rev_ticket] = tf_name
                                    position_sid[rev_ticket] = sid
                                    position_pattern[rev_ticket] = f"Reverse SELL (entry red) [{tf_name}]"
                                    _entry_state.pop(rev_ticket, None)
                                    save_runtime_state()
                                    log_event("ORDER_CREATED", "reverse_sell_market", ticket=rev_ticket, side="SELL", tf=tf_name, sl=mkt_sl, tp=rev_tp, price=float(tick_r.bid), from_ticket=ticket)
                                    await tg(app, f"🔄 *เปิด SELL Market (Reverse)*\n🔴 Ticket:`{rev_ticket}`\n📌 Entry: `{float(tick_r.bid):.2f}`\n🛑 SL: `{mkt_sl}` (Entry High+SL_BUFFER)\n🎯 TP: `{rev_tp}` (Swing Low)\n📊 TF: `{tf_name}`\n📝 จาก: `{ticket}`")
                                    print(f"[REVERSE_MARKET] SELL ticket={rev_ticket} entry={float(tick_r.bid):.2f} SL={mkt_sl} TP={rev_tp}")
                                else:
                                    rc = rev_r.retcode if rev_r else "None"
                                    cmt = rev_r.comment if rev_r else ""
                                    log_event("ORDER_FAILED", "reverse_sell_market", ticket=ticket, side="SELL", tf=tf_name, sl=mkt_sl, tp=rev_tp, price=float(tick_r.bid), retcode=rc, comment=cmt, from_ticket=ticket)
                                    print(f"[REVERSE_MARKET_FAIL] SELL retcode={rc} comment={cmt}")
                                    await tg(app, f"⚠️ *เปิด SELL Market Reverse ไม่สำเร็จ*\nretcode=`{rc}` {cmt}")

                        if config.ENTRY_CLOSE_REVERSE_LIMIT and rev_tp and candle_range > 0:
                            from mt5_utils import open_order
                            vol = SYMBOL_CONFIG[SYMBOL]["volume"]
                            lim_entry = round(entry_high + candle_range * 0.17, 2)
                            lim_sl = round(entry_high + candle_range * 0.31, 2)
                            res = open_order("SELL", vol, lim_sl, rev_tp, entry_price=lim_entry, tf=tf_name, sid=f"{sid}_rev_limit", pattern=f"Reverse SELL Limit (entry red) [{tf_name}]")
                            if res.get("success"):
                                rev_order = res["ticket"]
                                pending_order_tf[rev_order] = {
                                    "tf": tf_name, "gap_bot": lim_entry, "gap_top": lim_entry,
                                    "detect_bar_time": int(entry_bar["time"]),
                                    "signal": "SELL", "sid": sid,
                                    "pattern": f"Reverse SELL Limit (entry red) [{tf_name}]",
                                    "reverse": True,
                                }
                                save_runtime_state()
                                log_event("ORDER_CREATED", "reverse_sell_limit", ticket=rev_order, side="SELL", tf=tf_name, sl=lim_sl, tp=rev_tp, entry=lim_entry, from_ticket=ticket)
                                await tg(app, f"🔄 *ตั้ง SELL LIMIT (Reverse)*\n🔴 Ticket:`{rev_order}`\n📌 Entry: `{lim_entry:.2f}` (High+17%)\n🛑 SL: `{lim_sl:.2f}` (High+31%)\n🎯 TP: `{rev_tp}` (Swing Low)\n📊 TF: `{tf_name}`\n📝 จาก: `{ticket}`")
                                print(f"[REVERSE_LIMIT] SELL ticket={rev_order} entry={lim_entry:.2f} SL={lim_sl:.2f} TP={rev_tp}")
                            else:
                                err = res.get("error", "unknown")
                                print(f"[REVERSE_LIMIT_FAIL] SELL error={err}")
                                await tg(app, f"⚠️ *ตั้ง SELL LIMIT Reverse ไม่สำเร็จ*\n{err}")

                        if not rev_tp:
                            print(f"[REVERSE_SKIP] SELL no swing low")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด BUY ไม่สำเร็จ (entry แดง)*\n{sig_e} Ticket:`{ticket}`")

                elif not bull and current_price <= pos.price_open:
                    rates_swing = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 120)
                    swing_info = _find_prev_swing_low(rates_swing) if rates_swing is not None else None
                    swing_sl = round(swing_info["price"] - 1.0, 2) if swing_info else round(entry_low - 1.0, 2)
                    bad_tp = round(float(entry_bar["open"]) - spread_price, 2)
                    reason = f"แดง High>{prev_high:.2f}" if entry_high > prev_high else (
                        f"แดง body={body_pct_int}%>=65%" if body_pct >= 0.65 else f"แดง body={body_pct_int}%<65%")
                    ok = _apply_entry_sl_tp(pos, swing_sl, bad_tp)
                    _entry_state[ticket] = "waiting_bad"
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_bad", ticket=ticket, side=pos_type, state="waiting_bad", reason=reason, sl=swing_sl, tp=bad_tp)
                    if ok:
                        title = f"⚠️ *BUY Entry แดง -> waiting\\_bad*\n{sig_e} Ticket:`{ticket}` | {reason}"
                        msg = _entry_update_msg(title, sig_e, ticket, swing_sl, "swing low", bad_tp, "entry open")
                        await tg(app, msg)
                    print(f"[{now}] BUY {ticket} {reason} -> waiting_bad SL={swing_sl} TP={bad_tp}")

                elif not bull:
                    new_sl = round(pos.price_open + 50.0, 2)
                    ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "done", ticket=ticket, side=pos_type, state="done", reason="red candle but current above entry", sl=new_sl, tp=pos.tp)
                    if ok:
                        await tg(app, _entry_update_msg(
                            "✅ *BUY Entry แดง แต่ราคายังเหนือ entry*",
                            sig_e, ticket, new_sl, "entry + 50"
                        ))
                    print(f"[ENTRY] BUY {ticket} red entry but current>{pos.price_open:.2f} -> SL={new_sl}")

            else:  # SELL
                if not bull and body_pct >= 0.35:
                    if config.ENTRY_CANDLE_MODE == "close_percentage" and current_price < pos.price_open:
                        new_sl = round(float(pos.price_open) - spread_price, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] SELL modify SL failed ticket={ticket} sl={new_sl} -> retry next cycle")
                            continue
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "done", ticket=ticket, side=pos_type, state="done", reason=f"red body={body_pct_int}%")
                    print(f"[ENTRY] SELL {ticket} done red body={body_pct_int}%")

                elif not bull and body_pct < 0.35:
                    if config.ENTRY_CANDLE_MODE == "close_percentage" and current_price < pos.price_open:
                        new_sl = round(float(pos.price_open) - spread_price, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] SELL modify SL failed ticket={ticket} sl={new_sl} -> retry next cycle")
                            continue
                    _entry_state[ticket] = "waiting_next"
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_next", ticket=ticket, side=pos_type, state="waiting_next", reason=f"red body={body_pct_int}%")
                    print(f"[ENTRY] SELL {ticket} waiting_next red body={body_pct_int}%")

                elif bull and current_price > prev_high:
                    reason = f"entry_green close={current_price:.2f}>prev_high={prev_high:.2f} immediate"
                    ok, cp = _close_position(pos, pos_type, "entry green close > prev high")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                        await tg(app, f"CLOSE SELL - Entry Green > Prev High\n{sig_e} Ticket:`{ticket}`\nEntry Close: `{current_price:.2f}`\nPrev High: `{prev_high:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                        print(f"[CLOSE_IMMEDIATE] SELL ticket={ticket} reason={reason} close={cp}")
                        if config.LIMIT_SWEEP:
                            tf_name = position_tf.get(ticket, "M1")
                            lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                            rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                            if rates_sweep is not None and len(rates_sweep) >= 6:
                                reason_detail = f"แท่งจบเขียว close={current_price:.2f} > prev high={prev_high:.2f}"
                                await _run_limit_sweep_followup(
                                    app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                )
                        continue
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด SELL ไม่สำเร็จ (entry เขียว > prev high)*\n{sig_e} Ticket:`{ticket}`")

                elif bull and config.ENTRY_CANDLE_MODE == "close_percentage" and body_pct < 0.70:
                    tick_check = mt5.symbol_info_tick(SYMBOL)
                    bid_price = float(tick_check.bid) if tick_check else None
                    entry_minus_spread = float(pos.price_open) - spread_price
                    if bid_price is not None and bid_price < entry_minus_spread:
                        new_sl = round(entry_minus_spread, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] SELL modify SL failed ticket={ticket} sl={new_sl} -> retry next cycle")
                            continue
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "done_sl_protect", ticket=ticket, side=pos_type, state="done", sl=new_sl, reason=f"green body={body_pct_int}% bid={bid_price:.2f}<entry-spread={entry_minus_spread:.2f}")
                        await tg(app, f"🛡️ *SELL Entry เขียว - SL Protect*\n{sig_e} Ticket:`{ticket}`\n🛑 SL: `{new_sl}` (Entry-Spread)\n📊 Bid: `{bid_price:.2f}` < Entry-Spread: `{entry_minus_spread:.2f}`\nBody: `{body_pct_int}%`")
                        print(f"[ENTRY] SELL {ticket} done_sl_protect green body={body_pct_int}% bid={bid_price:.2f}<entry-spread SL={new_sl}")
                        if config.LIMIT_SWEEP:
                            tf_name = position_tf.get(ticket, "M1")
                            lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                            rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                            if rates_sweep is not None and len(rates_sweep) >= 6:
                                reason_detail = f"แท่งจบเขียว body={body_pct_int}% bid={bid_price:.2f} < entry-spread={entry_minus_spread:.2f}"
                                await _run_limit_sweep_followup(
                                    app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                )
                    else:
                        reason = f"entry_green body={body_pct_int}% bid>=entry-spread close_percentage"
                        ok, cp = _close_position(pos, pos_type, "entry green bid>=entry-spread")
                        if ok:
                            _entry_state[ticket] = "done"
                            fvg_order_tickets.pop(ticket, None)
                            save_runtime_state()
                            log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                            await tg(app, f"❌ *CLOSE SELL - Entry เขียว bid>=entry-spread*\n{sig_e} Ticket:`{ticket}`\nBid: `{bid_price}`\nEntry-Spread: `{entry_minus_spread:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                            print(f"[CLOSE_IMMEDIATE] SELL ticket={ticket} reason={reason} close={cp}")
                            if config.LIMIT_SWEEP:
                                tf_name = position_tf.get(ticket, "M1")
                                lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                                rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                                if rates_sweep is not None and len(rates_sweep) >= 6:
                                    reason_detail = f"แท่งจบเขียว body={body_pct_int}% bid>=entry-spread ปิดทันที"
                                    await _run_limit_sweep_followup(
                                        app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                    )
                            continue
                        else:
                            _entry_state[ticket] = "closing_fail"
                            save_runtime_state()
                            await tg(app, f"⚠️ *ปิด SELL ไม่สำเร็จ (entry เขียว bid>=entry-spread)*\n{sig_e} Ticket:`{ticket}`")

                elif bull and config.ENTRY_CANDLE_MODE == "close_percentage":
                    reason = f"entry_green body={body_pct_int}% mode=close_percentage immediate"
                    ok, cp = _close_position(pos, pos_type, "entry green candle close mode")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                        await tg(app, f"CLOSE SELL - Entry Green\n{sig_e} Ticket:`{ticket}`\nEntry Close: `{current_price:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                        print(f"[CLOSE_IMMEDIATE] SELL ticket={ticket} reason={reason} close={cp}")
                        if config.LIMIT_SWEEP and current_price > prev_high:
                            tf_name = position_tf.get(ticket, "M1")
                            lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                            rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                            if rates_sweep is not None and len(rates_sweep) >= 6:
                                reason_detail = f"แท่งจบเขียว close={current_price:.2f} > prev high={prev_high:.2f}"
                                await _run_limit_sweep_followup(
                                    app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                )
                        # close_percentage: close immediately only, no reverse market/limit
                        continue

                        tf_name = position_tf.get(ticket, "M1")
                        sid = position_sid.get(ticket, 1)
                        candle_range = entry_high - entry_low
                        rates_swing = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 120)
                        swing_info = _find_prev_swing_high(rates_swing) if rates_swing is not None else None
                        rev_tp = round(swing_info["price"], 2) if swing_info else None

                        if config.ENTRY_CLOSE_REVERSE_MARKET and rev_tp:
                            mkt_sl = round(entry_low - SL_BUFFER(), 2)
                            tick_r = mt5.symbol_info_tick(SYMBOL)
                            if tick_r:
                                vol = SYMBOL_CONFIG[SYMBOL]["volume"]
                                rev_r = mt5.order_send({
                                    "action":       mt5.TRADE_ACTION_DEAL,
                                    "symbol":       SYMBOL,
                                    "volume":       vol,
                                    "type":         mt5.ORDER_TYPE_BUY,
                                    "price":        float(tick_r.ask),
                                    "sl":           mkt_sl,
                                    "tp":           rev_tp,
                                    "deviation":    20,
                                    "magic":        234001,
                                    "comment":      f"{tf_name}_S{sid}_rev_market",
                                    "type_time":    mt5.ORDER_TIME_GTC,
                                    "type_filling": _get_filling_mode(),
                                })
                                if rev_r and rev_r.retcode == mt5.TRADE_RETCODE_DONE:
                                    rev_ticket = rev_r.order
                                    position_tf[rev_ticket] = tf_name
                                    position_sid[rev_ticket] = sid
                                    position_pattern[rev_ticket] = f"Reverse BUY (entry green) [{tf_name}]"
                                    _entry_state.pop(rev_ticket, None)
                                    save_runtime_state()
                                    log_event("ORDER_CREATED", "reverse_buy_market", ticket=rev_ticket, side="BUY", tf=tf_name, sl=mkt_sl, tp=rev_tp, price=float(tick_r.ask), from_ticket=ticket)
                                    await tg(app, f"🔄 *เปิด BUY Market (Reverse)*\n🟢 Ticket:`{rev_ticket}`\n📌 Entry: `{float(tick_r.ask):.2f}`\n🛑 SL: `{mkt_sl}` (Entry Low-SL_BUFFER)\n🎯 TP: `{rev_tp}` (Swing High)\n📊 TF: `{tf_name}`\n📝 จาก: `{ticket}`")
                                    print(f"[REVERSE_MARKET] BUY ticket={rev_ticket} entry={float(tick_r.ask):.2f} SL={mkt_sl} TP={rev_tp}")
                                else:
                                    rc = rev_r.retcode if rev_r else "None"
                                    cmt = rev_r.comment if rev_r else ""
                                    log_event("ORDER_FAILED", "reverse_buy_market", ticket=ticket, side="BUY", tf=tf_name, sl=mkt_sl, tp=rev_tp, price=float(tick_r.ask), retcode=rc, comment=cmt, from_ticket=ticket)
                                    print(f"[REVERSE_MARKET_FAIL] BUY retcode={rc} comment={cmt}")
                                    await tg(app, f"⚠️ *เปิด BUY Market Reverse ไม่สำเร็จ*\nretcode=`{rc}` {cmt}")

                        if config.ENTRY_CLOSE_REVERSE_LIMIT and rev_tp and candle_range > 0:
                            from mt5_utils import open_order
                            vol = SYMBOL_CONFIG[SYMBOL]["volume"]
                            lim_entry = round(entry_low - candle_range * 0.17, 2)
                            lim_sl = round(entry_low - candle_range * 0.31, 2)
                            res = open_order("BUY", vol, lim_sl, rev_tp, entry_price=lim_entry, tf=tf_name, sid=f"{sid}_rev_limit", pattern=f"Reverse BUY Limit (entry green) [{tf_name}]")
                            if res.get("success"):
                                rev_order = res["ticket"]
                                pending_order_tf[rev_order] = {
                                    "tf": tf_name, "gap_bot": lim_entry, "gap_top": lim_entry,
                                    "detect_bar_time": int(entry_bar["time"]),
                                    "signal": "BUY", "sid": sid,
                                    "pattern": f"Reverse BUY Limit (entry green) [{tf_name}]",
                                    "reverse": True,
                                }
                                save_runtime_state()
                                log_event("ORDER_CREATED", "reverse_buy_limit", ticket=rev_order, side="BUY", tf=tf_name, sl=lim_sl, tp=rev_tp, entry=lim_entry, from_ticket=ticket)
                                await tg(app, f"🔄 *ตั้ง BUY LIMIT (Reverse)*\n🟢 Ticket:`{rev_order}`\n📌 Entry: `{lim_entry:.2f}` (Low-17%)\n🛑 SL: `{lim_sl:.2f}` (Low-31%)\n🎯 TP: `{rev_tp}` (Swing High)\n📊 TF: `{tf_name}`\n📝 จาก: `{ticket}`")
                                print(f"[REVERSE_LIMIT] BUY ticket={rev_order} entry={lim_entry:.2f} SL={lim_sl:.2f} TP={rev_tp}")
                            else:
                                err = res.get("error", "unknown")
                                print(f"[REVERSE_LIMIT_FAIL] BUY error={err}")
                                await tg(app, f"⚠️ *ตั้ง BUY LIMIT Reverse ไม่สำเร็จ*\n{err}")

                        if not rev_tp:
                            print(f"[REVERSE_SKIP] BUY no swing high")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด SELL ไม่สำเร็จ (entry เขียว)*\n{sig_e} Ticket:`{ticket}`")

                elif bull and current_price >= pos.price_open:
                    rates_swing = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 120)
                    swing_info = _find_prev_swing_high(rates_swing) if rates_swing is not None else None
                    swing_sl = round(swing_info["price"] + 1.0, 2) if swing_info else round(entry_high + 1.0, 2)
                    bad_tp = round(float(entry_bar["open"]) + spread_price, 2)
                    reason = f"เขียว Low<{prev_low:.2f}" if entry_low < prev_low else (
                        f"เขียว body={body_pct_int}%>=65%" if body_pct >= 0.65 else f"เขียว body={body_pct_int}%<65%")
                    ok = _apply_entry_sl_tp(pos, swing_sl, bad_tp)
                    _entry_state[ticket] = "waiting_bad"
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_bad", ticket=ticket, side=pos_type, state="waiting_bad", reason=reason, sl=swing_sl, tp=bad_tp)
                    if ok:
                        title = f"⚠️ *SELL Entry เขียว -> waiting\\_bad*\n{sig_e} Ticket:`{ticket}` | {reason}"
                        msg = _entry_update_msg(title, sig_e, ticket, swing_sl, "swing high", bad_tp, "entry open")
                        await tg(app, msg)
                    print(f"⏳ [{now}] SELL {ticket} {reason} -> waiting_bad SL={swing_sl} TP={bad_tp}")

                elif bull:
                    new_sl = round(pos.price_open - 50.0, 2)
                    ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "done", ticket=ticket, side=pos_type, state="done", reason="green candle but current below entry", sl=new_sl, tp=pos.tp)
                    if ok:
                        await tg(app, _entry_update_msg(
                            "✅ *SELL Entry เขียว แต่ราคายังต่ำกว่า entry*",
                            sig_e, ticket, new_sl, "entry - 50"
                        ))
                    print(f"OK [{now}] SELL {ticket} green entry but current<{pos.price_open:.2f} -> SL={new_sl}")

        elif state == "closing_fail":
            # Retry close silently
            ok, cp = _close_position(pos, pos_type, "retry_close")
            if ok:
                _entry_state[ticket] = "done"
                save_runtime_state()
                await tg(app, f"✅ *retry ปิด {pos_type} สำเร็จ*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                print(f"OK [{now}] retry close {pos_type} {ticket} สำเร็จ @ {cp}")
            else:
                print(f"FAIL [{now}] retry close {pos_type} {ticket} ยังไม่สำเร็จ")
            continue

        elif state == "waiting_next":
            # Candle after entry
            if next_bar is None:
                continue

            bull_next, _, _ = bar_info(next_bar)
            next_c = float(next_bar["close"])
            entry_h = float(entry_bar["high"])
            entry_l = float(entry_bar["low"])

            if pos_type == "BUY":
                # Close when: red candle + Close < Low[entry]
                if not bull_next and next_c < entry_l:
                    ok, cp = _close_position(pos, pos_type, "waiting_next: red close < entry low")
                    if ok:
                        _entry_state[ticket] = "done"
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "waiting_next close", ticket=ticket, side=pos_type, state="done", close_price=cp, reason="red close < entry low")
                        await tg(app, f"❌ *ปิด BUY - แดง Close<Low[entry]*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                        print(f"❌ [{now}] ปิด BUY {ticket} แดง Close:{next_c:.2f}<Low[entry]:{entry_l:.2f}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด BUY ไม่สำเร็จ (waiting_next)*\n{sig_e} Ticket:`{ticket}`")
                else:
                # Pass -> set SL=next.low-1.0, TP=next.open (same as waiting_bad)
                    next_l = float(next_bar["low"])
                    next_o = float(next_bar["open"])
                    new_sl = round(next_l - 1.0, 2)
                    sl_note = "next low"
                    if new_sl < pos.price_open:
                        new_sl = round(pos.price_open + spread_price, 2)
                        sl_note = "entry+spread (next low < entry)"
                    new_tp = round(next_o - spread_price, 2)
                    tp_note = "next open - spread"
                    if new_tp < pos.price_open:
                        new_tp  = round(pos.price_open, 2)
                        tp_note = "entry (next open < entry)"
                    ok = _apply_entry_sl_tp(pos, new_sl, new_tp)
                    if not ok:
                        print(f"WARN [{now}] BUY {ticket} waiting_next modify SL failed sl={new_sl} -> retry next cycle")
                        continue
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_next done", ticket=ticket, side=pos_type, state="done", sl=new_sl, tp=new_tp, reason=tp_note)
                    await tg(app, _entry_update_msg(
                        "✅ *BUY waiting\\_next -> done*",
                        sig_e, ticket, new_sl, sl_note, new_tp, tp_note
                    ))
                    print(f"OK [{now}] BUY {ticket} waiting_next->done SL={new_sl} TP={new_tp} ({sl_note}, {tp_note})")

            else:  # SELL
                # Close when: green candle + Close > High[entry]
                if bull_next and next_c > entry_h:
                    ok, cp = _close_position(pos, pos_type, "waiting_next: green close > entry high")
                    if ok:
                        _entry_state[ticket] = "done"
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "waiting_next close", ticket=ticket, side=pos_type, state="done", close_price=cp, reason="green close > entry high")
                        await tg(app, f"❌ *ปิด SELL - เขียว Close>High[entry]*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                        print(f"❌ [{now}] ปิด SELL {ticket} เขียว Close:{next_c:.2f}>High[entry]:{entry_h:.2f}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด SELL ไม่สำเร็จ (waiting_next)*\n{sig_e} Ticket:`{ticket}`")
                else:
                    # Pass -> set SL=next.high+1.0, TP=next.open (same as waiting_bad)
                    next_h2 = float(next_bar["high"])
                    next_o  = float(next_bar["open"])
                    new_sl  = round(next_h2 + 1.0, 2)
                    sl_note = "next high"
                    if new_sl > pos.price_open:
                        new_sl = round(pos.price_open - spread_price, 2)
                        sl_note = "entry-spread (next high > entry)"
                    new_tp  = round(next_o + spread_price, 2)
                    tp_note = "next open + spread"
                    if new_tp > pos.price_open:
                        new_tp  = round(pos.price_open, 2)
                        tp_note = "entry (next open > entry)"
                    ok = _apply_entry_sl_tp(pos, new_sl, new_tp)
                    if not ok:
                        print(f"WARN [{now}] SELL {ticket} waiting_next modify SL failed sl={new_sl} -> retry next cycle")
                        continue
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_next done", ticket=ticket, side=pos_type, state="done", sl=new_sl, tp=new_tp, reason=tp_note)
                    await tg(app, _entry_update_msg(
                        "✅ *SELL waiting\\_next -> done*",
                        sig_e, ticket, new_sl, sl_note, new_tp, tp_note
                    ))
                    print(f"OK [{now}] SELL {ticket} waiting_next->done SL={new_sl} TP={new_tp} ({sl_note}, {tp_note})")

        elif state == "waiting_bad":
            # Candle after entry (red entry for BUY / green entry for SELL)
            if next_bar is None:
                continue

            next_c = float(next_bar["close"])
            next_h = float(next_bar["high"])
            next_l = float(next_bar["low"])

            if pos_type == "BUY":
                orig_tp = pos.tp  # original order TP
                if next_c >= pos.price_open:
                    print(f"[{now}] WAITING_BAD_CLOSE BUY ticket={ticket} next_close={next_c:.2f} entry={pos.price_open:.2f} next_high={next_h:.2f} next_low={next_l:.2f}")
                    ok, cp = _close_position(pos, pos_type, "waiting_bad: close >= entry")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "waiting_bad close", ticket=ticket, side=pos_type, state="done", close_price=cp, reason="close >= entry")
                        await tg(app, f"❌ *ปิด BUY -> waiting\\_bad close>=entry*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                        print(f"❌ [{now}] ปิด BUY {ticket} waiting_bad close:{next_c:.2f}>=entry:{pos.price_open:.2f}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด BUY ไม่สำเร็จ (waiting_bad)*\n{sig_e} Ticket:`{ticket}`")
                    continue
                    # close >= entry -> SL = entry + 0.5, TP unchanged
                    new_sl = round(pos.price_open + 0.5, 2)
                    new_tp = orig_tp
                    sl_note = "entry+0.5"
                else:
                    # close < entry -> SL = next.low - 1.0, TP unchanged
                    new_sl  = round(next_l - 1.0, 2)
                    new_tp  = orig_tp
                    sl_note = "next low"
                    if new_sl < pos.price_open:
                        new_sl = round(pos.price_open + spread_price, 2)
                        sl_note = "entry+spread (next low < entry)"
                    if new_tp < pos.price_open:
                        new_tp = round(pos.price_open, 2)
                ok = _apply_entry_sl_tp(pos, new_sl, new_tp)
                if not ok:
                    print(f"WARN [{now}] BUY {ticket} waiting_bad modify SL failed sl={new_sl} -> retry next cycle")
                    continue
                _entry_state[ticket] = "done"
                fvg_order_tickets.pop(ticket, None)
                save_runtime_state()
                log_event("ENTRY_QUALITY", "waiting_bad done", ticket=ticket, side=pos_type, state="done", sl=new_sl, tp=new_tp, reason=sl_note)
                await tg(app, _entry_update_msg(
                    "✅ *BUY waiting\\_bad -> done*",
                    sig_e, ticket, new_sl, sl_note, new_tp
                ))
                print(f"OK [{now}] BUY {ticket} waiting_bad->done SL={new_sl} TP={new_tp} ({sl_note})")

            else:  # SELL
                orig_tp = pos.tp  # original order TP
                if next_c <= pos.price_open:
                    print(f"[{now}] WAITING_BAD_CLOSE SELL ticket={ticket} next_close={next_c:.2f} entry={pos.price_open:.2f} next_high={next_h:.2f} next_low={next_l:.2f}")
                    ok, cp = _close_position(pos, pos_type, "waiting_bad: close <= entry")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "waiting_bad close", ticket=ticket, side=pos_type, state="done", close_price=cp, reason="close <= entry")
                        await tg(app, f"❌ *ปิด SELL -> waiting\\_bad close<=entry*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                        print(f"❌ [{now}] ปิด SELL {ticket} waiting_bad close:{next_c:.2f}<=entry:{pos.price_open:.2f}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด SELL ไม่สำเร็จ (waiting_bad)*\n{sig_e} Ticket:`{ticket}`")
                    continue
                    # close <= entry -> SL = entry - 0.5, TP unchanged
                    new_sl = round(pos.price_open - 0.5, 2)
                    new_tp = orig_tp
                    sl_note = "entry-0.5"
                else:
                    # close > entry -> SL = next.high + 1.0, TP unchanged
                    new_sl  = round(next_h + 1.0, 2)
                    new_tp  = orig_tp
                    sl_note = "next high"
                    if new_sl > pos.price_open:
                        new_sl = round(pos.price_open - spread_price, 2)
                        sl_note = "entry-spread (next high > entry)"
                    if new_tp > pos.price_open:
                        new_tp = round(pos.price_open, 2)
                ok = _apply_entry_sl_tp(pos, new_sl, new_tp)
                if not ok:
                    print(f"WARN [{now}] SELL {ticket} waiting_bad modify SL failed sl={new_sl} -> retry next cycle")
                    continue
                _entry_state[ticket] = "done"
                fvg_order_tickets.pop(ticket, None)
                save_runtime_state()
                log_event("ENTRY_QUALITY", "waiting_bad done", ticket=ticket, side=pos_type, state="done", sl=new_sl, tp=new_tp, reason=sl_note)
                await tg(app, _entry_update_msg(
                    "✅ *SELL waiting\\_bad -> done*",
                    sig_e, ticket, new_sl, sl_note, new_tp
                ))
                print(f"OK [{now}] SELL {ticket} waiting_bad->done SL={new_sl} TP={new_tp} ({sl_note})")


# -------------------------------------------------------------
async def check_engulf_trail_sl(app):
    """
    Trail SL by TF group.
    phase 1: check engulf on lower TFs in the group (group[1:]) -> move SL -> enter phase 2
    phase 2: check engulf on the order TF itself (group[0]) -> move SL -> done

    combined mode:
    - merge phases by TF group
    - check every TF in the group each cycle
    - keep moving SL when a better engulf result appears

    Groups from TRAIL_GROUPS:
      D1  -> [D1, H12, H4]
      H12 -> [H12, H4, H1]
      ...
      M1  -> [M1]
    """
    global _last_trail_tg_key
    if not getattr(config, "TRAIL_SL_ENABLED", True):
        return
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        _bar_count.clear()
        _trail_state.clear()
        _trend_filter_last_dir.clear()
        return

    # Cleanup tickets that are already closed
    open_tickets = {p.ticket for p in positions}
    for t in list(_trail_state.keys()):
        if t not in open_tickets:
            _trail_state.pop(t, None)
    for key in list(_trend_filter_last_dir.keys()):
        try:
            t = int(str(key).split("|", 1)[0])
        except (TypeError, ValueError):
            _trend_filter_last_dir.pop(key, None)
            continue
        if t not in open_tickets:
            _trend_filter_last_dir.pop(key, None)
    for t in list(_fill_notified.keys()):
        if t not in open_tickets:
            _fill_notified.pop(t, None)
    for t in list(_entry_bar_notified.keys()):
        if t not in open_tickets:
            _entry_bar_notified.pop(t, None)
    for t in list(_fill_rsi_checked):
        if t not in open_tickets:
            _fill_rsi_checked.discard(t)

    now = now_bkk().strftime("%H:%M:%S")

    # Trail SL Focus Opposite (frozen_side marker)
    # Same side as marker -> freeze every position (do not trail)
    # Opposite side -> allow trailing only after the gate passes
    focus_skip_tickets: set[int] = set()
    if getattr(config, "TRAIL_SL_FOCUS_NEW_ENABLED", False):
        pending_focus = mt5.orders_get(symbol=SYMBOL) or []
        frozen_side_ts = _focus_update_frozen_side("trail_sl", positions, pending_focus)
        if frozen_side_ts is not None:
            for p in positions:
                p_side = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                if p_side == frozen_side_ts:
                    focus_skip_tickets.add(p.ticket)
                elif not _focus_gate_passed(
                    "trail_sl", frozen_side_ts, positions, position_tf.get(p.ticket)
                ):
                    focus_skip_tickets.add(p.ticket)

    for pos in positions:
        ticket   = pos.ticket
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        sid      = position_sid.get(ticket)
        if sid in (10, 12, 13):
            continue
        # Resolve order timeframe
        fvg_info = fvg_order_tickets.get(ticket)
        order_tf = position_tf.get(ticket, "M1")
        if fvg_info:
            order_tf = fvg_info.get("tf", "M1")

        if not config.TRAIL_SL_IMMEDIATE and _entry_state.get(ticket) != "done":
            continue

        # Trail SL only when price is beyond entry:
        # above entry for BUY, below entry for SELL
        tick = mt5.symbol_info_tick(SYMBOL)
        if tick:
            if pos_type == "BUY" and tick.bid <= pos.price_open:
                continue
            if pos_type == "SELL" and tick.ask >= pos.price_open:
                continue

        trend_override, trend_override_reason = _trend_filter_trail_override(ticket, pos_type, order_tf)
        reversal_override, reversal_sl, reversal_override_reason = _reversal_trail_override(
            pos_type, order_tf, float(pos.sl)
        )
        if ticket in focus_skip_tickets and not trend_override and not reversal_override:
            continue

        mode = getattr(config, "TRAIL_SL_ENGULF_MODE", "separate")

        # init trail state
        if ticket not in _trail_state:
            group = TRAIL_GROUPS.get(order_tf, [order_tf])
            # combined = keep checking every TF in the group continuously
            if mode == "combined":
                phase = 0
            else:
                # phase 1 when smaller TFs exist, otherwise start at phase 2
                phase = 1 if len(group) > 1 else 2
            _trail_state[ticket] = {"phase": phase, "order_tf": order_tf}

        state    = _trail_state[ticket]
        phase    = state["phase"]
        group    = TRAIL_GROUPS.get(order_tf, [order_tf])

        # Phase 2 already done -> stop trailing (separate mode only)
        if mode != "combined" and phase > 2:
            continue

        # Choose TFs to inspect in this phase
        if mode == "combined":
            check_tfs = group
        elif phase == 1:
            # Check smaller TFs first, e.g. H4 order -> H1, M30
            check_tfs = group[1:] if len(group) > 1 else group
        else:
            # phase 2: check only the order TF itself
            check_tfs = [group[0]]

        new_sl       = 0.0
        engulf_found = False
        engulf_tf    = None
        label        = ""

        for tf_name in check_tfs:
            tf_val   = TF_OPTIONS.get(tf_name, mt5.TIMEFRAME_M1)
            lookback = min(TF_LOOKBACK.get(tf_name, SWING_LOOKBACK), 50)
            rates    = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback)
            if rates is None or len(rates) < 3:
                continue

            # Find the entry bar
            entry_bar_time = 0
            for r in rates:
                t = int(r["time"])
                if t <= pos.time and t > entry_bar_time:
                    entry_bar_time = t
            if entry_bar_time == 0:
                continue

            bars_after = [r for r in rates if int(r["time"]) >= entry_bar_time]
            if len(bars_after) < 2:
                continue

            # Count closed bars since entry
            cur_bar_time = int(bars_after[-1]["time"])
            key_last = f"{ticket}_{tf_name}_last"
            if cur_bar_time != _bar_count.get(key_last, 0):
                _bar_count[key_last] = cur_bar_time
                _bar_count[f"{ticket}_{tf_name}"] = _bar_count.get(f"{ticket}_{tf_name}", 0) + 1

            # Find the best engulf candidate in this TF
            current_sl = pos.sl
            found_in_tf = False
            for i in range(1, len(bars_after)):
                cur  = bars_after[i]; prev = bars_after[i-1]
                cur_c = float(cur["close"]); cur_o = float(cur["open"])
                cur_h = float(cur["high"]);  cur_l = float(cur["low"])
                prev_h = float(prev["high"]); prev_l = float(prev["low"])
                bull   = cur_c > cur_o

                if pos_type == "BUY" and bull and cur_c > prev_h:
                    candidate = round(cur_l - 1.0, 2)
                    if candidate > current_sl:
                        current_sl = candidate; found_in_tf = True

                elif pos_type == "SELL" and not bull and cur_c < prev_l:
                    candidate = round(cur_h + 1.0, 2)
                    if current_sl == 0 or candidate < current_sl:
                        current_sl = candidate; found_in_tf = True

            if found_in_tf and current_sl != pos.sl:
                # Keep the TF that gives the best SL
                if pos_type == "BUY" and (new_sl == 0 or current_sl > new_sl):
                    new_sl = current_sl; engulf_found = True
                    engulf_tf = tf_name; label = f"Trail SL [{tf_name}] Engulf"
                elif pos_type == "SELL" and (new_sl == 0 or current_sl < new_sl):
                    new_sl = current_sl; engulf_found = True
                    engulf_tf = tf_name; label = f"Trail SL [{tf_name}] Engulf"

        # Protective SL if no engulf appears within 3 bars
        if not engulf_found:
            if reversal_override and reversal_sl > 0:
                new_sl = reversal_sl
                label = f"Trail SL [{order_tf}] Reversal"
            main_tf  = group[0]
            key_cnt  = f"{ticket}_{main_tf}"
            bar_cnt  = _bar_count.get(key_cnt, 0)
            if new_sl == 0 and bar_cnt >= 3:
                entry_price = pos.price_open
                if pos_type == "BUY":
                    safe = round(entry_price + 0.5, 2)
                    if safe > pos.sl:
                        new_sl = safe; label = f"SL Protect [{main_tf}] +50pt"
                else:
                    safe = round(entry_price - 0.5, 2)
                    if pos.sl == 0 or safe < pos.sl:
                        new_sl = safe; label = f"SL Protect [{main_tf}] -50pt"

        # Check whether the latest closed candle is already beyond entry
        main_tf_val = TF_OPTIONS.get(group[0], mt5.TIMEFRAME_M1)
        latest_rates = mt5.copy_rates_from_pos(SYMBOL, main_tf_val, 1, 1)
        entry_price  = pos.price_open
        price_past_entry = False
        if latest_rates is not None and len(latest_rates) > 0:
            latest_close = float(latest_rates[0]["close"])
            if pos_type == "BUY" and latest_close > entry_price:
                price_past_entry = True
            elif pos_type == "SELL" and latest_close < entry_price:
                price_past_entry = True

        if new_sl > 0:
            old_sl = float(pos.sl)
            if _modify_sl(pos, new_sl):
                sig_e = "🟢" if pos_type == "BUY" else "🔴"

                # Advance phase only after price closes beyond entry
                if engulf_found and mode == "combined":
                    phase_note = f"combined mode (found on {engulf_tf}, keep trailing SL)"
                elif engulf_found:
                    if phase == 1:
                        if price_past_entry:
                            _trail_state[ticket]["phase"] = 2
                            save_runtime_state()
                            phase_note = f"phase 1->2 (found on {engulf_tf}, price passed entry)"
                        else:
                            phase_note = f"phase 1 pending (found on {engulf_tf}, waiting for price to pass entry)"
                    else:  # phase 2
                        if price_past_entry:
                            _trail_state[ticket]["phase"] = 3  # done
                            save_runtime_state()
                            phase_note = f"phase 2->done (found on {engulf_tf}, price passed entry)"
                        else:
                            phase_note = f"phase 2 pending (found on {engulf_tf}, waiting for price to pass entry)"
                else:
                    phase_note = "reversal override" if reversal_override else "SL Protect"
                if trend_override:
                    phase_note = f"{phase_note} | override {trend_override_reason}"
                if reversal_override:
                    phase_note = f"{phase_note} | {reversal_override_reason}" if phase_note else reversal_override_reason

                log_event(
                    "SL_CHANGED",
                    "trail_engulf" if engulf_found else "trail_safe",
                    ticket=ticket,
                    side=pos_type,
                    tf=order_tf,
                    old_sl=old_sl,
                    new_sl=float(new_sl),
                    reason=phase_note,
                    source=(engulf_tf if engulf_found else group[0]),
                    trend_override=trend_override,
                )
                trail_tg_key = f"{ticket}|{label}|{old_sl:.2f}|{float(new_sl):.2f}|{phase_note}"
                if trail_tg_key != _last_trail_tg_key:
                    await tg(app, (f"📐 *{label} - {pos_type}*\n"
                              f"{sig_e} Ticket:`{ticket}` [{order_tf}]\n"
                              f"🛑 SL: `{old_sl}` -> `{new_sl}`\n"
                              f"📋 {phase_note}"))
                    _last_trail_tg_key = trail_tg_key
                print(f"📐 [{now}] {label} {pos_type} {ticket}: {old_sl}->{new_sl} | {phase_note}")


# -------------------------------------------------------------
async def check_opposite_order_tp(app):
    """
    Opposite-side TP handling within the same timeframe:
    1) BUY position in profit + SELL limit -> set BUY TP to SELL limit entry
    2) SELL position in profit + BUY limit -> set SELL TP to BUY limit entry
    3) If both BUY and SELL positions exist on the same TF, handle them by the configured mode
    """
    if not getattr(config, "OPPOSITE_ORDER_ENABLED", True):
        return
    positions = mt5.positions_get(symbol=SYMBOL)
    pending   = mt5.orders_get(symbol=SYMBOL)
    if not positions:
        return

    global _last_sl_protect_tg_key
    open_tickets = {p.ticket for p in positions}
    for t in list(_sl_protect_applied):
        if t not in open_tickets:
            _sl_protect_applied.discard(t)

    now      = now_bkk().strftime("%H:%M:%S")
    buy_pos  = [p for p in positions if p.type == mt5.ORDER_TYPE_BUY and position_sid.get(p.ticket) not in (10, 12, 13)]
    sell_pos = [p for p in positions if p.type == mt5.ORDER_TYPE_SELL and position_sid.get(p.ticket) not in (10, 12, 13)]

    def _get_order_tf(ticket):
        info = pending_order_tf.get(ticket)
        if isinstance(info, dict):
            return info.get("tf")
        return info

    def _get_order_sid(ticket):
        info = pending_order_tf.get(ticket)
        if isinstance(info, dict):
            return info.get("sid")
        return None

    opp_mode = config.OPPOSITE_ORDER_MODE  # "tp_close" | "sl_protect"

    if pending and opp_mode == "tp_close":
        buy_lim  = [o for o in pending if o.type == mt5.ORDER_TYPE_BUY_LIMIT and _get_order_sid(o.ticket) not in (10, 12, 13)]
        sell_lim = [o for o in pending if o.type == mt5.ORDER_TYPE_SELL_LIMIT and _get_order_sid(o.ticket) not in (10, 12, 13)]

        # BUY position in profit + SELL limit on same TF -> BUY TP = SELL limit entry
        for pos in buy_pos:
            if pos.profit <= 0:
                continue
            pos_tf = position_tf.get(pos.ticket)
            if not pos_tf:
                continue
            for ord_ in sell_lim:
                ord_tf = _get_order_tf(ord_.ticket)
                if ord_tf != pos_tf:
                    continue
                se = ord_.price_open
                if _price_differs(pos.tp, se, 0.5):
                    old_sl, old_tp = float(pos.sl), float(pos.tp)
                    r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                                        "position": pos.ticket, "sl": pos.sl, "tp": se})
                    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                    _audit_sltp_event("opposite_tp:buy_link", pos, old_sl, old_tp, float(pos.sl), float(se), ok, r)
                    if ok:
                        log_event(
                            "TP_CHANGED",
                            "opposite_tp_buy_link",
                            ticket=pos.ticket,
                            side="BUY",
                            tf=pos_tf,
                            old_tp=old_tp,
                            new_tp=float(se),
                            old_sl=old_sl,
                            new_sl=float(pos.sl),
                        )
                        await _notify_sltp_audit(app, "opposite_tp:buy_link", pos, old_sl, old_tp, float(pos.sl), float(se), True)
                        if _trade_debug_enabled():
                            print(f"🔄 [{now}] BUY {pos.ticket} [{pos_tf}] TP->{se}")

        # SELL position in profit + BUY limit on same TF -> SELL TP = BUY limit entry
        for pos in sell_pos:
            if pos.profit <= 0:
                continue
            pos_tf = position_tf.get(pos.ticket)
            if not pos_tf:
                continue
            for ord_ in buy_lim:
                ord_tf = _get_order_tf(ord_.ticket)
                if ord_tf != pos_tf:
                    continue
                be = ord_.price_open
                if _price_differs(pos.tp, be, 0.5):
                    old_sl, old_tp = float(pos.sl), float(pos.tp)
                    r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                                        "position": pos.ticket, "sl": pos.sl, "tp": be})
                    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                    _audit_sltp_event("opposite_tp:sell_link", pos, old_sl, old_tp, float(pos.sl), float(be), ok, r)
                    if ok:
                        log_event(
                            "TP_CHANGED",
                            "opposite_tp_sell_link",
                            ticket=pos.ticket,
                            side="SELL",
                            tf=pos_tf,
                            old_tp=old_tp,
                            new_tp=float(be),
                            old_sl=old_sl,
                            new_sl=float(pos.sl),
                        )
                        await _notify_sltp_audit(app, "opposite_tp:sell_link", pos, old_sl, old_tp, float(pos.sl), float(be), True)
                        if _trade_debug_enabled():
                            print(f"🔄 [{now}] SELL {pos.ticket} [{pos_tf}] TP->{be}")

    # Both BUY and SELL positions exist on the same TF
    if buy_pos and sell_pos:
        spread = _get_spread_price()
        for bp in buy_pos:
            bp_tf = position_tf.get(bp.ticket)
            if not bp_tf:
                continue
            for sp in sell_pos:
                sp_tf = position_tf.get(sp.ticket)
                if sp_tf != bp_tf:
                    continue

                if opp_mode == "tp_close":
                    # tp_close: close the older position
                    if bp.time > sp.time:
                        ok, cp = _close_position(sp, "SELL", f"Close SELL - BUY filled [{bp_tf}]")
                        if ok:
                            await tg(app, (f"❒ *ปิด SELL - BUY Limit Fill [{bp_tf}]*\n"
                                      f"🔴 Ticket:`{sp.ticket}` ปิดที่`{cp}`"))
                            print(f"❒ [{now}] ปิด SELL {sp.ticket} BUY fill [{bp_tf}]")
                    elif sp.time > bp.time:
                        ok, cp = _close_position(bp, "BUY", f"Close BUY - SELL filled [{bp_tf}]")
                        if ok:
                            await tg(app, (f"❒ *ปิด BUY - SELL Limit Fill [{bp_tf}]*\n"
                                      f"🟢 Ticket:`{bp.ticket}` ปิดที่`{cp}`"))
                            print(f"❒ [{now}] ปิด BUY {bp.ticket} SELL fill [{bp_tf}]")

                else:
                    # sl_protect: set SL to entry +/- spread without closing
                    if bp.time > sp.time:
                        # BUY filled later -> protect SELL with entry - spread
                        new_sl = round(sp.price_open - spread, 2)
                        if sp.ticket in _sl_protect_applied:
                            continue
                        if _price_differs(sp.sl, new_sl, 0.3):
                            old_sl, old_tp = float(sp.sl), float(sp.tp)
                            r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                                                "position": sp.ticket, "sl": new_sl, "tp": sp.tp})
                            ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                            _audit_sltp_event("opposite_sl:sell_protect", sp, old_sl, old_tp, float(new_sl), float(sp.tp), ok, r)
                            if ok:
                                _sl_protect_applied.add(sp.ticket)
                                log_event(
                                    "SL_CHANGED",
                                    "sl_protect_sell_fill",
                                    ticket=sp.ticket,
                                    side="SELL",
                                    tf=bp_tf,
                                    old_sl=old_sl,
                                    new_sl=float(new_sl),
                                    old_tp=old_tp,
                                    new_tp=float(sp.tp),
                                )
                                protect_tg_key = f"SELL|{sp.ticket}|{bp_tf}|{old_sl:.2f}|{new_sl:.2f}"
                                if protect_tg_key != _last_sl_protect_tg_key:
                                    await tg(app, (f"🛡️ *SELL SL Protect - BUY Fill [{bp_tf}]*\n"
                                                  f"🔴 Ticket:`{sp.ticket}`\n"
                                                  f"🛑 SL: `{old_sl:.2f}` -> `{new_sl:.2f}` (entry-spread)"))
                                    _last_sl_protect_tg_key = protect_tg_key
                                print(f"🛡️ [{now}] SELL {sp.ticket} SL->{new_sl} (entry={sp.price_open:.2f}-spread={spread:.2f})")
                    elif sp.time > bp.time:
                        # SELL filled later -> protect BUY with entry + spread
                        new_sl = round(bp.price_open + spread, 2)
                        if bp.ticket in _sl_protect_applied:
                            continue
                        if _price_differs(bp.sl, new_sl, 0.3):
                            old_sl, old_tp = float(bp.sl), float(bp.tp)
                            r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                                                "position": bp.ticket, "sl": new_sl, "tp": bp.tp})
                            ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                            _audit_sltp_event("opposite_sl:buy_protect", bp, old_sl, old_tp, float(new_sl), float(bp.tp), ok, r)
                            if ok:
                                _sl_protect_applied.add(bp.ticket)
                                log_event(
                                    "SL_CHANGED",
                                    "sl_protect_buy_fill",
                                    ticket=bp.ticket,
                                    side="BUY",
                                    tf=bp_tf,
                                    old_sl=old_sl,
                                    new_sl=float(new_sl),
                                    old_tp=old_tp,
                                    new_tp=float(bp.tp),
                                )
                                protect_tg_key = f"BUY|{bp.ticket}|{bp_tf}|{old_sl:.2f}|{new_sl:.2f}"
                                if protect_tg_key != _last_sl_protect_tg_key:
                                    await tg(app, (f"🛡️ *BUY SL Protect - SELL Fill [{bp_tf}]*\n"
                                                  f"🟢 Ticket:`{bp.ticket}`\n"
                                                  f"🛑 SL: `{old_sl:.2f}` -> `{new_sl:.2f}` (entry+spread)"))
                                    _last_sl_protect_tg_key = protect_tg_key
                                print(f"🛡️ [{now}] BUY {bp.ticket} SL->{new_sl} (entry={bp.price_open:.2f}+spread={spread:.2f})")


async def check_breakeven_tp(app):
    """
    Breakeven TP logic for every strategy.
    After the entry candle, if price moves against the position and the latest
    closed candle shows a rejection/engulf pattern, set TP back to entry.

    BUY:
      price below entry and latest candle closes red:
        - engulf: Close < Low[prev]
        - rejection: Low[cur] < Low[prev] and Close stays inside prev body

    SELL:
      price above entry and latest candle closes green:
        - engulf: Close > High[prev]
        - rejection: High[cur] > High[prev] and Close stays inside prev body
    """
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        return

    now = now_bkk().strftime("%H:%M:%S")

    for pos in positions:
        ticket   = pos.ticket
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        entry    = pos.price_open

        # Only after entry candle flow is done
        if _entry_state.get(ticket) != "done":
            continue

        # TP already equals entry -> nothing to do
        if abs(pos.tp - entry) < 0.5:
            continue

        # Timeframe of this order
        fvg_info = fvg_order_tickets.get(ticket)
        pos_tf_name = position_tf.get(ticket, "M1")
        if fvg_info:
            tf_val = TF_OPTIONS.get(fvg_info.get("tf","M1"), mt5.TIMEFRAME_M1)
        else:
            tf_val = TF_OPTIONS.get(pos_tf_name, mt5.TIMEFRAME_M1)

        rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, 10)
        if rates is None or len(rates) < 3:
            continue

        # Latest closed candle and previous candle
        cur  = rates[-1]
        prev = rates[-2]

        cur_o  = float(cur["open"]);  cur_c  = float(cur["close"])
        cur_h  = float(cur["high"]);  cur_l  = float(cur["low"])
        prev_o = float(prev["open"]); prev_c = float(prev["close"])
        prev_h = float(prev["high"]); prev_l = float(prev["low"])
        bull_cur = cur_c > cur_o

        trigger = False
        reason  = ""

        if pos_type == "BUY":
            # Price moved below entry
            tick = mt5.symbol_info_tick(SYMBOL)
            if not tick or tick.bid >= entry:
                continue
            if not bull_cur:  # latest candle closes red
                # engulf: Close < Low[prev]
                if cur_c < prev_l:
                    trigger = True
                    reason  = f"แดงกลืนกิน Close:{cur_c:.2f} < Low[prev]:{prev_l:.2f}"
                # rejection: Low[cur] < Low[prev] and Close remains in prev range
                elif cur_l < prev_l and prev_l <= cur_c <= prev_h:
                    trigger = True
                    reason  = f"แดงปฏิเสธ Low:{cur_l:.2f} < Low[prev]:{prev_l:.2f}"

        else:  # SELL
            tick = mt5.symbol_info_tick(SYMBOL)
            if not tick or tick.ask <= entry:
                continue
            if bull_cur:  # latest candle closes green
                # engulf: Close > High[prev]
                if cur_c > prev_h:
                    trigger = True
                    reason  = f"เขียวกลืนกิน Close:{cur_c:.2f} > High[prev]:{prev_h:.2f}"
                # rejection: High[cur] > High[prev] and Close remains in prev range
                elif cur_h > prev_h and prev_l <= cur_c <= prev_h:
                    trigger = True
                    reason  = f"เขียวปฏิเสธ High:{cur_h:.2f} > High[prev]:{prev_h:.2f}"

        if trigger:
            print(f"[{now}] 🎯 DEBUG breakeven: {pos_type} {ticket} entry={entry} tp_now={pos.tp} cur={cur_c:.2f} prev_h={prev_h:.2f} prev_l={prev_l:.2f} ask/bid={(mt5.symbol_info_tick(SYMBOL).ask if pos_type=='SELL' else mt5.symbol_info_tick(SYMBOL).bid):.2f}")
            old_sl = float(pos.sl)
            old_tp = float(pos.tp)
            r = mt5.order_send({
                "action":   mt5.TRADE_ACTION_SLTP,
                "symbol":   SYMBOL,
                "position": ticket,
                "sl":       pos.sl,
                "tp":       entry,
            })
            ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
            _audit_sltp_event("check_breakeven_tp", pos, old_sl, old_tp, float(pos.sl), float(entry), ok, r)
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                await _notify_sltp_audit(app, "check_breakeven_tp", pos, old_sl, old_tp, float(pos.sl), float(entry), True)
                sig_e = "🟢" if pos_type == "BUY" else "🔴"
                await tg(app, (
                        f"🎯 *ตั้ง TP = Breakeven*\n"
                        f"{sig_e} Ticket:`{ticket}` [{pos_tf_name}]\n"
                        f"TP: `{pos.tp}` -> `{entry}` (entry)\n"
                        f"เหตุผล: {reason}"
                    ))
                if _trade_debug_enabled():
                    print(f"🎯 [{now}] Breakeven {pos_type} {ticket}: TP->{entry} ({reason})")


async def _s6_process_ticket(app, pos, positions, state_dict, mode_tag, now,
                             _find_prev_swing_high, _find_prev_swing_low, strategy_1):
    """
    Shared core logic for strategy 6.
    Used by both the original S6 flow and the independent S6i flow.
    mode_tag is either "S6" or "S6i" for logging.
    """
    ticket   = pos.ticket
    pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    sig_e    = "🟢" if pos_type == "BUY" else "🔴"
    entry    = pos.price_open

    tf_name  = position_tf.get(ticket, "M1")
    tf_val   = TF_OPTIONS.get(tf_name, mt5.TIMEFRAME_M1)
    lookback = min(TF_LOOKBACK.get(tf_name, SWING_LOOKBACK) + 6, 60)
    rates    = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback)
    if rates is None or len(rates) < 5:
        return

    # Check strategy 1 on every scan, both in wait and count phases
    r1 = strategy_1(rates)
    s1_signal = r1.get("signal", "WAIT")
    s1_entry  = r1.get("entry", 0)
    s1_is_opposite = (pos_type == "BUY" and s1_signal == "SELL") or \
                     (pos_type == "SELL" and s1_signal == "BUY")

    if s1_is_opposite:
        st = state_dict.get(ticket)
        in_wait_phase = st is None or st.get("phase") == "wait"

        if in_wait_phase:
            if s1_entry > 0:
                new_tp = round(s1_entry, 2)
                if _tp_valid_for_side(pos_type, entry, new_tp, 0.01):
                    old_sl = float(pos.sl)
                    old_tp = float(pos.tp)
                    r = mt5.order_send({
                        "action":   mt5.TRADE_ACTION_SLTP,
                        "symbol":   SYMBOL,
                        "position": ticket,
                        "sl":       pos.sl,
                        "tp":       new_tp,
                    })
                    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                    _audit_sltp_event(f"{mode_tag}:s1_entry", pos, old_sl, old_tp, float(pos.sl), float(new_tp), ok, r)
                    if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                        await _notify_sltp_audit(app, f"{mode_tag}:s1_entry", pos, old_sl, old_tp, float(pos.sl), float(new_tp), True)
                        if ticket not in state_dict:
                            state_dict[ticket] = {}
                        state_dict[ticket]["tp_set_by_s1"] = new_tp
                        await tg(app, (f"🎯 *{mode_tag} ตั้ง TP = ท่า1 Entry*\n"
                                  f"{sig_e} Ticket:`{ticket}` [{tf_name}]\n"
                                  f"ท่า1 {s1_signal} entry={s1_entry:.2f}\n"
                                  f"TP: `{pos.tp}` -> `{new_tp:.2f}`"))
                        if _trade_debug_enabled():
                            print(f"🎯 [{now}] {mode_tag} {ticket} TP->{new_tp:.2f} (ท่า1 {s1_signal})")
                else:
                    print(f"WARN [{now}] {mode_tag} skip invalid TP from S1 entry ticket={ticket} type={pos_type} entry={entry:.2f} new_tp={new_tp:.2f}")
        else:
            sell_positions = [p for p in positions
                              if p.type == mt5.ORDER_TYPE_SELL and p.ticket != ticket]
            if sell_positions or st.get("tp_set_by_s1"):
                ok, cp = _close_position(pos, pos_type, f"{mode_tag}: ท่า1 opposite trigger")
                if ok:
                    state_dict.pop(ticket, None)
                    await tg(app, (f"❒ *ปิด {pos_type} {mode_tag} - ท่า1 {s1_signal} trigger*\n"
                              f"{sig_e} Ticket:`{ticket}` [{tf_name}] ปิดที่`{cp:.2f}`"))
                    print(f"❒ [{now}] {mode_tag} ปิด {pos_type} {ticket} ท่า1 trigger")
                return

    # Init state
    if ticket not in state_dict:
        if pos_type == "BUY":
            sh_info = _find_prev_swing_high(rates)
            swing_ref = sh_info["price"] if sh_info else None
        else:
            sl_info = _find_prev_swing_low(rates)
            swing_ref = sl_info["price"] if sl_info else None

        if not swing_ref:
            return
        state_dict[ticket] = {
            "swing_h": swing_ref,
            "phase":   "wait",
            "count":   0,
            "last_bar_time": 0,
            "trail_count": 0,
        }
        print(f"🆕 [{now}] {mode_tag} {pos_type} {ticket} init swing={swing_ref:.2f}")

    st = state_dict[ticket]
    swing_h = st["swing_h"]

    # Latest closed candle
    cur_bar = rates[-1]
    cur_time = int(cur_bar["time"])
    cur_h  = float(cur_bar["high"])
    cur_l  = float(cur_bar["low"])
    cur_c  = float(cur_bar["close"])
    cur_o  = float(cur_bar["open"])
    bull   = cur_c > cur_o

    # Phase "wait": wait for price to touch swing_h
    if st["phase"] == "wait":
        touched = (pos_type == "BUY" and cur_h >= swing_h) or \
                  (pos_type == "SELL" and cur_l <= swing_h)
        if touched:
            st["phase"] = "count"
            st["count"] = 0
            st["last_bar_time"] = 0
            print(f"🎯 [{now}] {mode_tag} {ticket} touched swing={swing_h:.2f} start counting")
        return

    # Phase "count": count 1-5 candles
    if cur_time == st["last_bar_time"]:
        return  # Same candle, do not count twice

    st["last_bar_time"] = cur_time
    st["count"] += 1

    if pos_type == "BUY":
        broke_out = bull and cur_c > swing_h
    else:
        broke_out = (not bull) and cur_c < swing_h

    if broke_out:
        # Trail SL
        if pos_type == "BUY":
            new_sl = round(cur_l - 1.0, 2)
            if new_sl < entry and new_sl > pos.sl:
                if _modify_sl(pos, new_sl):
                    st["trail_count"] += 1
                    await tg(app, (f"📐 *{mode_tag} Trail SL รอบ{st['trail_count']} - BUY*\n"
                              f"{sig_e} Ticket:`{ticket}` [{tf_name}]\n"
                              f"แท่งปิดเหนือ Swing:{swing_h:.2f}\n"
                              f"O:`{cur_o:.2f}` H:`{cur_h:.2f}` L:`{cur_l:.2f}` C:`{cur_c:.2f}`\n"
                              f"🛑 SL: `{pos.sl}` -> `{new_sl}`"))
                    print(f"📐 [{now}] {mode_tag} Trail BUY {ticket}: {pos.sl}->{new_sl}")
            else:
                print(f"WARN [{now}] {mode_tag} Trail BUY {ticket}: new_sl={new_sl} invalid (entry={entry} pos.sl={pos.sl})")
        else:
            new_sl = round(cur_h + 1.0, 2)
            if new_sl > entry and (pos.sl == 0 or new_sl < pos.sl):
                if _modify_sl(pos, new_sl):
                    st["trail_count"] += 1
                    await tg(app, (f"📐 *{mode_tag} Trail SL รอบ{st['trail_count']} - SELL*\n"
                              f"{sig_e} Ticket:`{ticket}` [{tf_name}]\n"
                              f"แท่งปิดใต้ Swing:{swing_h:.2f}\n"
                              f"O:`{cur_o:.2f}` H:`{cur_h:.2f}` L:`{cur_l:.2f}` C:`{cur_c:.2f}`\n"
                              f"🛑 SL: `{pos.sl}` -> `{new_sl}`"))
                    print(f"📐 [{now}] {mode_tag} Trail SELL {ticket}: {pos.sl}->{new_sl}")
            else:
                print(f"WARN [{now}] {mode_tag} Trail SELL {ticket}: new_sl={new_sl} invalid (entry={entry} pos.sl={pos.sl})")

        # Find a new swing from the breakout candle -> reset state
        if pos_type == "BUY":
            sh_info = _find_prev_swing_high(rates)
            new_swing = sh_info["price"] if sh_info and sh_info["price"] > swing_h else None
        else:
            sl_info = _find_prev_swing_low(rates)
            new_swing = sl_info["price"] if sl_info and sl_info["price"] < swing_h else None

        if new_swing:
            st["swing_h"] = new_swing
            st["phase"]   = "wait"
            st["count"]   = 0
            print(f"🔄 [{now}] {mode_tag} {ticket} new swing={new_swing:.2f} wait for touch")
        else:
            state_dict.pop(ticket, None)
            print(f"OK [{now}] {mode_tag} {ticket} no new swing, done")

    elif st["count"] >= 5:
        # Reached 5 candles without breakout -> set TP to entry
        old_sl = float(pos.sl)
        old_tp = float(pos.tp)
        r = mt5.order_send({
            "action":   mt5.TRADE_ACTION_SLTP,
            "symbol":   SYMBOL,
            "position": ticket,
            "sl":       pos.sl,
            "tp":       entry,
        })
        ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
        _audit_sltp_event(f"{mode_tag}:count5_breakeven", pos, old_sl, old_tp, float(pos.sl), float(entry), ok, r)
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            await _notify_sltp_audit(app, f"{mode_tag}:count5_breakeven", pos, old_sl, old_tp, float(pos.sl), float(entry), True)
            state_dict.pop(ticket, None)
            await tg(app, (f"🎯 *{mode_tag} TP = Breakeven*\n"
                      f"{sig_e} Ticket:`{ticket}` ครบ 5 แท่งไม่ผ่าน swing\n"
                      f"TP -> `{entry}`"))
            print(f"🎯 [{now}] {mode_tag} {ticket} TP=entry={entry}")


# S6i helpers: check S1/S3 patterns without using zone filters

def _has_s1_sell_pattern(rates):
    """S1 SELL pattern without zone filter: green[2]->red[1]->red[0] close<low[1]."""
    if len(rates) < 4:
        return False
    o0, h0, l0, c0 = [float(rates[-1][k]) for k in ('open','high','low','close')]
    o1, h1, l1, c1 = [float(rates[-2][k]) for k in ('open','high','low','close')]
    o2, h2, l2, c2 = [float(rates[-3][k]) for k in ('open','high','low','close')]
    bull0, bull1, bull2 = c0 > o0, c1 > o1, c2 > o2
    return bull2 and not bull1 and not bull0 and c0 < l1


def _has_s1_buy_pattern(rates):
    """S1 BUY pattern without zone filter: red[2]->green[1]->green[0] close>high[1]."""
    if len(rates) < 4:
        return False
    o0, h0, l0, c0 = [float(rates[-1][k]) for k in ('open','high','low','close')]
    o1, h1, l1, c1 = [float(rates[-2][k]) for k in ('open','high','low','close')]
    o2, h2, l2, c2 = [float(rates[-3][k]) for k in ('open','high','low','close')]
    bull0, bull1, bull2 = c0 > o0, c1 > o1, c2 > o2
    return not bull2 and bull1 and bull0 and c0 > h1


def _has_s3_sell_pattern(rates):
    """S3 SP SELL pattern without zone filter: red[2] body>=35% -> green/doji[1] -> red[0] close<low[1]."""
    if len(rates) < 4:
        return False
    o0, h0, l0, c0 = [float(rates[-1][k]) for k in ('open','high','low','close')]
    o1, h1, l1, c1 = [float(rates[-2][k]) for k in ('open','high','low','close')]
    o2, h2, l2, c2 = [float(rates[-3][k]) for k in ('open','high','low','close')]
    r2 = h2 - l2; b2 = abs(c2 - o2)
    bull0, bull1, bull2 = c0 > o0, c1 > o1, c2 > o2
    bp2 = (b2 / r2 * 100) if r2 > 0 else 0
    r1 = h1 - l1; doji1 = (abs(c1 - o1) / r1 * 100 if r1 > 0 else 0) < 10
    return not bull2 and bp2 >= 35 and (bull1 or doji1) and not bull0 and c0 < l1


def _has_s3_buy_pattern(rates):
    """S3 SP BUY pattern without zone filter: green[2] body>=35% -> red/doji[1] -> green[0] close>high[1]."""
    if len(rates) < 4:
        return False
    o0, h0, l0, c0 = [float(rates[-1][k]) for k in ('open','high','low','close')]
    o1, h1, l1, c1 = [float(rates[-2][k]) for k in ('open','high','low','close')]
    o2, h2, l2, c2 = [float(rates[-3][k]) for k in ('open','high','low','close')]
    r2 = h2 - l2; b2 = abs(c2 - o2)
    bull0, bull1, bull2 = c0 > o0, c1 > o1, c2 > o2
    bp2 = (b2 / r2 * 100) if r2 > 0 else 0
    r1 = h1 - l1; doji1 = (abs(c1 - o1) / r1 * 100 if r1 > 0 else 0) < 10
    return bull2 and bp2 >= 35 and (not bull1 or doji1) and bull0 and c0 > h1


def _has_opposite_order_near(side, price, tolerance=2.0):
    """Return True when a pending order on the given side is near the target price."""
    orders = mt5.orders_get(symbol=SYMBOL)
    if not orders:
        return False
    otype = mt5.ORDER_TYPE_SELL_LIMIT if side == "SELL" else mt5.ORDER_TYPE_BUY_LIMIT
    return any(o.type == otype and abs(o.price_open - price) <= tolerance for o in orders)


# S6i: independent strategy 6 state machine

async def _s6i_process_ticket(app, pos, now,
                              _find_prev_swing_high, _find_prev_swing_low):
    """
    S6i - 2 High 2 Low Independent.
    Phase: watch -> count -> wait_swing2 -> order_placed

    SELL: find swing HIGH (resistance) -> check pattern -> set TP/order
    BUY:  find swing LOW (support)     -> mirrored logic
    """
    ticket   = pos.ticket
    pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    sig_e    = "🟢" if pos_type == "BUY" else "🔴"
    is_buy   = pos_type == "BUY"

    tf_name  = position_tf.get(ticket, "M1")
    tf_val   = TF_OPTIONS.get(tf_name, mt5.TIMEFRAME_M1)
    lookback = min(TF_LOOKBACK.get(tf_name, SWING_LOOKBACK) + 6, 60)
    rates    = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback)
    if rates is None or len(rates) < 5:
        return

    # Side-dependent references
    find_swing    = _find_prev_swing_low  if is_buy else _find_prev_swing_high
    find_swing_tp = _find_prev_swing_high if is_buy else _find_prev_swing_low
    has_s1        = _has_s1_buy_pattern   if is_buy else _has_s1_sell_pattern
    has_s3        = _has_s3_buy_pattern   if is_buy else _has_s3_sell_pattern
    order_side    = "BUY" if is_buy else "SELL"
    opp_lim_type  = mt5.ORDER_TYPE_SELL_LIMIT if is_buy else mt5.ORDER_TYPE_BUY_LIMIT
    our_lim_type  = mt5.ORDER_TYPE_BUY_LIMIT  if is_buy else mt5.ORDER_TYPE_SELL_LIMIT

    # Init: find swing, check S1/S3 pattern, set TP
    if ticket not in _s6i_state:
        sw_info   = find_swing(rates)
        swing_ref = sw_info["price"] if sw_info else None
        if not swing_ref:
            return

        s1_found = (has_s1(rates) or has_s3(rates) or
                    _has_opposite_order_near(order_side, swing_ref))

        tp_source = None
        if not s1_found:
            # TP = entry of opposite limit (strategy 2/3) or swing TP
            pending = mt5.orders_get(symbol=SYMBOL)
            opp_entry = None
            if pending:
                opp_limits = [o for o in pending if o.type == opp_lim_type]
                if opp_limits:
                    opp_entry  = opp_limits[0].price_open
                    tp_source  = opp_limits[0].ticket

            if opp_entry is None:
                sw_tp = find_swing_tp(rates)
                opp_entry = sw_tp["price"] if sw_tp else None

            if opp_entry and abs(pos.tp - opp_entry) > 0.5 and _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
                old_sl = float(pos.sl)
                old_tp = float(pos.tp)
                r = mt5.order_send({
                    "action":   mt5.TRADE_ACTION_SLTP,
                    "symbol":   SYMBOL,
                    "position": ticket,
                    "sl":       pos.sl,
                    "tp":       round(opp_entry, 2),
                })
                ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                _audit_sltp_event("S6i:init_tp", pos, old_sl, old_tp, float(pos.sl), round(opp_entry, 2), ok, r)
                if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                    log_event(
                        "TP_CHANGED",
                        "s6i_init_tp",
                        ticket=ticket,
                        side=pos_type,
                        tf=tf_name,
                        old_tp=old_tp,
                        new_tp=round(opp_entry, 2),
                        old_sl=old_sl,
                        new_sl=float(pos.sl),
                    )
                    await _notify_sltp_audit(app, "S6i:init_tp", pos, old_sl, old_tp, float(pos.sl), round(opp_entry, 2), True)
                    await tg(app, (f"🎯 *S6i ตั้ง TP - {pos_type}*\n"
                              f"{sig_e} Ticket:`{ticket}` [{tf_name}]\n"
                              f"TP: `{pos.tp}` -> `{opp_entry:.2f}`"))
                    if _trade_debug_enabled():
                        print(f"🎯 [{now}] S6i {ticket} TP->{opp_entry:.2f}")
            elif opp_entry and not _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
                print(f"WARN [{now}] S6i skip invalid TP ticket={ticket} type={pos_type} entry={pos.price_open:.2f} new_tp={opp_entry:.2f}")

        _s6i_state[ticket] = {
            "swing_h1":   swing_ref,
            "phase":      "watch",
            "s1_found":   s1_found,
            "count":      0,
            "last_bar_time": 0,
            "swing_h2":   None,
            "order_ticket": None,
            "tp_source":  tp_source,
        }
        print(f"🆕 [{now}] S6i {pos_type} {ticket} init swing={swing_ref:.2f} s1={s1_found}")

    st     = _s6i_state[ticket]
    swing1 = st["swing_h1"]

    # Monitor: close the position when the opposite limit fills
    if st.get("tp_source"):
        pending = mt5.orders_get(symbol=SYMBOL)
        still_exists = pending and any(o.ticket == st["tp_source"] for o in pending)
        if not still_exists:
            ok, cp = _close_position(pos, pos_type, "S6i: opposite limit filled")
            if ok:
                _s6i_state.pop(ticket, None)
                await tg(app, (f"❒ *ปิด {pos_type} S6i - ฝั่งตรงข้าม fill*\n"
                          f"{sig_e} Ticket:`{ticket}` [{tf_name}] ปิดที่`{cp:.2f}`"))
                print(f"❒ [{now}] S6i ปิด {pos_type} {ticket} opposite fill")
            return

    # Current bar
    cur_bar  = rates[-1]
    cur_time = int(cur_bar["time"])
    cur_c    = float(cur_bar["close"])
    cur_o    = float(cur_bar["open"])
    cur_h    = float(cur_bar["high"])
    cur_l    = float(cur_bar["low"])
    bull     = cur_c > cur_o

    # Phase: watch -> wait to see whether the candle closes beyond swing
    if st["phase"] == "watch":
        if cur_time == st["last_bar_time"]:
            return
        st["last_bar_time"] = cur_time

        # SELL: green close > swing_h1 -> breakout -> find a new swing
        # BUY:  red close < swing_l1 -> breakout -> find a new swing
        broke_out     = (bull and cur_c > swing1) if not is_buy else (not bull and cur_c < swing1)
        # SELL: green close <= swing_h1 -> enter count
        # BUY:  red close >= swing_l1 -> enter count
        trigger_count = (bull and cur_c <= swing1) if not is_buy else (not bull and cur_c >= swing1)

        if broke_out:
            sw_info  = find_swing(rates)
            new_sw   = sw_info["price"] if sw_info else None
            if new_sw:
                s1_found = (has_s1(rates) or has_s3(rates) or
                            _has_opposite_order_near(order_side, new_sw))
                st["swing_h1"] = new_sw
                st["s1_found"] = s1_found
                st["count"]    = 0

                if not s1_found:
                    # Update TP
                    pending = mt5.orders_get(symbol=SYMBOL)
                    opp_entry = None
                    if pending:
                        opp_limits = [o for o in pending if o.type == opp_lim_type]
                        if opp_limits:
                            opp_entry = opp_limits[0].price_open
                            st["tp_source"] = opp_limits[0].ticket
                    if opp_entry is None:
                        sw_tp = find_swing_tp(rates)
                        opp_entry = sw_tp["price"] if sw_tp else None
                        st["tp_source"] = None
                    if opp_entry and abs(pos.tp - opp_entry) > 0.5 and _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
                        old_sl = float(pos.sl)
                        old_tp = float(pos.tp)
                        r = mt5.order_send({
                            "action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                            "position": ticket, "sl": pos.sl, "tp": round(opp_entry, 2),
                        })
                        ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                        _audit_sltp_event("S6i:new_swing_tp", pos, old_sl, old_tp, float(pos.sl), round(opp_entry, 2), ok, r)
                        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                            log_event(
                                "TP_CHANGED",
                                "s6i_new_swing_tp",
                                ticket=ticket,
                                side=pos_type,
                                tf=tf_name,
                                old_tp=old_tp,
                                new_tp=round(opp_entry, 2),
                                old_sl=old_sl,
                                new_sl=float(pos.sl),
                            )
                            await _notify_sltp_audit(app, "S6i:new_swing_tp", pos, old_sl, old_tp, float(pos.sl), round(opp_entry, 2), True)
                            if _trade_debug_enabled():
                                print(f"🎯 [{now}] S6i {ticket} TP->{opp_entry:.2f} (new swing)")
                    elif opp_entry and not _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
                        print(f"WARN [{now}] S6i skip invalid TP at new swing ticket={ticket} type={pos_type} entry={pos.price_open:.2f} new_tp={opp_entry:.2f}")

                print(f"🔄 [{now}] S6i {ticket} new swing={new_sw:.2f} s1={s1_found}")
            return

        if trigger_count:
            st["phase"] = "count"
            st["count"] = 1
            print(f"📊 [{now}] S6i {ticket} watch->count")
            return

    # Phase: count -> count 1-5 candles
    elif st["phase"] == "count":
        if cur_time == st["last_bar_time"]:
            return
        st["last_bar_time"] = cur_time
        st["count"] += 1

        prev_h = float(rates[-2]["high"])
        prev_l = float(rates[-2]["low"])

        # SELL: green close > swing_h1 and > prev_high -> breakout -> restart
        # BUY:  red close < swing_l1 and < prev_low  -> breakout -> restart
        if not is_buy:
            breakout = bull and cur_c > swing1 and cur_c > prev_h
        else:
            breakout = not bull and cur_c < swing1 and cur_c < prev_l

        if breakout:
            sw_info = find_swing(rates)
            new_sw  = sw_info["price"] if sw_info else None
            if new_sw:
                s1_found = (has_s1(rates) or has_s3(rates) or
                            _has_opposite_order_near(order_side, new_sw))
                st["swing_h1"] = new_sw
                st["s1_found"] = s1_found
                st["phase"]    = "watch"
                st["count"]    = 0
                print(f"🔄 [{now}] S6i {ticket} count->watch new swing={new_sw:.2f}")
            return

        # Reached 5 candles -> look for swing2
        if st["count"] >= 5:
            sw2_info = find_swing(rates)
            if not is_buy:
                swing2 = sw2_info["price"] if sw2_info and sw2_info["price"] > swing1 + 0.5 else None
            else:
                swing2 = sw2_info["price"] if sw2_info and sw2_info["price"] < swing1 - 0.5 else None

            if swing2:
                await _s6i_on_swing2(app, pos, pos_type, rates, st, swing1, swing2,
                                     now, sig_e, tf_name, ticket, is_buy,
                                     has_s1, has_s3, order_side, our_lim_type,
                                     find_swing_tp)
            else:
                st["phase"] = "wait_swing2"
                print(f"INFO [{now}] S6i {ticket} reached 5 candles without swing2 -> wait")

    # Phase: wait_swing2 -> wait for the second swing
    elif st["phase"] == "wait_swing2":
        if cur_time == st["last_bar_time"]:
            return
        st["last_bar_time"] = cur_time

        sw2_info = find_swing(rates)
        if not is_buy:
            swing2 = sw2_info["price"] if sw2_info and sw2_info["price"] > swing1 + 0.5 else None
        else:
            swing2 = sw2_info["price"] if sw2_info and sw2_info["price"] < swing1 - 0.5 else None

        if swing2:
            await _s6i_on_swing2(app, pos, pos_type, rates, st, swing1, swing2,
                                 now, sig_e, tf_name, ticket, is_buy,
                                 has_s1, has_s3, order_side, our_lim_type,
                                 find_swing_tp)

    # Phase: order_placed -> monitor the placed SELL/BUY limit
    elif st["phase"] == "order_placed":
        order_ticket = st.get("order_ticket")
        swing2       = st.get("swing_h2")
        if not order_ticket:
            _s6i_state.pop(ticket, None)
            return

        # Does the order still exist?
        orders = mt5.orders_get(symbol=SYMBOL)
        order_exists = orders and any(o.ticket == order_ticket for o in orders)
        if not order_exists:
            _s6i_state.pop(ticket, None)
            print(f"OK [{now}] S6i {ticket} order {order_ticket} filled/cancelled -> done")
            return

        # Engulf through swing2 -> cancel the order
        if swing2:
            cancel = (bull and cur_c > swing2) if not is_buy else (not bull and cur_c < swing2)
            if cancel:
                r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": order_ticket})
                if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                    _s6i_state.pop(ticket, None)
                    await tg(app, (f"❌ *S6i ยกเลิก - กลืนกิน swing2*\n"
                              f"📝 Order:`{order_ticket}` ยกเลิก"))
                    print(f"❌ [{now}] S6i cancel {order_ticket} engulf swing2")


async def _s6i_on_swing2(app, pos, pos_type, rates, st, swing1, swing2,
                         now, sig_e, tf_name, ticket, is_buy,
                         has_s1, has_s3, order_side, our_lim_type,
                         find_swing_tp):
    """Handle swing 2: check S1/S3 pattern, then place an order or keep waiting."""
    st["swing_h2"] = swing2
    s1_at_2 = (has_s1(rates) or has_s3(rates) or
               _has_opposite_order_near(order_side, swing2))

    if s1_at_2:
        # S1/S3 found at swing2 -> wait for the normal limit and set TP from opposite limit
        opp_lim_type = mt5.ORDER_TYPE_SELL_LIMIT if is_buy else mt5.ORDER_TYPE_BUY_LIMIT
        pending = mt5.orders_get(symbol=SYMBOL)
        opp_entry = None
        if pending:
            opp_limits = [o for o in pending if o.type == opp_lim_type]
            if opp_limits:
                opp_entry = opp_limits[0].price_open
                st["tp_source"] = opp_limits[0].ticket
        if opp_entry is None:
            sw_tp = find_swing_tp(rates)
            opp_entry = sw_tp["price"] if sw_tp else None
            st["tp_source"] = None

        if opp_entry and abs(pos.tp - opp_entry) > 0.5 and _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
            old_sl = float(pos.sl)
            old_tp = float(pos.tp)
            r = mt5.order_send({
                "action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                "position": ticket, "sl": pos.sl, "tp": round(opp_entry, 2),
            })
            ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
            _audit_sltp_event("S6i:swing2_tp", pos, old_sl, old_tp, float(pos.sl), round(opp_entry, 2), ok, r)
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                log_event(
                    "TP_CHANGED",
                    "s6i_swing2_tp",
                    ticket=ticket,
                    side=pos_type,
                    tf=tf_name,
                    old_tp=old_tp,
                    new_tp=round(opp_entry, 2),
                    old_sl=old_sl,
                    new_sl=float(pos.sl),
                )
                await _notify_sltp_audit(app, "S6i:swing2_tp", pos, old_sl, old_tp, float(pos.sl), round(opp_entry, 2), True)
                if _trade_debug_enabled():
                    print(f"🎯 [{now}] S6i {ticket} TP->{opp_entry:.2f} (S1/S3 at swing2)")
        elif opp_entry and not _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
            print(f"WARN [{now}] S6i skip invalid TP at swing2 ticket={ticket} type={pos_type} entry={pos.price_open:.2f} new_tp={opp_entry:.2f}")

        st["phase"] = "watch"
        st["swing_h1"] = swing2
        st["count"] = 0
        print(f"OK [{now}] S6i {ticket} swing2={swing2:.2f} S1/S3 found -> keep watching")
    else:
        # No S1/S3 -> place a limit order at swing1
        sw_tp_info = find_swing_tp(rates)
        tp_price   = sw_tp_info["price"] if sw_tp_info else None
        if not tp_price:
            print(f"WARN [{now}] S6i {ticket} no swing TP found -> skip")
            _s6i_state.pop(ticket, None)
            return

        # SELL: SL = swing_h2 + 100pt | BUY: SL = swing_l2 - 100pt
        sl_price = round(swing2 + 1.0, 2) if not is_buy else round(swing2 - 1.0, 2)
        vol      = SYMBOL_CONFIG[SYMBOL]["volume"]

        r = mt5.order_send({
            "action":       mt5.TRADE_ACTION_PENDING,
            "symbol":       SYMBOL,
            "volume":       vol,
            "type":         our_lim_type,
            "price":        round(swing1, 2),
            "sl":           sl_price,
            "tp":           round(tp_price, 2),
            "deviation":    20,
            "magic":        0,
            "comment":      f"{tf_name}_S6i_{pos_type.lower()}",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": _get_filling_mode(),
        })
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            st["order_ticket"] = r.order
            st["phase"]        = "order_placed"
            side_label = "SELL" if not is_buy else "BUY"
            swing_label = f"H1:`{swing1:.2f}` H2:`{swing2:.2f}`" if not is_buy \
                          else f"L1:`{swing1:.2f}` L2:`{swing2:.2f}`"
            await tg(app, (f"📌 *S6i {side_label} LIMIT*\n"
                      f"{sig_e} [{tf_name}] Ticket:`{ticket}`\n"
                      f"📌 Entry:`{swing1:.2f}` SL:`{sl_price:.2f}` TP:`{tp_price:.2f}`\n"
                      f"Swing {swing_label}\n"
                      f"📝 Order:`{r.order}`"))
            print(f"📌 [{now}] S6i {side_label} LIMIT at {swing1:.2f} SL={sl_price} TP={tp_price}")
        else:
            retcode = r.retcode if r else "None"
            print(f"❌ [{now}] S6i order FAIL retcode={retcode}")
            _s6i_state.pop(ticket, None)


async def check_s6_trail(app):
    """
    Strategy 6 - 2 High 2 Low Trail SL.
    - Original S6: continues from positions opened by strategy 2/3
    - S6i: scans swings and places new orders for positions with entry done
    Both modes can run together.
    """
    from strategy1 import strategy_1

    s6_on  = active_strategies.get(6, False)
    s6i_on = active_strategies.get(7, False)

    if not s6_on and not s6i_on:
        return

    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        _s6_state.clear()
        _s6i_state.clear()
        return

    open_tickets = {p.ticket for p in positions}
    for t in list(_s6_state.keys()):
        if t not in open_tickets:
            _s6_state.pop(t, None)
    for t in list(_s6i_state.keys()):
        if t not in open_tickets:
            _s6i_state.pop(t, None)

    now = now_bkk().strftime("%H:%M:%S")

    for pos in positions:
        ticket   = pos.ticket
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        sid      = position_sid.get(ticket)
        state    = _entry_state.get(ticket)

        if state != "done":
            continue

        # Original S6: only sid 2/3
        if s6_on and sid in (2, 3):
            if _trade_debug_enabled():
                print(f"[{now}] 🔍 S6: {pos_type} {ticket} sid={sid}")
            await _s6_process_ticket(app, pos, positions, _s6_state, "S6", now,
                                     _get_s6_prev_swing_high, _get_s6_prev_swing_low, strategy_1)

        # S6i: every position not already tracked by original S6
        if s6i_on and ticket not in _s6_state:
            if _trade_debug_enabled():
                print(f"[{now}] 🔍 S6i: {pos_type} {ticket} sid={sid}")
            await _s6i_process_ticket(app, pos, now,
                                      _get_s6_prev_swing_high, _get_s6_prev_swing_low)


async def check_cancel_pending_orders(app):
    """
    Auto cancel limit orders when setup is no longer valid:
    BUY LIMIT:  price closes above the main swing high of that TF -> remove it
    SELL LIMIT: price closes below the main swing low of that TF  -> remove it

    Main swing high/low means max/min from the TF lookback window.
    """
    orders = mt5.orders_get(symbol=SYMBOL)
    if not orders:
        pending_order_tf.clear()
        return

    now = now_bkk().strftime("%H:%M:%S")
    open_tickets = {o.ticket for o in orders}

    # Cleanup tickets that no longer exist
    for t in list(pending_order_tf.keys()):
        if t not in open_tickets:
            info = pending_order_tf.pop(t, None)
            position_tf.pop(t, None)
            position_sid.pop(t, None)
            position_pattern.pop(t, None)
            if isinstance(info, dict):
                log_event(
                    "ORDER_CANCELED",
                    "Pending disappeared from MT5 order list",
                    tf=info.get("tf", ""),
                    sid=info.get("sid", ""),
                    signal=info.get("signal", ""),
                    ticket=t,
                    entry=info.get("entry"),
                    sl=info.get("sl"),
                    tp=info.get("tp"),
                    flow_id=info.get("flow_id", ""),
                    parent_flow_id=info.get("parent_flow_id", ""),
                )

    for order in orders:
        ticket = order.ticket
        info   = pending_order_tf.get(ticket)
        if not info:
            continue
        tf = info.get("tf") if isinstance(info, dict) else info

        # Use the smallest TF (check_tf) for candle quality checks
        # Use the main TF for swing high/low
        check_tf = position_tf.get(ticket) or tf

        tf_val   = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        lookback = TF_LOOKBACK.get(tf, SWING_LOOKBACK)
        rates    = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 6)
        if rates is None or len(rates) < 5:
            continue

        # Main swing high/low = max/min over the full TF lookback
        swing_high = max(float(r["high"]) for r in rates)
        swing_low  = min(float(r["low"])  for r in rates)

        last_close = float(rates[-1]["close"])

        # Candle quality uses check_tf (the smaller TF)
        check_tf_val   = TF_OPTIONS.get(check_tf, mt5.TIMEFRAME_M1)
        check_lookback = min(TF_LOOKBACK.get(check_tf, SWING_LOOKBACK) + 6, 50)
        candle_rates   = mt5.copy_rates_from_pos(SYMBOL, check_tf_val, 1, check_lookback)
        if candle_rates is None:
            candle_rates = rates

        should_cancel = False
        reason = ""

        # S10 HTF sweep recheck: once the next HTF bar starts, confirm that the original sweep bar is still valid
        if (
            isinstance(info, dict)
            and info.get("sid") == 10
            and not info.get("s10_sweep_checked")
            and info.get("s10_htf_tf")
            and info.get("s10_parent_time")
            and info.get("s10_sweep_time")
        ):
            from strategy10 import is_s10_htf_sweep_valid

            s10_htf_tf = info.get("s10_htf_tf") or tf
            s10_tf_val = TF_OPTIONS.get(s10_htf_tf, tf_val)
            s10_cur_bar = mt5.copy_rates_from_pos(SYMBOL, s10_tf_val, 0, 1)
            if s10_cur_bar is not None and len(s10_cur_bar) > 0:
                s10_cur_open = int(s10_cur_bar[0]["time"])
                s10_sweep_time = int(info.get("s10_sweep_time", 0) or 0)
                if s10_cur_open > s10_sweep_time:
                    s10_rates = mt5.copy_rates_from_pos(SYMBOL, s10_tf_val, 1, max(TF_LOOKBACK.get(s10_htf_tf, SWING_LOOKBACK) + 6, 50))
                    if s10_rates is not None and len(s10_rates) > 1:
                        parent_bar = next((r for r in s10_rates if int(r["time"]) == int(info.get("s10_parent_time", 0) or 0)), None)
                        sweep_bar = next((r for r in s10_rates if int(r["time"]) == s10_sweep_time), None)
                        if parent_bar is not None and sweep_bar is not None:
                            s10_valid = is_s10_htf_sweep_valid(parent_bar, sweep_bar, info.get("signal", ""), info.get("s10_bar_mode", ""))
                            if not s10_valid:
                                log_event(
                                    "S10_SWEEP_RECHECK",
                                    "FAIL",
                                    ticket=ticket,
                                    tf=tf,
                                    htf_tf=s10_htf_tf,
                                    signal=info.get("signal", ""),
                                    side=info.get("signal", ""),
                                    sweep_time=fmt_mt5_bkk_ts(s10_sweep_time, "%H:%M %d-%b-%Y"),
                                    parent_time=fmt_mt5_bkk_ts(int(info.get("s10_parent_time", 0) or 0), "%H:%M %d-%b-%Y"),
                                )
                                should_cancel = True
                                reason = (
                                    f"S10 Sweep Recheck [{s10_htf_tf}]: sweep bar "
                                    f"{fmt_mt5_bkk_ts(s10_sweep_time, '%H:%M %d-%b-%Y')} is no longer a valid sweep"
                                )
                            else:
                                info["s10_sweep_checked"] = True
                                pending_order_tf[ticket] = info
                                save_runtime_state()
                                log_event(
                                    "S10_SWEEP_RECHECK",
                                    "PASS",
                                    ticket=ticket,
                                    tf=tf,
                                    htf_tf=s10_htf_tf,
                                    signal=info.get("signal", ""),
                                    side=info.get("signal", ""),
                                    sweep_time=fmt_mt5_bkk_ts(s10_sweep_time, "%H:%M %d-%b-%Y"),
                                    parent_time=fmt_mt5_bkk_ts(int(info.get("s10_parent_time", 0) or 0), "%H:%M %d-%b-%Y"),
                                )

        # S10 pending invalidation: if SELL has already touched parent low before fill, cancel immediately
        if (
            not should_cancel
            and isinstance(info, dict)
            and info.get("sid") == 10
            and str(info.get("signal", "")).upper() == "SELL"
            and float(info.get("s10_parent_low", 0.0) or 0.0) > 0.0
        ):
            s10_parent_low = float(info.get("s10_parent_low", 0.0) or 0.0)
            s10_parent_time = int(info.get("s10_parent_time", 0) or 0)
            mon_tf = str(info.get("tf") or tf or "M1")
            mon_tf_val = TF_OPTIONS.get(mon_tf, mt5.TIMEFRAME_M1)
            mon_tf_secs = max(1, _get_tf_seconds(mon_tf_val))
            now_ref_ts = int(candle_rates[-1]["time"]) if candle_rates is not None and len(candle_rates) > 0 else int(time.time())
            bars_needed = max(10, min(500, int((max(0, now_ref_ts - s10_parent_time) // mon_tf_secs) + 10)))
            mon_rates = mt5.copy_rates_from_pos(SYMBOL, mon_tf_val, 0, bars_needed)
            touched_bar = None
            if mon_rates is not None and len(mon_rates) > 0:
                for _bar in mon_rates:
                    if int(_bar["time"]) <= s10_parent_time:
                        continue
                    if float(_bar["low"]) <= s10_parent_low:
                        touched_bar = _bar
                        break
            tick = mt5.symbol_info_tick(SYMBOL)
            cur_bid = float(getattr(tick, "bid", 0.0) or 0.0) if tick else 0.0
            if touched_bar is not None or (cur_bid > 0 and cur_bid <= s10_parent_low):
                touched_txt = ""
                if touched_bar is not None:
                    touched_txt = (
                        f" @ {fmt_mt5_bkk_ts(int(touched_bar['time']), '%H:%M %d-%b-%Y')} "
                        f"(L:{float(touched_bar['low']):.2f})"
                    )
                elif cur_bid > 0:
                    touched_txt = f" @ now (Bid:{cur_bid:.2f})"
                should_cancel = True
                reason = (
                    f"S10 Parent Low Touch Cancel [{info.get('s10_htf_tf', tf)}->{mon_tf}]: "
                    f"SELL pending touched parent low {s10_parent_low:.2f} before fill{touched_txt}"
                )

        # S10 pending invalidation: if BUY has already touched parent high before fill, cancel immediately
        if (
            not should_cancel
            and isinstance(info, dict)
            and info.get("sid") == 10
            and str(info.get("signal", "")).upper() == "BUY"
            and float(info.get("s10_parent_high", 0.0) or 0.0) > 0.0
        ):
            s10_parent_high = float(info.get("s10_parent_high", 0.0) or 0.0)
            s10_parent_time = int(info.get("s10_parent_time", 0) or 0)
            mon_tf = str(info.get("tf") or tf or "M1")
            mon_tf_val = TF_OPTIONS.get(mon_tf, mt5.TIMEFRAME_M1)
            mon_tf_secs = max(1, _get_tf_seconds(mon_tf_val))
            now_ref_ts = int(candle_rates[-1]["time"]) if candle_rates is not None and len(candle_rates) > 0 else int(time.time())
            bars_needed = max(10, min(500, int((max(0, now_ref_ts - s10_parent_time) // mon_tf_secs) + 10)))
            mon_rates = mt5.copy_rates_from_pos(SYMBOL, mon_tf_val, 0, bars_needed)
            touched_bar = None
            if mon_rates is not None and len(mon_rates) > 0:
                for _bar in mon_rates:
                    if int(_bar["time"]) <= s10_parent_time:
                        continue
                    if float(_bar["high"]) >= s10_parent_high:
                        touched_bar = _bar
                        break
            tick = mt5.symbol_info_tick(SYMBOL)
            cur_ask = float(getattr(tick, "ask", 0.0) or 0.0) if tick else 0.0
            if touched_bar is not None or (cur_ask > 0 and cur_ask >= s10_parent_high):
                touched_txt = ""
                if touched_bar is not None:
                    touched_txt = (
                        f" @ {fmt_mt5_bkk_ts(int(touched_bar['time']), '%H:%M %d-%b-%Y')} "
                        f"(H:{float(touched_bar['high']):.2f})"
                    )
                elif cur_ask > 0:
                    touched_txt = f" @ now (Ask:{cur_ask:.2f})"
                should_cancel = True
                reason = (
                    f"S10 Parent High Touch Cancel [{info.get('s10_htf_tf', tf)}->{mon_tf}]: "
                    f"BUY pending touched parent high {s10_parent_high:.2f} before fill{touched_txt}"
                )

        _order_sid = info.get("sid") if isinstance(info, dict) else None

        # Limit TP/SL Break Cancel: cancel when a confirmed candle breaks TP/SL on the selected TF
        # Skip S2 pattern 1 (green engulfing / red engulfing) by design
        # Skip S10 (CRT TBS) — managed by parent touch cancel instead
        _skip_break = (
            _order_sid == 10
            or (
                isinstance(info, dict)
                and info.get("sid") == 2
                and info.get("c3_type") in ("เขียวกลืนกิน", "แดงกลืนกิน")
            )
        )
        if (
            not should_cancel
            and not _skip_break
            and config.LIMIT_BREAK_CANCEL
            and config.LIMIT_BREAK_CANCEL_TF.get(tf, False)
            and len(rates) >= 2
        ):
            cur_bar = rates[-1]
            prev_bar = rates[-2]
            limit_tp = float(order.tp or 0.0)
            limit_sl = float(order.sl or 0.0)
            if not limit_sl and isinstance(info, dict):
                limit_sl = float(info.get("intended_sl", 0.0) or 0.0)

            if order.type == mt5.ORDER_TYPE_BUY_LIMIT:
                if limit_tp > 0 and _is_green_engulf_break(cur_bar, prev_bar, limit_tp):
                    should_cancel = True
                    reason = (
                        f"TP Break Cancel [{tf}]: BUY LIMIT got a confirmed green break above TP "
                        f"close:{_bar_close(cur_bar):.2f} > TP:{limit_tp:.2f} "
                        f"& engulf High[prev]:{_bar_high(prev_bar):.2f}"
                    )
                elif limit_sl > 0 and _is_red_engulf_break(cur_bar, prev_bar, limit_sl):
                    should_cancel = True
                    reason = (
                        f"SL Break Cancel [{tf}]: BUY LIMIT got a confirmed red break below SL "
                        f"close:{_bar_close(cur_bar):.2f} < SL:{limit_sl:.2f} "
                        f"& engulf Low[prev]:{_bar_low(prev_bar):.2f}"
                    )

            elif order.type == mt5.ORDER_TYPE_SELL_LIMIT:
                if limit_tp > 0 and _is_red_engulf_break(cur_bar, prev_bar, limit_tp):
                    should_cancel = True
                    reason = (
                        f"TP Break Cancel [{tf}]: SELL LIMIT got a confirmed red break below TP "
                        f"close:{_bar_close(cur_bar):.2f} < TP:{limit_tp:.2f} "
                        f"& engulf Low[prev]:{_bar_low(prev_bar):.2f}"
                    )
                elif limit_sl > 0 and _is_green_engulf_break(cur_bar, prev_bar, limit_sl):
                    should_cancel = True
                    reason = (
                        f"SL Break Cancel [{tf}]: SELL LIMIT got a confirmed green break above SL "
                        f"close:{_bar_close(cur_bar):.2f} > SL:{limit_sl:.2f} "
                        f"& engulf High[prev]:{_bar_high(prev_bar):.2f}"
                    )

        # Limit Guard: cancel limits whose entry is too far from an existing open position
        if not should_cancel and config.LIMIT_GUARD and _order_sid not in (10, 12, 13):
            limit_tf = info.get("tf") if isinstance(info, dict) else info
            positions = mt5.positions_get(symbol=SYMBOL)
            tf_separate = config.LIMIT_GUARD_TF_MODE == "separate"
            if positions and (limit_tf or not tf_separate):
                sym_info = mt5.symbol_info(SYMBOL)
                pt = sym_info.point if sym_info else 0.01
                guard_dist = config.LIMIT_GUARD_POINTS * pt * config.points_scale()  # BTC = 4ร— (background)

                if order.type == mt5.ORDER_TYPE_BUY_LIMIT:
                    for pos in positions:
                        if pos.type != mt5.ORDER_TYPE_BUY:
                            continue
                        if tf_separate:
                            pos_tf = position_tf.get(pos.ticket)
                            if pos_tf != limit_tf:
                                continue
                        pos_entry = pos.price_open
                        limit_entry = order.price_open
                        tick = mt5.symbol_info_tick(SYMBOL)
                        bid = tick.bid if tick else 0
                        if limit_entry > pos_entry and bid > pos_entry + guard_dist:
                            matched_tf = position_tf.get(pos.ticket, "?")
                            should_cancel = True
                            reason = (f"Limit Guard [{limit_tf}->{matched_tf}]: BUY LIMIT {limit_entry:.2f} > "
                                      f"BUY pos {pos_entry:.2f} "
                                      f"& bid {bid:.2f} > {pos_entry + guard_dist:.2f} (+{config.LIMIT_GUARD_POINTS}pt)")
                            break

                elif order.type == mt5.ORDER_TYPE_SELL_LIMIT:
                    for pos in positions:
                        if pos.type != mt5.ORDER_TYPE_SELL:
                            continue
                        if tf_separate:
                            pos_tf = position_tf.get(pos.ticket)
                            if pos_tf != limit_tf:
                                continue
                        pos_entry = pos.price_open
                        limit_entry = order.price_open
                        tick = mt5.symbol_info_tick(SYMBOL)
                        ask = tick.ask if tick else 0
                        if limit_entry < pos_entry and ask < pos_entry - guard_dist:
                            matched_tf = position_tf.get(pos.ticket, "?")
                            should_cancel = True
                            reason = (f"Limit Guard [{limit_tf}->{matched_tf}]: SELL LIMIT {limit_entry:.2f} < "
                                      f"SELL pos {pos_entry:.2f} "
                                      f"& ask {ask:.2f} < {pos_entry - guard_dist:.2f} (-{config.LIMIT_GUARD_POINTS}pt)")
                            break

        # Limit Trend Recheck: verify trend before fill when price gets near entry
        if not should_cancel and config.LIMIT_TREND_RECHECK and _order_sid not in (1, 9, 10, 11, 12, 13):
            _tick = mt5.symbol_info_tick(SYMBOL)
            _sym  = mt5.symbol_info(SYMBOL)
            if _tick and _sym:
                _pt           = _sym.point or 0.01
                _recheck_dist = config.LIMIT_TREND_RECHECK_POINTS * _pt * config.points_scale()
                _limit_entry  = order.price_open
                if order.type in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP):
                    _cur_price    = _tick.ask
                    _order_signal = "BUY"
                elif order.type in (mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP):
                    _cur_price    = _tick.bid
                    _order_signal = "SELL"
                else:
                    _cur_price = None
                    _order_signal = ""
                if _cur_price is not None and abs(_cur_price - _limit_entry) <= _recheck_dist:
                    from scanner import trend_allows_signal as _tas
                    _allowed, _why = _tas(tf, _order_signal)
                    if not _allowed:
                        should_cancel = True
                        _dist_pt = round(abs(_cur_price - _limit_entry) / _pt)
                        reason = (
                            f"Trend Recheck Cancel [{tf}]: {_pending_order_type_name(order)} entry:{_limit_entry:.2f} "
                            f"near {_dist_pt}pt but trend={_why}"
                        )

        # Near Approach Cancel: cancel limit when price gets near entry then pulls away
        if not should_cancel and config.NEAR_APPROACH_CANCEL_ENABLED and _order_sid != 10:
            _nac_sym = mt5.symbol_info(SYMBOL)
            if _nac_sym:
                _pt = _nac_sym.point or 0.01
                _approach_dist = config.NEAR_APPROACH_CANCEL_POINTS * _pt * config.points_scale()
                _nac_entry = order.price_open
                _nac_lb = max(2, config.NEAR_APPROACH_CANCEL_LOOKBACK)
                _nac_bars = list(rates[-_nac_lb:]) if len(rates) >= _nac_lb else list(rates)
                if len(_nac_bars) >= 2:
                    _last_bar = _nac_bars[-1]
                    _prev_bars = _nac_bars[:-1]
                    if order.type == mt5.ORDER_TYPE_SELL_LIMIT:
                        _threshold = _nac_entry - _approach_dist
                        if (any(float(b["high"]) >= _threshold for b in _prev_bars)
                                and float(_last_bar["high"]) < _threshold):
                            _peak = max(float(b["high"]) for b in _prev_bars)
                            _dist_pt = round((_nac_entry - _peak) / _pt)
                            should_cancel = True
                            reason = (
                                f"Near Approach Cancel [{tf}]: SELL LIMIT {_nac_entry:.2f} "
                                f"high moved within {_dist_pt}pt then pulled back"
                            )
                    elif order.type == mt5.ORDER_TYPE_BUY_LIMIT:
                        _threshold = _nac_entry + _approach_dist
                        if (any(float(b["low"]) <= _threshold for b in _prev_bars)
                                and float(_last_bar["low"]) > _threshold):
                            _valley = min(float(b["low"]) for b in _prev_bars)
                            _dist_pt = round((_valley - _nac_entry) / _pt)
                            should_cancel = True
                            reason = (
                                f"Near Approach Cancel [{tf}]: BUY LIMIT {_nac_entry:.2f} "
                                f"low moved within {_dist_pt}pt then pulled back"
                            )

        if isinstance(info, dict) and not info.get("sl_armed") and info.get("intended_sl"):
            _is_s8 = info.get("sid") == 8
            _should_check_sl = _is_s8 or config.DELAY_SL_MODE != "off"
            if _should_check_sl:
                intended_sl = float(info.get("intended_sl", 0) or 0)
                sig = info.get("signal", "")
                arm_now = False
                arm_reason = ""

                if _is_s8 and config.DELAY_SL_MODE == "off":
                    # Original S8: wait for breakout beyond swing
                    swing_price = float(info.get("swing_price", 0) or 0)
                    swing_bar_time = int(info.get("swing_bar_time", 0) or 0)
                    latest_bar = rates[-1] if len(rates) > 0 else None
                    if swing_price > 0 and latest_bar is not None and int(latest_bar["time"]) > swing_bar_time:
                        if sig == "SELL" and float(latest_bar["high"]) > swing_price:
                            arm_now = True
                            arm_reason = "breakout above Swing High"
                        elif sig == "BUY" and float(latest_bar["low"]) < swing_price:
                            arm_now = True
                            arm_reason = "breakout below Swing Low"

                elif config.DELAY_SL_MODE == "time":
                    # Arm SL during the last 10% of the TF candle
                    import time as _time
                    _now_ts = int(_time.time())
                    _tf_secs = _get_tf_seconds(tf_val)
                    _threshold = _tf_secs * 0.10
                    _latest = rates[-1] if len(rates) > 0 else None
                    if _latest is not None:
                        _candle_end = int(_latest["time"]) + _tf_secs
                        _time_left = _candle_end - _now_ts
                        if _time_left <= _threshold:
                            arm_now = True
                            arm_reason = f"time left {_time_left}s < {_threshold:.0f}s (10% of {tf})"

                elif config.DELAY_SL_MODE == "price":
                    # BUY: ask > entry+spread / SELL: bid < entry-spread
                    _tick = mt5.symbol_info_tick(SYMBOL)
                    if _tick:
                        _entry_price = float(order.price_open)
                        _spread = abs(float(_tick.ask) - float(_tick.bid))
                        if sig == "BUY" and float(_tick.ask) > _entry_price + _spread:
                            arm_now = True
                            arm_reason = f"ask {float(_tick.ask):.2f} > entry+spread {_entry_price + _spread:.2f}"
                        elif sig == "SELL" and float(_tick.bid) < _entry_price - _spread:
                            arm_now = True
                            arm_reason = f"bid {float(_tick.bid):.2f} < entry-spread {_entry_price - _spread:.2f}"

                if arm_now:
                    ok_mod, r_mod = _modify_pending_sl(order, intended_sl)
                    if ok_mod:
                        info["sl_armed"] = True
                        info["sl_arm_retry_count"] = 0
                        pending_order_tf[ticket] = info
                        save_runtime_state()
                        sig_e = "🟢" if sig == "BUY" else "🔴"
                        ot = "BUY LIMIT" if sig == "BUY" else "SELL LIMIT"
                        await tg(app, (
                            f"🛡️ *ตั้ง SL {ot}*\n"
                            f"{sig_e} [{tf}] Ticket:`{ticket}`\n"
                            f"🛑 SL: `{intended_sl:.2f}`\n"
                            f"เหตุผล: {arm_reason}"
                        ))
                        print(f"🛡️ [{now}] arm SL {ot} {ticket}: SL={intended_sl:.2f} ({arm_reason})")
                    else:
                        info["sl_arm_retry_count"] = int(info.get("sl_arm_retry_count", 0) or 0) + 1
                        pending_order_tf[ticket] = info
                        save_runtime_state()
                        retcode = getattr(r_mod, "retcode", None) if r_mod is not None else None
                        comment = getattr(r_mod, "comment", "") if r_mod is not None else ""
                        print(
                            f"WARN [{now}] arm SL retry {ticket}: "
                            f"attempt={info['sl_arm_retry_count']} SL={intended_sl:.2f} "
                            f"retcode={retcode} comment={comment}"
                        )

        # Reverse limit: if 3 candles close after detect and still no fill -> cancel
        if isinstance(info, dict) and info.get("reverse"):
            detect_time = int(info.get("detect_bar_time", 0) or 0)
            if detect_time:
                bars_after_detect = [r for r in candle_rates if int(r["time"]) > detect_time]
                if len(bars_after_detect) >= 3:
                    should_cancel = True
                    reason = f"Reverse limit expired after 3 closed {check_tf} candles from the detect bar"

        # S8 Swing Limit: cancel when swing changes
        if not should_cancel and isinstance(info, dict) and info.get("swing_price") and info.get("sid") == 8:
            from strategy4 import _find_prev_swing_high, _find_prev_swing_low
            old_swing = info["swing_price"]
            sig = info.get("signal", "")
            if sig == "SELL":
                new_sh = _find_prev_swing_high(rates)
                if new_sh and abs(new_sh["price"] - old_swing) > 0.01:
                    should_cancel = True
                    reason = f"Swing High changed {old_swing:.2f} -> {new_sh['price']:.2f}"
            elif sig == "BUY":
                new_sl = _find_prev_swing_low(rates)
                if new_sl and abs(new_sl["price"] - old_swing) > 0.01:
                    should_cancel = True
                    reason = f"Swing Low changed {old_swing:.2f} -> {new_sl['price']:.2f}"

        # cancel_bars: cancel after N candles (e.g. Pattern E cancels after 1 candle)
        if not should_cancel and isinstance(info, dict) and info.get("cancel_bars"):
            detect_time = int(info.get("detect_bar_time", 0) or 0)
            if detect_time:
                bars_after = [r for r in candle_rates if int(r["time"]) > detect_time]
                if len(bars_after) >= info["cancel_bars"]:
                    should_cancel = True
                    reason = f"Expired after {info['cancel_bars']} candles ({check_tf})"

        if order.type == mt5.ORDER_TYPE_BUY_LIMIT:
            # BUY LIMIT: cancel when price closes above the main swing high
            if not should_cancel and last_close > swing_high:
                should_cancel = True
                reason = f"Close:{last_close:.2f} > Swing High:{swing_high:.2f}"
            # BUY LIMIT: next candle after detect closes red with body>=35% -> setup fails
            elif not should_cancel:
                detect_time = info.get("detect_bar_time", 0) if isinstance(info, dict) else 0
                if detect_time:
                    next_bars = [r for r in candle_rates if int(r["time"]) > detect_time]
                    if next_bars:
                        nb = next_bars[0]
                        o_ = float(nb["open"]); c_ = float(nb["close"])
                        rng = float(nb["high"]) - float(nb["low"])
                        body = abs(c_-o_)/rng if rng > 0 else 0
                        if c_ < o_ and body >= 0.35:
                            should_cancel = True
                            reason = (f"Next {check_tf} candle closes red body:{body*100:.0f}%"
                                      f" O:{o_:.2f} H:{float(nb['high']):.2f}"
                                      f" L:{float(nb['low']):.2f} C:{c_:.2f}"
                                      f" setup failed")

        elif order.type == mt5.ORDER_TYPE_SELL_LIMIT:
            # SELL LIMIT: ลบเมื่อราคาปิดต่ำกว่า Swing Low หลัก
            if not should_cancel and last_close < swing_low:
                should_cancel = True
                reason = f"Close:{last_close:.2f} < Swing Low:{swing_low:.2f}"
            # SELL LIMIT: แท่งถัดจาก detect ปิดเขียว body>=35% -> setup ล้มเหลว
            elif not should_cancel:
                detect_time = info.get("detect_bar_time", 0) if isinstance(info, dict) else 0
                if detect_time:
                    next_bars = [r for r in candle_rates if int(r["time"]) > detect_time]
                    if next_bars:
                        nb = next_bars[0]
                        o_ = float(nb["open"]); c_ = float(nb["close"])
                        rng = float(nb["high"]) - float(nb["low"])
                        body = abs(c_-o_)/rng if rng > 0 else 0
                        if c_ > o_ and body >= 0.35:
                            should_cancel = True
                            reason = (f"แท่งถัดไป{check_tf}เขียว body:{body*100:.0f}%"
                                      f" O:{o_:.2f} H:{float(nb['high']):.2f}"
                                      f" L:{float(nb['low']):.2f} C:{c_:.2f}"
                                      f" setup ล้มเหลว")

        if should_cancel:
            r = mt5.order_send({
                "action": mt5.TRADE_ACTION_REMOVE,
                "order":  ticket,
            })
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                pending_order_tf.pop(ticket, None)
                sig_e = _pending_order_icon(order)
                ot    = _pending_order_type_name(order)
                log_event(
                    "ORDER_CANCELED",
                    reason,
                    ticket=ticket,
                    tf=tf,
                    side=_pending_order_side(order),
                    order_type=ot,
                    entry=order.price_open,
                    flow_id=info.get("flow_id", "") if isinstance(info, dict) else "",
                    parent_flow_id=info.get("parent_flow_id", "") if isinstance(info, dict) else "",
                )
                await tg(app, (
                        f"🗑️ *ยกเลิก {ot} อัตโนมัติ*\n"
                        f"{sig_e} [{tf}] Ticket:`{ticket}`\n"
                        f"Entry:`{order.price_open}`\n"
                        f"Flow: `{_short_flow_id(info.get('flow_id', ''))}`\n"
                        f"เหตุผล: {reason}"
                    ))
                print(f"🗑️ [{now}] ยกเลิก {ot} {ticket} [{tf}]: {reason}")


# -------------------------------------------------------------
async def check_limit_sweep(app):
    """
    Limit Sweep - เมื่อ position จบแท่งสวนทาง + ราคาทะลุ prev low/high
    BUY:  แท่งจบแดง + close < prev low -> ปิด position + sweep BUY LIMITs ใน TF
          -> เหลือตัวใกล้ Swing LL ที่สุด / ถ้าไม่มี -> ตั้ง S8 ที่ LL
    SELL: แท่งจบเขียว + close > prev high -> ปิด position + sweep SELL LIMITs ใน TF
          -> เหลือตัวใกล้ Swing HH ที่สุด / ถ้าไม่มี -> ตั้ง S8 ที่ HH
    """
    if not config.LIMIT_SWEEP:
        return

    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        _sweep_last_bar.clear()
        return

    now = now_bkk().strftime("%H:%M:%S")
    open_tickets = {p.ticket for p in positions}
    # cleanup stale tickets
    for t in list(_sweep_last_bar.keys()):
        if t not in open_tickets:
            _sweep_last_bar.pop(t, None)

    for pos in positions:
        ticket = pos.ticket
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        tf = position_tf.get(ticket)
        if not tf:
            continue

        # ดึง rates
        tf_val = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        lookback = TF_LOOKBACK.get(tf, SWING_LOOKBACK)
        rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
        if rates is None or len(rates) < 6:
            continue

        # แท่งปิดล่าสุด = rates[-2], แท่งก่อนหน้า = rates[-3]
        bar = rates[-2]
        prev_bar = rates[-3]
        bar_time = int(bar["time"])

        # ไม่ตรวจแท่งเดิมซ้ำ
        if _sweep_last_bar.get(ticket) == bar_time:
            continue

        bar_close = float(bar["close"])
        bar_open = float(bar["open"])
        prev_low = float(prev_bar["low"])
        prev_high = float(prev_bar["high"])

        is_red = bar_close < bar_open
        is_green = bar_close > bar_open

        trigger = False
        if pos_type == "BUY" and is_red and bar_close < prev_low:
            trigger = True
        elif pos_type == "SELL" and is_green and bar_close > prev_high:
            trigger = True

        _sweep_last_bar[ticket] = bar_time

        if not trigger:
            continue

        entry = float(pos.price_open)
        sig = "BUY" if pos_type == "BUY" else "SELL"
        opp = "SELL" if pos_type == "BUY" else "BUY"

        # -- 1) ปิด position --
        comment = f"Sweep_{tf}"
        ok, close_price = _close_position(pos, pos_type, comment)
        if not ok:
            print(f"[{now}] ⚠️ Limit Sweep: ปิด {pos_type} #{ticket} ไม่สำเร็จ")
            continue

        reason_detail = (f"แท่งจบ{'แดง' if is_red else 'เขียว'} close={bar_close:.2f} "
                         f"{'< prev low' if pos_type == 'BUY' else '> prev high'}="
                         f"{prev_low if pos_type == 'BUY' else prev_high:.2f}")
        print(f"[{now}] 🧹 Limit Sweep: ปิด {pos_type} #{ticket} [{tf}] {reason_detail}")

        # -- 2) หา Swing LL (BUY) หรือ HH (SELL) --
        sh_info = _find_prev_swing_high(rates)
        sl_info = _find_prev_swing_low(rates)

        if pos_type == "BUY":
            target_info = _find_ll(rates, sl_info)  # LL = swing low ที่ต่ำกว่า L
            while target_info and bar_close <= float(target_info["price"]):
                target_info = _find_ll(rates, target_info)
            target_price = target_info["price"] if target_info else None
            limit_type = mt5.ORDER_TYPE_BUY_LIMIT
        else:
            target_info = _find_hh(rates, sh_info)  # HH = swing high ที่สูงกว่า H
            while target_info and bar_close >= float(target_info["price"]):
                target_info = _find_hh(rates, target_info)
            target_price = target_info["price"] if target_info else None
            limit_type = mt5.ORDER_TYPE_SELL_LIMIT

        # -- 3) หา limit orders ใน TF เดียวกัน --
        #   ในช่วง LL-H / L-HH -> ยกเลิกทุกท่า
        #   นอกช่วง -> ยกเลิกเฉพาะท่าที่ 8
        h_price = sh_info["price"] if sh_info else None
        l_price = sl_info["price"] if sl_info else None
        orders = mt5.orders_get(symbol=SYMBOL)
        in_range_limits = []
        if orders:
            for o in orders:
                o_info = pending_order_tf.get(o.ticket)
                o_tf = o_info.get("tf") if isinstance(o_info, dict) else o_info
                if o_tf != tf:
                    continue
                o_sid = o_info.get("sid") if isinstance(o_info, dict) else None
                ep = o.price_open
                if pos_type == "BUY" and o.type == mt5.ORDER_TYPE_BUY_LIMIT:
                    in_rng = target_price and h_price and target_price <= ep <= h_price
                    if in_rng or o_sid == 8:
                        in_range_limits.append(o)
                elif pos_type == "SELL" and o.type == mt5.ORDER_TYPE_SELL_LIMIT:
                    in_rng = target_price and l_price and l_price <= ep <= target_price
                    if in_rng or o_sid == 8:
                        in_range_limits.append(o)

        # -- 4) เหลือตัวใกล้ LL/HH ที่สุด ยกเลิกตัวที่เหลือในช่วง --
        kept_ticket = None
        if target_price and in_range_limits:
            in_range_limits.sort(key=lambda o: abs(o.price_open - target_price))
            kept_ticket = in_range_limits[0].ticket
            for o in in_range_limits[1:]:
                r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                ok_cancel = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                status = "✅" if ok_cancel else "❌"
                print(f"[{now}] 🧹 Sweep cancel {pos_type} LIMIT #{o.ticket} [{tf}] entry={o.price_open:.2f} {status}")
                pending_order_tf.pop(o.ticket, None)
            rng = f"{'LL' if pos_type == 'BUY' else 'L'}-{'H' if pos_type == 'BUY' else 'HH'}"
            print(f"[{now}] 🧹 Sweep keep #{kept_ticket} [{tf}] ใกล้ {'LL' if pos_type == 'BUY' else 'HH'}={target_price:.2f} (range {rng})")

        # -- 5) ถ้าไม่มี limit ใกล้ target -> ตั้ง S8 --
        if target_info and not kept_ticket:
            candle = target_info.get("candle", {})
            c_high = candle.get("high", 0)
            c_low = candle.get("low", 0)
            c_range = c_high - c_low

            if c_range > 0:
                from mt5_utils import open_order
                if pos_type == "BUY":
                    s8_entry = round(c_low - c_range * 0.17, 2)
                    s8_sl = round(c_low - c_range * 0.31, 2)
                    s8_tp = sh_info["price"] if sh_info else round(c_high, 2)
                    s8_signal = "BUY"
                else:
                    s8_entry = round(c_high + c_range * 0.17, 2)
                    s8_sl = round(c_high + c_range * 0.31, 2)
                    s8_tp = sl_info["price"] if sl_info else round(c_low, 2)
                    s8_signal = "SELL"

                s8_pattern = f"ท่าที่ 8 กินไส้ Swing [Limit Sweep] {'🟢 BUY' if s8_signal == 'BUY' else '🔴 SELL'}"
                vol = config.get_volume()
                res = open_order(s8_signal, vol, s8_sl, s8_tp,
                                 entry_price=s8_entry, tf=tf, sid="8", pattern=s8_pattern)
                if res.get("success"):
                    s8_ticket = res["ticket"]
                    pending_order_tf[s8_ticket] = {
                        "tf": tf, "signal": s8_signal,
                        "detect_bar_time": bar_time,
                        "sid": 8, "pattern": s8_pattern,
                        "source": "limit_sweep",
                        "swing_price": target_price,
                        "swing_bar_time": int(target_info.get("time", 0)),
                    }
                    position_pattern[s8_ticket] = s8_pattern
                    log_event(
                        "ORDER_CREATED",
                        s8_pattern,
                        tf=tf,
                        sid=8,
                        signal=s8_signal,
                        entry=s8_entry,
                        sl=s8_sl,
                        tp=s8_tp,
                        ticket=s8_ticket,
                        order_type=res.get("order_type", "LIMIT"),
                        source="limit_sweep",
                        from_ticket=ticket,
                    )
                    print(f"[{now}] 🧹 Sweep -> S8 {s8_signal} LIMIT #{s8_ticket} [{tf}] "
                          f"Entry={s8_entry:.2f} SL={s8_sl:.2f} TP={s8_tp:.2f} "
                          f"{'LL' if pos_type == 'BUY' else 'HH'}={target_price:.2f}")
                    await tg(app,
                        f"🧹 *Limit Sweep -> S8*\n"
                        f"━━━━━━━━━━━━━━━━━\n"
                        f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                        f"{reason_detail}\n\n"
                        f"ตั้ง {s8_signal} LIMIT `#{s8_ticket}`\n"
                        f"📌 Entry: `{s8_entry:.2f}`\n"
                        f"🛑 SL: `{s8_sl:.2f}` | 🎯 TP: `{s8_tp:.2f}`\n"
                        f"{'📉 LL' if pos_type == 'BUY' else '📈 HH'}: `{target_price:.2f}`"
                    )
                else:
                    err = res.get("error", "?")
                    print(f"[{now}] ⚠️ Sweep S8 failed: {err}")
                    await tg(app,
                        f"🧹 *Limit Sweep*\n"
                        f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                        f"{reason_detail}\n\n"
                        f"⚠️ S8 {'LL' if pos_type == 'BUY' else 'HH'} ตั้งไม่สำเร็จ: {err}"
                    )
            else:
                await tg(app,
                    f"🧹 *Limit Sweep*\n"
                    f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                    f"{reason_detail}\n\n"
                    f"{'📉 LL' if pos_type == 'BUY' else '📈 HH'}: `{target_price:.2f}` (range=0 ข้าม S8)"
                )
        else:
            sweep_msg = ""
            if kept_ticket:
                sweep_msg = f"\nเหลือ LIMIT `#{kept_ticket}` ใกล้ {'LL' if pos_type == 'BUY' else 'HH'}"
            elif target_price:
                sweep_msg = f"\nไม่มี LIMIT ใน TF"
            await tg(app,
                f"🧹 *Limit Sweep*\n"
                f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                f"{reason_detail}{sweep_msg}"
            )

        # cleanup state
        _entry_state.pop(ticket, None)
        _trail_state.pop(ticket, None)
        _bar_count.pop(ticket, None)
        position_tf.pop(ticket, None)
        position_sid.pop(ticket, None)
        position_pattern.pop(ticket, None)
        position_trend_filter.pop(ticket, None)
        _s6_state.pop(ticket, None)
        _s6i_state.pop(ticket, None)
        _sweep_last_bar.pop(ticket, None)
        config.save_runtime_state()


async def check_fvg_candle_quality(app):
    """Deprecated - ท่าที่ 2 ใช้ check_entry_candle_quality เหมือนทุกท่าแล้ว"""
    pass


# -------------------------------------------------------------
async def _s12_close_all(app, reason: str):
    """ปิด S12 positions ทั้งหมด - ใช้ใน flip + breakout"""
    from strategy12 import _s12_state
    from bot_log import log_event

    positions   = mt5.positions_get(symbol=SYMBOL)
    s12_tickets = set(_s12_state["tickets"])
    closed = 0
    total_profit = 0.0

    if positions:
        tick = mt5.symbol_info_tick(SYMBOL)
        for pos in positions:
            if pos.ticket not in s12_tickets:
                continue
            close_type  = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            close_price = float(tick.bid) if pos.type == mt5.ORDER_TYPE_BUY else float(tick.ask)
            r = mt5.order_send({
                "action":       mt5.TRADE_ACTION_DEAL,
                "symbol":       SYMBOL,
                "volume":       pos.volume,
                "type":         close_type,
                "position":     pos.ticket,
                "price":        close_price,
                "deviation":    20,
                "magic":        0,
                "comment":      "S12 close",
                "type_time":    mt5.ORDER_TIME_GTC,
                "type_filling": _get_filling_mode(),
            })
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                closed += 1
                total_profit += pos.profit
                log_event("POSITION_CLOSED", reason,
                          ticket=pos.ticket,
                          side="BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                          symbol=SYMBOL, tf="M5", sid=12,
                          open_price=pos.price_open, close_price=close_price,
                          profit=round(pos.profit, 2))

    _s12_state["tickets"].clear()
    _s12_state["order_count"] = 0
    _s12_state["last_entry_price"] = None
    # side ไม่ล้างที่นี่ - caller กำหนดเอง

    now_str = now_bkk().strftime("%H:%M:%S")
    profit_str = f"+{total_profit:.2f}" if total_profit >= 0 else f"{total_profit:.2f}"
    print(f"🗑️ [{now_str}] S12 ปิด {closed} positions profit={profit_str}: {reason}")
    await tg(app, (
        f"🗑️ *S12 ปิด {closed} position*\n"
        f"Profit: `{profit_str}`\n"
        f"เหตุผล: {reason}"
    ))


async def check_s12_management(app):
    """S12 Range Trading management - ตรวจ flip + breakout"""
    from strategy12 import _s12_state, s12_get_swing_context, s12_cleanup_tickets

    if not active_strategies.get(12, False):
        return

    s12_cleanup_tickets()

    if not _s12_state["tickets"]:
        return

    rates_m5 = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, config.S12_LOOKBACK + 5)
    tick     = mt5.symbol_info_tick(SYMBOL)
    sym      = mt5.symbol_info(SYMBOL)

    if rates_m5 is None or len(rates_m5) < 5 or tick is None or sym is None:
        return

    pt        = sym.point or 0.01
    scale     = config.points_scale()
    zone_dist = config.S12_ZONE_POINTS * pt * scale
    side      = _s12_state["side"]

    context = s12_get_swing_context(rates_m5, config.S12_LOOKBACK)
    if not context:
        return
    swing_high = context["pivot_swing_high"]
    swing_low = context["pivot_swing_low"]

    # -- ตรวจ Breakout (แท่งปิดล่าสุด) --
    if len(rates_m5) >= 2:
        last_close = float(rates_m5[-2]["close"])
        if side == "BUY" and last_close > swing_high:
            await _s12_close_all(app, f"Breakout ขึ้น close:{last_close:.2f} > {swing_high:.2f}")
            _s12_state["side"] = None
            return
        elif side == "SELL" and last_close < swing_low:
            await _s12_close_all(app, f"Breakout ลง close:{last_close:.2f} < {swing_low:.2f}")
            _s12_state["side"] = None
            return

    # -- ตรวจ Flip --
    bid = float(tick.bid)
    ask = float(tick.ask)

    if side == "SELL" and ask <= swing_low + zone_dist:
        await _s12_close_all(app, f"Flip -> BUY: ราคาถึง bottom zone {swing_low:.2f}")
        _s12_state["side"]             = "BUY"
        _s12_state["order_count"]      = 0
        _s12_state["last_entry_price"] = None
    elif side == "BUY" and bid >= swing_high - zone_dist:
        await _s12_close_all(app, f"Flip -> SELL: ราคาถึง top zone {swing_high:.2f}")
        _s12_state["side"]             = "SELL"
        _s12_state["order_count"]      = 0
        _s12_state["last_entry_price"] = None
