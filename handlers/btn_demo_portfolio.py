from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from handlers.keyboard import main_keyboard


def _build_demo_portfolio_view(context=None):
    import demo_portfolio
    import config
    
    managed = context.user_data.get("demo_manage_portfolio") if context else None
    group_id = context.user_data.get("demo_manage_group") if context else None
    
    if managed and managed in demo_portfolio.PORTFOLIO_ORDER:
        active = config.DEMO_PORTFOLIO_ACTIVE.get(managed, False)
        text = f"⚙️ *จัดการ {managed}*\n━━━━━━━━━━━━━━━━━\n\n"
        if active:
            text += demo_portfolio.get_status_text(managed)
        else:
            text += f"พอร์ต {managed} ปิดอยู่"
        
        rows = []
        label_active = f"⏸️ หยุด {managed}" if active else f"▶️ เปิด {managed}"
        rows.append([InlineKeyboardButton(label_active, callback_data=f"demo_{managed.lower()}_toggle")])
        
        if managed in getattr(demo_portfolio, "AF_PORTFOLIO_LEGS", {}) or managed.startswith("LTS"):
            weight_on = getattr(config, "DEMO_PORTFOLIO_WEIGHT_ENABLED", {}).get(managed, False)
            scale = getattr(config, "DEMO_PORTFOLIO_WEIGHT_SCALE", {}).get(managed, 1.0)
            label_w = f"⚖️ {managed} Weight ON" if weight_on else f"⚖️ {managed} Weight OFF"
            label_s = f"🔍 Scale {scale:.2f}x"
            rows.append([
                InlineKeyboardButton(label_w, callback_data=f"demo_weight_toggle"),
                InlineKeyboardButton(label_s, callback_data=f"demo_scale_toggle")
            ])
            
            if managed.startswith("LTS"):
                dyn_lot = getattr(config, "DYNAMIC_LOT_ENABLED", {}).get(managed, False)
                smart_cut = getattr(config, "SMART_CUTLOSS_ENABLED", {}).get(managed, False)
                mom_stall = getattr(config, "MOMENTUM_STALL_EXIT_ENABLED", {}).get(managed, False)
                rows.append([
                    InlineKeyboardButton(f"📦 P3 Dyn. Lot: {'🟢' if dyn_lot else '🔴'}", callback_data="demo_p3_dyn_lot_toggle"),
                    InlineKeyboardButton(f"🚪 P4 Smart Exit: {'🟢' if smart_cut else '🔴'}", callback_data="demo_p4_smart_exit_toggle")
                ])
                rows.append([
                    InlineKeyboardButton(f"🛑 P4 Mom. Stall: {'🟢' if mom_stall else '🔴'}", callback_data="demo_p4_mom_stall_toggle")
                ])
            
        rows.append([
            InlineKeyboardButton("🔄 รีเฟรช", callback_data="demo_refresh"),
            InlineKeyboardButton("◀️ กลับ", callback_data="demo_manage_back")
        ])
        return text, InlineKeyboardMarkup(rows)

    detail_symbol = str(getattr(config, "DEMO_PORTFOLIO_DETAIL_SYMBOL", "XAUUSD") or "XAUUSD").upper()
    active_names = [name for name in demo_portfolio.PORTFOLIO_ORDER if config.DEMO_PORTFOLIO_ACTIVE.get(name)]

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

    if group_id and group_id in demo_portfolio.DEMO_GROUPS:
        # Show Portfolios in the selected group
        group_info = demo_portfolio.DEMO_GROUPS[group_id]
        names = group_info["keys"]
        for i in range(0, len(names), 2):
            row = []
            for name in names[i:i + 2]:
                icon = "✅" if config.DEMO_PORTFOLIO_ACTIVE.get(name) else "⚙️"
                row.append(InlineKeyboardButton(f"{icon} {name}", callback_data=f"demo_manage_{name.lower()}"))
            rows.append(row)
        rows.append([
            InlineKeyboardButton("🔄 รีเฟรช", callback_data="demo_refresh"),
            InlineKeyboardButton("◀️ กลับหน้ารวมกลุ่ม", callback_data="demo_group_back")
        ])
    else:
        # Show Groups
        groups = list(demo_portfolio.DEMO_GROUPS.items())
        for i in range(0, len(groups), 2):
            row = []
            for g_id, g_info in groups[i:i + 2]:
                # Check if any portfolio in group is active
                is_active = any(config.DEMO_PORTFOLIO_ACTIVE.get(k) for k in g_info["keys"])
                title = f"{'✅ ' if is_active else ''}{g_info['title']}"
                row.append(InlineKeyboardButton(title, callback_data=f"demo_group_{g_id.lower()}"))
            rows.append(row)
        rows.append([InlineKeyboardButton("🔄 รีเฟรช", callback_data="demo_refresh")])

    kb = InlineKeyboardMarkup(rows)
    return text, kb


async def handle_btn_demo_portfolio(update, context):
    context.user_data.pop("demo_manage_portfolio", None)
    context.user_data.pop("demo_manage_group", None)
    text, kb = _build_demo_portfolio_view(context)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())
    await update.message.reply_text("ควบคุม Demo Portfolio:", reply_markup=kb)
