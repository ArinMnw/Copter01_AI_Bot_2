from config import *
import config
from mt5_utils import connect_mt5
from datetime import datetime, timedelta, timezone
from bot_log import BOT_LOG_FILE, get_monthly_bot_log_file
import re
import os

def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📈 ราคาทอง"), KeyboardButton("💰 ยอดเงิน")],
        [KeyboardButton("🟢 BUY"), KeyboardButton("🔴 SELL")],
        [KeyboardButton("📊 Order"), KeyboardButton("❌ ปิดทั้งหมด")],
        [KeyboardButton("🤖 สแกนตอนนี้"), KeyboardButton("⚙️ สถานะ Auto")],
        [KeyboardButton("⏳ Pending Orders"), KeyboardButton("🗑️ ยกเลิก Pending")],
        [KeyboardButton("📊 สรุปกำไร"), KeyboardButton("⚙️ ตั้งค่า")],
    ], resize_keyboard=True)


async def start(update, context):
    if not auth(update):
        await alert_intruder(update)
        return
    status = "▶️ ทำงาน" if auto_active else "⏸️ หยุด"
    await update.message.reply_text(
        f"🤖 *Copter Gold Bot — ท่าที่ 1*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📊 A: กลืนกิน (เขียว/แดง 2 แท่ง)\n"
        f"📊 B: ตำหนิ (เขียว/แดง 2 แท่ง)\n"
        f"⏰ สแกนทุก {config.SCAN_INTERVAL} นาที\n"
        f"🕐 TF: {', '.join([tf for tf, on in TF_ACTIVE.items() if on]) or 'ยังไม่ได้เลือก'}\n"
        f"📦 Lot:{AUTO_VOLUME} | Max:{MAX_ORDERS} | Auto:{status}",
        parse_mode='Markdown', reply_markup=main_keyboard()
    )



async def show_main_settings_menu(update_or_query, is_query=False):
    """เมนูหลักสำหรับตั้งค่า Strategy, TF, Scan และ Lot"""
    active_tfs = [tf for tf, on in TF_ACTIVE.items() if on]
    tf_summary = ", ".join(active_tfs) if active_tfs else "ยังไม่ได้เลือก"
    strat_list = [STRATEGY_NAMES[sid] for sid, on in active_strategies.items() if on]
    strat_summ = ", ".join(strat_list) if strat_list else "ไม่มี"
    trail_mode_label = "รวม phase" if config.TRAIL_SL_ENGULF_MODE == "combined" else "แยก phase"
    if config.ENTRY_CANDLE_MODE == "classic":
        entry_mode_label = "Classic"
    elif config.ENTRY_CANDLE_MODE == "close_percentage":
        entry_mode_label = "Close Percentage"
    else:
        market_label = "M:ON" if config.ENTRY_CLOSE_REVERSE_MARKET else "M:OFF"
        limit_label = "L:ON" if config.ENTRY_CLOSE_REVERSE_LIMIT else "L:OFF"
        entry_mode_label = f"Close | {market_label} {limit_label}"
    opp_label = "ตั้ง TP+ปิด" if config.OPPOSITE_ORDER_MODE == "tp_close" else "ตั้ง SL Protect"
    lg_label = f"ON ({config.LIMIT_GUARD_POINTS}pt)" if config.LIMIT_GUARD else "OFF"
    engulf_label = f"{config.ENGULF_MIN_POINTS}pt"
    lbc_on_tfs = [tf for tf, on in config.LIMIT_BREAK_CANCEL_TF.items() if on]
    lbc_label = f"ON ({len(lbc_on_tfs)}TF)" if config.LIMIT_BREAK_CANCEL else "OFF"
    trail_suffix = f"🟢ON | Engulf / {trail_mode_label}{' ⚡' if config.TRAIL_SL_IMMEDIATE else ''}" if config.TRAIL_SL_ENABLED else "🔴OFF"
    entry_suffix = f"🟢ON | {entry_mode_label}" if config.ENTRY_CANDLE_ENABLED else "🔴OFF"
    opp_suffix = f"🟢ON | {opp_label}" if config.OPPOSITE_ORDER_ENABLED else "🔴OFF"
    entry_tp_suffix = "🟢ON" if config.ENTRY_CANDLE_UPDATE_TP else "🔴OFF"
    sweep_suffix = "🟢ON" if config.LIMIT_SWEEP else "🔴OFF"
    if config.DELAY_SL_MODE == "off":
        delay_sl_suffix = "🔴OFF"
    elif config.DELAY_SL_MODE == "time":
        delay_sl_suffix = "🟢ON | ช่วงท้าย TF"
    else:
        delay_sl_suffix = "🟢ON | ราคาผ่าน Entry"
    tf_parts = []
    per_tf_on_list = [t for t, on in config.TREND_FILTER_PER_TF.items() if on]
    if per_tf_on_list:
        tf_parts.append(f"Per-TF({len(per_tf_on_list)})")
    if config.TREND_FILTER_HIGHER_TF_ENABLED:
        tf_parts.append(f"Higher({config.TREND_FILTER_HIGHER_TF})")
    if config.TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED:
        tf_parts.append("TrailSL")
    trend_filter_suffix = f"🟢ON | {' + '.join(tf_parts)}" if tf_parts else "🔴OFF"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 เลือก Strategy", callback_data="open_strategy_menu")],
        [InlineKeyboardButton(f"📐 Trail SL: {trail_suffix}", callback_data="open_trail_menu")],
        [InlineKeyboardButton(f"🕯 Entry Candle Mode: {entry_suffix}", callback_data="open_entry_candle_mode_menu")],
        [InlineKeyboardButton(f"🎯 Entry Candle TP: {entry_tp_suffix}", callback_data="toggle_entry_candle_tp")],
        [InlineKeyboardButton(f"🔄 Opposite Order: {opp_suffix}", callback_data="open_opposite_menu")],
        [InlineKeyboardButton(f"🧹 Limit Sweep: {sweep_suffix}", callback_data="toggle_limit_sweep")],
        [InlineKeyboardButton(f"🕐 Delay SL: {delay_sl_suffix}", callback_data="cycle_delay_sl")],
        [InlineKeyboardButton(f"🧯 Limit TP/SL Break: {lbc_label}", callback_data="open_limit_break_menu")],
        [InlineKeyboardButton(f"🛡 Limit Guard: {lg_label}", callback_data="open_limit_guard_menu")],
        [InlineKeyboardButton(f"📏 Engulf ขั้นต่ำ: {engulf_label}", callback_data="open_engulf_menu")],
        [InlineKeyboardButton(f"🧭 Trend Filter: {trend_filter_suffix}", callback_data="open_trend_filter_menu")],
        [InlineKeyboardButton("🧪 Debug", callback_data="open_debug_menu")],
        [InlineKeyboardButton("⏰ ตั้งค่า Scan", callback_data="open_scan_menu")],
        [InlineKeyboardButton("🕐 เลือก Timeframe", callback_data="open_tf_menu")],
        [InlineKeyboardButton(f"📦 Lot Size Auto: {config.AUTO_VOLUME}", callback_data="open_lot_menu")],
        [InlineKeyboardButton("♻️ Reset Config", callback_data="reset_config_prompt")],
        [InlineKeyboardButton("🔙 กลับ", callback_data="close_settings")],
    ])
    text = (
        f"⚙️ *ตั้งค่า Auto Trade*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📋 Strategy: *{strat_summ}*\n"
        f"📊 ท่า 2 Mode: *{'ปกติ' if config.FVG_NORMAL else ''}{'+' if config.FVG_NORMAL and config.FVG_PARALLEL else ''}{'Parallel' if config.FVG_PARALLEL else ''}{'(ปิดหมด)' if not config.FVG_NORMAL and not config.FVG_PARALLEL else ''}*\n"
        f"📐 Trail SL: *{trail_suffix}*\n"
        f"🕯 Entry Candle Mode: *{entry_suffix}*\n"
        f"🎯 Entry Candle TP: *{entry_tp_suffix}*\n"
        f"🔄 Opposite Order: *{opp_suffix}*\n"
        f"🧹 Limit Sweep: *{sweep_suffix}*\n"
        f"🕐 Delay SL: *{delay_sl_suffix}*\n"
        f"🧯 Limit TP/SL Break: *{lbc_label}*\n"
        f"🛡 Limit Guard: *{lg_label}*\n"
        f"📏 Engulf ขั้นต่ำ: *{engulf_label}*\n"
        f"🧭 Trend Filter: *{trend_filter_suffix}*\n"
        f"🧪 Debug: *Queue {'ON' if config.TG_QUEUE_DEBUG else 'OFF'} | SLTP {'ON' if config.SLTP_AUDIT_DEBUG else 'OFF'} | Trade {'ON' if config.TRADE_DEBUG else 'OFF'}*\n"
        f"⏰ Scan: *ทุก {config.SCAN_INTERVAL} นาที*\n"
        f"🕐 Timeframe: *{tf_summary}*\n"
        f"📦 Lot Auto: *{config.AUTO_VOLUME}*\n\n"
        f"เลือกเมนูที่ต้องการ:"
    )
    if is_query:
        try:
            await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

