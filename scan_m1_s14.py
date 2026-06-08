import asyncio
from config import TF_ACTIVE
from scanner import auto_scan
from telegram.ext import ApplicationBuilder
import config
# Ensure M1 timeframe is active
TF_ACTIVE['M1'] = True

# Build a minimal Telegram application (uses existing token)
app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()

async def run_once():
    await auto_scan(app)
    # After scan, check bot.log for any S14 entries
    try:
        with open('logs/bot.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        s14_lines = [l.strip() for l in lines if 'S14' in l]
        if s14_lines:
            print('--- S14 signals found in log ---')
            for l in s14_lines:
                print(l)
        else:
            print('No S14 signals found in this scan.')
    except Exception as e:
        print(f'Error reading bot.log: {e}')

if __name__ == '__main__':
    asyncio.run(run_once())
