import MetaTrader5 as mt5
import os
import sys
from datetime import datetime, timezone, timedelta
import pytz

sys_path = r"d:\Project\Copter01_AI_Bot_2\profiles\demo\demo-exness-416010472\mt5\terminal64.exe"

if not mt5.initialize(path=sys_path, portable=True):
    print("MT5 Initialization FAILED")
    sys.exit(1)
    
print("Connected to Exness account:", mt5.account_info().login)

bkk = pytz.timezone("Asia/Bangkok")

start_naive = datetime.strptime("2026-07-15 17:50", "%Y-%m-%d %H:%M")
end_naive = datetime.strptime("2026-07-16 04:30", "%Y-%m-%d %H:%M")

correct_from = bkk.localize(start_naive).astimezone(timezone.utc)
correct_to = bkk.localize(end_naive).astimezone(timezone.utc)

deals = mt5.history_deals_get(correct_from, correct_to)
print(f"\n[Query] BKK {start_naive} -> UTC {correct_from}")
print(f"To BKK {end_naive} -> UTC {correct_to}")
print(f"Total raw deals found: {len(deals) if deals else 0}")

if deals:
    print("\nAll Deals Details (Sorted by Time):")
    deals = sorted(deals, key=lambda x: x.time)
    for i, d in enumerate(deals):
        deal_time_bkk = datetime.fromtimestamp(d.time, tz=timezone.utc).astimezone(bkk)
        print(f"{i+1}. Ticket: {d.ticket} | Time BKK: {deal_time_bkk} | Type: {d.type} | Volume: {d.volume} | Price: {d.price} | Profit: {d.profit} | Magic: {d.magic} | Comment: {d.comment}")

mt5.shutdown()