def build_lot_keyboard():
    """ปุ่มเลือก Lot Size สำหรับ Auto Trade"""
    row = []
    for lot in config.LOT_OPTIONS:
        label = f"{'✅ ' if lot == config.AUTO_VOLUME else ''}{lot}"
        row.append(InlineKeyboardButton(label, callback_data=f"set_lot_{lot}"))
    return InlineKeyboardMarkup([row, [
        InlineKeyboardButton("✏️ กรอกเอง", callback_data="lot_custom_input"),
        InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")
    ]])


def build_trail_menu():
    mode_label = "รวม phase" if config.TRAIL_SL_ENGULF_MODE == "combined" else "แยก phase"
    trail_label = f"Engulf / {mode_label} ✅" if config.TRAIL_SL_MODE == "engulf" else f"Engulf / {mode_label}"
    imm_label = "🟢 Trail ทันที (ไม่รอ done)" if config.TRAIL_SL_IMMEDIATE else "⬜ Trail ทันที (ไม่รอ done)"
    en_label = "🟢 เปิดใช้งาน Trail SL" if config.TRAIL_SL_ENABLED else "🔴 ปิดใช้งาน Trail SL"
    focus_status = f"🟢ON | {config.TRAIL_SL_FOCUS_NEW_POINTS}pt" if config.TRAIL_SL_FOCUS_NEW_ENABLED else "🔴OFF"
    focus_label = f"🎯 Focus Opposite ใหม่: {focus_status}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(en_label, callback_data="toggle_trail_sl_enabled")],
        [InlineKeyboardButton(trail_label, callback_data="open_trail_engulf_menu")],
        [InlineKeyboardButton(imm_label, callback_data="toggle_trail_immediate")],
        [InlineKeyboardButton(focus_label, callback_data="open_trail_focus_menu")],
        [InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")],
    ])


def build_trail_engulf_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{'🔵' if config.TRAIL_SL_ENGULF_MODE == 'combined' else '⬜'} รวม phase",
                callback_data="set_trail_engulf_mode_combined"
            ),
            InlineKeyboardButton(
                f"{'🔵' if config.TRAIL_SL_ENGULF_MODE == 'separate' else '⬜'} แยก phase",
                callback_data="set_trail_engulf_mode_separate"
            ),
        ],
        [InlineKeyboardButton("🔙 กลับ", callback_data="open_trail_menu")],
    ])


def build_trail_focus_keyboard():
    toggle_label = (
        "🟢 เปิด Trail Focus Opposite ใหม่"
        if config.TRAIL_SL_FOCUS_NEW_ENABLED
        else "🔴 ปิด Trail Focus Opposite ใหม่"
    )
    tf_mode = config.TRAIL_SL_FOCUS_NEW_TF_MODE
    tf_label = "🔀 รวม TF" if tf_mode == "combined" else "📌 แยก TF"
    pts = config.TRAIL_SL_FOCUS_NEW_POINTS
    pt_options = [0, 100, 200, 300, 500]
    pt_row = [
        InlineKeyboardButton(
            f"{'🔵' if pts == p else '⬜'} {p}pt",
            callback_data=f"set_tfn_pts_{p}"
        )
        for p in pt_options
    ]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_label, callback_data="toggle_trail_focus_new")],
        [InlineKeyboardButton(tf_label, callback_data="toggle_tfn_tf_mode")],
        pt_row,
        [InlineKeyboardButton("🔙 กลับ", callback_data="open_trail_menu")],
    ])


async def show_trail_focus_menu(update_or_query, is_query=False):
    status = f"🟢ON | {config.TRAIL_SL_FOCUS_NEW_POINTS}pt" if config.TRAIL_SL_FOCUS_NEW_ENABLED else "🔴OFF"
    tf_desc = "รวมทุก TF" if config.TRAIL_SL_FOCUS_NEW_TF_MODE == "combined" else "แยกตาม TF"
    text = (
        "🎯 *Trail Focus Opposite ใหม่*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"สถานะ: *{status}*\n"
        f"โหมด TF: *{tf_desc}*\n\n"
        "เมื่อ BUY position กำไร > threshold + spread\n"
        "และมี SELL ฝั่งตรงข้าม (position/pending limit)\n"
        "→ ไม่ trail BUY ตัวนั้น trail เฉพาะ SELL ที่พึ่งเปิด\n"
        "(ฝั่ง SELL ทำงานสลับกัน)\n\n"
        "📌 แยก TF = จับคู่เฉพาะ TF เดียวกัน\n"
        "🔀 รวม TF = จับคู่ข้าม TF ได้\n\n"
        "เลือก toggle / TF mode / threshold:"
    )
    keyboard = build_trail_focus_keyboard()
    if is_query:
        try:
            await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


def build_debug_keyboard():
    queue_label = "🟢 Queue: ON" if config.TG_QUEUE_DEBUG else "⬜ Queue: OFF"
    sltp_label = "🟢 SL/TP Audit: ON" if config.SLTP_AUDIT_DEBUG else "⬜ SL/TP Audit: OFF"
    trade_label = "🟢 Trade: ON" if config.TRADE_DEBUG else "⬜ Trade: OFF"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(queue_label, callback_data="toggle_debug_queue")],
        [InlineKeyboardButton(sltp_label, callback_data="toggle_debug_sltp")],
        [InlineKeyboardButton(trade_label, callback_data="toggle_debug_trade")],
        [InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")],
    ])


async def show_debug_menu(update_or_query, is_query=False):
    queue_label = "ON" if config.TG_QUEUE_DEBUG else "OFF"
    sltp_label = "ON" if config.SLTP_AUDIT_DEBUG else "OFF"
    trade_label = "ON" if config.TRADE_DEBUG else "OFF"
    text = (
        "🧪 *Debug Settings*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"Queue Debug: *{queue_label}*\n\n"
        f"SL/TP Audit Debug: *{sltp_label}*\n"
        f"Trade Debug: *{trade_label}*\n\n"
        "เลือกตัวที่ต้องการเปิด/ปิด:"
    )
    keyboard = build_debug_keyboard()
    if is_query:
        try:
            await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


def build_limit_guard_keyboard():
    toggle_label = "🟢 เปิด Limit Guard" if config.LIMIT_GUARD else "⬜ ปิด Limit Guard"
    tf_mode = config.LIMIT_GUARD_TF_MODE
    tf_label = "🔀 รวม TF" if tf_mode == "combined" else "📌 แยก TF"
    pts = config.LIMIT_GUARD_POINTS
    pt_options = [100, 200, 300, 500, 1000]
    pt_row = []
    for p in pt_options:
        label = f"{'🔵' if pts == p else '⬜'} {p}pt"
        pt_row.append(InlineKeyboardButton(label, callback_data=f"set_lg_pts_{p}"))
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_label, callback_data="toggle_limit_guard")],
        [InlineKeyboardButton(tf_label, callback_data="toggle_lg_tf_mode")],
        pt_row,
        [InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")],
    ])


async def show_limit_guard_menu(update_or_query, is_query=False):
    status = f"ON ({config.LIMIT_GUARD_POINTS}pt)" if config.LIMIT_GUARD else "OFF"
    tf_desc = "รวมทุก TF" if config.LIMIT_GUARD_TF_MODE == "combined" else "แยกตาม TF"
    text = (
        "🛡 *Limit Guard*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"สถานะ: *{status}*\n"
        f"โหมด TF: *{tf_desc}*\n\n"
        "ยกเลิก limit ที่ entry สูง/ต่ำกว่า position ที่เปิดอยู่\n"
        "เมื่อราคาห่างจาก entry ของ position มากกว่า N จุด\n\n"
        "📌 แยก TF = ดูเฉพาะ position TF เดียวกัน\n"
        "🔀 รวม TF = ดู position ทุก TF\n\n"
        "เลือกเปิด/ปิด และตั้งจำนวนจุด:"
    )
    keyboard = build_limit_guard_keyboard()
    if is_query:
        try:
            await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)



