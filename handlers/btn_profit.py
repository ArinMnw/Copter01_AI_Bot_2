from config import *
from handlers.keyboard import show_profit_summary
from datetime import datetime


async def handle_btn_profit(update, context):
    if not auth(update):
        return
    now = datetime.now()
    await show_profit_summary(update, now.year, now.month)
