import MetaTrader5 as mt5
import os
import sys
from datetime import datetime, timezone, timedelta
import pytz

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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
print("Total raw deals retrieved:", len(deals) if deals else 0)

if deals:
    deals = sorted(deals, key=lambda x: x.time)
    entry_deals = {d.position_id: d for d in deals if d.entry == mt5.DEAL_ENTRY_IN}
    
    matched = 0
    missed_entry = 0
    wrong_symbol = 0
    wrong_magic = 0
    
    target_magics = [992004]
    
    for d in deals:
        if d.entry in (1, 3): # Exit
            # 1. Check if entry deal is in the query range
            if d.position_id not in entry_deals:
                missed_entry += 1
                # Retrieve the actual entry deal from all time history
                all_time_deals = mt5.history_deals_get(position=d.position_id)
                entry_time_str = "Unknown"
                if all_time_deals:
                    entry_in = [x for x in all_time_deals if x.entry == 0]
                    if entry_in:
                        entry_time_bkk = datetime.fromtimestamp(entry_in[0].time, tz=timezone.utc).astimezone(bkk)
                        entry_time_str = entry_time_bkk.strftime('%Y-%m-%d %H:%M:%S')
                print(f"[MISSED_ENTRY] Exit Ticket {d.ticket} (Position {d.position_id}) MISSED entry deal! Entry was at BKK: {entry_time_str}")
                continue
                
            # 2. Check symbol
            if "XAUUSD" not in d.symbol:
                wrong_symbol += 1
                print(f"[WRONG_SYMBOL] Exit Ticket {d.ticket} has wrong symbol: {d.symbol}")
                continue
                
            # 3. Check magic number
            if d.magic not in target_magics:
                wrong_magic += 1
                print(f"[WRONG_MAGIC] Exit Ticket {d.ticket} has wrong magic: {d.magic}")
                continue
                
            matched += 1
            
    print(f"\nAnalysis Summary:")
    print(f"Total Exit Deals analyzed: {matched + missed_entry + wrong_symbol + wrong_magic}")
    print(f"- Matched & Outputted: {matched}")
    print(f"- Missed Entry (occurred before query start): {missed_entry}")
    print(f"- Wrong Symbol: {wrong_symbol}")
    print(f"- Wrong Magic: {wrong_magic}")

mt5.shutdown()