def build_limit_break_keyboard():
    toggle_label = "🟢 เปิด Limit TP/SL Break" if config.LIMIT_BREAK_CANCEL else "⬜ ปิด Limit TP/SL Break"
    rows = [[InlineKeyboardButton(toggle_label, callback_data="toggle_limit_break_cancel")]]
    tf_buttons = []
    tf_row = []
    for tf_name in TF_OPTIONS.keys():
        is_on = config.LIMIT_BREAK_CANCEL_TF.get(tf_name, False)
        label = ("✅ " if is_on else "⬜ ") + tf_name
        tf_row.append(InlineKeyboardButton(label, callback_data=f"toggle_lbc_tf_{tf_name}"))
        if len(tf_row) == 4:
            tf_buttons.append(tf_row)
            tf_row = []
    if tf_row:
        tf_buttons.append(tf_row)
    rows.extend(tf_buttons)
    all_on = all(config.LIMIT_BREAK_CANCEL_TF.values())
    rows.append([InlineKeyboardButton("⬜ ยกเลิกทุก TF" if all_on else "🟢 เลือกทุก TF", callback_data="toggle_lbc_tf_ALL")])
    rows.append([InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")])
    return InlineKeyboardMarkup(rows)


async def show_limit_break_menu(update_or_query, is_query=False):
    active_tfs = [tf for tf, on in config.LIMIT_BREAK_CANCEL_TF.items() if on]
    tf_desc = ", ".join(active_tfs) if active_tfs else "ยังไม่ได้เลือก"
    status = "ON" if config.LIMIT_BREAK_CANCEL else "OFF"
    text = (
        "🧯 *Limit TP/SL Break Cancel*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"สถานะ: *{status}*\n"
        f"TF ที่ใช้: *{tf_desc}*\n\n"
        "ยกเลิก LIMIT ของ TF ที่เลือกเมื่อแท่งยืนยันทะลุ TP หรือ SL\n"
        "BUY LIMIT: TP=เขียวปิดเหนือ TP + กลืน High แท่งก่อน + แท่งก่อนเขียว\n"
        "BUY LIMIT: SL=แดงปิดใต้ SL + กลืน Low แท่งก่อน + แท่งก่อนแดง\n"
        "SELL LIMIT ใช้กติกาสลับฝั่ง\n\n"
        "เลือกเปิด/ปิด และ TF ที่ต้องการ:"
    )
    keyboard = build_limit_break_keyboard()
    if is_query:
        try:
            await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


def build_engulf_keyboard():
    pt_options = [100, 200, 300, 500, 1000]
    pt_row = []
    for p in pt_options:
        label = f"{'✅' if config.ENGULF_MIN_POINTS == p else '⬜'} {p}pt"
        pt_row.append(InlineKeyboardButton(label, callback_data=f"set_engulf_pts_{p}"))
    return InlineKeyboardMarkup([
        pt_row,
        [InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")],
    ])


async def show_engulf_menu(update_or_query, is_query=False):
    text = (
        "📏 *Engulf ขั้นต่ำ*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"ค่าปัจจุบัน: *{config.ENGULF_MIN_POINTS} point*\n\n"
        "ใช้กับเงื่อนไขกลืนกินของท่า 1 และท่า 3\n"
        "BUY: Close ต้องสูงกว่า High เดิม + gap\n"
        "SELL: Close ต้องต่ำกว่า Low เดิม - gap\n\n"
        "เลือกจำนวนจุดขั้นต่ำ:"
    )
    keyboard = build_engulf_keyboard()
    if is_query:
        try:
            await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


def build_opposite_menu():
    en_label = "🟢 เปิดใช้งาน Opposite Order" if config.OPPOSITE_ORDER_ENABLED else "🔴 ปิดใช้งาน Opposite Order"
    tp_label = "🟢 ตั้ง TP+ปิด" if config.OPPOSITE_ORDER_MODE == "tp_close" else "⚪ ตั้ง TP+ปิด"
    sl_label = "🟢 ตั้ง SL Protect" if config.OPPOSITE_ORDER_MODE == "sl_protect" else "⚪ ตั้ง SL Protect"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(en_label, callback_data="toggle_opposite_enabled")],
        [InlineKeyboardButton(tp_label, callback_data="set_opposite_mode_tp_close")],
        [InlineKeyboardButton(sl_label, callback_data="set_opposite_mode_sl_protect")],
        [InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")],
    ])


async def show_opposite_menu(update_or_query, is_query=False):
    status = "ON" if config.OPPOSITE_ORDER_ENABLED else "OFF"
    mode_label = "ตั้ง TP+ปิด" if config.OPPOSITE_ORDER_MODE == "tp_close" else "ตั้ง SL Protect"
    text = (
        "🔄 *Opposite Order*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"สถานะ: *{status}*\n"
        f"โหมด: *{mode_label}*\n\n"
        "tp_close = ตั้ง TP ฝั่งตรงข้าม + ปิดตัวเก่าเมื่อ limit fill\n"
        "sl_protect = ไม่ตั้ง TP ไม่ปิด → ตั้ง SL = entry ± spread แทน\n"
    )
    keyboard = build_opposite_menu()
    if is_query:
        try:
            await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


def build_entry_candle_mode_keyboard():
    classic_label = "🟢 Classic" if config.ENTRY_CANDLE_MODE == "classic" else "⚪ Classic"
    close_label = "🟢 Close" if config.ENTRY_CANDLE_MODE == "close" else "⚪ Close"
    close_pct_label = "🟢 Close Percentage" if config.ENTRY_CANDLE_MODE == "close_percentage" else "⚪ Close Percentage"
    en_label = "🟢 เปิดใช้งาน Entry Candle" if config.ENTRY_CANDLE_ENABLED else "🔴 ปิดใช้งาน Entry Candle"
    focus_status = f"🟢ON | {config.ENTRY_CANDLE_FOCUS_NEW_POINTS}pt" if config.ENTRY_CANDLE_FOCUS_NEW_ENABLED else "🔴OFF"
    focus_label = f"🎯 Focus Opposite ใหม่: {focus_status}"
    rows = [
        [InlineKeyboardButton(en_label, callback_data="toggle_entry_candle_enabled")],
        [InlineKeyboardButton(classic_label, callback_data="set_entry_candle_mode_classic")],
        [InlineKeyboardButton(close_label, callback_data="set_entry_candle_mode_close")],
        [InlineKeyboardButton(close_pct_label, callback_data="set_entry_candle_mode_close_percentage")],
    ]
    if config.ENTRY_CANDLE_MODE == "close":
        market_label = "🟢 Close -> Market" if config.ENTRY_CLOSE_REVERSE_MARKET else "⚪ Close -> Market"
        limit_label = "🟢 Close -> Limit" if config.ENTRY_CLOSE_REVERSE_LIMIT else "⚪ Close -> Limit"
        rows.append([InlineKeyboardButton(market_label, callback_data="toggle_entry_close_reverse_market")])
        rows.append([InlineKeyboardButton(limit_label, callback_data="toggle_entry_close_reverse_limit")])
    rows.append([InlineKeyboardButton(focus_label, callback_data="open_entry_focus_menu")])
    rows.append([InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")])
    return InlineKeyboardMarkup(rows)


def build_entry_focus_keyboard():
    toggle_label = (
        "🟢 เปิด Entry Focus Opposite ใหม่"
        if config.ENTRY_CANDLE_FOCUS_NEW_ENABLED
        else "🔴 ปิด Entry Focus Opposite ใหม่"
    )
    tf_mode = config.ENTRY_CANDLE_FOCUS_NEW_TF_MODE
    tf_label = "🔀 รวม TF" if tf_mode == "combined" else "📌 แยก TF"
    pts = config.ENTRY_CANDLE_FOCUS_NEW_POINTS
    pt_options = [0, 100, 200, 300, 500]
    pt_row = [
        InlineKeyboardButton(
            f"{'🔵' if pts == p else '⬜'} {p}pt",
            callback_data=f"set_efn_pts_{p}"
        )
        for p in pt_options
    ]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_label, callback_data="toggle_entry_focus_new")],
        [InlineKeyboardButton(tf_label, callback_data="toggle_efn_tf_mode")],
        pt_row,
        [InlineKeyboardButton("🔙 กลับ", callback_data="open_entry_candle_mode_menu")],
    ])


