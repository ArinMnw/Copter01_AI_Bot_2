from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from handlers.keyboard import main_keyboard


def _build_demo_portfolio_view():
    import demo_portfolio
    import config
    names = list(getattr(demo_portfolio, "PORTFOLIO_ORDER", ("P13", "P16")))
    detail_symbol = str(getattr(config, "DEMO_PORTFOLIO_DETAIL_SYMBOL", "XAUUSD") or "XAUUSD").upper()
    active_names = [name for name in names if config.DEMO_PORTFOLIO_ACTIVE.get(name)]

    if detail_symbol == "BTCUSD":
        if active_names:
            sections = [demo_portfolio.get_symbol_exposure_text("BTCUSD")]
        else:
            sections = ["_ยังไม่มี Demo Portfolio เปิดอยู่ จึงไม่แสดงรายละเอียด_"]
    else:
        if active_names:
            sections = [demo_portfolio.get_status_text(name) for name in active_names]
        else:
            sections = ["_ยังไม่มี Demo Portfolio เปิดอยู่ จึงไม่แสดงรายละเอียด_"]

    text = (
        "🧪 *Demo Portfolio* (ทดสอบแยกอิสระจากบอทหลัก)\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        f"รายละเอียด: *{detail_symbol}*\n\n"
        + "\n\n━━━━━━━━━━━━━━━━━\n\n".join(sections)
    )
    rows = []
    rows.append([
        InlineKeyboardButton(
            ("✅ XAUUSD" if detail_symbol == "XAUUSD" else "XAUUSD"),
            callback_data="demo_view_xauusd",
        ),
        InlineKeyboardButton(
            ("✅ BTCUSD" if detail_symbol == "BTCUSD" else "BTCUSD"),
            callback_data="demo_view_btcusd",
        ),
    ])
    for i in range(0, len(names), 2):
        row = []
        for name in names[i:i + 2]:
            label = f"⏸️ หยุด {name}" if config.DEMO_PORTFOLIO_ACTIVE.get(name) else f"▶️ เปิด {name}"
            row.append(InlineKeyboardButton(label, callback_data=f"demo_{name.lower()}_toggle"))
        rows.append(row)
    weight_label = "AF Weight ON" if config.DEMO_PORTFOLIO_AF_WEIGHT_ENABLED else "AF Weight OFF"
    scale_label = f"Scale {float(config.DEMO_PORTFOLIO_AF_WEIGHT_SCALE):.2f}x"
    rows.append([
        InlineKeyboardButton(weight_label, callback_data="demo_af_weight_toggle"),
        InlineKeyboardButton(scale_label, callback_data="demo_af_weight_scale"),
    ])
    rows.append([InlineKeyboardButton("🔄 รีเฟรช", callback_data="demo_refresh")])
    kb = InlineKeyboardMarkup(rows)
    return text, kb


async def handle_btn_demo_portfolio(update, context):
    text, kb = _build_demo_portfolio_view()
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())
    await update.message.reply_text("ควบคุม Demo Portfolio:", reply_markup=kb)
