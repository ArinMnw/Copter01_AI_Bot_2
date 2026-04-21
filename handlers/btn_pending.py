from config import *
from mt5_utils import connect_mt5, open_order, get_existing_tp
from handlers.keyboard import (main_keyboard, build_strategy_keyboard,
    build_tf_keyboard, build_tf_keyboard_with_back,
    build_scan_keyboard, build_scan_keyboard_with_back)


async def handle_btn_pending(update, context):
    if not auth(update): return
    if not connect_mt5():
        await update.message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อ")
        return
    orders = mt5.orders_get(symbol=SYMBOL)
    if not orders:
        await update.message.reply_text("📭 ไม่มี Pending Order", reply_markup=main_keyboard())
        return
    msg = f"⏳ *Pending Orders ({len(orders)} รายการ):*\n━━━━━━━━━━━━━━━━━\n\n"
    for o in orders:
        t_map = {
            mt5.ORDER_TYPE_BUY_LIMIT:  "🟢 BUY LIMIT",
            mt5.ORDER_TYPE_BUY_STOP:   "🟢 BUY STOP",
            mt5.ORDER_TYPE_SELL_LIMIT: "🔴 SELL LIMIT",
            mt5.ORDER_TYPE_SELL_STOP:  "🔴 SELL STOP",
        }
        t = t_map.get(o.type, f"Type {o.type}")
        msg += f"{t} {getattr(o,'volume_current',o.volume_initial)}lot\n   📌 Entry:`{o.price_open}` | 🛑 SL:`{o.sl}` | 🎯 TP:`{o.tp}`\n   🔖 Ticket:`{o.ticket}`\n\n"
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=main_keyboard())

