import MetaTrader5 as mt5
import os
import sys
from datetime import datetime, timezone, timedelta
import pytz

sys_path = r"d:\Project\Copter01_AI_Bot_2\profiles\demo\demo-exness-416010472\mt5\terminal64.exe"

if not mt5.initialize(path=sys_path, portable=True):
    print("MT5 Initialization FAILED")
    sys.exit(1)
    
bkk = pytz.timezone("Asia/Bangkok")

start_naive = datetime.strptime("2026-07-15 17:50", "%Y-%m-%d %H:%M")
correct_from = bkk.localize(start_naive).astimezone(timezone.utc)
# To current time
correct_to = datetime.now(timezone.utc)

deals = mt5.history_deals_get(correct_from, correct_to)
print("Total raw deals retrieved to now:", len(deals) if deals else 0)

if deals:
    exits = 0
    entries = 0
    for d in deals:
        if d.entry == 1 or d.entry == 3:
            exits += 1
        else:
            entries += 1
    print(f"Summary to NOW: Total Entries = {entries}, Total Exits = {exits}")

mt5.shutdown()
