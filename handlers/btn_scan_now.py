from config import *
from scanner import scan_one_tf, _scan_results, _format_scan_summary_telegram_clean
from handlers.keyboard import main_keyboard
import config


async def handle_btn_scan_now(update, context):
    if not auth(update): return
    msg = await update.message.reply_text("⏳ กำลังสแกน...")
    try:
        from mt5_utils import connect_mt5
        if not connect_mt5():
            await msg.edit_text("❌ MT5 ไม่ได้เชื่อมต่อ\nเปิด MT5 แล้วลองใหม่ครับ")
            return

        from config import TF_ACTIVE
        import asyncio
        active_tfs = [tf for tf, on in TF_ACTIVE.items() if on]
        if not active_tfs:
            await msg.edit_text("⚠️ ยังไม่ได้เลือก Timeframe\nไปที่ ⚙️ ตั้งค่า → เลือก TF ก่อนครับ")
            return

        _scan_results.clear()
        await asyncio.gather(*[scan_one_tf(context.application, tf) for tf in active_tfs])

        # แสดงผลลัพธ์ — edit_text ไม่รับ ReplyKeyboardMarkup → ส่งแยก
        now = now_bkk().strftime("%H:%M:%S")
        if _scan_results:
            show_tfs = [tf for tf in active_tfs if tf in _scan_results]
            tg_text, _ = _format_scan_summary_telegram_clean(show_tfs)
            await msg.edit_text(tg_text)
        else:
            await msg.edit_text(f"✅ Scan [{now}] — ไม่มี Setup")

        # ส่ง keyboard แยกต่างหาก (ReplyKeyboardMarkup ใช้ send_message)
        await update.message.reply_text("─", reply_markup=main_keyboard())

    except asyncio.TimeoutError:
        await msg.edit_text("⚠️ สแกน Timeout\nMT5 ตอบช้าเกินไป ลองกดใหม่อีกครั้งครับ")
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)[:200]}")

