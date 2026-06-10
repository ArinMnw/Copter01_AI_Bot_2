import re
import config as _config
from bot_log import log_event
from config import *
from mt5_utils import connect_mt5
from trailing import position_tf, position_sid, position_pattern, position_trend_filter


def _fmt_bkk_ts(ts: int | float | None) -> str:
    return fmt_mt5_bkk_ts(ts)


def _parse_bot_comment(comment: str):
    """
    Parse comment เช่น 'M1_S3', 'H4_S2', 'M1_S6i_buy'
    คืน (tf, sid) เช่น ('M1', 3), ('H4', 2), ('M1', '6i')
    ถ้า parse ไม่ได้ คืน (None, None)
    """
    if not comment:
        return None, None
    m = re.match(r"(\[[\w-]+\]|M\d+|H\d+|D\d+)(?:_S(\w+))?", comment)
    if not m:
        return None, None
    tf = m.group(1)
    sid_raw = m.group(2)
    if sid_raw is None:
        return tf, None
    # "3" → 3, "6i" → 7 (S6i = active_strategies key 7)
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


def _get_tracked_meta(ticket: int, p_info: dict, deals) -> tuple[str, int | None, str, str]:
    tf_label = p_info.get("tf", "") or position_tf.get(ticket, "")
    sid_label = p_info.get("sid")
    if sid_label is None:
        sid_label = position_sid.get(ticket)
    pat_label = p_info.get("pattern", "") or position_pattern.get(ticket, "")
    trend_filter = p_info.get("trend_filter", "") or position_trend_filter.get(ticket, "")

    comment = p_info.get("comment", "")
    if (not tf_label or sid_label is None) and comment:
        c_tf, c_sid = _parse_bot_comment(comment)
        if not tf_label and c_tf:
            tf_label = c_tf
        if sid_label is None and c_sid is not None:
            sid_label = c_sid

    if deals and (not tf_label or sid_label is None):
        entry_deal = sorted(deals, key=lambda d: d.time)[0]
        c_tf, c_sid = _parse_bot_comment(getattr(entry_deal, "comment", "") or "")
        if not tf_label and c_tf:
            tf_label = c_tf
        if sid_label is None and c_sid is not None:
            sid_label = c_sid

    if not pat_label and sid_label:
        pat_label = STRATEGY_NAMES.get(sid_label, "")

    return tf_label, sid_label, pat_label, trend_filter

