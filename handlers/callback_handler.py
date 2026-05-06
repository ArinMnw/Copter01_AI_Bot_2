from config import *
import config
from mt5_utils import connect_mt5
from handlers.keyboard import (main_keyboard, build_strategy_keyboard,
    build_tf_keyboard, build_tf_keyboard_with_back,
    build_scan_keyboard, build_scan_keyboard_with_back,
    build_lot_keyboard,
    build_trail_menu, build_trail_engulf_keyboard,
    show_main_settings_menu, show_debug_menu, build_debug_keyboard,
    show_entry_candle_mode_menu, show_profit_summary, show_profit_strategy_detail,
    show_limit_break_menu, show_engulf_menu,
    show_limit_guard_menu, show_opposite_menu,
    show_trail_focus_menu, show_entry_focus_menu,
    show_trend_filter_menu)

async def handle_callback(update, ctx):
    global SCAN_INTERVAL, TF_CURRENT, TF_ACTIVE, active_strategies
    query = update.callback_query
    if update.effective_user.id != MY_USER_ID:
        await query.answer()
        return
    data = query.data

    if data == "cancel":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.answer("ปิดแล้ว")

    elif data == "toggle_auto":
        config.auto_active = not config.auto_active
        status = "▶️ ทำงาน" if config.auto_active else "⏸️ หยุด"
        if config.auto_active:
            try:
                checker = ctx.application.bot_data.get("check_symbol_switch")
                if checker:
                    await checker()
            except Exception as e:
                print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ toggle_auto symbol check error: {e}")
        try:
            await query.edit_message_text(
                f"⚙️ *Auto Trade: {status}*\n⏰ สแกนทุก {config.SCAN_INTERVAL} นาที",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⏸️ หยุด" if config.auto_active else "▶️ เปิด", callback_data="toggle_auto")
                ]])
            )
        except Exception:
            pass
        await query.answer(f"{'เปิด' if config.auto_active else 'หยุด'} Auto แล้ว")

    elif data == "open_strategy_menu":
        active_list = [STRATEGY_NAMES[s] for s, on in active_strategies.items() if on]
        summary = " + ".join(active_list) if active_list else "ไม่มี"
        new_text = (
            "📋 *เลือก Strategy*\n"
            "━━━━━━━━━━━━━━━━━\n"
            f"🔄 ที่เปิดอยู่: *{summary}*\n\n"
            "กดเพื่อเปิด/ปิด (เลือกพร้อมกันได้):"
        )
        try:
            await query.edit_message_text(
                new_text,
                parse_mode="Markdown",
                reply_markup=build_strategy_keyboard()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                pass
        await query.answer()

    elif data == "reset_config_prompt":
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ ยืนยัน Reset", callback_data="confirm_reset_config"),
            InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings"),
        ]])
        try:
            await query.edit_message_text(
                "♻️ *Reset Config*\n"
                "━━━━━━━━━━━━━━━━━\n"
                "จะรีเซทค่าตั้งค่าทั้งหมดให้กลับไปตรงกับค่าเริ่มต้นใน `config.py`\n"
                "และบันทึกทับ state ปัจจุบันทันที\n\n"
                "ยืนยันหรือไม่?",
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception:
            pass
        await query.answer()

    elif data == "confirm_reset_config":
        config.reset_runtime_config_to_defaults(save_state=True)
        await show_main_settings_menu(query, is_query=True)
        await query.answer("รีเซท config ตาม config.py แล้ว")

    elif data == "lot_custom_input":
        # เข้าสู่ mode รับ input lot สำหรับ auto
        ctx.user_data["waiting_lot_input"] = "auto"
        try:
            await query.edit_message_text(
                "✏️ *กรอก Lot Size สำหรับ Auto Trade*\n"
                "━━━━━━━━━━━━━━━━━\n"
                f"📦 ปัจจุบัน: *{config.AUTO_VOLUME}*\n\n"
                "พิมพ์ตัวเลข เช่น `0.03` หรือ `0.15`\n"
                "_(ขั้นต่ำ 0.01 สูงสุด 10.0)_",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await query.answer("พิมพ์ lot size ใน chat ได้เลย")

    elif data.startswith("lot_manual_"):
        # format: lot_manual_{direction}_custom_{price}
        parts     = data.split("_")
        direction = parts[2]   # buy / sell
        price_str = parts[4]   # ราคา
        ctx.user_data["waiting_lot_input"] = f"manual_{direction}_{price_str}"
        e = "🟢" if direction == "buy" else "🔴"
        try:
            await query.edit_message_text(
                f"✏️ *กรอก Lot Size — {e} {direction.upper()}*\n"
                "━━━━━━━━━━━━━━━━━\n"
                f"💰 ราคา: `{price_str}`\n\n"
                "พิมพ์ตัวเลข เช่น `0.03` หรือ `0.15`\n"
                "_(ขั้นต่ำ 0.01 สูงสุด 10.0)_",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await query.answer("พิมพ์ lot size ใน chat ได้เลย")

    elif data == "open_lot_menu":
        try:
            await query.edit_message_text(
                f"📦 *ตั้งค่า Lot Size — Auto Trade*\n━━━━━━━━━━━━━━━━━\n"
                f"📦 ปัจจุบัน: *{config.AUTO_VOLUME} lot*\n\nเลือก Lot:",
                parse_mode="Markdown",
                reply_markup=build_lot_keyboard()
            )
        except Exception:
            pass
        await query.answer()

    elif data.startswith("set_lot_"):
        new_lot = float(data.split("_")[-1])
        config.AUTO_VOLUME = new_lot
        import config as cfg_mod
        cfg_mod.AUTO_VOLUME = new_lot
        save_runtime_state()
        try:
            await query.edit_message_text(
                f"📦 *ตั้งค่า Lot Size — Auto Trade*\n━━━━━━━━━━━━━━━━━\n"
                f"📦 ปัจจุบัน: *{config.AUTO_VOLUME} lot*\n\nเลือก Lot:",
                parse_mode="Markdown",
                reply_markup=build_lot_keyboard()
            )
        except Exception:
            pass
        await query.answer(f"✅ Lot Auto = {config.AUTO_VOLUME}")

    elif data == "open_scan_menu":
        try:
            await query.edit_message_text(
                f"⏰ *ตั้งค่า Scan Interval*\n━━━━━━━━━━━━━━━━━\n⏰ ปัจจุบัน: *ทุก {config.SCAN_INTERVAL} นาที*\n\nเลือกความถี่:",
                parse_mode="Markdown",
                reply_markup=build_scan_keyboard_with_back()
            )
        except Exception:
            pass
        await query.answer()

    elif data == "open_trail_menu":
        trail_mode_label = "รวม phase" if config.TRAIL_SL_ENGULF_MODE == "combined" else "แยก phase"
        try:
            await query.edit_message_text(
                "📐 *ตั้งค่า Trail SL*\n"
                "━━━━━━━━━━━━━━━━━\n"
                f"โหมดปัจจุบัน: *Engulf / {trail_mode_label}*\n"
                f"Trail ทันที: *{'ON' if config.TRAIL_SL_IMMEDIATE else 'OFF'}*\n\n"
                "เลือกประเภท Trail SL:",
                parse_mode="Markdown",
                reply_markup=build_trail_menu()
            )
        except Exception:
            pass
        await query.answer()

    elif data == "open_trail_engulf_menu":
        trail_mode_label = "รวม phase" if config.TRAIL_SL_ENGULF_MODE == "combined" else "แยก phase"
        try:
            await query.edit_message_text(
                "📐 *Trail SL -> Engulf*\n"
                "━━━━━━━━━━━━━━━━━\n"
                "เลือกวิธีการทำงาน:\n"
                f"ปัจจุบัน: *{trail_mode_label}*\n\n"
                "รวม phase = ดูทุก TF ใน group พร้อมกัน และเลื่อน SL ต่อเนื่องเมื่อเจอ engulf\n"
                "แยก phase = TF เล็กกว่า -> TF order -> จบ",
                parse_mode="Markdown",
                reply_markup=build_trail_engulf_keyboard()
            )
        except Exception:
            pass
        await query.answer()

    elif data == "open_tf_menu":
        active_tfs = [tf for tf, on in TF_ACTIVE.items() if on]
        tf_summary = ", ".join(active_tfs) if active_tfs else "ยังไม่ได้เลือก"
        try:
            await query.edit_message_text(
                f"🕐 *เลือก Timeframe*\n━━━━━━━━━━━━━━━━━\n📊 ที่เปิดอยู่: *{tf_summary}*\n\nกดเลือกได้หลาย TF:",
                parse_mode="Markdown",
                reply_markup=build_tf_keyboard_with_back()
            )
        except Exception:
            pass
        await query.answer()

    elif data == "back_to_settings":
        await show_main_settings_menu(query, is_query=True)
        await query.answer()

    elif data == "toggle_entry_candle_tp":
        config.ENTRY_CANDLE_UPDATE_TP = not config.ENTRY_CANDLE_UPDATE_TP
        save_runtime_state()
        await show_main_settings_menu(query, is_query=True)
        status = "ON" if config.ENTRY_CANDLE_UPDATE_TP else "OFF"
        await query.answer(f"Entry Candle TP: {status}")

    elif data == "open_entry_candle_mode_menu":
        await show_entry_candle_mode_menu(query, is_query=True)
        await query.answer()

    elif data == "set_entry_candle_mode_classic":
        config.ENTRY_CANDLE_MODE = "classic"
        save_runtime_state()
        await show_entry_candle_mode_menu(query, is_query=True)
        await query.answer("Entry Candle Mode: Classic")

    elif data == "set_entry_candle_mode_close":
        config.ENTRY_CANDLE_MODE = "close"
        save_runtime_state()
        await show_entry_candle_mode_menu(query, is_query=True)
        await query.answer("Entry Candle Mode: Close")

    elif data == "set_entry_candle_mode_close_percentage":
        config.ENTRY_CANDLE_MODE = "close_percentage"
        save_runtime_state()
        await show_entry_candle_mode_menu(query, is_query=True)
        await query.answer("Entry Candle Mode: Close Percentage")

    elif data == "toggle_entry_close_reverse_market":
        config.ENTRY_CLOSE_REVERSE_MARKET = not config.ENTRY_CLOSE_REVERSE_MARKET
        save_runtime_state()
        await show_entry_candle_mode_menu(query, is_query=True)
        await query.answer(f"Close -> Market: {'ON' if config.ENTRY_CLOSE_REVERSE_MARKET else 'OFF'}")

    elif data == "toggle_entry_close_reverse_limit":
        config.ENTRY_CLOSE_REVERSE_LIMIT = not config.ENTRY_CLOSE_REVERSE_LIMIT
        save_runtime_state()
        await show_entry_candle_mode_menu(query, is_query=True)
        await query.answer(f"Close -> Limit: {'ON' if config.ENTRY_CLOSE_REVERSE_LIMIT else 'OFF'}")

    elif data == "open_opposite_menu":
        await show_opposite_menu(query, is_query=True)
        await query.answer()

    elif data == "set_opposite_mode_tp_close":
        config.OPPOSITE_ORDER_MODE = "tp_close"
        save_runtime_state()
        await show_opposite_menu(query, is_query=True)
        await query.answer("Opposite Order: ตั้ง TP+ปิด")

    elif data == "set_opposite_mode_sl_protect":
        config.OPPOSITE_ORDER_MODE = "sl_protect"
        save_runtime_state()
        await show_opposite_menu(query, is_query=True)
        await query.answer("Opposite Order: ตั้ง SL Protect")

    elif data == "toggle_trail_sl_enabled":
        config.TRAIL_SL_ENABLED = not config.TRAIL_SL_ENABLED
        save_runtime_state()
        trail_mode_label = "รวม phase" if config.TRAIL_SL_ENGULF_MODE == "combined" else "แยก phase"
        try:
            await query.edit_message_text(
                "📐 *ตั้งค่า Trail SL*\n"
                "━━━━━━━━━━━━━━━━━\n"
                f"สถานะ: *{'ON' if config.TRAIL_SL_ENABLED else 'OFF'}*\n"
                f"โหมดปัจจุบัน: *Engulf / {trail_mode_label}*\n"
                f"Trail ทันที: *{'ON' if config.TRAIL_SL_IMMEDIATE else 'OFF'}*\n\n"
                "เลือกประเภท Trail SL:",
                parse_mode="Markdown",
                reply_markup=build_trail_menu()
            )
        except Exception:
            pass
        await query.answer(f"Trail SL: {'ON' if config.TRAIL_SL_ENABLED else 'OFF'}")

    elif data == "toggle_entry_candle_enabled":
        config.ENTRY_CANDLE_ENABLED = not config.ENTRY_CANDLE_ENABLED
        save_runtime_state()
        await show_entry_candle_mode_menu(query, is_query=True)
        await query.answer(f"Entry Candle: {'ON' if config.ENTRY_CANDLE_ENABLED else 'OFF'}")

    elif data == "toggle_opposite_enabled":
        config.OPPOSITE_ORDER_ENABLED = not config.OPPOSITE_ORDER_ENABLED
        save_runtime_state()
        await show_opposite_menu(query, is_query=True)
        await query.answer(f"Opposite Order: {'ON' if config.OPPOSITE_ORDER_ENABLED else 'OFF'}")

    elif data == "open_debug_menu":
        await show_debug_menu(query, is_query=True)
        await query.answer()

    elif data == "toggle_debug_queue":
        config.TG_QUEUE_DEBUG = not config.TG_QUEUE_DEBUG
        try:
            import config as cfg_mod
            cfg_mod.TG_QUEUE_DEBUG = config.TG_QUEUE_DEBUG
        except Exception:
            pass
        save_runtime_state()
        await show_debug_menu(query, is_query=True)
        await query.answer(f"Queue Debug: {'ON' if config.TG_QUEUE_DEBUG else 'OFF'}")

    elif data == "toggle_debug_sltp":
        config.SLTP_AUDIT_DEBUG = not config.SLTP_AUDIT_DEBUG
        try:
            import config as cfg_mod
            cfg_mod.SLTP_AUDIT_DEBUG = config.SLTP_AUDIT_DEBUG
        except Exception:
            pass
        save_runtime_state()
        await show_debug_menu(query, is_query=True)
        await query.answer(f"SL/TP Audit Debug: {'ON' if config.SLTP_AUDIT_DEBUG else 'OFF'}")

    elif data == "toggle_debug_trade":
        config.TRADE_DEBUG = not config.TRADE_DEBUG
        try:
            import config as cfg_mod
            cfg_mod.TRADE_DEBUG = config.TRADE_DEBUG
        except Exception:
            pass
        save_runtime_state()
        await show_debug_menu(query, is_query=True)
        await query.answer(f"Trade Debug: {'ON' if config.TRADE_DEBUG else 'OFF'}")

    elif data == "close_settings":
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.answer("ปิดเมนูแล้ว")

    elif data.startswith("set_interval_"):
        SCAN_INTERVAL = int(data.split("_")[-1])
        config.SCAN_INTERVAL = SCAN_INTERVAL  # sync กลับ config module
        save_runtime_state()
        # อัพเดท scheduler — ดึงจาก application.bot_data
        try:
            scheduler = ctx.application.bot_data.get("scheduler")
            if scheduler:
                scheduler.reschedule_job("auto_scan_job", trigger="interval", minutes=SCAN_INTERVAL)
                print(f"[{now_bkk().strftime('%H:%M:%S')}] ✅ Reschedule scan → ทุก {SCAN_INTERVAL} นาที")
            else:
                print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ scheduler ไม่พบใน bot_data")
        except Exception as e:
            print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ reschedule error: {e}")
        try:
            await query.edit_message_text(
                f"⏰ *ตั้งค่า Scan Interval*\n━━━━━━━━━━━━━━━━━\n⏰ ปัจจุบัน: *ทุก {config.SCAN_INTERVAL} นาที*\n\nเลือกความถี่:",
                parse_mode="Markdown",
                reply_markup=build_scan_keyboard_with_back()
            )
        except Exception:
            pass
        await query.answer(f"✅ Scan ทุก {config.SCAN_INTERVAL} นาที")

    elif data.startswith("set_tf_"):
        tf_key = data.replace("set_tf_", "")
        if tf_key == "ALL":
            # Toggle เลือกทั้งหมด / ยกเลิกทั้งหมด
            all_active = all(TF_ACTIVE.values())
            for k in TF_ACTIVE:
                TF_ACTIVE[k] = not all_active
            config.TF_ACTIVE.update(TF_ACTIVE)
            msg_answer = "ยกเลิกทุก TF แล้ว" if all_active else "เลือกทุก TF แล้ว"
        elif tf_key in TF_ACTIVE:
            # ถ้าเลือกทุก TF อยู่แล้ว และกด TF อื่น = deselect เฉพาะ TF นั้น
            all_currently = all(TF_ACTIVE.values())
            if all_currently:
                # deselect เฉพาะ TF ที่กด
                TF_ACTIVE[tf_key] = False
                config.TF_ACTIVE[tf_key] = False
                msg_answer = f"ยกเลิก {tf_key} (เหลือ TF อื่น)"
            else:
                # toggle ปกติ
                TF_ACTIVE[tf_key] = not TF_ACTIVE[tf_key]
                config.TF_ACTIVE[tf_key] = TF_ACTIVE[tf_key]
                status = "เปิด" if TF_ACTIVE[tf_key] else "ปิด"
                msg_answer = f"{status} {tf_key} แล้ว"
        else:
            msg_answer = "ไม่พบ TF นี้"

        active_tfs = [tf for tf, on in TF_ACTIVE.items() if on]
        tf_summary = ", ".join(active_tfs) if active_tfs else "ไม่มี"
        try:
            await query.edit_message_text(
                f"🕐 *เลือก Timeframe*\n━━━━━━━━━━━━━━━━━\n📊 ที่เปิดอยู่: *{tf_summary}*\n\nกดเลือกได้หลาย TF:",
                parse_mode="Markdown",
                reply_markup=build_tf_keyboard_with_back()
            )
        except Exception:
            pass
        save_runtime_state()
        await query.answer(msg_answer)

    elif data.startswith("set_s1_zone_mode_"):
        mode = data.replace("set_s1_zone_mode_", "")   # "zone" หรือ "normal"
        config.S1_ZONE_MODE = mode
        save_runtime_state()
        label = "Zone 🔵 (ต้องใกล้ Swing)" if mode == "zone" else "ปกติ ⬜ (ไม่สนใจ Zone)"
        active_list = [STRATEGY_NAMES[s] for s, on in active_strategies.items() if on]
        summary = " + ".join(active_list) if active_list else "ไม่มี"
        new_text = (
            "📋 *เลือก Strategy*\n"
            "━━━━━━━━━━━━━━━━━\n"
            f"🔄 ที่เปิดอยู่: *{summary}*\n"
            f"🎯 ท่า 1 Zone: *{label}*\n\n"
            "กดเพื่อเปิด/ปิด:"
        )
        try:
            await query.edit_message_text(
                new_text, parse_mode="Markdown",
                reply_markup=build_strategy_keyboard()
            )
        except Exception:
            pass
        await query.answer(f"✅ ท่า 1: {label}")

    elif data in ("toggle_rsi9_regular", "toggle_rsi9_hidden"):
        # Toggle bull+bear ของแต่ละแบบพร้อมกัน — ON ก็ต่อเมื่อทั้งคู่ ON, มิฉะนั้น OFF
        if data == "toggle_rsi9_regular":
            currently_on = config.RSI9_PLOT_BULLISH and config.RSI9_PLOT_BEARISH
            new_state = not currently_on
            config.RSI9_PLOT_BULLISH = new_state
            config.RSI9_PLOT_BEARISH = new_state
            label = f"Regular: {'ON' if new_state else 'OFF'}"
        else:
            currently_on = config.RSI9_PLOT_HIDDEN_BULLISH and config.RSI9_PLOT_HIDDEN_BEARISH
            new_state = not currently_on
            config.RSI9_PLOT_HIDDEN_BULLISH = new_state
            config.RSI9_PLOT_HIDDEN_BEARISH = new_state
            label = f"Hidden: {'ON' if new_state else 'OFF'}"
        save_runtime_state()
        try:
            await query.edit_message_reply_markup(reply_markup=build_strategy_keyboard())
        except Exception:
            pass
        await query.answer(f"✅ ท่า 9: {label}")

    elif data.startswith("set_crt_bar_mode_"):
        mode = data.replace("set_crt_bar_mode_", "")
        if mode in ("2bar", "3bar"):
            config.CRT_BAR_MODE = mode
            save_runtime_state()
            try:
                await query.edit_message_reply_markup(reply_markup=build_strategy_keyboard())
            except Exception:
                pass
            await query.answer(f"✅ ท่า 10: {mode}")
        else:
            await query.answer("Mode ไม่ถูกต้อง")

    elif data.startswith("set_crt_entry_mode_"):
        mode = data.replace("set_crt_entry_mode_", "")
        if mode in ("htf", "mtf"):
            config.CRT_ENTRY_MODE = mode
            save_runtime_state()
            try:
                await query.edit_message_reply_markup(reply_markup=build_strategy_keyboard())
            except Exception:
                pass
            label = "HTF entry" if mode == "htf" else "MTF (LTF entry)"
            await query.answer(f"✅ ท่า 10: {label}")
        else:
            await query.answer("Entry mode ไม่ถูกต้อง")

    elif data in ("toggle_fvg_normal", "toggle_fvg_parallel"):
        if data == "toggle_fvg_normal":
            config.FVG_NORMAL = not config.FVG_NORMAL
        else:
            config.FVG_PARALLEL = not config.FVG_PARALLEL
        save_runtime_state()
        parts = []
        if config.FVG_NORMAL:
            parts.append("ปกติ")
        if config.FVG_PARALLEL:
            parts.append("Parallel")
        label = "+".join(parts) if parts else "(ปิดหมด)"
        active_list = [STRATEGY_NAMES[s] for s, on in active_strategies.items() if on]
        summary = " + ".join(active_list) if active_list else "ไม่มี"
        new_text = (
            "📋 *เลือก Strategy*\n"
            "━━━━━━━━━━━━━━━━━\n"
            f"🔄 ที่เปิดอยู่: *{summary}*\n"
            f"📊 ท่า 2 Mode: *{label}*\n\n"
            "กดเพื่อเปิด/ปิด:"
        )
        try:
            await query.edit_message_text(
                new_text, parse_mode="Markdown",
                reply_markup=build_strategy_keyboard()
            )
        except Exception:
            pass
        await query.answer(f"✅ ท่า 2: {label}")

    elif data.startswith("set_trail_engulf_mode_"):
        mode = data.replace("set_trail_engulf_mode_", "")
        if mode not in ("combined", "separate"):
            await query.answer("ไม่พบโหมดนี้")
            return

        config.TRAIL_SL_MODE = "engulf"
        config.TRAIL_SL_ENGULF_MODE = mode

        try:
            import trailing
            trailing._trail_state.clear()
            trailing._bar_count.clear()
        except Exception:
            pass

        trail_mode_label = "รวม phase" if config.TRAIL_SL_ENGULF_MODE == "combined" else "แยก phase"
        try:
            await query.edit_message_text(
                "📐 *Trail SL -> Engulf*\n"
                "━━━━━━━━━━━━━━━━━\n"
                "เลือกวิธีการทำงาน:\n"
                f"ปัจจุบัน: *{trail_mode_label}*\n\n"
                "รวม phase = ดูทุก TF ใน group พร้อมกัน และเลื่อน SL ต่อเนื่องเมื่อเจอ engulf\n"
                "แยก phase = TF เล็กกว่า -> TF order -> จบ",
                parse_mode="Markdown",
                reply_markup=build_trail_engulf_keyboard()
            )
        except Exception:
            pass
        save_runtime_state()
        await query.answer(f"✅ Trail SL Engulf: {trail_mode_label}")

    elif data == "toggle_trail_immediate":
        config.TRAIL_SL_IMMEDIATE = not config.TRAIL_SL_IMMEDIATE
        save_runtime_state()
        trail_mode_label = "รวม phase" if config.TRAIL_SL_ENGULF_MODE == "combined" else "แยก phase"
        imm_status = "เปิด" if config.TRAIL_SL_IMMEDIATE else "ปิด"
        try:
            await query.edit_message_text(
                "📐 *ตั้งค่า Trail SL*\n"
                "━━━━━━━━━━━━━━━━━\n"
                f"โหมดปัจจุบัน: *Engulf / {trail_mode_label}*\n"
                f"Trail ทันที: *{'ON' if config.TRAIL_SL_IMMEDIATE else 'OFF'}*\n\n"
                "เลือกประเภท Trail SL:",
                parse_mode="Markdown",
                reply_markup=build_trail_menu()
            )
        except Exception:
            pass
        await query.answer(f"Trail ทันที: {imm_status}")

    elif data == "open_trail_focus_menu":
        await show_trail_focus_menu(query, is_query=True)
        await query.answer()

    elif data == "toggle_trail_focus_new":
        config.TRAIL_SL_FOCUS_NEW_ENABLED = not config.TRAIL_SL_FOCUS_NEW_ENABLED
        if config.TRAIL_SL_FOCUS_NEW_ENABLED:
            from trailing import reset_focus_frozen_side
            reset_focus_frozen_side("trail_sl")
        save_runtime_state()
        await show_trail_focus_menu(query, is_query=True)
        await query.answer(f"Trail Focus: {'ON' if config.TRAIL_SL_FOCUS_NEW_ENABLED else 'OFF'}")

    elif data == "toggle_tfn_tf_mode":
        config.TRAIL_SL_FOCUS_NEW_TF_MODE = (
            "combined" if config.TRAIL_SL_FOCUS_NEW_TF_MODE == "separate" else "separate"
        )
        save_runtime_state()
        await show_trail_focus_menu(query, is_query=True)
        tf_desc = "รวมทุก TF" if config.TRAIL_SL_FOCUS_NEW_TF_MODE == "combined" else "แยกตาม TF"
        await query.answer(f"Trail Focus TF: {tf_desc}")

    elif data.startswith("set_tfn_pts_"):
        pts = int(data.replace("set_tfn_pts_", ""))
        config.TRAIL_SL_FOCUS_NEW_POINTS = pts
        save_runtime_state()
        await show_trail_focus_menu(query, is_query=True)
        await query.answer(f"Trail Focus Threshold: {pts} จุด")

    elif data == "open_entry_focus_menu":
        await show_entry_focus_menu(query, is_query=True)
        await query.answer()

    elif data == "toggle_entry_focus_new":
        config.ENTRY_CANDLE_FOCUS_NEW_ENABLED = not config.ENTRY_CANDLE_FOCUS_NEW_ENABLED
        if config.ENTRY_CANDLE_FOCUS_NEW_ENABLED:
            from trailing import reset_focus_frozen_side
            reset_focus_frozen_side("entry_candle")
        save_runtime_state()
        await show_entry_focus_menu(query, is_query=True)
        await query.answer(f"Entry Focus: {'ON' if config.ENTRY_CANDLE_FOCUS_NEW_ENABLED else 'OFF'}")

    elif data == "toggle_efn_tf_mode":
        config.ENTRY_CANDLE_FOCUS_NEW_TF_MODE = (
            "combined" if config.ENTRY_CANDLE_FOCUS_NEW_TF_MODE == "separate" else "separate"
        )
        save_runtime_state()
        await show_entry_focus_menu(query, is_query=True)
        tf_desc = "รวมทุก TF" if config.ENTRY_CANDLE_FOCUS_NEW_TF_MODE == "combined" else "แยกตาม TF"
        await query.answer(f"Entry Focus TF: {tf_desc}")

    elif data.startswith("set_efn_pts_"):
        pts = int(data.replace("set_efn_pts_", ""))
        config.ENTRY_CANDLE_FOCUS_NEW_POINTS = pts
        save_runtime_state()
        await show_entry_focus_menu(query, is_query=True)
        await query.answer(f"Entry Focus Threshold: {pts} จุด")

    elif data == "open_trend_filter_menu":
        await show_trend_filter_menu(query, is_query=True)
        await query.answer()

    elif data.startswith("toggle_trend_filter_per_tf_"):
        tf = data.replace("toggle_trend_filter_per_tf_", "")
        if tf == "ALL":
            all_on = all(config.TREND_FILTER_PER_TF.values())
            for t in config.TREND_FILTER_PER_TF:
                config.TREND_FILTER_PER_TF[t] = not all_on
            save_runtime_state()
            await show_trend_filter_menu(query, is_query=True)
            await query.answer("ยกเลิกทุก TF" if all_on else "เลือกทุก TF")
        elif tf in config.TREND_FILTER_PER_TF:
            config.TREND_FILTER_PER_TF[tf] = not config.TREND_FILTER_PER_TF[tf]
            save_runtime_state()
            await show_trend_filter_menu(query, is_query=True)
            await query.answer(f"Per-TF {tf}: {'ON' if config.TREND_FILTER_PER_TF[tf] else 'OFF'}")
        else:
            await query.answer("TF ไม่ถูกต้อง")

    elif data == "noop_trend_filter":
        await query.answer()

    elif data == "toggle_trend_filter_higher_tf":
        config.TREND_FILTER_HIGHER_TF_ENABLED = not config.TREND_FILTER_HIGHER_TF_ENABLED
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await query.answer(f"Trend Filter Higher TF: {'ON' if config.TREND_FILTER_HIGHER_TF_ENABLED else 'OFF'}")

    elif data == "toggle_trend_filter_trail_sl_override":
        config.TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED = not config.TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await query.answer(
            f"Trend Filter Trail SL Override: {'ON' if config.TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED else 'OFF'}"
        )

    elif data.startswith("set_trend_filter_higher_tf_"):
        tf = data.replace("set_trend_filter_higher_tf_", "")
        if tf in TF_OPTIONS:
            config.TREND_FILTER_HIGHER_TF = tf
            save_runtime_state()
            await show_trend_filter_menu(query, is_query=True)
            await query.answer(f"Higher TF: {tf}")
        else:
            await query.answer("TF ไม่ถูกต้อง")

    elif data.startswith("set_trend_filter_mode_"):
        mode = data.replace("set_trend_filter_mode_", "")
        if mode in ("basic", "breakout"):
            config.TREND_FILTER_MODE = mode
            save_runtime_state()
            await show_trend_filter_menu(query, is_query=True)
            await query.answer(f"Trend Filter Mode: {mode}")
        else:
            await query.answer("Mode ไม่ถูกต้อง")

    elif data.startswith("toggle_strategy_"):
        sid = int(data.split("_")[-1])
        if sid in active_strategies:
            active_strategies[sid] = not active_strategies[sid]
            config.active_strategies[sid] = active_strategies[sid]
            save_runtime_state()
            name     = STRATEGY_NAMES.get(sid, f"ท่าที่ {sid}")
            status_th = "เปิด ✅" if active_strategies[sid] else "ปิด ❌"
            active_list = [STRATEGY_NAMES[s] for s, on in active_strategies.items() if on]
            summary = " + ".join(active_list) if active_list else "ไม่มี"
            new_text = (
                "📋 *เลือก Strategy*\n"
                "━━━━━━━━━━━━━━━━━\n"
                f"🔄 ที่เปิดอยู่: *{summary}*\n\n"
                "กดเพื่อเปิด/ปิด (เลือกพร้อมกันได้):"
            )
            try:
                await query.edit_message_text(
                    new_text,
                    parse_mode="Markdown",
                    reply_markup=build_strategy_keyboard()
                )
            except Exception as e:
                if "not modified" not in str(e).lower():
                    raise
            await query.answer(f"{name}: {status_th}")

    elif data in ("strategy_all_on", "strategy_all_off"):
        # strategy_all_on = เปิดทั้งหมด, strategy_all_off = ปิดทั้งหมด
        turn_on = (data == "strategy_all_on")
        for sid in active_strategies:
            active_strategies[sid] = turn_on
            config.active_strategies[sid] = turn_on
        save_runtime_state()
        active_list = [STRATEGY_NAMES[s] for s, on in active_strategies.items() if on]
        summary = " + ".join(active_list) if active_list else "ไม่มี"
        new_text = (
            "📋 *เลือก Strategy*\n"
            "━━━━━━━━━━━━━━━━━\n"
            f"🔄 ที่เปิดอยู่: *{summary}*\n\n"
            "กดเพื่อเปิด/ปิด (เลือกพร้อมกันได้):"
        )
        try:
            await query.edit_message_text(
                new_text,
                parse_mode="Markdown",
                reply_markup=build_strategy_keyboard()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                raise
        await query.answer("เปิดทั้งหมด ✅" if turn_on else "ปิดทั้งหมด ❌")

    elif data == "cancel_pending":
        await query.answer("⏳ กำลังยกเลิก...")
        if not connect_mt5():
            await query.edit_message_text("❌ MT5 ไม่ได้เชื่อมต่อ")
            return
        orders = mt5.orders_get(symbol=SYMBOL)
        if not orders:
            await query.edit_message_text("📭 ไม่มี Pending Order")
            return
        cancelled = 0
        failed    = 0
        for o in orders:
            r = mt5.order_send({
                "action": mt5.TRADE_ACTION_REMOVE,
                "order":  o.ticket,
            })
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                cancelled += 1
            else:
                failed += 1
        txt = f"✅ ยกเลิก Pending สำเร็จ {cancelled} Order"
        if failed:
            txt += "\n⚠️ ยกเลิกไม่สำเร็จ " + str(failed) + " Order"
        # ล้าง fvg_pending และ pb_pending ด้วย
        fvg_pending.clear()
        pb_pending.clear()
        save_runtime_state()
        await query.edit_message_text(txt)

    elif data == "confirm_close":
        await query.edit_message_text("⏳ ปิดทุก Order...")
        if not connect_mt5():
            await query.edit_message_text("❌ MT5 ไม่ได้เชื่อมต่อ")
            return
        positions = mt5.positions_get(symbol=SYMBOL)
        if not positions:
            await query.edit_message_text("📭 ไม่มี Order")
            return
        closed = 0
        for p in positions:
            tick = mt5.symbol_info_tick(p.symbol)
            if not tick:
                continue
            price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask
            ct    = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            r     = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol,
                "volume": p.volume, "type": ct, "position": p.ticket,
                "price": price, "deviation": 20, "magic": 234001,
                "comment": "CloseAll", "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            })
            if r.retcode == mt5.TRADE_RETCODE_DONE:
                closed += 1
        await query.edit_message_text(f"✅ ปิดสำเร็จ {closed} Order")
        await query.answer("ปิด Order แล้ว")

    elif data == "open_limit_guard_menu":
        await show_limit_guard_menu(query, is_query=True)
        await query.answer()

    elif data == "open_limit_break_menu":
        await show_limit_break_menu(query, is_query=True)
        await query.answer()

    elif data == "open_engulf_menu":
        await show_engulf_menu(query, is_query=True)
        await query.answer()

    elif data == "toggle_limit_sweep":
        config.LIMIT_SWEEP = not config.LIMIT_SWEEP
        save_runtime_state()
        await show_main_settings_menu(query, is_query=True)
        await query.answer(f"Limit Sweep: {'ON' if config.LIMIT_SWEEP else 'OFF'}")

    elif data == "cycle_delay_sl":
        cycle = {"off": "time", "time": "price", "price": "off"}
        config.DELAY_SL_MODE = cycle.get(config.DELAY_SL_MODE, "off")
        save_runtime_state()
        label = {"off": "ปิด", "time": "ช่วงท้าย TF", "price": "ราคาผ่าน Entry"}.get(config.DELAY_SL_MODE, "ปิด")
        await show_main_settings_menu(query, is_query=True)
        await query.answer(f"Delay SL: {label}")

    elif data == "toggle_limit_break_cancel":
        config.LIMIT_BREAK_CANCEL = not config.LIMIT_BREAK_CANCEL
        save_runtime_state()
        await show_limit_break_menu(query, is_query=True)
        await query.answer(f"Limit TP/SL Break: {'ON' if config.LIMIT_BREAK_CANCEL else 'OFF'}")

    elif data == "toggle_lbc_tf_ALL":
        all_on = all(config.LIMIT_BREAK_CANCEL_TF.values())
        for tf_name in config.LIMIT_BREAK_CANCEL_TF:
            config.LIMIT_BREAK_CANCEL_TF[tf_name] = not all_on
        save_runtime_state()
        await show_limit_break_menu(query, is_query=True)
        await query.answer("เลือกทุก TF แล้ว" if not all_on else "ยกเลิกทุก TF แล้ว")

    elif data.startswith("toggle_lbc_tf_"):
        tf_name = data.replace("toggle_lbc_tf_", "")
        if tf_name in config.LIMIT_BREAK_CANCEL_TF:
            config.LIMIT_BREAK_CANCEL_TF[tf_name] = not config.LIMIT_BREAK_CANCEL_TF[tf_name]
            save_runtime_state()
            await show_limit_break_menu(query, is_query=True)
            await query.answer(f"Limit TP/SL Break TF {tf_name}: {'ON' if config.LIMIT_BREAK_CANCEL_TF[tf_name] else 'OFF'}")
        else:
            await query.answer("ไม่พบ TF นี้")

    elif data == "toggle_limit_guard":
        config.LIMIT_GUARD = not config.LIMIT_GUARD
        save_runtime_state()
        await show_limit_guard_menu(query, is_query=True)
        await query.answer(f"Limit Guard: {'ON' if config.LIMIT_GUARD else 'OFF'}")

    elif data == "toggle_lg_tf_mode":
        config.LIMIT_GUARD_TF_MODE = "combined" if config.LIMIT_GUARD_TF_MODE == "separate" else "separate"
        save_runtime_state()
        await show_limit_guard_menu(query, is_query=True)
        tf_desc = "รวมทุก TF" if config.LIMIT_GUARD_TF_MODE == "combined" else "แยกตาม TF"
        await query.answer(f"Limit Guard TF: {tf_desc}")

    elif data.startswith("set_lg_pts_"):
        pts = int(data.replace("set_lg_pts_", ""))
        config.LIMIT_GUARD_POINTS = pts
        save_runtime_state()
        await show_limit_guard_menu(query, is_query=True)
        await query.answer(f"Limit Guard: {pts} จุด")

    elif data.startswith("set_engulf_pts_"):
        pts = int(data.replace("set_engulf_pts_", ""))
        config.ENGULF_MIN_POINTS = pts
        save_runtime_state()
        await show_engulf_menu(query, is_query=True)
        await query.answer(f"Engulf ขั้นต่ำ: {pts} จุด")

    elif data.startswith("profit_sid_"):
        # format: profit_sid_{year}_{month}_{sid}_{trend_filter}
        # trend_filter อาจมี underscore (bull_strong, bear_weak ฯลฯ) ต้อง join ส่วนที่เหลือ
        parts = data.split("_")
        year = int(parts[2])
        month = int(parts[3])
        sid = int(parts[4])
        trend_filter_key = "_".join(parts[5:]) if len(parts) > 5 else "all"
        await show_profit_strategy_detail(query, year, month, sid, trend_filter_key, is_query=True)
        await query.answer()

    elif data.startswith("profit_"):
        # format: profit_{year}_{month}_{trend_filter}
        # trend_filter อาจมี underscore (bull_strong, bear_weak ฯลฯ) ต้อง join ส่วนที่เหลือ
        parts = data.split("_")
        year = int(parts[1])
        month = int(parts[2])
        trend_filter_key = "_".join(parts[3:]) if len(parts) > 3 else "all"
        await show_profit_summary(query, year, month, trend_filter_key, is_query=True)
        await query.answer()

    elif data.startswith("buy_") or data.startswith("sell_"):
        parts     = data.split("_")
        direction = parts[0]
        volume    = float(parts[1])
        if not connect_mt5():
            await query.edit_message_text("❌ MT5 ไม่ได้เชื่อมต่อ")
            return
        tick = mt5.symbol_info_tick(SYMBOL)
        if not tick:
            await query.edit_message_text("❌ ดึงราคาไม่ได้")
            return
        price = tick.ask if direction == "buy" else tick.bid
        sl    = round(price - 15, 2) if direction == "buy" else round(price + 15, 2)
        tp    = round(price + 30, 2) if direction == "buy" else round(price - 30, 2)
        ot    = mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL
        r     = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL,
            "volume": volume, "type": ot, "price": price,
            "sl": sl, "tp": tp, "deviation": 20, "magic": 234001,
            "comment": "Manual", "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        })
        e = "🟢" if direction == "buy" else "🔴"
        if r.retcode == mt5.TRADE_RETCODE_DONE:
            await query.edit_message_text(
                f"✅ *เปิดสำเร็จ!* {e} {direction.upper()} {volume}lot @ `{price}`\n🛑`{sl}` 🎯`{tp}` 🔖`{r.order}`",
                parse_mode='Markdown'
            )
            await query.answer('เปิด Order สำเร็จ!')
        else:
            await query.edit_message_text(f"❌ ไม่สำเร็จ: {r.retcode} — {r.comment}")
            await query.answer('เปิด Order ไม่สำเร็จ')


# ============================================================
#  MAIN
# ============================================================
