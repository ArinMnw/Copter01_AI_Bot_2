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
end_naive = datetime.strptime("2026-07-16 04:30", "%Y-%m-%d %H:%M")

correct_from = bkk.localize(start_naive).astimezone(timezone.utc)
correct_to = bkk.localize(end_naive).astimezone(timezone.utc)

deals = mt5.history_deals_get(correct_from, correct_to)
print("Total raw deals retrieved:", len(deals) if deals else 0)

if deals:
    deals = sorted(deals, key=lambda x: x.time)
    print("\nListing all exit deals (entry/exit type mapping):")
    # In MT5: entry type (d.entry) values: 
    # 0 = ENTRY_IN, 1 = ENTRY_OUT, 2 = ENTRY_INOUT, 3 = ENTRY_OUT_BY
    exits = 0
    entries = 0
    for i, d in enumerate(deals):
        deal_time_bkk = datetime.fromtimestamp(d.time, tz=timezone.utc).astimezone(bkk)
        type_str = "IN" if d.entry == 0 else "OUT" if d.entry == 1 else "INOUT" if d.entry == 2 else "OUT_BY"
        if d.entry == 1 or d.entry == 3:
            exits += 1
        else:
            entries += 1
        print(f"[{i+1}] Time: {deal_time_bkk} | Ticket: {d.ticket} | Position: {d.position_id} | EntryType: {type_str} ({d.entry}) | ActionType: {d.type} | Vol: {d.volume} | Profit: {d.profit} | Comm: {d.comment}")
        
    print(f"\nSummary: Total Entries (IN/INOUT) = {entries}, Total Exits (OUT/OUT_BY) = {exits}")

mt5.shutdown()