async def show_entry_focus_menu(update_or_query, is_query=False):
    status = f"🟢ON | {config.ENTRY_CANDLE_FOCUS_NEW_POINTS}pt" if config.ENTRY_CANDLE_FOCUS_NEW_ENABLED else "🔴OFF"
    tf_desc = "รวมทุก TF" if config.ENTRY_CANDLE_FOCUS_NEW_TF_MODE == "combined" else "แยกตาม TF"
    text = (
        "🎯 *Entry Focus Opposite ใหม่*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"สถานะ: *{status}*\n"
        f"โหมด TF: *{tf_desc}*\n\n"
        "เมื่อ BUY position กำไร > threshold + spread\n"
        "และมี SELL ฝั่งตรงข้าม (position/pending limit)\n"
        "→ ข้าม Entry Candle Mode ของ BUY ตัวนั้น\n"
        "(ฝั่ง SELL ทำงานสลับกัน)\n\n"
        "📌 แยก TF = จับคู่เฉพาะ TF เดียวกัน\n"
        "🔀 รวม TF = จับคู่ข้าม TF ได้\n\n"
        "เลือก toggle / TF mode / threshold:"
    )
    keyboard = build_entry_focus_keyboard()
    if is_query:
        try:
            await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def show_entry_candle_mode_menu(update_or_query, is_query=False):
    if config.ENTRY_CANDLE_MODE == "classic":
        mode_label = "Classic"
    elif config.ENTRY_CANDLE_MODE == "close_percentage":
        mode_label = "Close Percentage"
    else:
        mode_label = "Close"
    focus_status = f"ON ({config.ENTRY_CANDLE_FOCUS_NEW_POINTS}pt)" if config.ENTRY_CANDLE_FOCUS_NEW_ENABLED else "OFF"
    text = (
        "🕯 *Entry Candle Mode*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"Mode: *{mode_label}*\n"
    )
    if config.ENTRY_CANDLE_MODE == "close":
        market_label = "ON" if config.ENTRY_CLOSE_REVERSE_MARKET else "OFF"
        limit_label = "ON" if config.ENTRY_CLOSE_REVERSE_LIMIT else "OFF"
        text += (
            f"Close -> Market: *{market_label}*\n"
            f"Close -> Limit: *{limit_label}*\n"
        )
    text += f"Focus Opposite: *{focus_status}*\n"
    text += "\nเลือกโหมดที่ต้องการ:"
    keyboard = build_entry_candle_mode_keyboard()
    if is_query:
        try:
            await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


def build_scan_keyboard_with_back():
    """ปุ่มเลือก Scan Interval พร้อมปุ่มกลับ"""
    row = []
    for mins in INTERVAL_OPTIONS:
        label = ("✅ " if mins == config.SCAN_INTERVAL else "   ") + f"{mins}m"
        row.append(InlineKeyboardButton(label, callback_data=f"set_interval_{mins}"))
    return InlineKeyboardMarkup([row, [
        InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")
    ]])


def build_tf_keyboard_with_back():
    """ปุ่มเลือก Timeframe พร้อมปุ่มกลับ"""
    tf_buttons = []
    tf_row = []
    for tf_name in TF_OPTIONS.keys():
        is_on = TF_ACTIVE.get(tf_name, False)
        label = ("✅ " if is_on else "⬜ ") + tf_name
        tf_row.append(InlineKeyboardButton(label, callback_data=f"set_tf_{tf_name}"))
        if len(tf_row) == 4:
            tf_buttons.append(tf_row)
            tf_row = []
    if tf_row:
        tf_buttons.append(tf_row)
    all_active = all(TF_ACTIVE.values())
    ctrl_row = [
        InlineKeyboardButton("⬜ ยกเลิกทุก TF" if all_active else "🟢 เลือกทุก TF", callback_data="set_tf_ALL"),
        InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")
    ]
    return InlineKeyboardMarkup(tf_buttons + [ctrl_row])


def build_scan_keyboard():
    """ปุ่มเลือก Scan Interval"""
    row = []
    for mins in INTERVAL_OPTIONS:
        label = f"{'✅' if mins == config.SCAN_INTERVAL else '  '} {mins}m"
        row.append(InlineKeyboardButton(label, callback_data=f"set_interval_{mins}"))
    return InlineKeyboardMarkup([row, [InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")]])


def build_tf_keyboard():
    """ปุ่มเลือก Timeframe แบบ multi-select"""
    tf_buttons = []
    tf_row = []
    for tf_name in TF_OPTIONS.keys():
        is_on = TF_ACTIVE.get(tf_name, False)
        label = f"{'✅' if is_on else '⬜'} {tf_name}"
        tf_row.append(InlineKeyboardButton(label, callback_data=f"set_tf_{tf_name}"))
        if len(tf_row) == 4:
            tf_buttons.append(tf_row)
            tf_row = []
    if tf_row:
        tf_buttons.append(tf_row)
    all_active = all(TF_ACTIVE.values())
    ctrl_row = [
        InlineKeyboardButton("⬜ ยกเลิกทุก TF" if all_active else "🟢 เลือกทุก TF", callback_data="set_tf_ALL"),
        InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")
    ]
    return InlineKeyboardMarkup(tf_buttons + [ctrl_row])


async def show_scan_menu(update):
    """เมนูตั้งค่า Scan Interval"""
    await update.message.reply_text(
        f"⚙️ *ตั้งค่า Scan Interval*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⏰ ปัจจุบัน: *ทุก {config.SCAN_INTERVAL} นาที*\n\n"
        f"เลือกความถี่ในการสแกน:",
        parse_mode="Markdown",
        reply_markup=build_scan_keyboard()
    )


async def show_tf_menu(update):
    """เมนูเลือก Timeframe"""
    active_tfs = [tf for tf, on in TF_ACTIVE.items() if on]
    tf_summary = ", ".join(active_tfs) if active_tfs else "ยังไม่ได้เลือก"
    await update.message.reply_text(
        f"🕐 *เลือก Timeframe*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📊 ที่เปิดอยู่: *{tf_summary}*\n\n"
        f"กดเลือกได้หลาย TF พร้อมกัน:",
        parse_mode="Markdown",
        reply_markup=build_tf_keyboard()
    )


async def handle_buttons(update, context):
    global auto_active
    if not auth(update):
        await alert_intruder(update)
        return
    text = update.message.text

    if text == "📈 ราคาทอง":
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

    elif text == "💰 ยอดเงิน":
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

    elif text == "📊 Order":
        if not connect_mt5():
            await update.message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อ")
            return
        positions = mt5.positions_get(symbol=SYMBOL)
        if not positions:
            await update.message.reply_text("📭 ไม่มี Order", reply_markup=main_keyboard())
            return
        msg = f"📊 *Order ({len(positions)} รายการ)*\n━━━━━━━━━━━━━━━━━\n\n"
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

    elif text == "❌ ปิดทั้งหมด":
        await update.message.reply_text(
            "⚠️ *ยืนยันปิดทุก Order?*", parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ ยืนยัน", callback_data="confirm_close"),
                InlineKeyboardButton("❌ ยกเลิก", callback_data="cancel")
            ]])
        )

    elif text == "🟢 BUY":
        await order_menu(update, "buy")

    elif text == "🔴 SELL":
        await order_menu(update, "sell")

    elif text == "🤖 สแกนตอนนี้":
        from scanner import auto_scan
        msg = await update.message.reply_text("⏳ กำลังสแกน...")
        try:
            await asyncio.wait_for(auto_scan(context.application), timeout=30)
        except asyncio.TimeoutError:
            await msg.edit_text("⚠️ สแกน Timeout\nMT5 ตอบช้าเกินไป ลองกดใหม่อีกครั้งครับ")
            return
        await msg.edit_text("✅ สแกนเสร็จแล้ว")

    elif text == "⚙️ สถานะ Auto":
        status = "▶️ ทำงาน" if auto_active else "⏸️ หยุด"
        await update.message.reply_text(
            f"⚙️ *Auto Trade: {status}*\n⏰ สแกนทุก {config.SCAN_INTERVAL} นาที\n🕐 TF: {', '.join([tf for tf,on in TF_ACTIVE.items() if on]) or 'ยังไม่ได้เลือก'}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⏸️ หยุด" if auto_active else "▶️ เปิด", callback_data="toggle_auto")
            ]])
        )

    elif text == "⚙️ ตั้งค่า":
        await show_main_settings_menu(update)

    elif text == "🕐 เลือก Timeframe":
        await show_tf_menu(update)

    elif text == "⏳ Pending Orders":
        if not connect_mt5():
            await update.message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อ")
            return
        orders = mt5.orders_get(symbol=SYMBOL)
        if not orders:
            await update.message.reply_text("📭 ไม่มี Pending Order", reply_markup=main_keyboard())
            return
        msg = f"⏳ *Pending Orders ({len(orders)} รายการ)*\n━━━━━━━━━━━━━━━━━\n\n"
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

    elif text == "🗑️ ยกเลิก Pending":
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

    elif text == "📊 สรุปกำไร":
        now = datetime.now()
        await show_profit_summary(update, now.year, now.month)

    elif text == "📋 เลือก Strategy":
        await show_strategy_menu(update)


