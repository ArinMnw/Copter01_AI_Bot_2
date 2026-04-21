from config import *
import config
from mt5_utils import connect_mt5, open_order, get_existing_tp
from handlers.keyboard import (main_keyboard, build_strategy_keyboard,
    build_tf_keyboard, build_tf_keyboard_with_back,
    build_scan_keyboard, build_scan_keyboard_with_back)


async def handle_btn_auto(update, context):
    if not auth(update): return
    status = "▶️ ทำงาน" if config.auto_active else "⏸️ หยุด"
    await update.message.reply_text(
        f"⚙️ *Auto Trade: {status}*\n⏰ สแกนทุก {config.SCAN_INTERVAL} นาที\n🕐 TF: {', '.join([tf for tf,on in TF_ACTIVE.items() if on]) or 'ยังไม่ได้เลือก'}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⏸️ หยุด" if config.auto_active else "▶️ เปิด", callback_data="toggle_auto")
        ]])
    )

