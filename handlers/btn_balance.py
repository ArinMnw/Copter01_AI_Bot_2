from config import *
from mt5_utils import connect_mt5, open_order, get_existing_tp
from handlers.keyboard import (main_keyboard, build_strategy_keyboard,
    build_tf_keyboard, build_tf_keyboard_with_back,
    build_scan_keyboard, build_scan_keyboard_with_back)


async def handle_btn_balance(update, context):
    if not auth(update): return
    if not connect_mt5():
        await update.message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อ")
        return
    info = mt5.account_info()
    if not info:
        await update.message.reply_text("❌ ดึงข้อมูลไม่ได้")
        return
    await update.message.reply_text(
        f"💰 *บัญชี {info.login}*\n💵 Balance:`{info.balance:.2f}` | Equity:`{info.equity:.2f}`\n✅ Free:`{info.margin_free:.2f}`",
        parse_mode='Markdown', reply_markup=main_keyboard()
    )

