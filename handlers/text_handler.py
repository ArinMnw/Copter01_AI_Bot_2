from config import *
import config
from handlers.keyboard import main_keyboard, show_main_settings_menu, show_strategy_menu

from handlers.btn_price import handle_btn_price
from handlers.btn_balance import handle_btn_balance
from handlers.btn_buy import handle_btn_buy
from handlers.btn_sell import handle_btn_sell
from handlers.btn_order import handle_btn_order
from handlers.btn_close_all import handle_btn_close_all
from handlers.btn_scan_now import handle_btn_scan_now
from handlers.btn_auto import handle_btn_auto
from handlers.btn_pending import handle_btn_pending
from handlers.btn_cancel_pending import handle_btn_cancel_pending
from handlers.btn_settings import handle_btn_settings
from handlers.btn_tf import handle_btn_tf
from handlers.btn_profit import handle_btn_profit
from mt5_utils import connect_mt5
from handlers.keyboard import main_keyboard
from datetime import datetime, timedelta


# Route map: ข้อความปุ่ม → handler function
BUTTON_ROUTES = {
    "📈 ราคาทอง":        handle_btn_price,
    "💰 ยอดเงิน":         handle_btn_balance,
    "🟢 BUY":             handle_btn_buy,
    "🔴 SELL":            handle_btn_sell,
    "📊 Order":           handle_btn_order,
    "❌ ปิดทั้งหมด":      handle_btn_close_all,
    "🤖 สแกนตอนนี้":     handle_btn_scan_now,
    "⚙️ สถานะ Auto":      handle_btn_auto,
    "⏳ Pending Orders":  handle_btn_pending,
    "🗑️ ยกเลิก Pending": handle_btn_cancel_pending,
    "⚙️ ตั้งค่า":         handle_btn_settings,
    "🕐 เลือก Timeframe": handle_btn_tf,
    "📊 สรุปกำไร":        handle_btn_profit,
}


async def handle_buttons(update, context):
    """Route ข้อความปุ่มไปยัง handler ที่ถูกต้อง"""
    global auto_active
    if not auth(update):
        await alert_intruder(update)
        return

    text = update.message.text

    # ── ตรวจ waiting_lot_input ก่อน ──────────────────────────────
    waiting = context.user_data.get("waiting_lot_input")
    if waiting:
        await _handle_lot_input(update, context, text, waiting)
        return

    stripped = text.strip()
    if stripped.isdigit():
        await _handle_ticket_lookup(update, int(stripped))
        return

    handler = BUTTON_ROUTES.get(text)
    if handler:
        await handler(update, context)
    else:
        await update.message.reply_text(
            f"❓ ไม่รู้จักคำสั่ง: {text}",
            reply_markup=main_keyboard()
        )


