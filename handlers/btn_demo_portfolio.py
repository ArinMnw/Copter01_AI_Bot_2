from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from handlers.keyboard import main_keyboard


def _build_demo_portfolio_view():
    import demo_portfolio
    text = (
        "🧪 *Demo Portfolio* (ทดสอบแยกอิสระจากบอทหลัก)\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        f"{demo_portfolio.get_status_text('P13')}\n\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        f"{demo_portfolio.get_status_text('P16')}"
    )
    import config
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "⏸️ หยุด P13" if config.DEMO_PORTFOLIO_ACTIVE.get("P13") else "▶️ เปิด P13",
            callback_data="demo_p13_toggle"),
         InlineKeyboardButton(
            "⏸️ หยุด P16" if config.DEMO_PORTFOLIO_ACTIVE.get("P16") else "▶️ เปิด P16",
            callback_data="demo_p16_toggle")],
        [InlineKeyboardButton("🔄 รีเฟรช", callback_data="demo_refresh")],
    ])
    return text, kb


async def handle_btn_demo_portfolio(update, context):
    text, kb = _build_demo_portfolio_view()
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())
    await update.message.reply_text("ควบคุม Demo Portfolio:", reply_markup=kb)
