import asyncio
import config
from telegram import Bot

async def main():
    bot = Bot(config.TELEGRAM_TOKEN)
    await bot.send_message(chat_id=config.MY_USER_ID, text='Test message from Agent')
    print('Sent successfully')

asyncio.run(main())