async def _handle_lot_input(update, context, text, waiting):
    """รับ lot size จาก user input"""
    context.user_data.pop("waiting_lot_input", None)

    try:
        lot = round(float(text.strip()), 2)
        if lot < 0.01 or lot > 10.0:
            raise ValueError("out of range")
    except (ValueError, TypeError):
        await update.message.reply_text(
            f"❌ ค่าไม่ถูกต้อง: `{text}`\n"
            "กรุณากรอกตัวเลข เช่น `0.03` (ขั้นต่ำ 0.01 สูงสุด 10.0)",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        return

    if waiting == "auto":
        # ตั้งค่า lot สำหรับ auto trade
        import config as cfg_mod
        cfg_mod.AUTO_VOLUME = lot
        config.AUTO_VOLUME  = lot
        save_runtime_state()
        await update.message.reply_text(
            f"✅ *ตั้งค่า Lot Auto สำเร็จ*\n📦 Lot: `{lot}`",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    elif waiting.startswith("manual_"):
        # manual order BUY/SELL ด้วย lot ที่กรอก
        # format: manual_buy_4600.5 หรือ manual_sell_4600.5
        parts   = waiting.split("_")
        direction = parts[1]
        price_str = parts[2]

        if not connect_mt5():
            await update.message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อ", reply_markup=main_keyboard())
            return

        try:
            price = float(price_str)
        except ValueError:
            tick  = mt5.symbol_info_tick(SYMBOL)
            price = (tick.ask if direction == "buy" else tick.bid) if tick else 0

        ot  = mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL
        sl  = round(price - 15, 2) if direction == "buy" else round(price + 15, 2)
        tp  = round(price + 30, 2) if direction == "buy" else round(price - 30, 2)
        e   = "🟢" if direction == "buy" else "🔴"

        r = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL,
            "volume": lot, "type": ot, "price": price,
            "sl": sl, "tp": tp, "deviation": 20, "magic": 234001,
            "comment": "Manual-Custom", "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        })
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            await update.message.reply_text(
                f"✅ *เปิดสำเร็จ!* {e} {direction.upper()} `{lot}` lot @ `{price}`\n"
                f"🛑 `{sl}` 🎯 `{tp}` 🔖 `{r.order}`",
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
        else:
            err = r.retcode if r else "no result"
            await update.message.reply_text(
                f"❌ ไม่สำเร็จ: {err}",
                reply_markup=main_keyboard()
            )


def _fmt_dt(ts):
    try:
        return fmt_mt5_bkk_ts(ts, "%d/%m %H:%M:%S")
    except Exception:
        return "-"


def _deal_type_name(deal_type):
    mapping = {
        mt5.DEAL_TYPE_BUY: "BUY",
        mt5.DEAL_TYPE_SELL: "SELL",
        mt5.DEAL_TYPE_BALANCE: "BAL",
        mt5.DEAL_TYPE_CREDIT: "CREDIT",
        mt5.DEAL_TYPE_CHARGE: "CHARGE",
        mt5.DEAL_TYPE_CORRECTION: "CORR",
        mt5.DEAL_TYPE_BONUS: "BONUS",
        mt5.DEAL_TYPE_COMMISSION: "COMM",
        mt5.DEAL_TYPE_COMMISSION_DAILY: "COMM_DAY",
        mt5.DEAL_TYPE_COMMISSION_MONTHLY: "COMM_MON",
        mt5.DEAL_TYPE_COMMISSION_AGENT_DAILY: "COMM_AG_DAY",
        mt5.DEAL_TYPE_COMMISSION_AGENT_MONTHLY: "COMM_AG_MON",
        mt5.DEAL_TYPE_INTEREST: "INTEREST",
        mt5.DEAL_TYPE_BUY_CANCELED: "BUY_CANCEL",
        mt5.DEAL_TYPE_SELL_CANCELED: "SELL_CANCEL",
    }
    return mapping.get(deal_type, str(deal_type))


def _deal_entry_name(entry_type):
    mapping = {
        mt5.DEAL_ENTRY_IN: "IN",
        mt5.DEAL_ENTRY_OUT: "OUT",
        mt5.DEAL_ENTRY_INOUT: "INOUT",
        mt5.DEAL_ENTRY_OUT_BY: "OUT_BY",
    }
    return mapping.get(entry_type, str(entry_type))


def _order_type_name(order_type):
    mapping = {
        mt5.ORDER_TYPE_BUY: "BUY",
        mt5.ORDER_TYPE_SELL: "SELL",
        mt5.ORDER_TYPE_BUY_LIMIT: "BUY_LIMIT",
        mt5.ORDER_TYPE_SELL_LIMIT: "SELL_LIMIT",
        mt5.ORDER_TYPE_BUY_STOP: "BUY_STOP",
        mt5.ORDER_TYPE_SELL_STOP: "SELL_STOP",
        mt5.ORDER_TYPE_BUY_STOP_LIMIT: "BUY_STOP_LIMIT",
        mt5.ORDER_TYPE_SELL_STOP_LIMIT: "SELL_STOP_LIMIT",
        mt5.ORDER_TYPE_CLOSE_BY: "CLOSE_BY",
    }
    return mapping.get(order_type, str(order_type))


async def _handle_ticket_lookup(update, ticket: int):
    """พิมพ์เลข ticket ใน Telegram เพื่อดู log/order history ของใบนั้น"""
    if not connect_mt5():
        await update.message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อ", reply_markup=main_keyboard())
        return

    import trailing

    now = datetime.now()
    dt_from = now - timedelta(days=30)
    dt_to = now + timedelta(days=1)

    positions = mt5.positions_get() or []
    orders_now = mt5.orders_get() or []
    deals = mt5.history_deals_get(dt_from, dt_to) or []
    orders_hist = mt5.history_orders_get(dt_from, dt_to) or []

    pos = next((p for p in positions if int(p.ticket) == ticket), None)
    cur_order = next((o for o in orders_now if int(o.ticket) == ticket), None)

    linked_orders = [
        o for o in orders_hist
        if int(getattr(o, "ticket", 0)) == ticket
        or int(getattr(o, "position_id", 0)) == ticket
    ]
    linked_deals = [
        d for d in deals
        if int(getattr(d, "position_id", 0)) == ticket
        or int(getattr(d, "order", 0)) == ticket
        or int(getattr(d, "ticket", 0)) == ticket
    ]

    tf_name = trailing.position_tf.get(ticket) or trailing.pending_order_tf.get(ticket, {}).get("tf", "-")
    sid = trailing.position_sid.get(ticket, trailing.pending_order_tf.get(ticket, {}).get("sid", "-"))
    pattern = trailing.position_pattern.get(ticket, "-")
    entry_state = trailing._entry_state.get(ticket, "-")
    trail_state = trailing._trail_state.get(ticket, {})
    mt5_to_bkk_hours = TZ_OFFSET - MT5_SERVER_TZ
    tz_summary = f"MT5->BKK +{mt5_to_bkk_hours} | MT5 Server UTC+{MT5_SERVER_TZ} | Display BKK"


    if not pos and not cur_order and not linked_orders and not linked_deals:
        await update.message.reply_text(
            f"🔎 ไม่พบข้อมูล ticket `{ticket}` ใน current/history 30 วัน",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        return

    lines = [
        f"🔎 *Ticket Lookup*",
        f"🔖 Ticket: `{ticket}`",
        f"🕒 Time Mode: `{tz_summary}`",
        f"🕐 TF: `{tf_name}` | SID: `{sid}`",
        f"🏷 Pattern: `{pattern}`",
        f"📋 Entry state: `{entry_state}`",
    ]

    if trail_state:
        lines.append(f"📐 Trail state: `{trail_state}`")

    if pos:
        side = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        lines += [
            "",
            "*Current Position*",
            f"{side} {pos.symbol} vol=`{pos.volume}`",
            f"📌 Open:`{pos.price_open}` | 🛑 SL:`{pos.sl}` | 🎯 TP:`{pos.tp}`",
            f"💵 Profit:`{pos.profit}` | Time:`{_fmt_dt(pos.time)}`",
        ]

    if cur_order:
        lines += [
            "",
            "*Current Pending/Order*",
            f"`{_order_type_name(cur_order.type)}` {cur_order.symbol} vol=`{getattr(cur_order, 'volume_current', cur_order.volume_initial)}`",
            f"📌 Open:`{cur_order.price_open}` | 🛑 SL:`{cur_order.sl}` | 🎯 TP:`{cur_order.tp}`",
            f"🕐 Time:`{_fmt_dt(cur_order.time_setup)}` | Comment:`{getattr(cur_order, 'comment', '')}`",
        ]

    if linked_orders:
        lines += ["", "*Order History*"]
        for o in sorted(linked_orders, key=lambda x: getattr(x, "time_setup", 0))[-8:]:
            lines.append(
                f"`{_fmt_dt(getattr(o, 'time_setup', 0))}` {_order_type_name(o.type)} state=`{getattr(o, 'state', '-')}` "
                f"open=`{getattr(o, 'price_open', 0)}` sl=`{getattr(o, 'sl', 0)}` tp=`{getattr(o, 'tp', 0)}`"
            )

    if linked_deals:
        lines += ["", "*Deal History*"]
        for d in sorted(linked_deals, key=lambda x: getattr(x, "time", 0))[-12:]:
            lines.append(
                f"`{_fmt_dt(getattr(d, 'time', 0))}` {_deal_type_name(d.type)}/{_deal_entry_name(d.entry)} "
                f"price=`{getattr(d, 'price', 0)}` vol=`{getattr(d, 'volume', 0)}` "
                f"profit=`{round(float(getattr(d, 'profit', 0.0)), 2)}`"
            )

    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3900] + "\n\n`...truncated...`"

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

async def start(update, context):
    if not auth(update):
        await alert_intruder(update)
        return
    status = "▶️ ทำงาน" if auto_active else "⏸️ หยุด"
    await update.message.reply_text(
        f"🤖 *Copter Gold Bot — ท่าที่ 1*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📊 A: กลืนกิน (เขียว/แดง 2 แท่ง)\n"
        f"📊 B: ตำหนิ (เขียว/แดง 2 แท่ง)\n"
        f"⏰ สแกนทุก {config.SCAN_INTERVAL} นาที\n"
        f"🕐 TF: {', '.join([tf for tf,on in TF_ACTIVE.items() if on]) or 'ยังไม่ได้เลือก'}\n"
        f"📦 Lot:{AUTO_VOLUME} | Max:{MAX_ORDERS} | Auto:{status}",
        parse_mode='Markdown', reply_markup=main_keyboard()
    )


# alias สำหรับ main.py
handle_text = handle_buttons
