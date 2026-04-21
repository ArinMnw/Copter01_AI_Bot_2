from config import *
from mt5_utils import connect_mt5, open_order, get_existing_tp
from handlers.keyboard import (main_keyboard, build_strategy_keyboard,
    build_tf_keyboard, build_tf_keyboard_with_back,
    build_scan_keyboard, build_scan_keyboard_with_back)


async def handle_btn_close_all(update, context):
    if not auth(update): return
    await update.message.reply_text(
        "⚠️ *ยืนยันปิดทุก Order?*", parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ ยืนยัน", callback_data="confirm_close"),
            InlineKeyboardButton("❌ ยกเลิก", callback_data="cancel")
        ]])
    )

