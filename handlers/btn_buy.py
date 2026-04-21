from config import *
from mt5_utils import connect_mt5
from handlers.keyboard import order_menu
from handlers.keyboard import main_keyboard


async def handle_btn_buy(update, context):
    if not auth(update): return
    await order_menu(update, 'buy')

