from config import *
from mt5_utils import connect_mt5
from handlers.keyboard import show_main_settings_menu
from handlers.keyboard import main_keyboard


async def handle_btn_settings(update, context):
    if not auth(update): return
    await show_main_settings_menu(update)

