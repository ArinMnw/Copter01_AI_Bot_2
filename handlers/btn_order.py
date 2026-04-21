from config import *
from mt5_utils import connect_mt5, open_order, get_existing_tp
from handlers.keyboard import (main_keyboard, build_strategy_keyboard,
    build_tf_keyboard, build_tf_keyboard_with_back,
    build_scan_keyboard, build_scan_keyboard_with_back)


async def handle_btn_order(update, context):
    if not auth(update): return
    if not connect_mt5():
        await update.message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อ")
        return
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        await update.message.reply_text("📭 ไม่มี Order", reply_markup=main_keyboard())
        return
    msg = f"📊 *Order ({len(positions)} รายการ):*\n━━━━━━━━━━━━━━━━━\n\n"
    total = 0
    for p in positions:
        t  = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
        e  = "🟢" if t == "BUY" else "🔴"
        pe = "🟢" if p.profit >= 0 else "🔴"
        total += p.profit
        msg += f"{e} *{t}* {p.volume}lot @ `{p.price_open}` | 🛑`{p.sl}` 🎯`{p.tp}` | {pe}`{p.profit:.2f}`\n\n"
    te = "🟢" if total >= 0 else "🔴"
    msg += f"━━━━━━━━━━━━━━━━━\n{te} *รวม:{total:.2f} USD*"
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=main_keyboard())

