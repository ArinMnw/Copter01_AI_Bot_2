from config import *
from mt5_utils import connect_mt5
from handlers.keyboard import show_strategy_menu
from handlers.keyboard import main_keyboard


async def handle_btn_strategy(update, context):
    if not auth(update): return
    await show_strategy_menu(update)