async def check_sl_tp_hits(app):
    """
    ตรวจสอบว่ามี Position ที่โดน SL หรือ TP แล้วหรือยัง
    ถ้าโดน → แจ้งเตือน Telegram
    """
    if not connect_mt5():
        return

    tracked_positions = _config.tracked_positions

    # ดึง positions ปัจจุบัน
    current_positions = mt5.positions_get(symbol=SYMBOL)
    # ถ้า positions_get() คืน None = MT5 error (เช่น maintenance window หรือ disconnect)
    # ห้ามประมวลผลต่อ เพราะจะทำให้ tracked_positions ทั้งหมดดูเหมือน "ปิดแล้ว"
    # และยิง phantom POSITION_CLOSED พร้อม profit=0, close_time=fill_time
    if current_positions is None:
        return
    current_tickets = {p.ticket for p in current_positions}

    # หา ticket ที่หายไป (ปิดไปแล้ว = โดน SL หรือ TP หรือ manual)
    closed_tickets = set(tracked_positions.keys()) - current_tickets
    for ticket in closed_tickets:
        p_info = tracked_positions.get(ticket)
        if not p_info:
            tracked_positions.pop(ticket, None)
            continue
        # ดูประวัติ deal ล่าสุด
        deals = mt5.history_deals_get(position=ticket)
        result_msg = ""
        profit     = 0.0
        close_type = "ปิด"
        _sl_guard_extra_msg = ""
        if deals:
            # deal สุดท้าย = ปิด position
            close_deal = sorted(deals, key=lambda d: d.time)[-1]
            profit     = close_deal.profit
            close_price = close_deal.price
            close_time = _fmt_bkk_ts(getattr(close_deal, "time", None))
            close_reason = (getattr(close_deal, "comment", "") or "").strip()
            sl_price    = p_info.get("sl", 0)
            tp_price    = p_info.get("tp", 0)
            sig_e       = "🟢" if p_info.get("type") == "BUY" else "🔴"
            pnl_e       = "💰" if profit >= 0 else "💸"

            # ตรวจว่าโดน SL หรือ TP ด้วย deal.reason (แม่นกว่าเปรียบราคา)
            # MT5 constants: SL=1, TP=2, Expert=3, Client=0, Mobile=4, Web=5
            DEAL_REASON_SL     = 1
            DEAL_REASON_TP     = 2
            DEAL_REASON_EXPERT = 3
            dr = getattr(close_deal, "reason", None)
            if dr == DEAL_REASON_SL:
                close_type = "🛑 SL Hit"
            elif dr == DEAL_REASON_TP:
                close_type = "🎯 TP Hit"
            elif dr == DEAL_REASON_EXPERT:
                close_type = "🤖 Bot ปิด"
            else:
                # fallback: เปรียบราคากับ SL/TP ถ้า reason ไม่ชัด
                if sl_price > 0 and tp_price > 0:
                    if p_info.get("type") == "BUY":
                        if close_price <= sl_price + 1:
                            close_type = "🛑 SL Hit"
                        elif close_price >= tp_price - 1:
                            close_type = "🎯 TP Hit"
                    else:
                        if close_price >= sl_price - 1:
                            close_type = "🛑 SL Hit"
                        elif close_price <= tp_price + 1:
                            close_type = "🎯 TP Hit"

            tf_label, sid_label, pat_label, trend_filter = _get_tracked_meta(ticket, p_info, deals)

            # SL Guard: track SL hits per (tf, side)
            _sl_guard_extra_msg = ""
            if close_type == "🛑 SL Hit" and profit < 0 and _config.SL_GUARD_ENABLED and tf_label:
                try:
                    from trailing import _sl_guard_record_sl, _sl_guard_close_open_positions
                    _just_activated = _sl_guard_record_sl(tf_label, p_info.get("type", ""))
                    if _just_activated:
                        _guard_side = p_info.get("type", "")
                        _closed = _sl_guard_close_open_positions(tf_label, _guard_side)
                        _close_note = f"\n🚫 ปิด {_guard_side} position: {', '.join(f'`{t}`' for t in _closed)}" if _closed else ""
                        _sl_guard_extra_msg = (
                            f"🛡️ *SL Guard เปิดใช้งาน*\n"
                            f"━━━━━━━━━━━━━━━━━\n"
                            f"📊 TF: {tf_label} | {_guard_side}\n"
                            f"⚠️ SL hit ครบ {_config.SL_GUARD_COUNT}x — บล็อก {_guard_side} LIMIT ใหม่\n"
                            f"⏳ รอ Swing {'Low' if _guard_side=='BUY' else 'High'} ใหม่เกิดก่อน\n"
                            f"🔔 Ticket: `{ticket}`"
                            f"{_close_note}"
                        )
                except Exception:
                    pass

            # SL Guard Loss: นับ close ที่ขาดทุนเกิน threshold (ไม่ใช่ SL hit ปกติ)
            _sg_loss_ok = (
                close_type != "🛑 SL Hit"
                and getattr(_config, "SL_GUARD_LOSS_ENABLED", False)
                and profit < -float(getattr(_config, "SL_GUARD_LOSS_THRESHOLD", 5.0))
                and tf_label
            )
            if _sg_loss_ok and _config.SL_GUARD_ENABLED:
                try:
                    from trailing import _sl_guard_record_sl, _sl_guard_close_open_positions
                    _just_activated = _sl_guard_record_sl(tf_label, p_info.get("type", ""))
                    if _just_activated and not _sl_guard_extra_msg:
                        _guard_side = p_info.get("type", "")
                        _closed = _sl_guard_close_open_positions(tf_label, _guard_side)
                        _close_note = f"\n🚫 ปิด {_guard_side} position: {', '.join(f'`{t}`' for t in _closed)}" if _closed else ""
                        _sl_guard_extra_msg = (
                            f"🛡️ *SL Guard เปิดใช้งาน*\n"
                            f"━━━━━━━━━━━━━━━━━\n"
                            f"📊 TF: {tf_label} | {_guard_side}\n"
                            f"⚠️ ขาดทุน >{_config.SL_GUARD_LOSS_THRESHOLD:.0f}$ ครบ {_config.SL_GUARD_COUNT}x — บล็อก {_guard_side} LIMIT ใหม่\n"
                            f"⏳ รอ Swing {'Low' if _guard_side=='BUY' else 'High'} ใหม่เกิดก่อน\n"
                            f"🔔 Ticket: `{ticket}`"
                            f"{_close_note}"
                        )
                except Exception:
                    pass

            # SL Guard Combined: track SL hits across TFs
            if close_type == "🛑 SL Hit" and profit < 0 and getattr(_config, "SL_GUARD_COMBINED_ENABLED", False) and tf_label:
                try:
                    from trailing import _combined_guard_record_sl, _sl_guard_close_combined_positions
                    _cg_act_msg = _combined_guard_record_sl(tf_label, p_info.get("type", ""))
                    if _cg_act_msg:
                        _guard_side = p_info.get("type", "")
                        _closed = _sl_guard_close_combined_positions(_guard_side)
                        _close_note = f"\n🚫 ปิด {_guard_side} positions: {', '.join(f'`{t}`' for t in _closed)}" if _closed else ""
                        if not _sl_guard_extra_msg:
                            _sl_guard_extra_msg = _cg_act_msg + _close_note
                except Exception:
                    pass

            # SL Guard Combined: นับ loss close ด้วย
            if _sg_loss_ok and getattr(_config, "SL_GUARD_COMBINED_ENABLED", False):
                try:
                    from trailing import _combined_guard_record_sl, _sl_guard_close_combined_positions
                    _cg_act_msg = _combined_guard_record_sl(tf_label, p_info.get("type", ""))
                    if _cg_act_msg:
                        _guard_side = p_info.get("type", "")
                        _closed = _sl_guard_close_combined_positions(_guard_side)
                        _close_note = f"\n🚫 ปิด {_guard_side} positions: {', '.join(f'`{t}`' for t in _closed)}" if _closed else ""
                        if not _sl_guard_extra_msg:
                            _sl_guard_extra_msg = _cg_act_msg + _close_note
                except Exception:
                    pass

            # SL Guard: reset ทันทีเมื่อ TP hit ใน TF/side เดียวกัน
            if close_type == "🎯 TP Hit" and _config.SL_GUARD_ENABLED and tf_label:
                try:
                    from trailing import _sl_guard_reset_on_tp
                    _reset_msg = _sl_guard_reset_on_tp(tf_label, p_info.get("type", ""))
                    if _reset_msg:
                        _sl_guard_extra_msg = _reset_msg
                except Exception:
                    pass

            # SL Guard Combined: reset TF นี้ทันทีเมื่อ TP hit
            if close_type == "🎯 TP Hit" and getattr(_config, "SL_GUARD_COMBINED_ENABLED", False) and tf_label:
                try:
                    from trailing import _combined_guard_reset_on_tp
                    _cg_reset_msg = _combined_guard_reset_on_tp(tf_label, p_info.get("type", ""))
                    if _cg_reset_msg and not _sl_guard_extra_msg:
                        _sl_guard_extra_msg = _cg_reset_msg
                except Exception:
                    pass

            # SL Guard Group: SL Hit → บันทึก + ปิด position ทั้งหมดของ side ถ้า group activate
            if close_type == "🛑 SL Hit" and profit < 0 and getattr(_config, "SL_GUARD_GROUP_ENABLED", False) and tf_label:
                try:
                    from trailing import _group_guard_record_sl, _sl_guard_close_all_side_positions
                    _gg_msgs = _group_guard_record_sl(tf_label, p_info.get("type", ""))
                    if _gg_msgs:
                        _guard_side = p_info.get("type", "")
                        _closed = _sl_guard_close_all_side_positions(_guard_side)
                        _close_note = f"\n🚫 ปิด {_guard_side} positions: {', '.join(f'`{t}`' for t in _closed)}" if _closed else ""
                        if not _sl_guard_extra_msg:
                            _sl_guard_extra_msg = _gg_msgs[0] + _close_note
                except Exception:
                    pass

            # SL Guard Group: Loss Guard → บันทึกเหมือน SL Hit
            if _sg_loss_ok and getattr(_config, "SL_GUARD_GROUP_ENABLED", False):
                try:
                    from trailing import _group_guard_record_sl, _sl_guard_close_all_side_positions
                    _gg_msgs = _group_guard_record_sl(tf_label, p_info.get("type", ""))
                    if _gg_msgs:
                        _guard_side = p_info.get("type", "")
                        _closed = _sl_guard_close_all_side_positions(_guard_side)
                        _close_note = f"\n🚫 ปิด {_guard_side} positions: {', '.join(f'`{t}`' for t in _closed)}" if _closed else ""
                        if not _sl_guard_extra_msg:
                            _sl_guard_extra_msg = _gg_msgs[0] + _close_note
                except Exception:
                    pass

            # SL Guard Group: TP hit → unblock TF นี้ออกจากทุก group
            if close_type == "🎯 TP Hit" and getattr(_config, "SL_GUARD_GROUP_ENABLED", False) and tf_label:
                try:
                    from trailing import _group_guard_reset_on_tp
                    _gg_reset_msg = _group_guard_reset_on_tp(tf_label, p_info.get("type", ""))
                    if _gg_reset_msg and not _sl_guard_extra_msg:
                        _sl_guard_extra_msg = _gg_reset_msg
                except Exception:
                    pass

            strat_txt = STRATEGY_NAMES.get(sid_label, "") if sid_label else ""
            info_line = ""
            if tf_label or strat_txt or pat_label:
                parts = []
                if tf_label:
                    parts.append(f"TF: {tf_label}")
                if strat_txt:
                    parts.append(strat_txt)
                if pat_label:
                    parts.append(f"Pattern: {pat_label}")
                info_line = f"📊 {' | '.join(parts)}\n"

            reason_line = f"💬 เหตุผล: `{close_reason}`\n" if close_reason else ""

            result_msg = (
                f"{sig_e} *{close_type}*\n"
                "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
                f"{info_line}"
                f"\U0001f4ca {p_info.get('type','')} {p_info.get('symbol','')}\n"
                f"\U0001f4cc \u0e40\u0e1b\u0e34\u0e14: `{p_info.get('price_open',0)}`\n"
                f"\U0001f4cc \u0e1b\u0e34\u0e14: `{round(close_price,2)}`\n"
                f"\U0001f6d1 SL: `{sl_price}` | \U0001f3af TP: `{tp_price}`\n"
                f"{reason_line}"
                f"{pnl_e} P/L: `{round(profit,2)}` USD\n"
                f"\U0001f516 Ticket: `{ticket}`\n"
                f"\U0001f550 Close Time: `{close_time}`"
            )
            log_event(
                "POSITION_CLOSED",
                close_type,
                ticket=ticket,
                side=p_info.get("type", ""),
                symbol=p_info.get("symbol", ""),
                tf=tf_label,
                sid=sid_label,
                pattern=pat_label,
                trend_filter=trend_filter,
                open_price=p_info.get("price_open", 0),
                close_price=round(close_price, 2),
                sl=sl_price,
                tp=tp_price,
                profit=round(profit, 2),
                reason=close_reason,
                close_time=close_time,
            )
        else:
            sig_e = "🟢" if p_info.get("type") == "BUY" else "🔴"
            result_msg = (
                f"{sig_e} *Position \u0e1b\u0e34\u0e14\u0e41\u0e25\u0e49\u0e27*\n"
                f"\U0001f516 Ticket: `{ticket}`\n"
                f"\U0001f4ca {p_info.get('type','')} {p_info.get('symbol','')}"
            )
            log_event("POSITION_CLOSED", "Position closed without deal history", ticket=ticket, side=p_info.get("type", ""), symbol=p_info.get("symbol", ""))

        if result_msg:
            try:
                await app.bot.send_message(
                    chat_id=MY_USER_ID,
                    text=result_msg,
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        # SL Guard extra notification (sent after close message)
        if _sl_guard_extra_msg:
            try:
                await app.bot.send_message(
                    chat_id=MY_USER_ID,
                    text=_sl_guard_extra_msg,
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        # ── S10: notify strategy10 ว่า ticket ปิดแล้ว (สำหรับ continuous re-trigger) ──
        try:
            if sid_label == 10:
                from strategy10 import handle_ticket_closed
                from trailing import pending_order_tf, position_tf as _ptf
                # หา htf_tf จาก pending_order_tf หรือ position metadata
                _info = pending_order_tf.get(ticket) or {}
                _htf_tf = _info.get("s10_htf_tf", "")
                if _htf_tf:
                    handle_ticket_closed(_htf_tf, ticket, close_type)
        except Exception:
            pass

        _config.tracked_positions.pop(ticket, None)

    # อัพเดท tracked_positions ด้วย positions ใหม่ + sync SL/TP ที่เปลี่ยนไป
    if current_positions:
        for p in current_positions:
            p_type = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
            if p.ticket not in _config.tracked_positions:
                tf_label = position_tf.get(p.ticket, "")
                sid_label = position_sid.get(p.ticket)
                pat_label = position_pattern.get(p.ticket, "")
                trend_filter = position_trend_filter.get(p.ticket, "")
                if not tf_label or sid_label is None:
                    c_tf, c_sid = _parse_bot_comment(getattr(p, "comment", "") or "")
                    if not tf_label and c_tf:
                        tf_label = c_tf
                    if sid_label is None and c_sid is not None:
                        sid_label = c_sid
                _config.tracked_positions[p.ticket] = {
                    "symbol":     p.symbol,
                    "type":       p_type,
                    "price_open": p.price_open,
                    "sl":         p.sl,
                    "tp":         p.tp,
                    "tf":         tf_label,
                    "sid":        sid_label,
                    "pattern":    pat_label,
                    "trend_filter": trend_filter,
                    "comment":    getattr(p, "comment", "") or "",
                }
            else:
                # sync SL/TP ที่อาจเปลี่ยนไป (trail SL, breakeven TP ฯลฯ)
                _config.tracked_positions[p.ticket]["sl"] = p.sl
                _config.tracked_positions[p.ticket]["tp"] = p.tp
                if not _config.tracked_positions[p.ticket].get("tf"):
                    _config.tracked_positions[p.ticket]["tf"] = position_tf.get(p.ticket, "")
                if _config.tracked_positions[p.ticket].get("sid") is None:
                    _config.tracked_positions[p.ticket]["sid"] = position_sid.get(p.ticket)
                if not _config.tracked_positions[p.ticket].get("pattern"):
                    _config.tracked_positions[p.ticket]["pattern"] = position_pattern.get(p.ticket, "")
                if not _config.tracked_positions[p.ticket].get("trend_filter"):
                    _config.tracked_positions[p.ticket]["trend_filter"] = position_trend_filter.get(p.ticket, "")
                if not _config.tracked_positions[p.ticket].get("comment"):
                    _config.tracked_positions[p.ticket]["comment"] = getattr(p, "comment", "") or ""

