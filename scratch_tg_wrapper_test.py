import asyncio
import config
from telegram import Bot

async def main():
    bot = Bot(config.TELEGRAM_TOKEN)
    wrapper = config._TgWrapper(bot)
    print("Putting message in wrapper...")
    await wrapper.send_message(chat_id=config.MY_USER_ID, text='Test message via wrapper')
    print("Message put. Waiting for worker to process...")
    await asyncio.sleep(5)  # Wait for worker
    print("Done waiting.")

asyncio.run(main())
