from config import *
from mt5_utils import connect_mt5, open_order, get_existing_tp
from handlers.keyboard import (main_keyboard, build_strategy_keyboard,
    build_tf_keyboard, build_tf_keyboard_with_back,
    build_scan_keyboard, build_scan_keyboard_with_back)


async def handle_btn_price(update, context):
    if not auth(update): return
    if not connect_mt5():
        await update.message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อ")
        return
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        await update.message.reply_text("❌ ดึงราคาไม่ได้")
        return
    await update.message.reply_text(
        f"📈 *{SYMBOL}*\n🟢 Ask:`{tick.ask}` | 🔴 Bid:`{tick.bid}`\n📊 Spread:`{round((tick.ask-tick.bid)*10,1)}`",
        parse_mode='Markdown', reply_markup=main_keyboard()
    )

