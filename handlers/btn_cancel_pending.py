from config import *
from mt5_utils import connect_mt5, open_order, get_existing_tp
from handlers.keyboard import (main_keyboard, build_strategy_keyboard,
    build_tf_keyboard, build_tf_keyboard_with_back,
    build_scan_keyboard, build_scan_keyboard_with_back)


async def handle_btn_cancel_pending(update, context):
    if not auth(update): return
    if not connect_mt5():
        await update.message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อ")
        return
    orders = mt5.orders_get(symbol=SYMBOL)
    if not orders:
        await update.message.reply_text("📭 ไม่มี Pending Order ที่จะยกเลิก", reply_markup=main_keyboard())
        return
    await update.message.reply_text(
        f"⚠️ *ยืนยันยกเลิก Pending {len(orders)} Order?*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ ยืนยัน", callback_data="cancel_pending"),
            InlineKeyboardButton("❌ ยกเลิก", callback_data="cancel")
        ]])
    )