async def show_settings_menu(update):
    """เมนูตั้งค่า Scan Interval และ Timeframe"""
    # ปุ่ม Interval
    interval_row = []
    for mins in INTERVAL_OPTIONS:
        label = f"{'✅' if mins == config.SCAN_INTERVAL else '  '} {mins}m"
        interval_row.append(InlineKeyboardButton(label, callback_data=f"set_interval_{mins}"))

    # ปุ่ม Timeframe (แถวละ 3)
    tf_buttons = []
    tf_row = []
    for i, tf_name in enumerate(TF_OPTIONS.keys()):
        label = f"{'✅' if tf_name == TF_CURRENT else '  '} {tf_name}"
        tf_row.append(InlineKeyboardButton(label, callback_data=f"set_tf_{tf_name}"))
        if len(tf_row) == 3:
            tf_buttons.append(tf_row)
            tf_row = []
    if tf_row:
        tf_buttons.append(tf_row)

    keyboard = InlineKeyboardMarkup(
        [interval_row] +
        tf_buttons +
        [[InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")]]
    )

    await update.message.reply_text(
        f"⚙️ *ตั้งค่า Auto Trade*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⏰ Scan ทุก: *{config.SCAN_INTERVAL} นาที*\n"
        f"📊 Timeframe: *{TF_CURRENT}*\n\n"
        f"เลือก Interval (บรรทัดบน) และ Timeframe (บรรทัดล่าง):",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


def build_strategy_keyboard():
    """สร้าง keyboard สำหรับเลือก Strategy พร้อม sub-option ของท่า 1 และ 2"""
    rows = []
    row = []
    for sid, name in STRATEGY_NAMES.items():
        is_on = active_strategies.get(sid, False)
        label = f"{'✅' if is_on else '⬜'} {name}"
        row.append(InlineKeyboardButton(label, callback_data=f"toggle_strategy_{sid}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    # sub-option ท่า 1: Zone mode
    if active_strategies.get(1, False):
        zone_mode = config.S1_ZONE_MODE
        rows.append([
            InlineKeyboardButton(
                f"{'✅' if zone_mode == 'zone' else '⬜'} ท่า1: Zone",
                callback_data="set_s1_zone_mode_zone"
            ),
            InlineKeyboardButton(
                f"{'✅' if zone_mode == 'normal' else '⬜'} ท่า1: ปกติ (ไม่สนใจ Zone)",
                callback_data="set_s1_zone_mode_normal"
            ),
        ])

    # sub-option ท่า 2: FVG Mode
    if active_strategies.get(2, False):
        rows.append([
            InlineKeyboardButton(
                f"{'🟢' if config.FVG_NORMAL else '⬜'} ท่า2: ปกติ",
                callback_data="toggle_fvg_normal"
            ),
            InlineKeyboardButton(
                f"{'🟢' if config.FVG_PARALLEL else '⬜'} ท่า2: Parallel",
                callback_data="toggle_fvg_parallel"
            ),
        ])

    # sub-option ท่า 9: RSI Divergence — รวม bull/bear ในแต่ละแบบ (Regular / Hidden)
    if active_strategies.get(9, False):
        regular_on = config.RSI9_PLOT_BULLISH and config.RSI9_PLOT_BEARISH
        hidden_on  = config.RSI9_PLOT_HIDDEN_BULLISH and config.RSI9_PLOT_HIDDEN_BEARISH
        rows.append([
            InlineKeyboardButton(
                f"{'🟢' if regular_on else '⬜'} ท่า9: Regular",
                callback_data="toggle_rsi9_regular"
            ),
            InlineKeyboardButton(
                f"{'🟢' if hidden_on else '⬜'} ท่า9: Hidden",
                callback_data="toggle_rsi9_hidden"
            ),
        ])

    # sub-option ท่า 10: CRT bar mode (2bar / 3bar)
    if active_strategies.get(10, False):
        crt_mode = getattr(config, "CRT_BAR_MODE", "2bar")
        rows.append([
            InlineKeyboardButton(
                f"{'✅' if crt_mode == '2bar' else '⬜'} ท่า10: 2bar (classic)",
                callback_data="set_crt_bar_mode_2bar"
            ),
            InlineKeyboardButton(
                f"{'✅' if crt_mode == '3bar' else '⬜'} ท่า10: 3bar (TBS)",
                callback_data="set_crt_bar_mode_3bar"
            ),
        ])
        crt_entry = getattr(config, "CRT_ENTRY_MODE", "htf")
        rows.append([
            InlineKeyboardButton(
                f"{'✅' if crt_entry == 'htf' else '⬜'} ท่า10: HTF entry",
                callback_data="set_crt_entry_mode_htf"
            ),
            InlineKeyboardButton(
                f"{'✅' if crt_entry == 'mtf' else '⬜'} ท่า10: MTF (LTF entry)",
                callback_data="set_crt_entry_mode_mtf"
            ),
        ])

    all_on = all(active_strategies.values())
    ctrl = [
        InlineKeyboardButton(
            "⬜ ยกเลิกทุก Strategy" if all_on else "🟢 เลือกทุก Strategy",
            callback_data="strategy_all_on" if not all_on else "strategy_all_off"
        ),
        InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings"),
    ]
    rows.append(ctrl)
    return InlineKeyboardMarkup(rows)


async def show_strategy_menu(update):
    """แสดงเมนูเลือก Strategy พร้อมสถานะเปิด/ปิด"""
    active_list = [STRATEGY_NAMES[sid] for sid, on in active_strategies.items() if on]
    summary = " + ".join(active_list) if active_list else "ไม่มี"
    msg = (
        "📋 *เลือก Strategy*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"🔄 ที่เปิดอยู่: *{summary}*\n\n"
        "กดเพื่อเปิด/ปิด (เลือกพร้อมกันได้):"
    )
    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=build_strategy_keyboard()
    )


async def order_menu(update, direction):
    if not connect_mt5():
        await update.message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อ")
        return
    tick  = mt5.symbol_info_tick(SYMBOL)
    price = (tick.ask if direction == "buy" else tick.bid) if tick else 0
    e     = "🟢" if direction == "buy" else "🔴"

    # สร้างปุ่ม lot จาก LOT_OPTIONS (แบ่งแถวละ 3 ปุ่ม)
    lot_buttons = []
    row = []
    for lot in config.LOT_OPTIONS:
        label = f"{'✅ ' if lot == config.AUTO_VOLUME else ''}{lot}"
        row.append(InlineKeyboardButton(label, callback_data=f"{direction}_{lot}_{price}"))
        if len(row) == 3:
            lot_buttons.append(row)
            row = []
    if row:
        lot_buttons.append(row)
    # ปุ่มกรอกเอง + ยกเลิก
    lot_buttons.append([
        InlineKeyboardButton("✏️ กรอกเอง", callback_data=f"lot_manual_{direction}_custom_{price}"),
        InlineKeyboardButton("❌ ยกเลิก",  callback_data="cancel"),
    ])

    await update.message.reply_text(
        f"{e} *{direction.upper()} {SYMBOL}* @ `{price}`\n"
        f"📦 Auto Lot: `{config.AUTO_VOLUME}` (✅ = ค่าปัจจุบัน)\n"
        f"เลือก Lot Size:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(lot_buttons)
    )


# ============================================================
#  Profit Summary — สรุปกำไรรายเดือน แยก Strategy
# ============================================================

_THAI_MONTHS = {
    1: "ม.ค.", 2: "ก.พ.", 3: "มี.ค.", 4: "เม.ย.",
    5: "พ.ค.", 6: "มิ.ย.", 7: "ก.ค.", 8: "ส.ค.",
    9: "ก.ย.", 10: "ต.ค.", 11: "พ.ย.", 12: "ธ.ค.",
}


_PATTERN_LABELS = {
    "PA": "Pattern A", "PB": "Pattern B", "PC": "Pattern C",
    "PD": "Pattern D", "PE": "Pattern E", "P4": "Pattern 4แท่ง",
    "DMSP": "DM SP", "MARU": "Marubozu",
    "FVG": "FVG", "SIGFVG": "นัยยะ FVG", "S5": "Scalping", "RSI9": "RSI Divergence",
    "SWING": "กินไส้ Swing",
}

_PROFIT_TREND_FILTERS = {
    "all": {"label": "ทั้งหมด", "title": "ทั้งหมด"},
    "bull_strong": {"label": "Bull+ (strong)", "title": "Bullish (strong)"},
    "bull_weak": {"label": "Bull+ (weak)", "title": "Bullish (weak)"},
    "sideway": {"label": "SW", "title": "SW"},
    "bear_weak": {"label": "Bear- (weak)", "title": "Bearish (weak)"},
    "bear_strong": {"label": "Bear- (strong)", "title": "Bearish (strong)"},
}


def _parse_comment_detail(comment: str):
    """Parse comment เช่น Bot_H4_S2_FVG -> (tf, sid, pattern_code)"""
    if not comment or not comment.startswith("Bot_"):
        return None, None, None
    m = re.match(r"Bot_(M\d+|H\d+|D\d+)(?:_S(\w+?))?(?:_(PA|PB|PC|PD|PE|P4|DMSP|MARU|FVG|SIGFVG|S5|SWING|RSI9))?$", comment)
    if not m:
        return None, None, None
    tf = m.group(1)
    sid_raw = m.group(2)
    pat = m.group(3) or ""
    sid = None
    if sid_raw:
        if sid_raw == "6i":
            sid = 7
        else:
            try:
                sid = int(sid_raw)
            except ValueError:
                pass
    return tf, sid, pat


def _profit_trend_title(trend_filter_key: str) -> str:
    return _PROFIT_TREND_FILTERS.get(trend_filter_key, _PROFIT_TREND_FILTERS["all"])["title"]


def _profit_trend_match(raw_value: str, trend_filter_key: str) -> bool:
    if trend_filter_key == "all":
        return True
    values = [v.strip() for v in (raw_value or "").split(",") if v.strip()]
    return trend_filter_key in values


def _get_profit_data(year: int, month: int, trend_filter_key: str = "all"):
    """ดึง POSITION_CLOSED จาก bot.log แยก strategy -> tf -> pattern"""
    bkk = timezone(timedelta(hours=TZ_OFFSET))
    dt_from = datetime(year, month, 1, tzinfo=bkk)
    if month == 12:
        dt_to = datetime(year + 1, 1, 1, tzinfo=bkk)
    else:
        dt_to = datetime(year, month + 1, 1, tzinfo=bkk)
    result = {}
    side_summary = {}  # {sid: {"BUY": {profit, volume, count}, "SELL": {...}}}
    total_profit = 0.0
    total_volume = 0.0
    total_count = 0

    log_file = get_monthly_bot_log_file(year, month)
    if not os.path.exists(log_file):
        log_file = BOT_LOG_FILE

    if not os.path.exists(log_file):
        return result, total_profit, total_volume, total_count, side_summary

    volume_by_ticket = {}
    try:
        deals = mt5.history_deals_get(dt_from, dt_to) or []
        DEAL_ENTRY_OUT = 1
        for d in deals:
            if getattr(d, "entry", None) != DEAL_ENTRY_OUT:
                continue
            if getattr(d, "magic", None) != 234001:
                continue
            ticket = int(getattr(d, "position_id", 0) or 0)
            if ticket > 0:
                volume_by_ticket[ticket] = float(getattr(d, "volume", 0.0) or 0.0)
    except Exception:
        volume_by_ticket = {}

    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.strip()
            if "POSITION_CLOSED" not in line:
                continue

            m = re.match(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] POSITION_CLOSED(?: \| (.*))?$", line)
            if not m:
                continue

            try:
                event_dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=bkk)
            except Exception:
                continue

            if not (dt_from <= event_dt < dt_to):
                continue

            fields = {}
            for part in (m.group(2) or "").split(" | "):
                if "=" in part:
                    key, value = part.split("=", 1)
                    fields[key.strip()] = value.strip()

            try:
                sid = int(fields.get("sid", "0"))
            except Exception:
                sid = 0
            try:
                ticket = int(fields.get("ticket", "0"))
            except Exception:
                ticket = 0
            tf = fields.get("tf", "-") or "-"
            pat = fields.get("pattern", "-") or "-"
            trend_filter = fields.get("trend_filter", "") or ""
            if not _profit_trend_match(trend_filter, trend_filter_key):
                continue
            try:
                pnl = float(fields.get("profit", "0") or 0.0)
            except Exception:
                pnl = 0.0
            try:
                volume = float(fields.get("volume", "0") or 0.0)
            except Exception:
                volume = 0.0
            if volume <= 0 and ticket > 0:
                volume = volume_by_ticket.get(ticket, 0.0)

            result.setdefault(sid, {}).setdefault(tf, {}).setdefault(pat, {"profit": 0.0, "volume": 0.0, "count": 0})
            result[sid][tf][pat]["profit"] += pnl
            result[sid][tf][pat]["volume"] += volume
            result[sid][tf][pat]["count"] += 1

            side_raw = (fields.get("side") or "").upper()
            if "BUY" in side_raw:
                side_key = "BUY"
            elif "SELL" in side_raw:
                side_key = "SELL"
            else:
                side_key = None
            if side_key:
                side_summary.setdefault(sid, {}).setdefault(
                    side_key, {"profit": 0.0, "volume": 0.0, "count": 0}
                )
                side_summary[sid][side_key]["profit"] += pnl
                side_summary[sid][side_key]["volume"] += volume
                side_summary[sid][side_key]["count"] += 1

            total_profit += pnl
            total_volume += volume
            total_count += 1

    return result, total_profit, total_volume, total_count, side_summary


def _format_profit_summary(year: int, month: int):
    """สร้างข้อความสรุปกำไรของเดือน แยก Strategy -> TF -> Pattern"""
    data, total_profit, total_volume, total_count, _ = _get_profit_data(year, month)

    month_name = _THAI_MONTHS.get(month, str(month))
    lines = [
        f"📊 *สรุปกำไร — {month_name} {year}*",
        "━━━━━━━━━━━━━━━━━",
    ]

    if not data:
        lines.append("📭 ไม่มีข้อมูลเดือนนี้")
    else:
        # TF sort order
        tf_order = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1", "-"]

        for sid in sorted(data.keys()):
            # รวมกำไรของ strategy นี้
            sid_profit = sum(
                info["profit"]
                for tfs in data[sid].values()
                for info in tfs.values()
            )
            sid_count = sum(
                info["count"]
                for tfs in data[sid].values()
                for info in tfs.values()
            )
            sid_volume = sum(
                info["volume"]
                for tfs in data[sid].values()
                for info in tfs.values()
            )
            pnl_e = "🟢" if sid_profit >= 0 else "🔴"
            name = "ไม่ระบุท่า" if sid == 0 else STRATEGY_NAMES.get(sid, f"ท่าที่ {sid}")
            lines.append(
                f"\n{pnl_e} *{name}* — `{sid_profit:+.2f}` | "
                f"{sid_volume:.2f}lot | {sid_count}ออเดอร์"
            )

            # แยก TF
            sorted_tfs = sorted(data[sid].keys(), key=lambda t: tf_order.index(t) if t in tf_order else 99)
            for tf in sorted_tfs:
                pats = data[sid][tf]
                # รวม TF
                tf_profit = sum(v["profit"] for v in pats.values())
                tf_count = sum(v["count"] for v in pats.values())
                tf_e = "+" if tf_profit >= 0 else ""
                lines.append(f"  📐 *{tf}*: `{tf_e}{tf_profit:.2f}` ({tf_count})")

                # แยก Pattern (ถ้ามีมากกว่า 1 หรือ pattern ไม่ใช่ "-")
                show_pat = len(pats) > 1 or list(pats.keys()) != ["-"]
                if show_pat:
                    for pat in sorted(pats.keys()):
                        info = pats[pat]
                        pat_label = _PATTERN_LABELS.get(pat, pat) if pat != "-" else "ไม่ระบุ"
                        p_e = "+" if info["profit"] >= 0 else ""
                        lines.append(
                            f"      {pat_label}: `{p_e}{info['profit']:.2f}` ({info['count']})"
                        )

        lines.append("\n━━━━━━━━━━━━━━━━━")
        total_e = "🟢" if total_profit >= 0 else "🔴"
        lines.append(
            f"{total_e} *รวม: `{total_profit:+.2f}` USD* | "
            f"📦 `{total_volume:.2f}` lot | "
            f"🔢 `{total_count}` ออเดอร์"
        )

    return "\n".join(lines)


def _format_profit_overview(year: int, month: int, trend_filter_key: str = "all"):
    """หน้าแรก: รวมรายเดือน แยกตาม strategy"""
    data, total_profit, total_volume, total_count, side_summary = _get_profit_data(year, month, trend_filter_key)
    month_name = _THAI_MONTHS.get(month, str(month))
    lines = [
        f"📊 *สรุปกำไร — {month_name} {year}*",
        "━━━━━━━━━━━━━━━━━",
        f"🧭 Trend Filter: *{_profit_trend_title(trend_filter_key)}*",
    ]

    if not data:
        lines.append("📭 ไม่มีข้อมูลเดือนนี้")
        return "\n".join(lines)

    for sid in sorted(data.keys()):
        sid_profit = sum(
            info["profit"]
            for tfs in data[sid].values()
            for info in tfs.values()
        )
        sid_count = sum(
            info["count"]
            for tfs in data[sid].values()
            for info in tfs.values()
        )
        sid_volume = sum(
            info["volume"]
            for tfs in data[sid].values()
            for info in tfs.values()
        )
        pnl_e = "🟢" if sid_profit >= 0 else "🔴"
        name = "ไม่ระบุท่า" if sid == 0 else STRATEGY_NAMES.get(sid, f"ท่าที่ {sid}")
        lines.append(
            f"\n{pnl_e} *{name}* — `{sid_profit:+.2f}` | "
            f"{sid_volume:.2f}lot | {sid_count}ออเดอร์"
        )

        sides = side_summary.get(sid, {})
        for side_key in ("BUY", "SELL"):
            info = sides.get(side_key)
            if not info or info["count"] == 0:
                continue
            side_e = "🟢" if side_key == "BUY" else "🔴"
            lines.append(
                f"    {side_e} {side_key} — `{info['profit']:+.2f}` | "
                f"{info['volume']:.2f} lot | {info['count']} ออเดอร์"
            )

    total_e = "🟢" if total_profit >= 0 else "🔴"
    lines.append("\n━━━━━━━━━━━━━━━━━")
    lines.append(
        f"{total_e} *รวม: `{total_profit:+.2f}` USD* | "
        f"📦 `{total_volume:.2f}` lot | "
        f"🔢 `{total_count}` ออเดอร์"
    )
    lines.append("\nกดปุ่มด้านล่างเพื่อดูรายละเอียดแต่ละท่า")
    return "\n".join(lines)


def _format_profit_pattern_label(pat: str) -> str:
    """ย่อชื่อ pattern สำหรับหน้าสรุปกำไร"""
    if not pat or pat == "-":
        return "ไม่ระบุ Pattern"
    if pat in _PATTERN_LABELS:
        return _PATTERN_LABELS[pat]

    label = pat.strip()
    label = re.sub(r"^ท่าที่\s*\d+\s*[^🟢🔴]*\s*", "", label).strip()
    label = re.sub(r"\s*\[(M\d+|H\d+|D\d+)\]$", "", label).strip()
    label = re.sub(r"\s+(M\d+|H\d+|D\d+)$", "", label).strip()
    return label or pat


def _profit_pattern_sort_key(pat: str):
    label = _format_profit_pattern_label(pat)
    if "SELL" in label:
        side_rank = 0
    elif "BUY" in label:
        side_rank = 1
    else:
        side_rank = 2
    return side_rank, label


def _format_profit_strategy_detail(year: int, month: int, sid: int, trend_filter_key: str = "all"):
    """หน้ารายละเอียด strategy: แยกตาม TF -> รวม -> Pattern"""
    data, _, _, _, _ = _get_profit_data(year, month, trend_filter_key)
    month_name = _THAI_MONTHS.get(month, str(month))
    name = "ไม่ระบุท่า" if sid == 0 else STRATEGY_NAMES.get(sid, f"ท่าที่ {sid}")
    lines = [
        f"📊 *{name} — {month_name} {year}*",
        "━━━━━━━━━━━━━━━━━",
        f"🧭 Trend Filter: *{_profit_trend_title(trend_filter_key)}*",
    ]

    sid_data = data.get(sid, {})
    if not sid_data:
        lines.append("📭 ไม่มีข้อมูลของท่านี้ในเดือนนี้")
        return "\n".join(lines)

    tf_order = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1", "-"]
    sorted_tfs = sorted(sid_data.keys(), key=lambda t: tf_order.index(t) if t in tf_order else 99)
    for tf in sorted_tfs:
        pats = sid_data[tf]
        tf_profit = sum(v["profit"] for v in pats.values())
        tf_volume = sum(v["volume"] for v in pats.values())
        tf_count = sum(v["count"] for v in pats.values())
        lines.append(f"{tf} — รวม `{tf_profit:+.2f}` | {tf_volume:.2f} lot | {tf_count} ออเดอร์")
        lines.append(
            f"• {name} รวม `{tf_profit:+.2f}` | {tf_volume:.2f} lot | {tf_count} ออเดอร์"
        )
        for pat in sorted(pats.keys(), key=_profit_pattern_sort_key):
            info = pats[pat]
            pat_label = _format_profit_pattern_label(pat)
            lines.append(
                f"    {pat_label}: `{info['profit']:+.2f}` | "
                f"{info['volume']:.2f} lot | {info['count']} ออเดอร์"
            )
        lines.append("")

    return "\n".join(lines).rstrip()


def build_profit_nav_keyboard(year: int, month: int, trend_filter_key: str = "all"):
    """ปุ่มเลื่อนเดือน ซ้าย/ขวา"""
    # เดือนก่อนหน้า
    prev_m = month - 1
    prev_y = year
    if prev_m < 1:
        prev_m = 12
        prev_y -= 1

    # เดือนถัดไป
    next_m = month + 1
    next_y = year
    if next_m > 12:
        next_m = 1
        next_y += 1

    now = datetime.now()
    rows = [[
        InlineKeyboardButton(f"◀️ {_THAI_MONTHS[prev_m]}", callback_data=f"profit_{prev_y}_{prev_m}_{trend_filter_key}"),
        InlineKeyboardButton("🔙 ปิด", callback_data="cancel"),
    ]]
    # ไม่แสดงปุ่มไปอนาคต
    if next_y < now.year or (next_y == now.year and next_m <= now.month):
        rows[0].insert(1, InlineKeyboardButton(f"▶️ {_THAI_MONTHS[next_m]}", callback_data=f"profit_{next_y}_{next_m}_{trend_filter_key}"))

    return InlineKeyboardMarkup(rows)


def build_profit_trend_filter_keyboard(year: int, month: int, sid: int | None = None, active_key: str = "all"):
    rows = []
    top = []
    for key in ("all", "bull_strong", "bull_weak"):
        label = _PROFIT_TREND_FILTERS[key]["label"]
        prefix = "✅ " if key == active_key else ""
        cb = f"profit_{year}_{month}_{key}" if sid is None else f"profit_sid_{year}_{month}_{sid}_{key}"
        top.append(InlineKeyboardButton(f"{prefix}{label}", callback_data=cb))
    rows.append(top)
    bottom = []
    for key in ("sideway", "bear_weak", "bear_strong"):
        label = _PROFIT_TREND_FILTERS[key]["label"]
        prefix = "✅ " if key == active_key else ""
        cb = f"profit_{year}_{month}_{key}" if sid is None else f"profit_sid_{year}_{month}_{sid}_{key}"
        bottom.append(InlineKeyboardButton(f"{prefix}{label}", callback_data=cb))
    rows.append(bottom)
    return rows


def build_profit_overview_keyboard(year: int, month: int, trend_filter_key: str = "all"):
    data, _, _, _, _ = _get_profit_data(year, month, trend_filter_key)
    rows = []
    rows.extend(build_profit_trend_filter_keyboard(year, month, None, trend_filter_key))
    for sid in sorted(data.keys()):
        name = "ไม่ระบุท่า" if sid == 0 else STRATEGY_NAMES.get(sid, f"ท่าที่ {sid}")
        rows.append([InlineKeyboardButton(name, callback_data=f"profit_sid_{year}_{month}_{sid}_{trend_filter_key}")])

    nav = build_profit_nav_keyboard(year, month, trend_filter_key).inline_keyboard[0]
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def build_profit_detail_keyboard(year: int, month: int, sid: int, trend_filter_key: str = "all"):
    rows = [[InlineKeyboardButton("🔙 กลับหน้ารวม", callback_data=f"profit_{year}_{month}_{trend_filter_key}")]]
    rows.extend(build_profit_trend_filter_keyboard(year, month, sid, trend_filter_key))
    nav = build_profit_nav_keyboard(year, month, trend_filter_key).inline_keyboard[0]
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def _split_telegram_text(text: str, limit: int = 3500) -> list[str]:
    parts = []
    current = []
    current_len = 0
    for line in text.splitlines():
        line_len = len(line) + 1
        if current and current_len + line_len > limit:
            parts.append("\n".join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len
    if current:
        parts.append("\n".join(current))
    return parts or [text]


async def show_profit_summary(update_or_query, year: int, month: int, trend_filter_key: str = "all", is_query=False):
    """แสดงหน้ารวมกำไรรายเดือน แยกตาม strategy"""
    if not connect_mt5():
        text = "❌ MT5 ไม่ได้เชื่อมต่อ"
        if is_query:
            try:
                await update_or_query.edit_message_text(text)
            except Exception:
                pass
        else:
            await update_or_query.message.reply_text(text, reply_markup=main_keyboard())
        return

    text = _format_profit_overview(year, month, trend_filter_key)
    chunks = _split_telegram_text(text)
    keyboard = build_profit_overview_keyboard(year, month, trend_filter_key)

    if is_query:
        try:
            await update_or_query.edit_message_text(chunks[0], parse_mode="Markdown", reply_markup=keyboard)
            for extra in chunks[1:]:
                await update_or_query.message.reply_text(extra, parse_mode="Markdown")
        except Exception:
            pass
    else:
        await update_or_query.message.reply_text(chunks[0], parse_mode="Markdown", reply_markup=keyboard)
        for extra in chunks[1:]:
            await update_or_query.message.reply_text(extra, parse_mode="Markdown")


async def show_profit_strategy_detail(update_or_query, year: int, month: int, sid: int, trend_filter_key: str = "all", is_query=False):
    """แสดงรายละเอียดกำไรของ strategy เดียว แยกตาม TF -> Pattern"""
    if not connect_mt5():
        text = "❌ MT5 ไม่ได้เชื่อมต่อ"
        if is_query:
            try:
                await update_or_query.edit_message_text(text)
            except Exception:
                pass
        else:
            await update_or_query.message.reply_text(text, reply_markup=main_keyboard())
        return

    text = _format_profit_strategy_detail(year, month, sid, trend_filter_key)
    chunks = _split_telegram_text(text)
    keyboard = build_profit_detail_keyboard(year, month, sid, trend_filter_key)

    if is_query:
        try:
            await update_or_query.edit_message_text(chunks[0], parse_mode="Markdown", reply_markup=keyboard)
            for extra in chunks[1:]:
                await update_or_query.message.reply_text(extra, parse_mode="Markdown")
        except Exception:
            pass
    else:
        await update_or_query.message.reply_text(chunks[0], parse_mode="Markdown", reply_markup=keyboard)
        for extra in chunks[1:]:
            await update_or_query.message.reply_text(extra, parse_mode="Markdown")


def build_trend_filter_keyboard():
    rows = []
    # Per-TF checklist (ของใครของมัน — ติ๊ก M1 → M1 signal filter ด้วย M1 trend)
    rows.append([InlineKeyboardButton("━ Per-TF (ของใครของมัน) ━", callback_data="noop_trend_filter")])
    tf_row = []
    for tf_name in TF_OPTIONS.keys():
        is_on = config.TREND_FILTER_PER_TF.get(tf_name, False)
        label = ("✅ " if is_on else "⬜ ") + tf_name
        tf_row.append(InlineKeyboardButton(label, callback_data=f"toggle_trend_filter_per_tf_{tf_name}"))
        if len(tf_row) == 4:
            rows.append(tf_row)
            tf_row = []
    if tf_row:
        rows.append(tf_row)
    all_on = all(config.TREND_FILTER_PER_TF.values())
    rows.append([InlineKeyboardButton(
        "⬜ ยกเลิกทุก TF" if all_on else "🟢 เลือกทุก TF",
        callback_data="toggle_trend_filter_per_tf_ALL"
    )])
    # Higher TF (เลือก 1 — filter ทุก signal ด้วย trend ของ TF นี้)
    higher_label = (
        f"🟢 Higher TF: ON ({config.TREND_FILTER_HIGHER_TF})"
        if config.TREND_FILTER_HIGHER_TF_ENABLED
        else "🔴 Higher TF: OFF"
    )
    rows.append([InlineKeyboardButton("━ Higher TF (เลือก 1) ━", callback_data="noop_trend_filter")])
    rows.append([InlineKeyboardButton(higher_label, callback_data="toggle_trend_filter_higher_tf")])
    tf_options = ["M15", "M30", "H1", "H4", "H12", "D1"]
    htf_row = [
        InlineKeyboardButton(
            f"{'🔵' if config.TREND_FILTER_HIGHER_TF == t else '⬜'} {t}",
            callback_data=f"set_trend_filter_higher_tf_{t}"
        )
        for t in tf_options
    ]
    rows.append(htf_row)
    trail_override_label = (
        "🟢 Trail SL Override: ON"
        if config.TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED
        else "🔴 Trail SL Override: OFF"
    )
    rows.append([InlineKeyboardButton("━ Trail SL ━", callback_data="noop_trend_filter")])
    rows.append([InlineKeyboardButton(trail_override_label, callback_data="toggle_trend_filter_trail_sl_override")])

    # === Filter Mode (basic / breakout) ===
    mode = getattr(config, "TREND_FILTER_MODE", "basic")
    rows.append([InlineKeyboardButton("━ Mode ━", callback_data="noop_trend_filter")])
    rows.append([
        InlineKeyboardButton(
            ("🔵 Basic" if mode == "basic" else "⬜ Basic"),
            callback_data="set_trend_filter_mode_basic"
        ),
        InlineKeyboardButton(
            ("🔵 Breakout" if mode == "breakout" else "⬜ Breakout"),
            callback_data="set_trend_filter_mode_breakout"
        ),
    ])
    rows.append([InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings")])
    return InlineKeyboardMarkup(rows)


async def show_trend_filter_menu(update_or_query, is_query=False):
    per_tf_on_list = [t for t, on in config.TREND_FILTER_PER_TF.items() if on]
    per_status = f"🟢ON | {', '.join(per_tf_on_list)}" if per_tf_on_list else "🔴OFF"
    higher_status = (
        f"🟢ON | {config.TREND_FILTER_HIGHER_TF}"
        if config.TREND_FILTER_HIGHER_TF_ENABLED
        else "🔴OFF"
    )
    trail_override_status = "🟢ON" if config.TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED else "🔴OFF"
    mode = getattr(config, "TREND_FILTER_MODE", "basic")
    mode_status = "🔵 Basic" if mode == "basic" else "🔵 Breakout"
    if mode == "basic":
        mode_rules = (
            "🟢 BULL (strong/weak) → BUY เท่านั้น\n"
            "🔴 BEAR (strong/weak) → SELL เท่านั้น\n"
            "⚪ SIDEWAY / UNKNOWN → ผ่านทั้งคู่"
        )
    else:
        mode_rules = (
            "🟢 BULL strong + ไม่ BREAK↓ → BUY เท่านั้น\n"
            "🟢 BULL strong + BREAK↓ → ผ่านทั้งคู่\n"
            "🔴 BEAR strong + ไม่ BREAK↑ → SELL เท่านั้น\n"
            "🔴 BEAR strong + BREAK↑ → ผ่านทั้งคู่\n"
            "⚪ weak / SIDEWAY / UNKNOWN → ผ่านทั้งคู่"
        )
    text = (
        "🧭 *Trend Filter (Scan Trend)*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"Per-TF: *{per_status}*\n"
        f"Higher TF: *{higher_status}*\n"
        f"Trail SL Override: *{trail_override_status}*\n"
        f"Mode: *{mode_status}*\n\n"
        "กรอง signal ตาม trend ที่คำนวณจาก swing H/L\n\n"
        f"{mode_rules}\n\n"
        "Trail SL Override: ถ้า Focus Opposite freeze อยู่ จะยอมให้ Trail SL ทำงานเมื่อ trend เปลี่ยนเป็นฝั่งตรงข้ามของ position\n"
        "SELL: BEAR/SIDEWAY → BULL | BUY: BULL/SIDEWAY → BEAR\n\n"
        "Per-TF: ติ๊ก TF ที่ต้องการ filter (ของใครของมัน)\n"
        "  เช่น ติ๊ก M1 → M1 signal filter ด้วย M1 trend เท่านั้น\n"
        "Higher TF: เลือก 1 TF — ทุก signal ต้องผ่าน trend ของ TF นี้ด้วย"
    )
    keyboard = build_trend_filter_keyboard()
    if is_query:
        try:
            await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
