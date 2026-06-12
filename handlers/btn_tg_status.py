import time as _time
import config
from handlers.keyboard import main_keyboard


async def handle_btn_tg_status(update, context):
    wrapper = context.application.bot
    if hasattr(wrapper, "_retry_until"):
        remaining = max(0.0, wrapper._retry_until - _time.monotonic())
        qsize = wrapper._queue.qsize() if hasattr(wrapper, "_queue") else "?"
        if remaining > 0:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            msg = f"🔴 *Flood Control*\nยังต้องรอ: `{mins}:{secs:02d}` นาที\n📬 Queue: `{qsize}` รายการ"
        else:
            msg = f"🟢 *TG ปกติ* ไม่มี Flood Control\n📬 Queue: `{qsize}` รายการ"
    else:
        msg = "❓ ไม่พบ TgWrapper (bot ยังไม่ได้ wrap)"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())
